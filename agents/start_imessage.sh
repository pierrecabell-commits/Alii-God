#!/bin/bash
# start_imessage.sh — Start the iMessage bridge
set -euo pipefail

WORKDIR="/home/avalii/moltbot"
PID_FILE="$WORKDIR/logs/imessage_bridge.pid"
LOG_FILE="$WORKDIR/logs/imessage_bridge.log"

# Source environment
if [ -f "$WORKDIR/.env" ]; then
    set -a
    source "$WORKDIR/.env"
    set +a
fi

mkdir -p "$WORKDIR/logs" "$WORKDIR/data"

# Kill existing instance if running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[imessage_bridge] Stopping old instance PID=$OLD_PID"
        kill "$OLD_PID"
        sleep 1
    fi
fi

echo "[imessage_bridge] Starting..."
cd "$WORKDIR"
nohup python3 agents/imessage_bridge.py >> "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
echo "[imessage_bridge] Started PID=$NEW_PID, health on :7010/health"
echo "[imessage_bridge] Logs: $LOG_FILE"
