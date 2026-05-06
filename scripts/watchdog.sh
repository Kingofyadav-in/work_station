#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "$LOG_DIR"

API_URL="${API_URL:-http://127.0.0.1:5050/api/health}"
DASHBOARD_URL="${DASHBOARD_URL:-http://127.0.0.1:8501}"

API_SERVICE="${API_SERVICE:-jarvis-api.service}"
DASHBOARD_SERVICE="${DASHBOARD_SERVICE:-jarvis-dashboard.service}"
KING_SERVICE="${KING_SERVICE:-jarvis-kingofyadav.service}"

API_SCRIPT="${ROOT_DIR}/scripts/start_api.sh"
DASHBOARD_SCRIPT="${ROOT_DIR}/scripts/start_dashboard.sh"
KING_APP="${ROOT_DIR}/Kingofyadav/app.py"
KING_PID_FILE="${LOG_DIR}/kingofyadav.pid"

ALERT_SCRIPT="${ROOT_DIR}/scripts/alert.sh"
PUBLIC_HEALTH_SCRIPT="${ROOT_DIR}/scripts/public-health.sh"

alert() {
  [[ -x "$ALERT_SCRIPT" ]] && "$ALERT_SCRIPT" "$1" "$2" "$3" >/dev/null 2>&1 || true
}

failure_count() {
  local key="$1"
  local file="$LOG_DIR/${key}.failcount"
  local count=0
  [ -f "$file" ] && count="$(cat "$file" 2>/dev/null || echo 0)"
  count=$((count + 1))
  echo "$count" > "$file"
  echo "$count"
}

clear_failure_count() {
  rm -f "$LOG_DIR/${1}.failcount"
}

mark_recovered() {
  local key="$1"
  local file="$LOG_DIR/${key}.failcount"

  if [ -f "$file" ]; then
    alert "INFO" "$key recovered" "Service is back to normal"
    rm -f "$file"
  fi
}

log() {
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [watchdog] $*"
}

has_systemd_unit() {
  systemctl list-unit-files "$1" >/dev/null 2>&1
}

has_user_systemd_unit() {
  systemctl --user list-unit-files "$1" >/dev/null 2>&1
}

restart_systemd_unit() {
  local name="$1"
  local svc="$2"

  if has_user_systemd_unit "$svc"; then
    log "$name: restarting user systemd unit"
    systemctl --user restart "$svc" >/dev/null 2>&1 || return 1
    sleep 1
    systemctl --user is-active --quiet "$svc"
    return $?
  fi

  has_systemd_unit "$svc" || return 1

  log "$name: restarting systemd unit"
  systemctl restart "$svc" >/dev/null 2>&1 || return 1
  sleep 1

  systemctl is-active --quiet "$svc"
}

restart_service_or_script() {
  restart_systemd_unit "$1" "$2" && return 0
  [[ -x "$3" ]] && bash "$3" >/dev/null 2>&1 && return 0
  log "$1: restart failed"
}

http_ok() {
  curl -fsS --max-time 4 "$1" >/dev/null 2>&1
}

api_deep_ok() {
  local body
  body="$(curl -fsS --max-time 4 "$API_URL" 2>/dev/null || true)"
  [[ -n "$body" ]] || return 1
  echo "$body" | grep -q '"ok":true' || return 1
  echo "$body" | grep -q '"jarvis_ok":true' || return 1
}

# =========================
# API
# =========================
check_api() {
  if api_deep_ok; then
    log "API: OK"
    mark_recovered api
  else
    count="$(failure_count api)"
    log "API: FAIL count=$count"

    [ "$count" -ge 2 ] && alert "CRITICAL" "API failed" "count=$count"
    [ "$count" -ge 3 ] && {
      restart_service_or_script "API" "$API_SERVICE" "$API_SCRIPT"
      clear_failure_count api
    }
  fi
}

# =========================
# DASHBOARD
# =========================
check_dashboard() {
  if http_ok "$DASHBOARD_URL"; then
    log "Dashboard: OK"
    mark_recovered dashboard
  else
    count="$(failure_count dashboard)"
    log "Dashboard: FAIL count=$count"

    [ "$count" -ge 2 ] && alert "WARN" "Dashboard failed" "count=$count"
    [ "$count" -ge 3 ] && {
      restart_service_or_script "Dashboard" "$DASHBOARD_SERVICE" "$DASHBOARD_SCRIPT"
      clear_failure_count dashboard
    }
  fi
}

# =========================
# KINGOFYADAV
# =========================
check_kingofyadav() {
  if has_user_systemd_unit "$KING_SERVICE" && systemctl --user is-active --quiet "$KING_SERVICE"; then
    log "Kingofyadav: OK"
    mark_recovered king
    return
  fi

  if has_systemd_unit "$KING_SERVICE" && systemctl is-active --quiet "$KING_SERVICE"; then
    log "Kingofyadav: OK"
    mark_recovered king
    return
  fi

  count="$(failure_count king)"
  log "Kingofyadav: FAIL count=$count"

  [ "$count" -ge 2 ] && alert "WARN" "Kingofyadav down" "count=$count"

  if [ "$count" -ge 3 ]; then
    restart_systemd_unit "Kingofyadav" "$KING_SERVICE" || {
      nohup python3 "$KING_APP" >> "$LOG_DIR/kingofyadav.log" 2>&1 &
      echo $! > "$KING_PID_FILE"
    }
    clear_failure_count king
  fi
}

# =========================
# PORTS
# =========================
check_ports() {
  log "Ports:"
  ss -tulpen 2>/dev/null | grep -E ':5050|:8501|:8502' || log "No ports"
}

# =========================
# PUBLIC WEBSITE ENDPOINTS
# =========================
check_public_health() {
  if [[ -x "$PUBLIC_HEALTH_SCRIPT" ]] && "$PUBLIC_HEALTH_SCRIPT" >> "$LOG_DIR/public-health.log" 2>&1; then
    log "Public endpoints: OK"
    mark_recovered public
  else
    count="$(failure_count public)"
    log "Public endpoints: FAIL count=$count"
    [ "$count" -ge 2 ] && alert "WARN" "Public Jarvis endpoints degraded" "count=$count; see logs/public-health.log"
    [ "$count" -ge 4 ] && clear_failure_count public
  fi
}

main() {
  log "Starting watchdog"

  check_api
  check_public_health
  check_dashboard
  check_kingofyadav
  check_ports

  log "Done"
  exit 0
}

main "$@"
