#!/usr/bin/env bash
# Public website/Jarvis health probe.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "$LOG_DIR"

PUBLIC_ORIGIN="${PUBLIC_ORIGIN:-https://kingofyadav.in}"
LOCAL_ORIGIN="${LOCAL_ORIGIN:-http://127.0.0.1:5050}"
CHAT_TIMEOUT="${CHAT_TIMEOUT:-65}"

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
  local body
  body="$(curl -fsS --max-time 8 "$url" 2>/dev/null || true)"
  if echo "$body" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
    pass "$name"
  else
    fail "$name body=${body:-unreachable}"
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
      fail "$name fallback body=$body"
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
  "${ROOT_DIR}/.venv/bin/python" - "$url" <<'PY' >/tmp/jarvis_ws_probe.txt 2>&1
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
    fail "$name $(tr '\n' ' ' </tmp/jarvis_ws_probe.txt)"
  fi
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
  check_http_json_ok "public-api-health" "${PUBLIC_ORIGIN}/api/health"
  check_chat "public-chat" "${PUBLIC_ORIGIN}/api/jarvis-chat"
  check_ws "public-websocket" "${PUBLIC_ORIGIN/https:/wss:}/api/ws/public"
  check_ollama

  if [ "$failures" -gt 0 ]; then
    log "done failures=$failures"
    exit 1
  fi
  log "done failures=0"
}

main "$@"
