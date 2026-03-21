#!/bin/bash
# alii_mac.sh — MacBook entry point for the Alii Terminal Hub
#
# INSTALL ON MACBOOK:
#   sudo curl -o /usr/local/bin/alii https://raw.../alii_mac.sh
#   sudo chmod +x /usr/local/bin/alii
#
# OR copy manually:
#   scp avalii@100.75.36.73:/home/avalii/moltbot/scripts/alii_mac.sh /usr/local/bin/alii
#   chmod +x /usr/local/bin/alii
#
# Then just type: alii

set -euo pipefail

PRECISION_IP="100.75.36.73"
PRECISION_USER="avalii"
SESSION="alii"
LAUNCHER="/home/avalii/moltbot/alii_launcher.sh"

# ── Connectivity check ────────────────────────────────────────────────────────
echo "◈ Connecting to Alii..."

if ! ping -c 1 -W 2 "$PRECISION_IP" &>/dev/null 2>&1; then
    echo ""
    echo "  ✗ Precision ($PRECISION_IP) is unreachable."
    echo ""
    echo "  Possible fixes:"
    echo "    1. Start Tailscale: sudo tailscale up"
    echo "    2. Check Precision is powered on"
    echo "    3. Try: ssh ${PRECISION_USER}@${PRECISION_IP}"
    echo ""
    exit 1
fi

echo "  ✓ Precision reachable"

# ── SSH into Precision and attach/create tmux session with TUI ────────────────
# -t  forces TTY allocation (required for TUI)
# tmux new-session -A  attaches to existing session or creates new one
# -s  session name
# The TUI runs on Precision, you see it locally — survives disconnects

exec ssh \
    -t \
    -o "StrictHostKeyChecking=accept-new" \
    -o "ConnectTimeout=8" \
    -o "ServerAliveInterval=30" \
    -o "ServerAliveCountMax=3" \
    "${PRECISION_USER}@${PRECISION_IP}" \
    "tmux new-session -A -s '${SESSION}' 'bash ${LAUNCHER}'"
