#!/bin/bash
# alii_launcher.sh — Sources .env and launches alii_core.py
set -euo pipefail

WORKDIR="/home/avalii/moltbot"

# Source environment
if [ -f "$WORKDIR/.env" ]; then
    set -a
    source "$WORKDIR/.env"
    set +a
fi

cd "$WORKDIR"
exec python3 "$WORKDIR/alii_core.py" "$@"
