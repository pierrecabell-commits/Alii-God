#!/bin/bash
# Alii UI Watchdog — flock-based single-instance, self-healing via Claude
set -uo pipefail

LOCK="/tmp/alii-watchdog.lock"
LOG="/home/avalii/moltbot/logs/watchdog.log"
SERVICE="alii-ui.service"
PORT=8001
WORKDIR="/home/avalii/moltbot"

# Ensure log dir exists
mkdir -p "$(dirname "$LOG")"

# Single-instance lock — exit silently if another instance is running
exec 9>"$LOCK"
flock -n 9 || exit 0

stamp() { date +"%Y-%m-%d %H:%M:%S"; }
log()   { echo "[$(stamp)] $*" >> "$LOG"; }
is_up() { ss -lntp 2>/dev/null | grep -q ":${PORT}"; }

if is_up; then
    exit 0
fi

log "WARN: Port $PORT not listening. Attempting service restart..."
systemctl --user reset-failed "$SERVICE" 2>/dev/null || true
systemctl --user restart "$SERVICE" 2>/dev/null || true

sleep 8

if is_up; then
    log "OK: Service recovered — port $PORT is now listening."
    exit 0
fi

log "ERROR: Still down after restart. Dumping logs and invoking Claude..."

# Dump recent journal to log for context
{
    echo "=== journalctl dump: $(stamp) ==="
    journalctl --user -u "$SERVICE" -n 100 --no-pager 2>&1
    echo "=== py_compile check ==="
    cd "$WORKDIR"
    python3 -m py_compile alii_ui.py 2>&1 && echo "alii_ui.py: OK" || echo "alii_ui.py: SYNTAX ERROR"
    python3 -m py_compile alii_model_router.py 2>&1 && echo "alii_model_router.py: OK" || echo "alii_model_router.py: SYNTAX ERROR"
    echo "=== end ==="
} >> "$LOG" 2>&1

PROMPT="Alii UI is down on port $PORT. Steps: (1) run: journalctl --user -u alii-ui.service -n 100 --no-pager to see crash logs; (2) run: python3 -m py_compile /home/avalii/moltbot/alii_ui.py /home/avalii/moltbot/alii_model_router.py to check syntax; (3) fix any errors found in those files; (4) run: systemctl --user restart alii-ui.service; (5) confirm: ss -lntp | grep $PORT. Working directory: $WORKDIR"

cd "$WORKDIR"
# Try forced restart via systemctl --user, then kill+let-systemd-restart as fallback
systemctl --user reset-failed "$SERVICE" 2>/dev/null || true
systemctl --user restart "$SERVICE" 2>/dev/null && log "INFO: Forced restart issued via systemctl" || \
    { pkill -f "chainlit run alii_ui.py" 2>/dev/null; log "INFO: Killed chainlit process — systemd will restart it"; }

sleep 10
if is_up; then
    log "OK: Recovery succeeded — port $PORT is live."
else
    log "CRIT: Port $PORT still down after recovery attempt. Manual action required."
    # Send ntfy alert
    curl -s -d "Alii UI (port $PORT) is down and could not recover automatically. Manual intervention needed on aliirecision." \
        https://ntfy.sh/alii-precision >> "$LOG" 2>&1 || true
fi
