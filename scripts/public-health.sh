#!/usr/bin/env bash
# Public website/Jarvis health probe.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "$LOG_DIR"

PUBLIC_API_ORIGIN="${PUBLIC_API_ORIGIN:-${PUBLIC_ORIGIN:-https://jarvis.kingofyadav.in}}"
LOCAL_ORIGIN="${LOCAL_ORIGIN:-http://127.0.0.1:5050}"
CHAT_TIMEOUT="${CHAT_TIMEOUT:-65}"
ALLOW_PUBLIC_CHAT_FALLBACK="${ALLOW_PUBLIC_CHAT_FALLBACK:-0}"

failures=0

log() {
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [public-health] $*"
}

pass() {
  log "PASS $*"
}

fail() {
  failures=$((failures + 1))
  log "FAIL $*"
}

check_http_json_ok() {
  local name="$1"
  local url="$2"
  local tmp
  local body
  local code
  tmp="$(mktemp)"
  code="$(curl -sS --max-time 8 -o "$tmp" -w '%{http_code}' "$url" 2>/dev/null || true)"
  body="$(cat "$tmp" 2>/dev/null || true)"
  rm -f "$tmp"
  if echo "$body" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
    pass "$name"
  else
    fail "$name status=${code:-000} body=${body:-unreachable}"
  fi
}

check_chat() {
  local name="$1"
  local url="$2"
  local body
  body="$(curl -fsS --max-time "$CHAT_TIMEOUT" \
    -H 'Content-Type: application/json' \
    -d '{"message":"What services are offered?","history":[]}' \
    "$url" 2>/dev/null || true)"
  if echo "$body" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
    if echo "$body" | grep -q '"mode"[[:space:]]*:[[:space:]]*"fallback"'; then
      if [ "$ALLOW_PUBLIC_CHAT_FALLBACK" = "1" ]; then
        pass "$name fallback"
      else
        fail "$name fallback body=$body"
      fi
    else
      pass "$name"
    fi
  else
    fail "$name body=${body:-unreachable}"
  fi
}

check_ws() {
  local name="$1"
  local url="$2"
  local tmp
  tmp="$(mktemp)"
  timeout 15s "${ROOT_DIR}/.venv/bin/python" - "$url" <<'PY' >"$tmp" 2>&1
import asyncio
import sys
import websockets

async def main(url: str) -> None:
    async with websockets.connect(url, open_timeout=8) as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=8)
        if "public_chat_enabled" not in msg:
            raise RuntimeError("unexpected websocket payload")

asyncio.run(main(sys.argv[1]))
PY
  if [ "$?" -eq 0 ]; then
    pass "$name"
  else
    fail "$name $(tr '\n' ' ' <"$tmp")"
  fi
  rm -f "$tmp"
}

ws_origin() {
  case "$1" in
    https://*) printf 'wss://%s' "${1#https://}" ;;
    http://*)  printf 'ws://%s' "${1#http://}" ;;
    *)         printf '%s' "$1" ;;
  esac
}

check_ollama() {
  local url="${OLLAMA_HOST:-http://localhost:11434}"
  local body
  body="$(curl -fsS --max-time 5 "$url/api/tags" 2>/dev/null || true)"
  if echo "$body" | grep -q '"models"'; then
    pass "ollama"
  else
    fail "ollama body=${body:-unreachable}"
  fi
}

main() {
  check_http_json_ok "local-api-health" "${LOCAL_ORIGIN}/api/health"
  check_http_json_ok "public-api-health" "${PUBLIC_API_ORIGIN}/api/health"
  check_chat "public-chat" "${PUBLIC_API_ORIGIN}/api/jarvis-chat"
  check_ws "public-websocket" "$(ws_origin "$PUBLIC_API_ORIGIN")/api/ws/public"
  check_ollama

  if [ "$failures" -gt 0 ]; then
    log "done failures=$failures"
    exit 1
  fi
  log "done failures=0"
}

main "$@"
