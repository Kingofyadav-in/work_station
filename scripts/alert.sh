#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
STATE_DIR="$LOG_DIR/alert_state"
ALERT_LOG="$LOG_DIR/alerts.log"
ENV_FILE="$ROOT_DIR/.env"

mkdir -p "$LOG_DIR" "$STATE_DIR"

[ -f "$ENV_FILE" ] && set -a && . "$ENV_FILE" && set +a

LEVEL="${1:-INFO}"
TITLE="${2:-Jarvis Alert}"
MESSAGE="${3:-No message}"
COOLDOWN_SECONDS="${ALERT_COOLDOWN_SECONDS:-600}"

TS="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
NOW="$(date +%s)"

KEY="$(printf '%s|%s' "$LEVEL" "$TITLE" | sha256sum | awk '{print $1}')"
STATE_FILE="$STATE_DIR/$KEY.last"

LAST=0
[ -f "$STATE_FILE" ] && LAST="$(cat "$STATE_FILE" 2>/dev/null || echo 0)"

if [ $((NOW - LAST)) -lt "$COOLDOWN_SECONDS" ]; then
  echo "[$TS] [SUPPRESSED] [$LEVEL] $TITLE - $MESSAGE" >> "$ALERT_LOG"
  exit 0
fi

echo "$NOW" > "$STATE_FILE"
echo "[$TS] [$LEVEL] $TITLE - $MESSAGE" >> "$ALERT_LOG"

if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
  text="[$LEVEL] $TITLE
$MESSAGE
Host: $(hostname)
Time: $TS"

  curl -fsS --max-time 8 \
    -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${text}" \
    >/dev/null 2>&1 || echo "[$TS] [WARN] Telegram send failed" >> "$ALERT_LOG"
fi

if command -v notify-send >/dev/null 2>&1; then
  notify-send "[$LEVEL] $TITLE" "$MESSAGE" >/dev/null 2>&1 || true
fi

exit 0
