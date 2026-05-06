#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "${LOG_DIR}"

# Load environment variables from .env
ENV_FILE="${ROOT_DIR}/.env"
if [[ -f "${ENV_FILE}" ]]; then
    set -a; source "${ENV_FILE}"; set +a
fi

start_bg() {
  local name="$1"
  local dir="$2"
  local log_file="$3"

  (
    cd "${dir}"
    nohup python3 app.py >> "${log_file}" 2>&1 &
    echo $! > "${LOG_DIR}/${name,,}.pid"
  )
  echo "${name} started with PID $(cat "${LOG_DIR}/${name,,}.pid")"
}

start_bg "Kingofyadav" "${ROOT_DIR}/Kingofyadav" "${LOG_DIR}/kingofyadav.log"
sleep 1
start_bg "Jarvis" "${ROOT_DIR}/Jarvis" "${LOG_DIR}/jarvis.log"
