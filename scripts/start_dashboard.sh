#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${ROOT_DIR}/app"
KING_DIR="${ROOT_DIR}/Kingofyadav"
LOG_DIR="${ROOT_DIR}/logs"

if [[ -f "${ROOT_DIR}/.env" ]]; then
    set -a; source "${ROOT_DIR}/.env"; set +a
fi
VENV_DIR="${APP_DIR}/.venv"
STREAMLIT_APP="${APP_DIR}/app.py"
KING_TARGET="${KING_DIR}/app.py"
STREAMLIT_LOG="${LOG_DIR}/dashboard.log"
STREAMLIT_PID_FILE="${LOG_DIR}/dashboard.pid"
KING_PID_FILE="${LOG_DIR}/kingofyadav.pid"
KING_OWNED_MARKER="${LOG_DIR}/kingofyadav.dashboard_owned"

mkdir -p "${LOG_DIR}"

start_kingofyadav_if_needed() {
  existing_pid="$(pgrep -f "${KING_TARGET}" | head -n 1 || true)"
  if [[ -n "${existing_pid}" ]]; then
    echo "${existing_pid}" > "${KING_PID_FILE}"
    echo "Kingofyadav listener already running with PID ${existing_pid}"
    rm -f "${KING_OWNED_MARKER}"
    return
  fi

  # Bug 7 fix: use the digitalworld venv python (has all Jarvis deps).
  local KING_PYTHON="${HOME}/digitalworld/bin/python3"
  if [[ ! -x "${KING_PYTHON}" ]]; then
    KING_PYTHON="$(command -v python3)"
  fi

  (
    cd "${KING_DIR}"
    nohup "${KING_PYTHON}" app.py >> "${LOG_DIR}/kingofyadav.log" 2>&1 &
    echo $! > "${KING_PID_FILE}"
  )
  touch "${KING_OWNED_MARKER}"

  sleep 1
  echo "Kingofyadav listener started with PID $(cat "${KING_PID_FILE}")"
}

PYTHON="${VENV_DIR}/bin/python3"
if [[ -f "/.dockerenv" ]]; then
  PYTHON="$(command -v python3)"
fi

ensure_venv() {
  if [[ ! -x "${PYTHON}" ]]; then
    if python3 -m streamlit --version >/dev/null 2>&1; then
      PYTHON="$(command -v python3)"
      return
    fi
    echo "Streamlit runtime not ready."
    echo "Create the local venv with:"
    echo "  cd ${APP_DIR}"
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r ../requirements.txt"
    exit 1
  fi
}

start_kingofyadav_if_needed
ensure_venv

if [[ -f "/.dockerenv" ]]; then
  echo "Starting dashboard on 0.0.0.0:8501"
  exec "${PYTHON}" -m streamlit run "${STREAMLIT_APP}" \
    --server.address 0.0.0.0 \
    --server.port 8501 \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --server.headless true \
    --browser.serverAddress 127.0.0.1
fi

if [[ -f "${STREAMLIT_PID_FILE}" ]] && kill -0 "$(cat "${STREAMLIT_PID_FILE}")" 2>/dev/null; then
  echo "Dashboard already running with PID $(cat "${STREAMLIT_PID_FILE}")"
  exit 0
fi

existing_dashboard_pid="$(pgrep -f "[s]treamlit run ${STREAMLIT_APP}" | head -n 1 || true)"
if [[ -n "${existing_dashboard_pid}" ]]; then
  echo "${existing_dashboard_pid}" > "${STREAMLIT_PID_FILE}"
  echo "Dashboard already running with PID ${existing_dashboard_pid}"
  exit 0
fi

# Use python -m streamlit to avoid broken shebangs when the venv is relocated.
# setsid keeps the dashboard independent of the shell/session that launched it.
nohup setsid "${PYTHON}" -m streamlit run "${STREAMLIT_APP}" \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --server.headless true \
  --browser.serverAddress 127.0.0.1 \
  >> "${STREAMLIT_LOG}" 2>&1 &
echo $! > "${STREAMLIT_PID_FILE}"
sleep 2
echo "Dashboard started with PID $(cat "${STREAMLIT_PID_FILE}")"
echo "Open http://127.0.0.1:8501"
