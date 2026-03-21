#!/bin/bash
# alii_launcher.sh — Unified Alii entry point
# Usage:
#   alii          → launches the TUI (default)
#   alii --tui    → launches the TUI (explicit)
#   alii --chat   → launches alii_core.py REPL (text-only)
#   alii --help   → show this help

set -euo pipefail

WORKDIR="/home/avalii/moltbot"
VENV_PYTHON="$WORKDIR/venv/bin/python3"

# Use venv python if available, fallback to system python3
PYTHON="${VENV_PYTHON:-python3}"
if [ ! -f "$PYTHON" ]; then PYTHON="python3"; fi

# Source environment
if [ -f "$WORKDIR/.env" ]; then
    set -a
    source "$WORKDIR/.env"
    set +a
fi

cd "$WORKDIR"

# Route based on flag
case "${1:-}" in
    --tui|"")
        exec "$PYTHON" "$WORKDIR/alii_tui.py"
        ;;
    --chat)
        exec "$PYTHON" "$WORKDIR/alii_core.py" "${@:2}"
        ;;
    --help|-h)
        echo "Alii — Sovereign AI Terminal Hub"
        echo ""
        echo "Usage:"
        echo "  alii          Launch the unified TUI (default)"
        echo "  alii --tui    Launch the unified TUI (explicit)"
        echo "  alii --chat   Launch text-only REPL (alii_core.py)"
        echo "  alii --help   Show this help"
        echo ""
        echo "Cluster: precision + xps + nuc + jetson"
        echo "Models:  dolphin-phi fast | qwen2.5 smart | qwen2.5-coder code | llama3 heavy"
        echo "ntfy:    https://ntfy.sh/alii-precision"
        exit 0
        ;;
    *)
        # Pass any other args directly to alii_core
        exec "$PYTHON" "$WORKDIR/alii_core.py" "$@"
        ;;
esac
