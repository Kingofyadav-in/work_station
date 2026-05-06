#!/usr/bin/env bash
# Deploy nginx configs from repo → /etc/nginx and reload.
# Run with: sudo bash scripts/install-nginx.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AVAIL="/etc/nginx/sites-available"
ENABLED="/etc/nginx/sites-enabled"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "ERROR: run as root: sudo bash $0"
    exit 1
fi

install_conf() {
    local src="$1"   # filename under web/
    local name="$2"  # name under sites-available / sites-enabled
    cp "${REPO_DIR}/web/${src}" "${AVAIL}/${name}"
    echo "  installed  ${AVAIL}/${name}"
    ln -sf "${AVAIL}/${name}" "${ENABLED}/${name}"
    echo "  enabled    ${ENABLED}/${name}"
}

echo "── Jarvis nginx install ──────────────────────────────────────────────"
echo "  repo: ${REPO_DIR}"
echo

echo "── Configs ──"
install_conf "nginx-kingofyadav.in.conf" "kingofyadav.in"
if [[ -f "${REPO_DIR}/web/nginx-jarvis-local.conf" ]]; then
    install_conf "nginx-jarvis-local.conf" "jarvis-local"
else
    echo "  skipped    nginx-jarvis-local.conf (not present)"
fi

# Remove old legacy block (proxied Streamlit directly on port 80 — wrong)
for legacy in jarvis-localhost; do
    if [[ -e "${AVAIL}/${legacy}" ]]; then
        rm -f "${AVAIL}/${legacy}" "${ENABLED}/${legacy}"
        echo "  removed legacy ${legacy}"
    fi
done

echo
echo "── Test & reload ──"
nginx -t
systemctl reload nginx

echo
echo "── Active stack ─────────────────────────────────────────────────────"
echo "  :80    → Cloudflare origin HTTP      (static + /api/ → :5050)"
echo "  :443   → Cloudflare edge HTTPS       (TLS handled by Cloudflare)"
echo "  :3000  → local website preview       (static + /api/ → :5050)"
echo "  :8080  → Jarvis dashboard            (nginx → Streamlit :8501)"
echo "  :8501  → Streamlit app               (127.0.0.1 only)"
echo "  :5050  → Jarvis API                  (127.0.0.1 only)"
echo
echo "── Done ──"
