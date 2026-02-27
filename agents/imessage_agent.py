#!/usr/bin/env python3
"""
iMessageAgent — Two-way iMessage bridge between Pierre's iPhone and Alii.

Architecture:
  Precision  --SSH-->  MacBook (Messages.app)  <-->  iPhone (iMessage)

  SEND:  ssh MACBOOK osascript -e 'tell app Messages to send MSG to buddy PHONE'
  READ:  ssh MACBOOK osascript -e 'tell app Messages ...'
  POLL:  Every 15s — check for new messages, route as commands, reply.

SSH SETUP (one-time on MacBook):
  1. System Settings > General > Sharing > Remote Login → ENABLE
  2. In Terminal on MacBook:
       mkdir -p ~/.ssh
       cat >> ~/.ssh/authorized_keys << 'KEY'
       ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCxoBP0QbY+EW+H0fFHvdm3FnRlBOgUuM0s69j99tB2TWAAWghnRTAVp4dj4Ep2WA84PUA8WlI83lhArqJicvBamsQfKf1oYUxljvGMUaiMTOD+WO0FrHRK9t7V2VIB9v0n7fnXH++Nw29OhQ004i8HZuTWk0r2SnkxQvp7/zUj/r1BoSg8OcsEc2yPLugheKAo5s1KW8+N2X+0gxD12hIZzPmKCy1SoFy9AMkv22JzubzEZY18VHTUEwcrzULoPTabaA5OdDeLpE/B3y8yO6pW8JFb1q58ertBhlgrJFnU3PQXRJWNZoCSZxyujcn4fRfS8dGTs+oL0Rfc7uY8j4Ok5YOqKpaLulJK6F8zXZ31c2GiNw8q/0HLjB+n0C94sEMRtrNiOcZMMJajEy+ulNeO5H6jLuhLGws68fiztome8B+28YNfF+qhJmWZ2MOCztIJgQNL3E3gmESuBn8CM3SRvzBRsot4TukXE7gsozgNVS2HrtjQTv8L7O1sEVlU/VHTb+oW37OMrsKoxGwyCpFt8Sj1OuOXrX8ufWE9KRpSQmbxGAOA5mMFYsXjXeKjWRW26wrGgqtEXqCcjM8BsAUL3X7BpiAMVwZRMoBR6ll66ibnSrVx3EfXK4pExR9q1KhuUwpzC0v+F4b1Rv4B1aK+cCnNCrLDoVRkofGITtCDNw== avalii@aliirecision
       KEY
       chmod 600 ~/.ssh/authorized_keys
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger("alii.imessage")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [imessage] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/home/avalii/moltbot/logs/imessage_agent.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

WORKDIR      = Path("/home/avalii/moltbot")
PENDING_FILE = WORKDIR / "pending_messages.json"
STATE_FILE   = WORKDIR / "memory" / "imessage_state.json"
TODO_FILE    = WORKDIR / "alfred_todo.json"

# Try local IP first (faster), fall back to Tailscale
MACBOOK_LOCAL     = os.getenv("MACBOOK_LOCAL_IP",    "192.168.1.98")
MACBOOK_TAILSCALE = os.getenv("MACBOOK_TAILSCALE_IP","100.111.127.89")
MACBOOK_USER      = os.getenv("MACBOOK_SSH_USER",    "pierre")
MY_PHONE          = os.getenv("ALII_PHONE_NUMBER",   "")   # Pierre's number — set in .env

POLL_INTERVAL = 15   # seconds between message checks

SSH_OPTS = [
    "-o", "StrictHostKeyChecking=no",
    "-o", "ConnectTimeout=5",
    "-o", "BatchMode=yes",
    "-o", "PasswordAuthentication=no",
]

# Whitelisted commands for 'run:' routing
SAFE_COMMANDS = {
    "status":        ["systemctl", "--user", "status", "alfred.service", "--no-pager"],
    "logs":          ["tail", "-50", str(WORKDIR / "logs" / "overnight.log")],
    "watchdog":      ["tail", "-20", str(WORKDIR / "logs" / "watchdog.log")],
    "git":           ["git", "-C", str(WORKDIR), "log", "--oneline", "-10"],
    "alfred logs":   ["tail", "-30", str(WORKDIR / "logs" / "alfred.log")],
    "todo":          None,   # handled specially
    "morning":       None,   # handled specially
}


# ── SSH helpers ────────────────────────────────────────────────────────────────

def _macbook_ip() -> str:
    """Return whichever MacBook IP responds first."""
    for ip in [MACBOOK_LOCAL, MACBOOK_TAILSCALE]:
        try:
            r = subprocess.run(
                ["ssh"] + SSH_OPTS + [f"{MACBOOK_USER}@{ip}", "echo pong"],
                capture_output=True, text=True, timeout=6
            )
            if r.returncode == 0:
                return ip
        except Exception:
            pass
    return MACBOOK_TAILSCALE   # default even if unreachable


def _ssh(ip: str, cmd: str, timeout: int = 15) -> tuple[int, str]:
    """Run a command on the MacBook via SSH. Returns (returncode, output)."""
    result = subprocess.run(
        ["ssh"] + SSH_OPTS + [f"{MACBOOK_USER}@{ip}", cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def ssh_available() -> bool:
    try:
        rc, _ = _ssh(_macbook_ip(), "echo pong", timeout=6)
        return rc == 0
    except Exception:
        return False


# ── Send ──────────────────────────────────────────────────────────────────────

def send_imessage(to: str, msg: str) -> dict:
    """
    Send an iMessage to phone number or Apple ID via MacBook Messages.app.
    Falls back to pending_messages.json queue if SSH unavailable.
    """
    if not to:
        log.error("send_imessage: 'to' is empty")
        return {"ok": False, "error": "recipient empty"}

    # Escape for AppleScript
    safe = msg.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    applescript = (
        f'tell application "Messages"\\n'
        f'  set s to first service whose service type is iMessage\\n'
        f'  set b to buddy "{to}" of s\\n'
        f'  send "{safe}" to b\\n'
        f'end tell'
    )

    ip = _macbook_ip()
    log.info("Sending iMessage to %s via %s", to[:6] + "***", ip)
    try:
        rc, out = _ssh(ip, f"osascript -e '{applescript}'")
        if rc == 0:
            log.info("iMessage sent OK")
            return {"ok": True, "to": to[:6] + "***", "via": ip}
        else:
            log.warning("osascript failed: %s", out)
            _queue(to, msg)
            return {"ok": False, "error": out, "queued": True}
    except subprocess.TimeoutExpired:
        log.warning("SSH timeout — queuing message")
        _queue(to, msg)
        return {"ok": False, "error": "SSH timeout", "queued": True}
    except Exception as exc:
        log.warning("SSH error: %s — queuing", exc)
        _queue(to, msg)
        return {"ok": False, "error": str(exc), "queued": True}


def _queue(to: str, msg: str):
    pending = []
    if PENDING_FILE.exists():
        try:
            pending = json.loads(PENDING_FILE.read_text())
        except Exception:
            pass
    pending.append({"to": to, "msg": msg, "queued_at": datetime.now().isoformat()})
    PENDING_FILE.write_text(json.dumps(pending, indent=2))


def retry_pending() -> int:
    if not PENDING_FILE.exists():
        return 0
    try:
        pending = json.loads(PENDING_FILE.read_text())
    except Exception:
        return 0
    unsent = []
    sent = 0
    for item in pending:
        r = send_imessage(item["to"], item["msg"])
        if r.get("ok"):
            sent += 1
        else:
            unsent.append(item)
    PENDING_FILE.write_text(json.dumps(unsent, indent=2))
    return sent


# ── Read ──────────────────────────────────────────────────────────────────────

def read_recent_messages(chat_index: int = 1, count: int = 5) -> list[dict]:
    """
    Read the most recent messages from the first iMessage chat on the MacBook.
    Returns list of {sender, text, date} dicts.
    """
    # AppleScript to read last N messages from first chat
    applescript = (
        f'set output to ""\\n'
        f'tell application "Messages"\\n'
        f'  set theChat to item 1 of (chats whose service type is iMessage)\\n'
        f'  set msgs to messages of theChat\\n'
        f'  set startIdx to (count of msgs) - {count} + 1\\n'
        f'  if startIdx < 1 then set startIdx to 1\\n'
        f'  repeat with i from startIdx to count of msgs\\n'
        f'    set m to item i of msgs\\n'
        f'    set output to output & (date of m as string) & "|" & (sender of m as string) & "|" & (content of m) & "\\n"\\n'
        f'  end repeat\\n'
        f'end tell\\n'
        f'return output'
    )
    ip = _macbook_ip()
    try:
        rc, out = _ssh(ip, f"osascript -e '{applescript}'", timeout=10)
        if rc != 0 or not out.strip():
            return []
        messages = []
        for line in out.strip().splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3:
                messages.append({"date": parts[0], "sender": parts[1], "text": parts[2]})
        return messages
    except Exception as exc:
        log.debug("read_recent_messages error: %s", exc)
        return []


# ── Command routing ───────────────────────────────────────────────────────────

def _system_status_text() -> str:
    def svc(name):
        try:
            r = subprocess.run(["systemctl", "--user", "is-active", name],
                               capture_output=True, text=True, timeout=5)
            return r.stdout.strip()
        except Exception:
            return "?"
    def port(p):
        try:
            r = subprocess.run(["ss", "-lntp"], capture_output=True, text=True, timeout=5)
            return "UP" if f":{p}" in r.stdout else "DOWN"
        except Exception:
            return "?"
    try:
        tasks   = json.loads((WORKDIR / "alfred_todo.json").read_text())
        pending = sum(1 for t in tasks if not t.get("done"))
    except Exception:
        pending = -1
    return (
        f"Alfred:{svc('alfred.service')} "
        f"UI:{svc('alii-ui.service')}({port(8001)}) "
        f"Todo:{pending} pending "
        f"Time:{datetime.now().strftime('%H:%M')}"
    )


def _add_todo(task: str, priority: str = "normal"):
    try:
        tasks = json.loads(TODO_FILE.read_text()) if TODO_FILE.exists() else []
        tasks.insert(0, {
            "task":       task,
            "created_at": datetime.now().isoformat(),
            "done":       False,
            "priority":   priority,
            "source":     "iMessage",
        })
        TODO_FILE.write_text(json.dumps(tasks, indent=2))
        return True
    except Exception as exc:
        log.error("_add_todo error: %s", exc)
        return False


def route_command(text: str, sender: str) -> str:
    """Parse an incoming message and return a reply string."""
    text = text.strip()
    low  = text.lower()

    if low in ("status", "s", "?"):
        return "STATUS: " + _system_status_text()

    if low.startswith("task:"):
        task = text[5:].strip()
        if _add_todo(task, priority="high"):
            return f"QUEUED: '{task[:60]}' added as high priority task."
        return "ERROR: Could not add task."

    if low.startswith("run:"):
        cmd_key = text[4:].strip().lower()
        if cmd_key == "todo":
            try:
                tasks   = json.loads(TODO_FILE.read_text())
                pending = [t["task"] for t in tasks if not t.get("done")][:5]
                return "TODO:\n" + "\n".join(f"• {p[:60]}" for p in pending)
            except Exception:
                return "Could not read todo list."
        if cmd_key in SAFE_COMMANDS and SAFE_COMMANDS[cmd_key]:
            try:
                r = subprocess.run(SAFE_COMMANDS[cmd_key], capture_output=True,
                                   text=True, timeout=10)
                return (r.stdout + r.stderr).strip()[-300:] or "(no output)"
            except Exception as exc:
                return f"ERROR: {exc}"
        return f"Unknown command '{cmd_key}'. Safe commands: {', '.join(SAFE_COMMANDS)}"

    if low in ("morning", "report", "briefing"):
        return _system_status_text()

    if low in ("help", "commands"):
        return (
            "Alii commands:\n"
            "status — system health\n"
            "task: <text> — queue a task\n"
            "run: logs|watchdog|git|status|todo\n"
            "morning — quick briefing\n"
            "help — this list"
        )

    # Anything else → queue as task
    if len(text) > 3:
        _add_todo(text, priority="normal")
        return f"GOT IT: Queued as task → '{text[:60]}'"

    return "?"


# ── Polling loop ──────────────────────────────────────────────────────────────

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_seen_date": "", "processed_texts": []}


def _save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def poll_and_respond(reply_to: str | None = None):
    """
    Poll iMessages every POLL_INTERVAL seconds.
    When a new message arrives from Pierre, route it and reply.
    reply_to: phone number or Apple ID to reply to (defaults to MY_PHONE)
    """
    target = reply_to or MY_PHONE
    state  = _load_state()

    log.info("iMessage poll loop starting. reply_to=%s interval=%ds",
             target[:6] + "***" if target else "(no phone set)", POLL_INTERVAL)

    if not ssh_available():
        log.warning("MacBook SSH not available. Add public key — see docstring.")
        log.warning("Public key: cat ~/.ssh/id_rsa.pub")
        _ntfy("iMessage bridge waiting for MacBook SSH auth. "
              "Run 'cat ~/.ssh/id_rsa.pub' on Precision and add to MacBook authorized_keys.")

    while True:
        try:
            messages = read_recent_messages(count=5)
            for m in messages:
                text = m.get("text", "").strip()
                date = m.get("date", "")
                sender = m.get("sender", "")

                # Skip already-processed or empty
                if not text or text in state.get("processed_texts", []):
                    continue

                # Skip messages sent by this system
                if "ALII" in text.upper() or "STATUS:" in text.upper():
                    continue

                log.info("New message from %s: %s", sender[:20], text[:60])
                reply = route_command(text, sender)
                log.info("Reply: %s", reply[:80])

                if target:
                    send_imessage(target, reply)
                else:
                    log.warning("No ALII_PHONE_NUMBER set — reply not sent: %s", reply)

                # Track processed
                processed = state.get("processed_texts", [])
                processed.append(text)
                state["processed_texts"] = processed[-50:]   # keep last 50
                state["last_seen_date"]  = date
                _save_state(state)

            # Retry any queued messages
            sent = retry_pending()
            if sent:
                log.info("Sent %d queued messages.", sent)

        except Exception as exc:
            log.debug("Poll cycle error (non-fatal): %s", exc)

        time.sleep(POLL_INTERVAL)


def _ntfy(msg: str, title: str = "Alii iMessage"):
    try:
        subprocess.run(
            ["curl", "-s", "-X", "POST",
             "-H", f"Title: {title}",
             "-d", msg,
             "ntfy.sh/alii-precision"],
            capture_output=True, timeout=5
        )
    except Exception:
        pass


# ── System status for morning report ─────────────────────────────────────────

def system_status() -> dict:
    def svc(name):
        try:
            r = subprocess.run(["systemctl", "--user", "is-active", name],
                               capture_output=True, text=True, timeout=5)
            return r.stdout.strip()
        except Exception:
            return "?"

    def port_up(p):
        try:
            r = subprocess.run(["ss", "-lntp"], capture_output=True, text=True, timeout=5)
            return "UP" if f":{p}" in r.stdout else "DOWN"
        except Exception:
            return "?"

    def watchdog_last():
        wlog = WORKDIR / "logs" / "watchdog.log"
        try:
            return wlog.read_text().splitlines()[-1] if wlog.exists() else "(none)"
        except Exception:
            return "(unreadable)"

    def todo_pending():
        try:
            tasks = json.loads(TODO_FILE.read_text())
            return sum(1 for t in tasks if not t.get("done"))
        except Exception:
            return -1

    def commits_12h():
        try:
            r = subprocess.run(
                ["git", "-C", str(WORKDIR), "log", "--oneline", "--since=12 hours ago"],
                capture_output=True, text=True, timeout=5
            )
            lines = r.stdout.strip().splitlines()
            return len(lines), lines[:3]
        except Exception:
            return 0, []

    n, recent = commits_12h()
    return {
        "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        "alfred":        svc("alfred.service"),
        "alii_ui":       svc("alii-ui.service"),
        "port_8001":     port_up(8001),
        "watchdog_last": watchdog_last()[-80:],
        "todo_pending":  todo_pending(),
        "commits_12h":   n,
        "recent_commits":recent,
        "ssh_available": ssh_available(),
    }


def morning_report(phone: str | None = None) -> str:
    target = phone or MY_PHONE
    s = system_status()
    report = (
        f"=== Alii {s['timestamp']} ===\n"
        f"Alfred:{s['alfred']} UI:{s['alii_ui']}({s['port_8001']})\n"
        f"Watchdog:{s['watchdog_last'][-60:]}\n"
        f"Todo:{s['todo_pending']} pending | Commits:{s['commits_12h']}\n"
        f"SSH bridge:{'READY' if s['ssh_available'] else 'WAITING FOR KEY'}\n"
        + ("".join(f"  {c}\n" for c in s["recent_commits"]))
        + "=== end ==="
    )
    if target:
        send_imessage(target, report)
    return report


# ── Register as systemd service ───────────────────────────────────────────────

def register_as_service():
    service = """[Unit]
