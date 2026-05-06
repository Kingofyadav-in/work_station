#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"

for name in kingofyadav jarvis; do
  pid_file="${LOG_DIR}/${name}.pid"
  echo "=== ${name} ==="
  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    echo "RUNNING PID $(cat "${pid_file}")"
  else
    echo "NOT RUNNING"
  fi
done

echo
echo "Bus log tail:"
tail -n 20 "${LOG_DIR}/bus.log" 2>/dev/null || true
