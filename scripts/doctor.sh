#!/usr/bin/env bash
# Jarvis Doctor Pro: full diagnostic report for local/systemd/docker runtime.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 2

if [ -f ".env" ]; then
  set -a
  . ".env"
  set +a
fi

REPORT_DIR="$ROOT/logs/doctor"
mkdir -p "$REPORT_DIR"

TS="$(date -u +"%Y-%m-%dT%H-%M-%SZ")"
TEXT_REPORT="$REPORT_DIR/doctor-$TS.txt"
JSON_REPORT="$REPORT_DIR/doctor-$TS.json"
LATEST_JSON="$REPORT_DIR/latest.json"

PASS=0
WARN=0
FAIL=0
_CHECKS_RAW=""

log(){ echo "$*" | tee -a "$TEXT_REPORT"; }

record(){
  local status="$1"
  local area="$2"
  local name="$3"
  local detail="${4:-}"
  local icon="•"
  local severity="OPTIONAL"

  case "$status" in
    PASS) PASS=$((PASS+1)); icon="✅" ;;
    WARN) WARN=$((WARN+1)); icon="⚠️ " ;;
    FAIL) FAIL=$((FAIL+1)); icon="❌" ;;
  esac
  case "$area" in
    security|secrets|endpoint|bridge|syntax|files|dirs|pid|python|python-module|json|bus|bus-health)
      severity="CRITICAL"
      ;;
  esac

  log "$icon [$status] [$severity] [$area] $name ${detail:+- $detail}"
  _CHECKS_RAW="${_CHECKS_RAW}${status}	${area}	${name}	${detail}"$'\n'
}

section(){
  log ""
  log "== $1 =="
}

cmd_exists(){ command -v "$1" >/dev/null 2>&1; }
sudo_available(){ sudo -n true >/dev/null 2>&1; }

require_file(){ [ -f "$1" ] && record PASS files "$1" "exists" || record FAIL files "$1" "missing"; }
warn_file(){ [ -f "$1" ] && record PASS files "$1" "exists" || record WARN files "$1" "missing"; }
require_dir(){ [ -d "$1" ] && record PASS dirs "$1" "exists" || record FAIL dirs "$1" "missing"; }

http_code(){
  curl -s -o /dev/null -w "%{http_code}" --max-time 4 "$@" 2>/dev/null || echo "000"
}

log "========================================"
log " JARVIS DOCTOR PRO"
log " root=$ROOT"
log " utc=$TS"
log " user=$(whoami)"
log " host=$(hostname)"
log " kernel=$(uname -srmo)"
log "========================================"

section "1. Operating system"
if [ -f /etc/os-release ]; then
  . /etc/os-release
  record PASS os "distribution" "${PRETTY_NAME:-unknown}"
else
  record WARN os "distribution" "/etc/os-release missing"
fi

section "2. Required commands"
for c in python3 pip git curl jq node npm ffmpeg arecord pactl ss systemctl journalctl ufw docker redis-cli nginx logrotate; do
  cmd_exists "$c" && record PASS command "$c" "$(command -v "$c")" || record WARN command "$c" "not found"
done

section "3. Tool versions"
python3 --version 2>&1 | tee -a "$TEXT_REPORT" || record WARN version python3 "unavailable"
pip --version 2>&1 | tee -a "$TEXT_REPORT" || record WARN version pip "unavailable"
git --version 2>&1 | tee -a "$TEXT_REPORT" || record WARN version git "unavailable"
node --version 2>&1 | tee -a "$TEXT_REPORT" || record WARN version node "unavailable"
npm --version 2>&1 | tee -a "$TEXT_REPORT" || record WARN version npm "unavailable"
ffmpeg -version 2>/dev/null | head -n 1 | tee -a "$TEXT_REPORT" || record WARN version ffmpeg "unavailable"

