#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
API_SCRIPT="${ROOT_DIR}/web/api.py"
API_PID_FILE="${LOG_DIR}/api.pid"
API_LOG="${LOG_DIR}/api.log"

# Use Docker-installed Python inside container.
# Use project venv on host.
if [[ -f "/.dockerenv" ]]; then
  PYTHON="$(command -v python)"
else
  PYTHON="${ROOT_DIR}/.venv/bin/python"
fi

mkdir -p "${LOG_DIR}"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  source "${ROOT_DIR}/.env"
  set +a
fi

API_PORT="${API_PORT:-5050}"

if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="$(command -v python3)"
fi

if [[ -f "/.dockerenv" ]]; then
  if [[ -z "${API_HOST:-}" || "${API_HOST}" == "127.0.0.1" || "${API_HOST}" == "localhost" ]]; then
    export API_HOST="0.0.0.0"
  fi
  echo "Starting Jarvis API on ${API_HOST}:${API_PORT}"
  exec "${PYTHON}" "${API_SCRIPT}"
fi

port_pid() {
  ss -ltnp 2>/dev/null \
    | awk -v port=":${API_PORT}" '$4 ~ port {print $NF}' \
    | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' \
    | head -n 1
}

if [[ -f "${API_PID_FILE}" ]]; then
  existing_pid="$(cat "${API_PID_FILE}")"
  if kill -0 "${existing_pid}" 2>/dev/null; then
    echo "Jarvis API already running with PID ${existing_pid}"
    exit 0
  fi
  rm -f "${API_PID_FILE}"
fi

bound_pid="$(port_pid || true)"
if [[ -n "${bound_pid}" ]] && kill -0 "${bound_pid}" 2>/dev/null; then
  echo "${bound_pid}" > "${API_PID_FILE}"
  echo "Jarvis API already bound to port ${API_PORT} with PID ${bound_pid}"
  exit 0
fi

nohup setsid -f "${PYTHON}" "${API_SCRIPT}" </dev/null >> "${API_LOG}" 2>&1 &

sleep 1

started_pid="$(port_pid || true)"
if [[ -n "${started_pid}" ]]; then
  echo "${started_pid}" > "${API_PID_FILE}"
fi

if [[ ! -f "${API_PID_FILE}" ]] || ! kill -0 "$(cat "${API_PID_FILE}")" 2>/dev/null; then
  echo "Jarvis API failed to start. Last log lines:"
  tail -n 20 "${API_LOG}" || true
  exit 1
fi

echo "Jarvis API started with PID $(cat "${API_PID_FILE}")"
echo "Endpoint: http://127.0.0.1:${API_PORT}/api/status"
