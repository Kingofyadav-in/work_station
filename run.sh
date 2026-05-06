#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# Prefer the app venv (where all deps live); fall back to a root-level .venv
if [[ -f "app/.venv/bin/activate" ]]; then
    source app/.venv/bin/activate
elif [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
else
    echo "No venv found. Create one with:"
    echo "  cd app && python3 -m venv .venv && pip install -r ../requirements.txt"
    exit 1
fi

echo "Starting services..."
bash scripts/start_all.sh
