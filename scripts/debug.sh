#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 2

echo "=================================="
echo " JARVIS LOCAL DEBUG"
echo " time=$(date)"
echo " root=$ROOT"
echo " user=$(whoami)"
echo " host=$(hostname)"
echo "=================================="

echo
echo "== Internet =="
ping -c 2 8.8.8.8 >/dev/null 2>&1 && echo "✅ Internet IP reachable" || echo "❌ Internet IP failed"
ping -c 2 google.com >/dev/null 2>&1 && echo "✅ DNS working" || echo "❌ DNS failed"

echo
echo "== Local ports =="
ss -tulpen 2>/dev/null | grep -E ':5050|:5051|:8501|:8502|:80|:443|:8080' || echo "No Jarvis/server ports found"

echo
echo "== API health =="
curl -fsS --max-time 4 http://127.0.0.1:5050/api/health && echo || echo "❌ API local failed"

echo
echo "== Dashboard =="
code="$(curl -s -o /dev/null -w "%{http_code}" --max-time 4 http://127.0.0.1:8501 || true)"
echo "Local dashboard HTTP: $code"

code="$(curl -s -o /dev/null -w "%{http_code}" --max-time 4 http://127.0.0.1:8502 || true)"
echo "Docker dashboard HTTP: $code"

echo
echo "== Services =="
for svc in jarvis-api jarvis-dashboard jarvis-kingofyadav jarvis-watchdog; do
  systemctl is-active --quiet "$svc.service" && echo "✅ $svc active" || echo "⚠️  $svc not active/system"
  systemctl --user is-active --quiet "$svc.service" 2>/dev/null && echo "✅ $svc active user" || true
done

echo
echo "== Timers =="
systemctl list-timers | grep -E 'jarvis-watchdog|jarvis-doctor' || echo "No Jarvis timers found"

echo
echo "== Local/runtime ports =="
ss -tulpen 2>/dev/null | grep -E ':5050|:8501|:80|:443|:8080' || echo "No local runtime ports found"

echo
echo "== Docker backup ports (optional) =="
ss -tulpen 2>/dev/null | grep -E ':5051|:8502' || echo "No Docker backup ports active — OK"

echo
echo "== Recent alerts =="
tail -n 10 logs/alerts.log 2>/dev/null || echo "No alerts.log yet"

echo
echo "== Recent watchdog logs =="
journalctl -u jarvis-watchdog.service -n 20 --no-pager 2>/dev/null || true

echo
echo "✅ Debug complete"
