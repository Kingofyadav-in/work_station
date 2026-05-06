#!/usr/bin/env bash
# One-command deploy: pull latest code, sync deps, restart services, run doctor.
# Usage: bash scripts/deploy.sh [--skip-pull] [--skip-doctor]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="${ROOT_DIR}/scripts"
LOG_DIR="${ROOT_DIR}/logs"
DEPLOY_LOG="${LOG_DIR}/deploy.log"

SKIP_PULL=0
SKIP_DOCTOR=0
for arg in "$@"; do
    case "$arg" in
        --skip-pull)   SKIP_PULL=1 ;;
        --skip-doctor) SKIP_DOCTOR=1 ;;
    esac
done

mkdir -p "${LOG_DIR}"

TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
log() { echo "[deploy $TS] $*" | tee -a "${DEPLOY_LOG}"; }

log "=== Deploy started ==="
log "root=${ROOT_DIR}"

# ── 1. Git pull ────────────────────────────────────────────────────────────────

if [ "${SKIP_PULL}" -eq 0 ]; then
    log "Pulling latest code..."
    cd "${ROOT_DIR}"
    git fetch origin
    BRANCH="$(git rev-parse --abbrev-ref HEAD)"
    BEFORE="$(git rev-parse HEAD)"
    git pull --ff-only origin "${BRANCH}"
    AFTER="$(git rev-parse HEAD)"
    if [ "${BEFORE}" = "${AFTER}" ]; then
        log "Already up to date (${BEFORE:0:8})"
    else
        log "Updated ${BEFORE:0:8} → ${AFTER:0:8}"
        git log --oneline "${BEFORE}..${AFTER}" | tee -a "${DEPLOY_LOG}"
    fi
else
    log "Skipping git pull (--skip-pull)"
fi

# ── 2. Pip sync ────────────────────────────────────────────────────────────────

PYTHON="${ROOT_DIR}/.venv/bin/python"
if [ ! -x "${PYTHON}" ]; then
    PYTHON="$(command -v python3)"
fi

PIP="${ROOT_DIR}/.venv/bin/pip"
if [ ! -x "${PIP}" ]; then
    PIP="$(command -v pip3)"
fi

if [ -f "${ROOT_DIR}/requirements.lock.txt" ]; then
    log "Syncing dependencies from requirements.lock.txt..."
    "${PIP}" install --quiet -r "${ROOT_DIR}/requirements.lock.txt" 2>&1 | tee -a "${DEPLOY_LOG}"
elif [ -f "${ROOT_DIR}/requirements.txt" ]; then
    log "Syncing dependencies from requirements.txt..."
    "${PIP}" install --quiet -r "${ROOT_DIR}/requirements.txt" 2>&1 | tee -a "${DEPLOY_LOG}"
else
    log "WARN: no requirements file found — skipping pip sync"
fi

# ── 3. Restart services ────────────────────────────────────────────────────────

log "Restarting services..."

_restart_service() {
    local name="$1"
    if systemctl --user is-active --quiet "${name}" 2>/dev/null; then
        systemctl --user restart "${name}"
        log "Restarted: ${name}"
    elif systemctl --user is-enabled --quiet "${name}" 2>/dev/null; then
        systemctl --user start "${name}"
        log "Started: ${name}"
    else
        log "WARN: ${name} not managed by systemd — restarting via script"
        case "${name}" in
            jarvis-api)         bash "${SCRIPTS_DIR}/start_api.sh" ;;
            jarvis-dashboard)   bash "${SCRIPTS_DIR}/start_dashboard.sh" ;;
            jarvis-kingofyadav) nohup "${PYTHON}" "${ROOT_DIR}/Kingofyadav/app.py" \
                                  >> "${LOG_DIR}/kingofyadav.log" 2>&1 & ;;
        esac
    fi
}

_restart_service "jarvis-kingofyadav"
sleep 1
_restart_service "jarvis-api"
sleep 1
_restart_service "jarvis-dashboard"

# ── 4. Wait for API to be reachable ───────────────────────────────────────────

API_PORT="${API_PORT:-5050}"
log "Waiting for API on :${API_PORT}..."
MAX_WAIT=20
elapsed=0
until curl -fsS --max-time 2 "http://127.0.0.1:${API_PORT}/api/health" >/dev/null 2>&1; do
    sleep 1
    elapsed=$((elapsed + 1))
    if [ "${elapsed}" -ge "${MAX_WAIT}" ]; then
        log "WARN: API not reachable after ${MAX_WAIT}s — check ${LOG_DIR}/api.log"
        break
    fi
done
[ "${elapsed}" -lt "${MAX_WAIT}" ] && log "API reachable after ${elapsed}s"

# ── 5. Doctor ─────────────────────────────────────────────────────────────────

if [ "${SKIP_DOCTOR}" -eq 0 ]; then
    log "Running doctor..."
    if bash "${SCRIPTS_DIR}/doctor.sh" >> "${DEPLOY_LOG}" 2>&1; then
        log "Doctor: PASS or WARNING (see logs/doctor/latest.json)"
    else
        log "Doctor: FAIL — review logs/doctor/latest.json before proceeding"
    fi
else
    log "Skipping doctor (--skip-doctor)"
fi

# ── 6. Summary ────────────────────────────────────────────────────────────────

log "=== Deploy complete ==="
echo ""
echo "Deploy log: ${DEPLOY_LOG}"
echo "Doctor report: ${ROOT_DIR}/logs/doctor/latest.json"
