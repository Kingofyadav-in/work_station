#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
ENV_FILE="${ROOT_DIR}/.env"

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

PASS=0
WARN=0
FAIL=0

green=$'\033[32m'
yellow=$'\033[33m'
red=$'\033[31m'
blue=$'\033[34m'
reset=$'\033[0m'

use_color() {
  [[ -t 1 && "${NO_COLOR:-}" == "" ]]
}

paint() {
  local color="$1"
  local text="$2"
  if use_color; then
    printf '%s%s%s' "${color}" "${text}" "${reset}"
  else
    printf '%s' "${text}"
  fi
}

line() {
  printf '%s\n' "----------------------------------------------------------------"
}

record() {
  local status="$1"
  local area="$2"
  local name="$3"
  local detail="${4:-}"
  case "${status}" in
    PASS) PASS=$((PASS + 1)); printf '%s ' "$(paint "${green}" "PASS")" ;;
    WARN) WARN=$((WARN + 1)); printf '%s ' "$(paint "${yellow}" "WARN")" ;;
    FAIL) FAIL=$((FAIL + 1)); printf '%s ' "$(paint "${red}" "FAIL")" ;;
  esac
  printf '[%s] %s' "${area}" "${name}"
  [[ -n "${detail}" ]] && printf ' - %s' "${detail}"
  printf '\n'
}

section() {
  printf '\n%s\n' "$(paint "${blue}" "$1")"
  line
}

pid_alive() {
  local pid="${1:-}"
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

check_pid() {
  local name="$1"
  local pid_file="${LOG_DIR}/${name}.pid"
  if [[ ! -f "${pid_file}" ]]; then
    record WARN process "${name}" "PID file missing"
    return
  fi

  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  if pid_alive "${pid}"; then
    record PASS process "${name}" "PID ${pid}"
  else
    record FAIL process "${name}" "stale PID file ${pid_file}"
  fi
}

check_jarvis_bridge() {
  local python_bin="${ROOT_DIR}/.venv/bin/python"
  if [[ ! -x "${python_bin}" ]]; then
    python_bin="$(command -v python3)"
  fi

  local out
  out="$(
    cd "${ROOT_DIR}/Jarvis" &&
      "${python_bin}" app.py 2>&1
  )"

  if grep -q "response received" <<<"${out}"; then
    record PASS bridge "jarvis" "message bus request/response ok"
  else
    record FAIL bridge "jarvis" "message bus check failed"
    printf '%s\n' "${out}" | tail -n 12 | sed 's/^/      /'
  fi
}

http_code() {
  local code
  code="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 4 "$1" 2>/dev/null || true)"
  if [[ -z "${code}" ]]; then
    printf '000'
  else
    printf '%s' "${code}"
  fi
}

check_http() {
  local name="$1"
  local url="$2"
  local code
  code="$(http_code "${url}")"
  if [[ "${code}" =~ ^[23] ]]; then
    record PASS http "${name}" "${url} -> ${code}"
  elif [[ "${code}" == "401" || "${code}" == "403" ]]; then
    record PASS http "${name}" "${url} protected -> ${code}"
  elif [[ "${code}" == "000" ]]; then
    record FAIL http "${name}" "${url} unreachable"
  else
    record WARN http "${name}" "${url} -> ${code}"
  fi
}

check_file() {
  local path="$1"
  local level="${2:-FAIL}"
  if [[ -e "${ROOT_DIR}/${path}" ]]; then
    record PASS file "${path}" "exists"
  else
    record "${level}" file "${path}" "missing"
  fi
}

check_log_tail() {
  local name="$1"
  local file="${LOG_DIR}/${name}.log"
  if [[ ! -f "${file}" ]]; then
    record WARN logs "${name}" "log missing"
    return
  fi

  local err_count
  err_count="$(tail -n 80 "${file}" 2>/dev/null | grep -Eic 'error|exception|traceback|failed' || true)"
  if [[ "${err_count}" -gt 0 ]]; then
    record WARN logs "${name}" "${err_count} warning/error marker(s) in last 80 lines"
  else
    record PASS logs "${name}" "last 80 lines clean"
  fi
}

check_env() {
  if [[ -f "${ENV_FILE}" ]]; then
    record PASS config ".env" "present and ignored by git"
  else
    record WARN config ".env" "missing; copy .env.example before production"
  fi

  if [[ "${APP_ENV:-}" == "production" && -z "${DASHBOARD_PASSWORD:-}" ]]; then
    record FAIL security "DASHBOARD_PASSWORD" "required when APP_ENV=production"
  elif [[ -n "${DASHBOARD_PASSWORD:-}" ]]; then
    record PASS security "DASHBOARD_PASSWORD" "set"
  else
    record WARN security "DASHBOARD_PASSWORD" "not set"
  fi

  if [[ -n "${JARVIS_API_KEY:-}" ]]; then
    record PASS security "JARVIS_API_KEY" "set"
  else
    record WARN security "JARVIS_API_KEY" "missing; private API commands will be unavailable"
  fi

  if [[ "${ALLOWED_ORIGIN:-}" == "https://kingofyadav.in" || "${ALLOWED_ORIGINS:-}" == *"https://kingofyadav.in"* ]]; then
    record PASS security "kingofyadav.in origin" "allowed"
  else
    record WARN security "kingofyadav.in origin" "not explicitly allowed"
  fi
}

check_git() {
  if [[ ! -d "${ROOT_DIR}/.git" ]]; then
    record WARN git repository "not a git repo"
    return
  fi

  local status
  status="$(git -C "${ROOT_DIR}" status --short 2>/dev/null || true)"
  if [[ -z "${status}" ]]; then
    record PASS git working-tree "clean"
  else
    record WARN git working-tree "has local changes"
    printf '%s\n' "${status}" | sed 's/^/      /'
  fi
}

main() {
  printf 'Work Station Health\n'
  printf 'Root: %s\n' "${ROOT_DIR}"
  printf 'Time: %s\n' "$(date -Iseconds)"

  section "Processes"
  check_pid kingofyadav
  check_pid api
  check_pid dashboard
  [[ -f "${LOG_DIR}/automation.pid" ]] && check_pid automation || record WARN process automation "not configured/running"

  section "Bridge"
  check_jarvis_bridge

  section "HTTP"
  check_http "API health" "http://${API_HOST}:${API_PORT}/api/health"
  check_http "API detail" "http://${API_HOST}:${API_PORT}/api/health/detail"
  check_http "Dashboard" "http://${DASHBOARD_HOST}:${DASHBOARD_PORT}"

  section "Files"
  check_file "Jarvis/app.py"
  check_file "Kingofyadav/app.py"
  check_file "web/api.py"
  check_file "app/app.py"
  check_file "shared/intent_schema.json"
  check_file "requirements.txt" WARN
  check_file ".env.example" WARN

  section "Configuration"
  check_env

  section "Logs"
  check_log_tail kingofyadav
  check_log_tail jarvis
  check_log_tail api
  check_log_tail dashboard
  [[ -f "${LOG_DIR}/automation.log" ]] && check_log_tail automation || true

  section "Git"
  check_git

  section "Summary"
  printf 'PASS=%d WARN=%d FAIL=%d\n' "${PASS}" "${WARN}" "${FAIL}"

  if [[ "${FAIL}" -gt 0 ]]; then
    printf '\nNext: inspect failed logs, or run: bash scripts/start_workstation.sh\n'
    exit 1
  fi
  if [[ "${WARN}" -gt 0 ]]; then
    printf '\nHealth is usable with warnings.\n'
    exit 2
  fi
  printf '\nHealth is clean.\n'
}

main "$@"
