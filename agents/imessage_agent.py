#!/usr/bin/env python3
"""
iMessageAgent — Send iMessages from the Linux cluster via SSH to MacBook.
Uses osascript (AppleScript) over SSH to the MacBook on Tailscale.
MacBook Tailscale IP: 100.111.127.89 (pierres-macbook-pro-1)
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

log = logging.getLogger("alii.imessage_agent")

WORKDIR     = Path("/home/avalii/moltbot")
MACBOOK_IP  = os.getenv("MACBOOK_TAILSCALE_IP", "100.111.127.89")
SSH_USER    = os.getenv("MACBOOK_SSH_USER", "avalii")
PHONE       = os.getenv("ALII_PHONE_NUMBER", "")   # set in .env — not stored in code
LOG_FILE    = WORKDIR / "logs" / "overnight.log"


def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] [imessage_agent] {msg}"
    log.info(msg)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(entry + "\n")
    except Exception:
        pass


def send_imessage(phone: str, message: str) -> dict:
    """
    Send an iMessage to `phone` by running osascript on the MacBook via SSH.
    Requires passwordless SSH access (key-based) to MACBOOK_TAILSCALE_IP.
    """
    if not phone:
        _log("ERROR: send_imessage called with empty phone number.")
        return {"ok": False, "error": "phone number not set (export ALII_PHONE_NUMBER=+1...)"}

    # Escape double-quotes in message for AppleScript string safety
    safe_msg = message.replace("\\", "\\\\").replace('"', '\\"')

    applescript = (
        'tell application "Messages"\n'
        '  set targetService to 1st service whose service type = iMessage\n'
        f'  set targetBuddy to buddy "{phone}" of targetService\n'
        f'  send "{safe_msg}" to targetBuddy\n'
        'end tell'
    )

    ssh_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        "-o", "BatchMode=yes",
        f"{SSH_USER}@{MACBOOK_IP}",
        f"osascript -e '{applescript}'"
    ]

    _log(f"Sending iMessage to {phone[:4]}***")
    try:
        result = subprocess.run(
            ssh_cmd, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            _log(f"iMessage sent OK to {phone[:4]}***")
            return {"ok": True, "phone": phone[:4] + "***"}
        else:
            _log(f"iMessage failed: {result.stderr.strip()}")
            return {"ok": False, "error": result.stderr.strip()}
    except subprocess.TimeoutExpired:
        _log("iMessage SSH timed out after 30s")
        return {"ok": False, "error": "SSH timeout"}
    except Exception as exc:
        _log(f"iMessage exception: {exc}")
        return {"ok": False, "error": str(exc)}


def _service_status(name: str) -> str:
    try:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", name],
            capture_output=True, text=True, timeout=5
        )
        return r.stdout.strip()
    except Exception:
        return "unknown"


def _port_open(port: int) -> bool:
    try:
        r = subprocess.run(
            ["ss", "-lntp"],
            capture_output=True, text=True, timeout=5
        )
        return f":{port}" in r.stdout
    except Exception:
        return False


def _watchdog_tail(lines: int = 10) -> str:
    wlog = WORKDIR / "logs" / "watchdog.log"
    if not wlog.exists():
        return "(watchdog.log not found)"
    try:
        text = wlog.read_text().splitlines()
        return "\n".join(text[-lines:])
    except Exception:
        return "(unreadable)"


def _todo_summary() -> str:
    todo_file = WORKDIR / "alfred_todo.json"
    if not todo_file.exists():
        return "No todo file found."
    try:
        tasks = json.loads(todo_file.read_text())
        done  = sum(1 for t in tasks if t.get("done"))
        total = len(tasks)
        pending = [t["task"] for t in tasks if not t.get("done")][:5]
        lines = [f"{done}/{total} tasks done."]
        if pending:
            lines.append("Next up:")
            for p in pending:
                lines.append(f"  • {p[:60]}")
        return "\n".join(lines)
    except Exception as exc:
        return f"(todo parse error: {exc})"


def _overnight_commits() -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(WORKDIR), "log", "--oneline", "--since=12 hours ago"],
            capture_output=True, text=True, timeout=10
        )
        out = r.stdout.strip()
        return out if out else "(no commits in last 12h)"
    except Exception:
        return "(git error)"


def morning_report(phone: str | None = None) -> str:
    """
    Collect system status and send as an iMessage morning briefing.
    phone defaults to ALII_PHONE_NUMBER env var.
    """
    target = phone or PHONE
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    alfred_status  = _service_status("alfred.service")
    ui_status      = _service_status("alii-ui.service")
    port_8001      = "UP" if _port_open(8001) else "DOWN"
    watchdog_tail  = _watchdog_tail(5)
    todo_summary   = _todo_summary()
    commits        = _overnight_commits()

    report = f"""=== Alii Morning Report — {ts} ===
Alfred   : {alfred_status}
Alii UI  : {ui_status} (port 8001: {port_8001})

--- Watchdog (last 5 lines) ---
{watchdog_tail}

--- Todo Status ---
{todo_summary}

--- Overnight Commits ---
{commits}
=== end ==="""

    _log("morning_report generated, sending iMessage...")
    result = send_imessage(target, report)
    _log(f"morning_report send result: {result}")
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1:
        # Allow: python3 imessage_agent.py +15551234567 "custom message"
        ph  = sys.argv[1]
        msg = sys.argv[2] if len(sys.argv) > 2 else None
        if msg:
            print(send_imessage(ph, msg))
        else:
            print(morning_report(ph))
    else:
        print(morning_report())
