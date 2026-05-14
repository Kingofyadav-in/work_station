#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
ENV_FILE="${ROOT_DIR}/.env"

mkdir -p "${LOG_DIR}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-5050}"
DASHBOARD_HOST="${DASHBOARD_HOST:-127.0.0.1}"
DASHBOARD_PORT="${DASHBOARD_PORT:-8501}"
START_AUTOMATION="${START_AUTOMATION:-0}"

PYTHON="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="$(command -v python3)"
fi

APP_PYTHON="${ROOT_DIR}/app/.venv/bin/python"
if [[ ! -x "${APP_PYTHON}" ]]; then
  APP_PYTHON="${PYTHON}"
fi

ts() { date +"%Y-%m-%d %H:%M:%S"; }
info() { printf '[%s] [INFO] %s\n' "$(ts)" "$*"; }
warn() { printf '[%s] [WARN] %s\n' "$(ts)" "$*" >&2; }
fail() { printf '[%s] [FAIL] %s\n' "$(ts)" "$*" >&2; exit 1; }

pid_alive() {
  local pid="${1:-}"
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

pid_file_alive() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] && pid_alive "$(cat "${pid_file}" 2>/dev/null || true)"
}

clean_stale_pid() {
  local pid_file="$1"
  if [[ -f "${pid_file}" ]] && ! pid_file_alive "${pid_file}"; then
    warn "Removing stale PID file ${pid_file}"
    rm -f "${pid_file}"
  fi
}

find_process() {
  local pattern="$1"
  pgrep -f "${pattern}" | head -n 1 || true
}

http_ok() {
  local url="$1"
  local code
  code="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 2 "${url}" 2>/dev/null || true)"
  [[ "${code}" =~ ^[23] ]]
}

wait_for_http() {
  local name="$1"
  local url="$2"
  local attempts="${3:-30}"
  local i

  for i in $(seq 1 "${attempts}"); do
    if http_ok "${url}"; then
      info "${name} healthy at ${url}"
      return 0
    fi
    sleep 1
  done
  return 1
}

start_python_service() {
  local name="$1"
  local workdir="$2"
  local script="$3"
  local pid_file="$4"
  local log_file="$5"
  local pattern="$6"
  local python_bin="${7:-${PYTHON}}"

  clean_stale_pid "${pid_file}"

  if pid_file_alive "${pid_file}"; then
    info "${name} already running with PID $(cat "${pid_file}")"
    return 0
  fi

  local existing_pid
  existing_pid="$(find_process "${pattern}")"
  if pid_alive "${existing_pid}"; then
    echo "${existing_pid}" > "${pid_file}"
    info "${name} already running with PID ${existing_pid}"
    return 0
  fi

  info "Starting ${name}"
  (
    cd "${workdir}"
    nohup setsid "${python_bin}" "${script}" </dev/null >> "${log_file}" 2>&1 &
    echo $! > "${pid_file}"
  )

  sleep 1
  if ! pid_file_alive "${pid_file}"; then
    warn "${name} failed to stay running. Last log lines:"
    tail -n 30 "${log_file}" 2>/dev/null || true
    return 1
  fi
  info "${name} started with PID $(cat "${pid_file}")"
}

