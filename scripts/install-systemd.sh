#!/usr/bin/env bash
# Install Jarvis systemd user services/timers and logrotate config.
# Run once: bash scripts/install-systemd.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"

mkdir -p "${UNIT_DIR}"

# Substitute the repo path so service files work for any user / install location.
install_unit() {
    local src="${SCRIPT_DIR}/$1"
    local dst="${UNIT_DIR}/$1"
    sed "s|/home/kingofyadav/jarvis-platform|${REPO_DIR}|g" "${src}" > "${dst}"
    echo "Installed: ${dst}"
}

# ── Services ───────────────────────────────────────────────────────────────────

for svc in jarvis-kingofyadav jarvis-api jarvis-dashboard; do
    install_unit "${svc}.service"
done

# ── Watchdog timer (every 2 minutes) ──────────────────────────────────────────

for unit in jarvis-watchdog.service jarvis-watchdog.timer; do
    install_unit "${unit}"
done

# ── Doctor timer (daily 04:00) ─────────────────────────────────────────────────

for unit in jarvis-doctor.service jarvis-doctor.timer; do
    install_unit "${unit}"
done

systemctl --user daemon-reload

# ── Enable services ────────────────────────────────────────────────────────────

for svc in jarvis-kingofyadav jarvis-api jarvis-dashboard; do
    systemctl --user enable "${svc}.service"
    echo "Enabled: ${svc}"
done

for timer in jarvis-watchdog.timer jarvis-doctor.timer; do
    systemctl --user enable "${timer}"
    echo "Enabled: ${timer}"
done

# ── Logrotate ──────────────────────────────────────────────────────────────────

LOGROTATE_CONF="/etc/logrotate.d/jarvis"
if command -v logrotate >/dev/null 2>&1; then
    if [ -w /etc/logrotate.d ] || sudo -n true >/dev/null 2>&1; then
        sed "s|/home/kingofyadav/jarvis-platform|${REPO_DIR}|g" \
            "${SCRIPT_DIR}/jarvis-logrotate.conf" | sudo tee "${LOGROTATE_CONF}" > /dev/null
        echo "Installed logrotate config: ${LOGROTATE_CONF}"
    else
        echo "WARN: cannot write to /etc/logrotate.d — install manually:"
        echo "  sudo cp ${SCRIPT_DIR}/jarvis-logrotate.conf ${LOGROTATE_CONF}"
    fi
else
    echo "WARN: logrotate not found — skipping log rotation setup"
fi

# ── Summary ────────────────────────────────────────────────────────────────────

echo ""
echo "Start all services now with:"
echo "  systemctl --user start jarvis-kingofyadav jarvis-api jarvis-dashboard"
echo "  systemctl --user start jarvis-watchdog.timer jarvis-doctor.timer"
echo ""
echo "Check status:"
echo "  systemctl --user status jarvis-kingofyadav jarvis-api jarvis-dashboard"
echo "  systemctl --user list-timers"
echo ""
echo "Auto-start on login (run once per user session):"
echo "  loginctl enable-linger ${USER}"
echo ""
echo "Deploy nginx configs (run separately as root):"
echo "  sudo bash scripts/install-nginx.sh"