Description=Alii iMessage Two-Way Bridge
After=network.target alfred.service

[Service]
ExecStart=/usr/bin/python3 /home/avalii/moltbot/agents/imessage_agent.py --poll
WorkingDirectory=/home/avalii/moltbot
Restart=always
RestartSec=15
EnvironmentFile=-/home/avalii/moltbot/.env
StandardOutput=append:/home/avalii/moltbot/logs/imessage_agent.log
StandardError=append:/home/avalii/moltbot/logs/imessage_agent.log

[Install]
WantedBy=default.target
"""
    path = Path.home() / ".config/systemd/user/imessage-agent.service"
    path.write_text(service)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "imessage-agent.service"], check=False)
    log.info("Service registered: %s", path)
    return str(path)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--poll" in sys.argv:
        poll_and_respond()
    elif "--status" in sys.argv:
        print(json.dumps(system_status(), indent=2))
    elif "--morning" in sys.argv:
        phone = sys.argv[sys.argv.index("--morning") + 1] if len(sys.argv) > 2 else None
        print(morning_report(phone))
    elif "--register" in sys.argv:
        print(register_as_service())
    elif "--retry" in sys.argv:
        print(f"Sent {retry_pending()} queued messages")
    elif len(sys.argv) >= 3 and (sys.argv[1].startswith("+") or "@" in sys.argv[1]):
        result = send_imessage(sys.argv[1], " ".join(sys.argv[2:]))
        print(result)
    else:
        print("Usage:")
        print("  --poll              start polling loop")
        print("  --status            print system status JSON")
        print("  --morning [phone]   send morning report")
        print("  --register          install systemd service")
        print("  --retry             retry pending messages")
        print("  +1... 'message'     send a message")