start_streamlit_dashboard() {
  local pid_file="${LOG_DIR}/dashboard.pid"
  local log_file="${LOG_DIR}/dashboard.log"
  local app_file="${ROOT_DIR}/app/app.py"

  clean_stale_pid "${pid_file}"

  if pid_file_alive "${pid_file}"; then
    info "Dashboard already running with PID $(cat "${pid_file}")"
    return 0
  fi

  local existing_pid
  existing_pid="$(find_process "[s]treamlit run ${app_file}")"
  if pid_alive "${existing_pid}"; then
    echo "${existing_pid}" > "${pid_file}"
    info "Dashboard already running with PID ${existing_pid}"
    return 0
  fi

  if ! "${APP_PYTHON}" -m streamlit --version >/dev/null 2>&1; then
    fail "Streamlit is not available. Install dependencies with: ${PYTHON} -m pip install -r requirements.txt"
  fi

  info "Starting dashboard on http://${DASHBOARD_HOST}:${DASHBOARD_PORT}"
  nohup setsid "${APP_PYTHON}" -m streamlit run "${app_file}" \
    --server.address "${DASHBOARD_HOST}" \
    --server.port "${DASHBOARD_PORT}" \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --server.headless true \
    --browser.serverAddress "${DASHBOARD_HOST}" \
    </dev/null >> "${log_file}" 2>&1 &
  echo $! > "${pid_file}"

  sleep 2
  if ! pid_file_alive "${pid_file}"; then
    warn "Dashboard failed to stay running. Last log lines:"
    tail -n 30 "${log_file}" 2>/dev/null || true
    return 1
  fi
  info "Dashboard started with PID $(cat "${pid_file}")"
}

check_jarvis_bridge() {
  local log_file="${LOG_DIR}/jarvis.log"
  local pid_file="${LOG_DIR}/jarvis.pid"

  clean_stale_pid "${pid_file}"

  info "Checking Jarvis bridge"
  (
    cd "${ROOT_DIR}/Jarvis"
    "${PYTHON}" app.py
  ) >> "${log_file}" 2>&1

  info "Jarvis bridge is responding through the message bus"
}

require_runtime() {
  [[ -x "${PYTHON}" ]] || fail "Python runtime not found"
  command -v curl >/dev/null 2>&1 || fail "curl is required for health checks"
}

main() {
  info "Starting Work Station from ${ROOT_DIR}"
  require_runtime

  start_python_service \
    "Kingofyadav listener" \
    "${ROOT_DIR}/Kingofyadav" \
    "app.py" \
    "${LOG_DIR}/kingofyadav.pid" \
    "${LOG_DIR}/kingofyadav.log" \
    "${ROOT_DIR}/Kingofyadav/app.py"

  for _ in $(seq 1 15); do
    [[ -d "${ROOT_DIR}/shared/bus" ]] && break
    sleep 0.5
  done

  check_jarvis_bridge

  start_python_service \
    "Jarvis API" \
    "${ROOT_DIR}" \
    "web/api.py" \
    "${LOG_DIR}/api.pid" \
    "${LOG_DIR}/api.log" \
    "${ROOT_DIR}/web/api.py"

  if ! wait_for_http "Jarvis API" "http://${API_HOST}:${API_PORT}/api/health" 30; then
    warn "Jarvis API did not pass health check. Last log lines:"
    tail -n 40 "${LOG_DIR}/api.log" 2>/dev/null || true
    exit 1
  fi

  start_streamlit_dashboard
  if ! wait_for_http "Dashboard" "http://${DASHBOARD_HOST}:${DASHBOARD_PORT}" 30; then
    warn "Dashboard did not answer HTTP health check. Last log lines:"
    tail -n 40 "${LOG_DIR}/dashboard.log" 2>/dev/null || true
    exit 1
  fi

  if [[ "${START_AUTOMATION}" == "1" ]]; then
    start_python_service \
      "Automation daemon" \
      "${ROOT_DIR}" \
      "automation/app.py" \
      "${LOG_DIR}/automation.pid" \
      "${LOG_DIR}/automation.log" \
      "${ROOT_DIR}/automation/app.py"
  elif pid_file_alive "${LOG_DIR}/automation.pid"; then
    info "Automation daemon already running with PID $(cat "${LOG_DIR}/automation.pid"). Leaving it running."
  else
    info "Automation daemon skipped. Set START_AUTOMATION=1 to start it."
  fi

  info "Work Station is ready"
  printf '\n'
  printf 'API:       http://%s:%s/api/health\n' "${API_HOST}" "${API_PORT}"
  printf 'Dashboard: http://%s:%s\n' "${DASHBOARD_HOST}" "${DASHBOARD_PORT}"
  printf 'Health:    bash scripts/health_workstation.sh\n'
}

main "$@"
