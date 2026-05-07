#!/usr/bin/env bash
# Railway entry point — starts Kingofyadav listener + Jarvis API.
# Mount a Railway volume at /app/persist to keep state across deploys.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Persistent volume ──────────────────────────────────────────────────────────
# Set mount path in Railway dashboard → Add Volume → Mount Path: /app/persist
PERSIST="${RAILWAY_VOLUME_MOUNT_PATH:-/app/persist}"

mkdir -p \
  "${PERSIST}/logs" \
  "${PERSIST}/Kingofyadav" \
  "${PERSIST}/Jarvis" \
  "${PERSIST}/shared/events" \
  "${PERSIST}/shared/bus/requests" \
  "${PERSIST}/shared/bus/responses" \
  "${PERSIST}/shared/bus/processed" \
  "${PERSIST}/shared/bus/deadletter"

# Link runtime directories to the volume so state survives redeploys
link_dir() {
  local src="$1" dst="$2"
  [[ -L "${dst}" ]] && return
  rm -rf "${dst}"
  ln -sfn "${src}" "${dst}"
}

link_dir "${PERSIST}/logs"               "${ROOT_DIR}/logs"
link_dir "${PERSIST}/shared/events"      "${ROOT_DIR}/shared/events"
link_dir "${PERSIST}/shared/bus"         "${ROOT_DIR}/shared/bus"

# state.json — HI truth (initialize on first run)
if [[ ! -f "${PERSIST}/Kingofyadav/state.json" ]]; then
  echo '{"profile":{},"preferences":{},"memory":[],"workflow":{"tasks":[]}}' \
    > "${PERSIST}/Kingofyadav/state.json"
fi
[[ -L "${ROOT_DIR}/Kingofyadav/state.json" ]] || \
  ln -sfn "${PERSIST}/Kingofyadav/state.json" "${ROOT_DIR}/Kingofyadav/state.json"

# memory.db — SQLite memory index (rebuilt from state.json if missing, that is fine)
[[ -L "${ROOT_DIR}/Kingofyadav/memory.db" ]] || \
  ln -sfn "${PERSIST}/Kingofyadav/memory.db" "${ROOT_DIR}/Kingofyadav/memory.db"

# profiles.json — AI session + profile
[[ -L "${ROOT_DIR}/Jarvis/profiles.json" ]] || \
  ln -sfn "${PERSIST}/Jarvis/profiles.json" "${ROOT_DIR}/Jarvis/profiles.json"

# ── Port ───────────────────────────────────────────────────────────────────────
# Railway injects PORT — Jarvis API reads API_PORT
export API_PORT="${PORT:-5050}"
export API_HOST="0.0.0.0"

# ── Kingofyadav listener (background) ─────────────────────────────────────────
echo "[Railway] Starting Kingofyadav listener..."
python3 "${ROOT_DIR}/Kingofyadav/app.py" \
  >> "${PERSIST}/logs/kingofyadav.log" 2>&1 &

echo -n "[Railway] Waiting for listener"
for i in $(seq 1 30); do
  [[ -f "${PERSIST}/logs/kingofyadav.pid" ]] \
    && { echo " ready (PID $(cat "${PERSIST}/logs/kingofyadav.pid"))"; break; }
  echo -n "."
  sleep 0.5
done
echo

# ── Jarvis API (foreground — Railway monitors this process) ────────────────────
echo "[Railway] Starting Jarvis API on 0.0.0.0:${API_PORT}..."
exec python3 "${ROOT_DIR}/web/api.py"
