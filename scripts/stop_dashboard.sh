#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
STREAMLIT_PID_FILE="${LOG_DIR}/dashboard.pid"
KING_PID_FILE="${LOG_DIR}/kingofyadav.pid"
KING_OWNED_MARKER="${LOG_DIR}/kingofyadav.dashboard_owned"

stop_pid_file() {
  local pid_file="$1"
  local label="$2"
  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    kill "$(cat "${pid_file}")"
    rm -f "${pid_file}"
    echo "${label} stopped"
  else
    rm -f "${pid_file}"
    echo "${label} not running"
  fi
}

stop_pid_file "${STREAMLIT_PID_FILE}" "Dashboard"
pkill -f "streamlit run ${ROOT_DIR}/app/app.py" >/dev/null 2>&1 || true

if [[ -f "${KING_OWNED_MARKER}" ]]; then
  stop_pid_file "${KING_PID_FILE}" "Kingofyadav listener"
  rm -f "${KING_OWNED_MARKER}"
else
  echo "Kingofyadav listener left running"
fi
