#!/usr/bin/env python3
"""
NtfyCommandListener — Two-way bridge between Pierre's iPhone and Alii via ntfy.sh.

SEND commands to:  ntfy.sh/alii-precision-commands
RECEIVE replies at: ntfy.sh/alii-precision

Commands:
  status           → full system status report
  task: <text>     → add high-priority task to alfred_todo.json
  run: <key>       → run whitelisted command (logs, watchdog, git, todo, alfred)
  anything else    → queued as natural language task
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ntfy] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/home/avalii/moltbot/logs/ntfy_listener.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("alii.ntfy")

WORKDIR        = Path("/home/avalii/moltbot")
TODO_FILE      = WORKDIR / "alfred_todo.json"
COMMANDS_TOPIC = "alii-precision-commands"
REPLY_TOPIC    = "alii-precision"
POLL_INTERVAL  = 10   # seconds
NTFY_BASE      = "https://ntfy.sh"

# Whitelisted run: commands
SAFE_RUNS = {
    "logs":     ["tail", "-40", str(WORKDIR / "logs" / "overnight.log")],
    "alfred":   ["tail", "-40", str(WORKDIR / "logs" / "alfred.log")],
    "watchdog": ["tail", "-20", str(WORKDIR / "logs" / "watchdog.log")],
    "git":      ["git", "-C", str(WORKDIR), "log", "--oneline", "-10"],
    "status":   ["systemctl", "--user", "status", "alfred.service", "--no-pager", "-l"],
    "services": ["systemctl", "--user", "list-units", "--type=service", "--state=running", "--no-pager"],
    "memory":   ["tail", "-30", str(WORKDIR / "logs" / "morning_briefing.log")],
}


def _ntfy_send(msg: str, title: str = "Alii", priority: str = "default"):
    """POST a message to the reply topic."""
    try:
        subprocess.run(
            ["curl", "-s", "-X", "POST",
             "-H", f"Title: {title}",
             "-H", f"Priority: {priority}",
             "-d", msg[:4096],
             f"{NTFY_BASE}/{REPLY_TOPIC}"],
            capture_output=True, timeout=8
        )
    except Exception as exc:
        log.warning("ntfy send error: %s", exc)


def _add_todo(task: str, priority: str = "normal", source: str = "ntfy"):
    try:
        tasks = json.loads(TODO_FILE.read_text()) if TODO_FILE.exists() else []
        tasks.insert(0, {
            "task":       task,
            "created_at": datetime.now().isoformat(),
            "done":       False,
            "priority":   priority,
            "source":     source,
        })
        TODO_FILE.write_text(json.dumps(tasks, indent=2))
        return True
    except Exception as exc:
        log.error("_add_todo: %s", exc)
        return False


def _system_status() -> str:
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
        tasks   = json.loads(TODO_FILE.read_text())
        pending = sum(1 for t in tasks if not t.get("done"))
    except Exception:
        pending = -1

    try:
        r = subprocess.run(
            ["git", "-C", str(WORKDIR), "log", "--oneline", "-3"],
            capture_output=True, text=True, timeout=5
        )
        commits = r.stdout.strip()
    except Exception:
        commits = "?"

    return (
        f"=== Alii Status {datetime.now().strftime('%H:%M')} ===\n"
        f"Alfred : {svc('alfred.service')}\n"
        f"UI     : {svc('alii-ui.service')} (port 8001: {port(8001)})\n"
        f"Ntfy   : {svc('ntfy-listener.service')}\n"
        f"Todo   : {pending} pending tasks\n"
        f"Commits:\n{commits}\n"
        f"=== end ==="
    )


def route(message: str) -> str:
    """Route an incoming ntfy command. Returns reply string."""
    text = message.strip()
    low  = text.lower()

    if low in ("status", "s", "?", "ping"):
        return _system_status()

    if low == "help":
        return (
            "Alii commands (send to alii-precision-commands):\n"
            "  status         → system health\n"
            "  task: <text>   → queue a task\n"
            "  run: logs      → overnight log tail\n"
            "  run: alfred    → alfred log\n"
            "  run: watchdog  → watchdog log\n"
            "  run: git       → recent commits\n"
            "  run: services  → running services\n"
            "  run: todo      → pending tasks\n"
            "  run: memory    → morning briefing\n"
            "  help           → this list"
        )

    if low.startswith("task:"):
        task = text[5:].strip()
        if not task:
            return "ERROR: task text is empty"
        _add_todo(task, priority="high", source="ntfy")
        return f"✓ QUEUED (high priority): {task[:80]}"

    if low.startswith("run:"):
        key = text[4:].strip().lower()
        if key == "todo":
            try:
                tasks   = json.loads(TODO_FILE.read_text())
                pending = [t["task"] for t in tasks if not t.get("done")][:8]
                if not pending:
                    return "Todo list is empty — all done!"
                return "PENDING TASKS:\n" + "\n".join(f"• {p[:70]}" for p in pending)
            except Exception as exc:
                return f"ERROR reading todo: {exc}"
        if key in SAFE_RUNS:
            try:
                r = subprocess.run(SAFE_RUNS[key], capture_output=True, text=True, timeout=15)
                out = (r.stdout + r.stderr).strip()
                return out[-3000:] if out else "(no output)"
            except Exception as exc:
                return f"ERROR: {exc}"
        return (f"Unknown run command: '{key}'\n"
                f"Valid: {', '.join(SAFE_RUNS)} todo")

    # Natural language → queue as task
    if len(text) > 3:
        _add_todo(text, priority="normal", source="ntfy")
        return f"✓ Queued as task: {text[:80]}"

    return "?"


def _poll_once(since_id: str) -> tuple[str, list[dict]]:
    """
    Poll ntfy for new messages since last message ID.
    Returns (new_last_id, [messages]).
    """
    url = f"{NTFY_BASE}/{COMMANDS_TOPIC}/json?poll=1"
    if since_id:
        url += f"&since={since_id}"

    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "8", url],
            capture_output=True, text=True, timeout=12
        )
        if r.returncode != 0 or not r.stdout.strip():
            return since_id, []

        messages = []
        last_id  = since_id
        for line in r.stdout.strip().splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if obj.get("event") == "message":
                    messages.append(obj)
                    last_id = obj.get("id", last_id)
            except json.JSONDecodeError:
                pass

        return last_id, messages

    except Exception as exc:
        log.debug("poll error: %s", exc)
        return since_id, []


def poll_loop():
    """Main polling loop — checks for commands every POLL_INTERVAL seconds."""
    log.info("ntfy command listener starting. Topic: %s", COMMANDS_TOPIC)
    _ntfy_send(
        "TWO-WAY BRIDGE ACTIVE\n"
        "Subscribe to ntfy topic 'alii-precision-commands' to send commands.\n\n"
        "Examples:\n"
        "  status           → system report\n"
        "  task: do X       → queue a task\n"
        "  run: logs        → tail overnight log\n"
        "  run: git         → recent commits\n"
        "  help             → full command list\n\n"
        "Waiting for your orders. -Alii",
        title="Alii Bridge Active",
        priority="high",
    )

    since_id = ""
    # Skip any existing messages on first boot
    since_id, _ = _poll_once("")
    log.info("Skipped existing messages, listening from id=%s", since_id)

    while True:
        try:
            since_id, messages = _poll_once(since_id)
            for msg in messages:
                text  = msg.get("message", "").strip()
                msg_id = msg.get("id", "")
                if not text:
                    continue
                log.info("Command received [%s]: %s", msg_id, text[:80])
                reply = route(text)
                log.info("Reply: %s", reply[:120])
                _ntfy_send(reply, title=f"Alii → {text[:30]}")
        except Exception as exc:
            log.debug("Loop error (non-fatal): %s", exc)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    poll_loop()
