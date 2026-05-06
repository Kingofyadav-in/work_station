#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

APPLY=0
REMOVE_VENVS=0

usage() {
  cat <<'EOF'
Usage: bash scripts/clean_runtime.sh [--apply] [--venvs]

Default mode is dry-run.

What it cleans with --apply:
  - Python __pycache__ directories and *.pyc files
  - .pytest_cache
  - dead-letter bus messages, archived to /tmp through bus_health.py
  - stale unclaimed bus responses, archived through MessageBus.reap_stale_responses()

Extra:
  --venvs  also removes .venv and app/.venv. This saves space but requires reinstalling dependencies.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --venvs) REMOVE_VENVS=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

pycache_count="$(find . -path './.git' -prune -o -name '__pycache__' -type d -print | wc -l)"
pyc_count="$(find . -path './.git' -prune -o -name '*.pyc' -type f -print | wc -l)"
pytest_cache_count="$([ -d .pytest_cache ] && echo 1 || echo 0)"

echo "Runtime cleanup summary"
echo "  __pycache__ dirs : ${pycache_count}"
echo "  *.pyc files      : ${pyc_count}"
echo "  .pytest_cache    : ${pytest_cache_count}"
echo "  venv cleanup     : $([[ ${REMOVE_VENVS} -eq 1 ]] && echo enabled || echo disabled)"

if [[ "${APPLY}" -ne 1 ]]; then
  echo
  echo "Dry-run only. Re-run with --apply to clean generated files."
  exit 0
fi

find . -path './.git' -prune -o -name '__pycache__' -type d -exec rm -rf {} +
find . -path './.git' -prune -o -name '*.pyc' -type f -exec rm -f {} +
rm -rf .pytest_cache

python3 shared/bus_health.py --clear-dl
python3 - <<'PY'
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "shared"))
from message_bus import MessageBus

archived = MessageBus(actor="Jarvis").reap_stale_responses()
print(f"Archived stale responses: {archived}")
PY

if [[ "${REMOVE_VENVS}" -eq 1 ]]; then
  rm -rf .venv app/.venv
  echo "Removed virtualenvs. Reinstall dependencies before running services."
fi

find . -path './.git' -prune -o -name '__pycache__' -type d -exec rm -rf {} +
find . -path './.git' -prune -o -name '*.pyc' -type f -exec rm -f {} +

echo "Runtime cleanup complete."