section "4. Python environment"
[ -x ".venv/bin/python" ] && record PASS python "api venv" ".venv/bin/python exists" || record FAIL python "api venv" "missing .venv/bin/python"
[ -x "app/.venv/bin/streamlit" ] && record PASS python "dashboard venv" "app/.venv/bin/streamlit exists" || record FAIL python "dashboard venv" "missing app/.venv/bin/streamlit"
[ -n "${VIRTUAL_ENV:-}" ] && record PASS python "shell virtualenv" "$VIRTUAL_ENV" || record WARN python "shell virtualenv" "not active; ok for systemd"

python3 - <<'PY' >/tmp/jarvis_pycheck.txt 2>&1
import sys, site
print("executable:", sys.executable)
print("version:", sys.version.replace("\n", " "))
print("site-packages:", site.getsitepackages())
PY
cat /tmp/jarvis_pycheck.txt | tee -a "$TEXT_REPORT"

section "5. Python modules"

API_PY=".venv/bin/python"
APP_PY="app/.venv/bin/python"
: > /tmp/jarvis_modcheck.txt

for mod in requests fastapi uvicorn pydantic; do
  "$API_PY" -c "import $mod" >/dev/null 2>&1 && \
  record PASS python-module "$mod (api)" "ok" || \
  record WARN python-module "$mod (api)" "missing"
done

"$API_PY" -m pip check >/tmp/jarvis_api_pipcheck.txt 2>&1 && \
  record PASS python-module "api package versions" "pip check ok" || \
  record WARN python-module "api package versions" "$(tr '\n' ' ' < /tmp/jarvis_api_pipcheck.txt)"

for mod in streamlit; do
  "$APP_PY" -c "import $mod" >/dev/null 2>&1 && \
  record PASS python-module "$mod (dashboard)" "ok" || \
  record WARN python-module "$mod (dashboard)" "missing"
done

"$APP_PY" -m pip check >/tmp/jarvis_app_pipcheck.txt 2>&1 && \
  record PASS python-module "dashboard package versions" "pip check ok" || \
  record WARN python-module "dashboard package versions" "$(tr '\n' ' ' < /tmp/jarvis_app_pipcheck.txt)"

while read -r status mod rest; do
  [ -z "${mod:-}" ] && continue
  [ "$status" = "PASS" ] && record PASS python-module "$mod" "${rest:-import ok}" || record WARN python-module "$mod" "${rest:-missing}"
done < /tmp/jarvis_modcheck.txt

section "6. Project contract files"
require_file "Jarvis/bridge.py"
require_file "Kingofyadav/handler.py"
require_file "Kingofyadav/app.py"
require_file "shared/message_bus.py"
require_file "shared/intent_schema.json"
require_file "web/api.py"
require_file "app/app.py"
require_file "scripts/start_all.sh"
require_file "scripts/status.sh"
require_file "scripts/watchdog.sh"
warn_file "requirements.txt"
warn_file "requirements.lock.txt"
warn_file "apt-packages.txt"
warn_file ".env.example"
warn_file ".env"
warn_file "run.sh"
warn_file "Dockerfile"
warn_file "docker-compose.yml"

section "7. Script syntax and executability"
for f in scripts/*.sh run.sh; do
  [ -e "$f" ] || continue
  bash -n "$f" >/dev/null 2>&1 && record PASS syntax "$f" "bash syntax ok" || record FAIL syntax "$f" "bash syntax error"
  [ -x "$f" ] && record PASS executable "$f" "ok" || record WARN executable "$f" "run chmod +x $f"
done

section "8. Secret hygiene"
if [ -f ".env" ]; then
  if grep -Eq 'OPENAI_API_KEY=sk-|API_KEY=.*[A-Za-z0-9_-]{20,}' .env; then
    record WARN secrets ".env" "contains secret-like values; never commit"
  else
    record PASS secrets ".env" "no obvious secret pattern found"
  fi
else
  record WARN secrets ".env" "missing"
fi

if [ -f ".gitignore" ]; then
  grep -Eq '^\.env$|\.env' .gitignore && record PASS secrets ".gitignore" ".env ignored" || record FAIL secrets ".gitignore" ".env not ignored"
else
  record FAIL secrets ".gitignore" "missing"
fi

section "9. Git cleanliness"
if [ -d ".git" ]; then
  record PASS git "repository" "detected"
  git status --short | tee -a "$TEXT_REPORT"
else
  record WARN git "repository" "not detected"
fi

section "10. JSON validity"
python3 - <<'PY' > /tmp/jarvis_jsoncheck.txt 2>&1
import json
from pathlib import Path
files = [
 "Kingofyadav/state.json",
 "Kingofyadav/state.backup.json",
 "Kingofyadav/memory_event_archive.json",
 "logs/ai_model_config.json",
 "logs/public_chat_config.json",
 "logs/dashboard_session.json",
 "shared/intent_schema.json",
]
for f in files:
    p = Path(f)
    if not p.exists():
        print("WARN", f, "missing")
        continue
    try:
        json.loads(p.read_text())
        print("PASS", f, "valid")
    except Exception as e:
        print("FAIL", f, str(e))
PY

while read -r status file detail; do
  [ -z "${file:-}" ] && continue
  record "$status" json "$file" "${detail:-}"
done < /tmp/jarvis_jsoncheck.txt

section "11. Message bus"
for d in shared/bus/requests shared/bus/responses shared/bus/processed shared/bus/deadletter logs; do
  require_dir "$d"
done

for d in requests responses processed deadletter; do
  count="$(find "shared/bus/$d" -type f 2>/dev/null | wc -l)"
  record PASS bus "$d count" "$count"
done

processing_count="$(find shared/bus/requests shared/bus/responses -name '*.processing' -type f 2>/dev/null | wc -l)"
[ "$processing_count" -eq 0 ] && record PASS bus "processing files" "none" || record WARN bus "processing files" "$processing_count found"

dead_count="$(find shared/bus/deadletter -type f 2>/dev/null | wc -l)"
[ "$dead_count" -eq 0 ] && record PASS bus "deadletter" "empty" || record WARN bus "deadletter" "$dead_count files"

section "12. Process checks"
api_pid="$(pgrep -f "$ROOT/web/api.py" | head -n 1 || true)"
king_pid="$(pgrep -f "$ROOT/Kingofyadav/app.py" | head -n 1 || true)"
dash_pid="$(pgrep -f "streamlit run $ROOT/app/app.py" | head -n 1 || true)"

[ -n "$api_pid" ] && record PASS process "api" "pid=$api_pid" || record WARN process "api" "not running"
[ -n "$king_pid" ] && record PASS process "kingofyadav" "pid=$king_pid" || record WARN process "kingofyadav" "not running"
[ -n "$dash_pid" ] && record PASS process "dashboard" "pid=$dash_pid" || record WARN process "dashboard" "not running"

section "13. PID file integrity"
[ -f logs/jarvis.pid ] && ! kill -0 "$(cat logs/jarvis.pid)" 2>/dev/null && rm -f logs/jarvis.pid
shopt -s nullglob
for pf in logs/*.pid; do
  pid="$(cat "$pf" 2>/dev/null || true)"
  name="$(basename "$pf")"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    record PASS pid "$name" "alive pid=$pid"
  else
    record WARN pid "$name" "stale pid=$pid"
  fi
done
shopt -u nullglob

section "14. Port exposure"
ss -tulnp 2>/dev/null | grep -E '(:5050|:5051|:8501|:8502|:80|:443|:8080)' | tee -a "$TEXT_REPORT" || true

ss -tuln | grep -q "0.0.0.0:8501" && record FAIL security "streamlit exposure" "8501 public" || record PASS security "streamlit exposure" "8501 not public"
ss -tuln | grep -q "0.0.0.0:5050" && record FAIL security "api exposure" "5050 public" || record PASS security "api exposure" "5050 not public"

section "15. Endpoint health"
api_body="$(curl -fsS --max-time 4 http://127.0.0.1:5050/api/health 2>/dev/null || true)"
if echo "$api_body" | grep -q '"ok"[[:space:]]*:[[:space:]]*true' && echo "$api_body" | grep -q '"jarvis_ok"[[:space:]]*:[[:space:]]*true'; then
  record PASS endpoint "api deep health" "$api_body"
else
  record FAIL endpoint "api deep health" "${api_body:-not reachable}"
fi

for path in /api/health /api/status /api/live /api/; do
  if [[ "$path" == "/api/status" || "$path" == "/api/live" ]]; then
    code="$(http_code -H "Authorization: Bearer ${JARVIS_API_KEY:-}" "http://127.0.0.1:5050$path")"
  else
    code="$(http_code "http://127.0.0.1:5050$path")"
  fi
  case "$code" in
    200|204|301|302|307|308) record PASS endpoint "$path" "http=$code" ;;
    000) record WARN endpoint "$path" "not reachable" ;;
    *) record WARN endpoint "$path" "http=$code" ;;
  esac
done

code="$(http_code "http://127.0.0.1:8501")"
case "$code" in
  200|302) record PASS endpoint "dashboard local /" "http=$code" ;;
  *) record WARN endpoint "dashboard local /" "http=$code" ;;
esac

code="$(http_code "http://127.0.0.1:8502")"
case "$code" in
  200|302) record PASS endpoint "dashboard docker /" "http=$code" ;;
  000) record WARN endpoint "dashboard docker /" "not reachable; ok if docker stopped" ;;
  *) record WARN endpoint "dashboard docker /" "http=$code" ;;
esac

section "16. Base services"
for svc in redis-server nginx ssh; do
  if systemctl list-unit-files "$svc.service" >/dev/null 2>&1; then
    systemctl is-active --quiet "$svc" && record PASS service "$svc" "running" || if systemctl show "$svc.service" -p Type 2>/dev/null | grep -q oneshot; then
  record PASS jarvis-service "$svc" "oneshot (expected)"
else
  record WARN jarvis-service "$svc" "inactive"
fi
  else
    record WARN service "$svc" "not installed"
  fi
done

section "17. Jarvis systemd services"

check_service_anywhere() {
  local svc="$1"

  if systemctl list-unit-files "$svc.service" >/dev/null 2>&1; then
    if systemctl is-active --quiet "$svc.service"; then
      record PASS jarvis-service "$svc" "active system service"
    elif systemctl show "$svc.service" -p Type 2>/dev/null | grep -q oneshot; then
      record PASS jarvis-service "$svc" "oneshot system service"
    else
      record WARN jarvis-service "$svc" "inactive system service"
    fi
    return
  fi

  if systemctl --user list-unit-files "$svc.service" >/dev/null 2>&1; then
    if systemctl --user is-active --quiet "$svc.service"; then
      record PASS jarvis-service "$svc" "active user service"
    elif systemctl --user show "$svc.service" -p Type 2>/dev/null | grep -q oneshot; then
      record PASS jarvis-service "$svc" "oneshot user service"
    else
      record WARN jarvis-service "$svc" "inactive user service"
    fi
    return
  fi

  record WARN jarvis-service "$svc" "unit missing"
}

check_timer_anywhere() {
  local timer="$1"

  if systemctl list-unit-files "$timer.timer" >/dev/null 2>&1; then
    systemctl is-active --quiet "$timer.timer" && \
      record PASS jarvis-timer "$timer.timer" "active system timer" || \
      record WARN jarvis-timer "$timer.timer" "inactive system timer"
    return
  fi

  if systemctl --user list-unit-files "$timer.timer" >/dev/null 2>&1; then
    systemctl --user is-active --quiet "$timer.timer" && \
      record PASS jarvis-timer "$timer.timer" "active user timer" || \
      record WARN jarvis-timer "$timer.timer" "inactive user timer"
    return
  fi

  record WARN jarvis-timer "$timer.timer" "missing"
}

for svc in jarvis-api jarvis-dashboard jarvis-kingofyadav jarvis-watchdog jarvis-doctor; do
  check_service_anywhere "$svc"
done

for timer in jarvis-watchdog jarvis-doctor; do
  check_timer_anywhere "$timer"
done

section "18. Systemd failed units"
failed_units="$(systemctl --failed --no-legend 2>/dev/null | awk '{print $1}' | tr '\n' ' ' || true)"
[ -z "$failed_units" ] && record PASS systemd "failed units" "none" || record WARN systemd "failed units" "$failed_units"

section "19. Docker"
if cmd_exists docker; then
  if docker info >/dev/null 2>&1; then
    record PASS docker "daemon access" "current user can use docker"
    if [ -f docker-compose.yml ]; then
      docker compose ps 2>/dev/null | tee -a "$TEXT_REPORT" || record WARN docker "compose ps" "failed"
    fi
  else
    record WARN docker "daemon access" "try: newgrp docker or logout/login"
  fi
else
  record WARN docker "docker" "missing"
fi

section "20. Nginx"
if cmd_exists nginx; then
  if sudo_available; then
    sudo -n nginx -t >/tmp/jarvis_nginx.txt 2>&1 && record PASS nginx "config test" "$(tr '\n' ' ' < /tmp/jarvis_nginx.txt)" || record WARN nginx "config test" "$(tr '\n' ' ' < /tmp/jarvis_nginx.txt)"
  else
    record WARN nginx "config test" "requires passwordless sudo or privileged terminal"
  fi
else
  record WARN nginx "nginx" "missing"
fi

section "21. Firewall"
if cmd_exists ufw; then
  if sudo_available; then
    sudo -n ufw status numbered | tee -a "$TEXT_REPORT"
    sudo -n ufw status | grep -q "Status: active" && record PASS firewall "ufw" "active" || record WARN firewall "ufw" "inactive"
  else
    record WARN firewall "ufw" "requires passwordless sudo or privileged terminal"
  fi
else
  record WARN firewall "ufw" "missing"
fi

section "22. Logrotate"
if [ -f /etc/logrotate.d/jarvis ]; then
  if sudo_available; then
    sudo -n logrotate -d /etc/logrotate.d/jarvis >/tmp/jarvis_logrotate.txt 2>&1
    grep -q "error:" /tmp/jarvis_logrotate.txt && record WARN logrotate "jarvis config" "$(grep 'error:' /tmp/jarvis_logrotate.txt | head -n 2 | tr '\n' ' ')" || record PASS logrotate "jarvis config" "debug test ok"
  else
    record WARN logrotate "jarvis config" "requires privileged terminal"
  fi
else
  record WARN logrotate "jarvis config" "/etc/logrotate.d/jarvis missing"
fi

section "23. Audio"
if pactl info >/dev/null 2>&1; then
  record PASS audio "pulse/pipewire" "available"
  pactl info | grep -E "Server Name|Default Source|Default Sink" | tee -a "$TEXT_REPORT" || true
else
  record WARN audio "pulse/pipewire" "not responding"
fi

arecord -l >/dev/null 2>&1 && record PASS audio "capture devices" "visible" || record WARN audio "capture devices" "not visible"

section "24. Resources"
disk_pct="$(df / | awk 'NR==2 {gsub("%","",$5); print $5}')"
inode_pct="$(df -i / | awk 'NR==2 {gsub("%","",$5); print $5}')"
mem_avail_mb="$(free -m | awk '/Mem:/ {print $7}')"
load1="$(awk '{print $1}' /proc/loadavg)"

[ "$disk_pct" -lt 85 ] && record PASS resource "disk /" "${disk_pct}% used" || record WARN resource "disk /" "${disk_pct}% used"
[ "$inode_pct" -lt 85 ] && record PASS resource "inodes /" "${inode_pct}% used" || record WARN resource "inodes /" "${inode_pct}% used"
[ "$mem_avail_mb" -gt 1024 ] && record PASS resource "memory" "${mem_avail_mb}MB available" || record WARN resource "memory" "${mem_avail_mb}MB available"
record PASS resource "load average 1m" "$load1"

section "25. Test suite discovery"
tests_found="$(find . -path './.git' -prune -o -path './.venv' -prune -o -path './app/.venv' -prune -o -path '*/tests/*.py' -print -o -name 'test_*.py' -print 2>/dev/null | wc -l)"
[ "$tests_found" -gt 0 ] && record PASS tests "test files" "$tests_found found" || record WARN tests "test files" "none found"

section "26. Bus health script"
if [ -f shared/bus_health.py ]; then
  timeout 20 python3 shared/bus_health.py >/tmp/jarvis_bushealth.txt 2>&1 && record PASS bus-health "shared/bus_health.py" "ok" || record WARN bus-health "shared/bus_health.py" "$(tail -n 5 /tmp/jarvis_bushealth.txt | tr '\n' ' ')"
else
  record WARN bus-health "shared/bus_health.py" "missing"
fi

section "27. Bridge smoke test"
if [ -f Jarvis/bridge.py ]; then
  if timeout 50 python3 Jarvis/bridge.py "memory" >/tmp/jarvis_bridge.txt 2>&1; then
    record PASS bridge "memory smoke test" "ok"
    tail -n 8 /tmp/jarvis_bridge.txt | tee -a "$TEXT_REPORT"
  else
    code=$?
    [ "$code" -eq 124 ] && record FAIL bridge "memory smoke test" "timeout" || record WARN bridge "memory smoke test" "exit=$code"
    tail -n 12 /tmp/jarvis_bridge.txt | tee -a "$TEXT_REPORT"
  fi
else
  record FAIL bridge "Jarvis/bridge.py" "missing"
fi

section "28. Recommendations"
[ ! -f requirements.txt ] && log "- Create requirements.txt from curated runtime dependencies."
[ ! -f .env.example ] && log "- Create .env.example without secrets."
[ ! -f run.sh ] && log "- Create run.sh as the single local entrypoint."
[ ! -f Dockerfile ] && log "- Add Dockerfile for portable deployment."
[ ! -f docker-compose.yml ] && log "- Add docker-compose.yml for API/dashboard/redis/nginx."
[ ! -f /etc/logrotate.d/jarvis ] && log "- Install logrotate config: sudo cp scripts/jarvis-logrotate.conf /etc/logrotate.d/jarvis"

section "29. Summary"
log "PASS=$PASS"
log "WARN=$WARN"
log "FAIL=$FAIL"
log "TEXT_REPORT=$TEXT_REPORT"
log "JSON_REPORT=$JSON_REPORT"

CHECKS_FILE="$(mktemp)"
printf '%s' "${_CHECKS_RAW}" > "$CHECKS_FILE"

python3 - "$JSON_REPORT" "$LATEST_JSON" "$TS" "$ROOT" "$PASS" "$WARN" "$FAIL" "$CHECKS_FILE" <<'PY'
import json, sys
out, latest, ts, root, p, w, f, checks_file = sys.argv[1:]
checks = []
with open(checks_file, encoding="utf-8") as fh:
    for line in fh.read().splitlines():
        parts = line.split("\t", 3)
        if len(parts) == 4:
            checks.append({"status": parts[0], "area": parts[1], "name": parts[2], "detail": parts[3]})
data = {
    "timestamp_utc": ts,
    "root": root,
    "summary": {"pass": int(p), "warn": int(w), "fail": int(f)},
    "checks": checks,
}
payload = json.dumps(data, indent=2)
open(out, "w", encoding="utf-8").write(payload)
open(latest, "w", encoding="utf-8").write(payload)
PY
rm -f "$CHECKS_FILE"

if [ "$FAIL" -gt 0 ]; then
  log "RESULT=FAIL"
  exit 1
elif [ "$WARN" -gt 0 ]; then
  log "RESULT=WARNING"
  exit 0
else
  log "RESULT=PASS"
  exit 0
fi
