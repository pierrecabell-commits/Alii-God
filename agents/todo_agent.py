#!/usr/bin/env python3
"""
TodoAgent — Owner task tracking for Alii sovereign system.
Storage: data/owner_todos.json
Access:  from agents.todo_agent import todo; todo.add_todo(...)
"""

import json
import os
import sys
import time
import uuid
import logging
import subprocess
from pathlib import Path
from datetime import datetime, date
from typing import Optional

WORKDIR   = Path("/home/avalii/moltbot")
DATA_FILE = WORKDIR / "data" / "owner_todos.json"
LOG_FILE  = WORKDIR / "logs" / "todo_agent.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [todo] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stderr),
    ],
)
log = logging.getLogger("alii.todo")

CATEGORIES = {"security", "account", "config", "action"}
PRIORITIES = {"critical", "high", "medium", "low"}
STATUSES   = {"pending", "done", "snoozed"}

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _ntfy(msg: str, title: str = "Alii Todo"):
    """Send ntfy notification (gracefully skips if unavailable)."""
    try:
        subprocess.run(
            ["curl", "-s", "-X", "POST",
             "-H", f"Title: {title}",
             "-d", msg,
             "https://ntfy.sh/alii-precision"],
            capture_output=True, timeout=8
        )
    except Exception as exc:
        log.debug("ntfy unavailable: %s", exc)


class TodoAgent:
    def __init__(self):
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not DATA_FILE.exists():
            DATA_FILE.write_text("[]")
        self._todos: list[dict] = json.loads(DATA_FILE.read_text())

    def _save(self):
        DATA_FILE.write_text(json.dumps(self._todos, indent=2))

    def _find(self, todo_id: str) -> Optional[dict]:
        for t in self._todos:
            if t["id"] == todo_id:
                return t
        return None

    def add_todo(
        self,
        title: str,
        description: str = "",
        category: str = "action",
        priority: str = "medium",
        context: str = "",
        added_by: str = "alii",
    ) -> dict:
        if category not in CATEGORIES:
            category = "action"
        if priority not in PRIORITIES:
            priority = "medium"
        todo = {
            "id": str(uuid.uuid4())[:8],
            "created_at": datetime.utcnow().isoformat() + "Z",
            "category": category,
            "priority": priority,
            "title": title,
            "description": description,
            "context": context,
            "status": "pending",
            "added_by": added_by,
            "completed_at": None,
            "snoozed_until": None,
        }
        self._todos.append(todo)
        self._save()
        log.info("Todo added [%s/%s]: %s", priority, category, title)
        return todo

    def complete_todo(self, todo_id: str) -> bool:
        t = self._find(todo_id)
        if not t:
            return False
        t["status"] = "done"
        t["completed_at"] = datetime.utcnow().isoformat() + "Z"
        self._save()
        log.info("Todo completed: %s", t["title"])
        return True

    def snooze_todo(self, todo_id: str, until_date: str) -> bool:
        """Snooze until ISO date string e.g. '2026-03-08'."""
        t = self._find(todo_id)
        if not t:
            return False
        t["status"] = "snoozed"
        t["snoozed_until"] = until_date
        self._save()
        log.info("Todo snoozed until %s: %s", until_date, t["title"])
        return True

    def get_pending(self) -> list[dict]:
        """Return all pending (and un-snoozed) todos sorted by priority."""
        today = date.today().isoformat()
        result = []
        for t in self._todos:
            if t["status"] == "done":
                continue
            if t["status"] == "snoozed":
                snooze_until = t.get("snoozed_until") or ""
                if snooze_until > today:
                    continue
                # Snooze expired — restore to pending
                t["status"] = "pending"
                t["snoozed_until"] = None
                self._save()
            result.append(t)
        result.sort(key=lambda x: (PRIORITY_ORDER.get(x["priority"], 9), x["created_at"]))
        return result

    def daily_digest(self) -> str:
        """Return a formatted digest of all pending todos."""
        pending = self.get_pending()
        if not pending:
            return "No pending todos — all clear!"

        lines = [f"Alii Owner Todo Digest — {datetime.utcnow().strftime('%Y-%m-%d')}\n"]
        lines.append(f"  {len(pending)} item(s) pending\n")
        lines.append("─" * 50 + "\n")

        for i, t in enumerate(pending, 1):
            pri   = t["priority"].upper()
            cat   = t["category"]
            title = t["title"]
            desc  = t["description"]
            lines.append(f"{i}. [{pri}/{cat}] {title}\n")
            if desc:
                lines.append(f"   {desc}\n")
            lines.append("\n")

        return "".join(lines)

    def send_digest_ntfy(self):
        """Format and send today's digest via ntfy."""
        pending = self.get_pending()
        if not pending:
            _ntfy("All clear — no pending todos!", title="Alii Daily Digest")
            return

        # ntfy body limit ~4k; keep concise
        items = []
        for t in pending:
            items.append(f"[{t['priority'].upper()}/{t['category']}] {t['title']}")

        body = f"{len(pending)} pending tasks:\n" + "\n".join(items[:15])
        if len(pending) > 15:
            body += f"\n...and {len(pending)-15} more"

        _ntfy(body, title=f"Alii Daily Digest — {len(pending)} todos")
        log.info("Digest sent via ntfy (%d items)", len(pending))

    def format_ntfy_list(self) -> str:
        """Return compact ntfy-friendly todo list."""
        pending = self.get_pending()
        if not pending:
            return "No pending todos."
        lines = [f"{i+1}. [{t['priority'].upper()}] {t['title']}" for i, t in enumerate(pending)]
        return "\n".join(lines)


# ── Module-level singleton ──────────────────────────────────────────────────────
todo = TodoAgent()

# ── Pre-populate todos ──────────────────────────────────────────────────────────
def _prepopulate():
    """Add initial owner todos if not already present."""
    existing_titles = {t["title"] for t in todo._todos}

    items = [
        dict(
            title="Set vault master password",
            description="Vault in bypass mode. Run: cd /home/avalii/moltbot && python3 vault/vault_manager.py init   to set your permanent password before connecting to any public network.",
            category="security", priority="critical",
            context="vault currently uses bypass mode — no encryption password set",
            added_by="phase3",
        ),
        dict(
            title="Rotate cluster node passwords",
            description="All 3 nodes still use old exposed password. Run sudo passwd avalii on precision then SSH to aliiaiserver and xpsavaliiserver.",
            category="security", priority="critical",
            context="Godmode1993! was exposed in logs — rotate immediately",
            added_by="phase3",
        ),
        dict(
            title="Set up BlueBubbles for iMessage",
            description="Download BlueBubbles Server on MacBook, enable Private API, add BLUEBUBBLES_URL and BLUEBUBBLES_PASSWORD to vault. 10 min job.",
            category="config", priority="high",
            context="iMessage agent requires BlueBubbles server running on macOS",
            added_by="phase3",
        ),
        dict(
            title="Add ALII_PHONE_NUMBER to vault",
            description="python3 vault/vault_manager.py set ALII_PHONE_NUMBER +1YOURNUMBER",
            category="config", priority="high",
            context="needed for SMS/iMessage routing",
            added_by="phase3",
        ),
        dict(
            title="Add Apple ID app-specific password for email agent",
            description="Go to appleid.apple.com, generate app password, add as APPLE_APP_PASSWORD in vault.",
            category="config", priority="high",
            context="email agent uses IMAP imap.mail.me.com:993",
            added_by="phase3",
        ),
        dict(
            title="Get new Perplexity API key",
            description="Old key rotated (leaked in git). Go to perplexity.ai/settings/api, generate new key, add as PERPLEXITY_API_KEY in vault.",
            category="account", priority="high",
            context="old key in commits ba5e2e3 + 95ba959 — compromised",
            added_by="phase3",
        ),
        dict(
            title="Activate Stripe",
            description="Sign up at stripe.com, add STRIPE_SECRET_KEY to vault to enable SaaS payments.",
            category="account", priority="medium",
            context="SaaS API at port 8080 ready but Stripe not connected",
            added_by="phase3",
        ),
        dict(
            title="Add GitHub token",
            description="github.com/settings/tokens — add as GITHUB_TOKEN in vault.",
            category="config", priority="medium",
            context="needed for revenue agent and alii-public repo push",
            added_by="phase3",
        ),
        dict(
            title="Review and push alii-public repo",
            description="Sanitized repo staged at /home/avalii/alii-public/ — review then git push.",
            category="action", priority="medium",
            context="repo initialized and sanitized, needs manual review before push",
            added_by="phase3",
        ),
    ]

    added = 0
    for item in items:
        if item["title"] not in existing_titles:
            todo.add_todo(**item)
            added += 1

    if added:
        log.info("Pre-populated %d todos", added)

    return added


# ── CLI ─────────────────────────────────────────────────────────────────────────
def main():
    import argparse
    ap = argparse.ArgumentParser(description="Alii Todo Agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list",   help="List pending todos")
    sub.add_parser("digest", help="Print daily digest")
    sub.add_parser("ntfy",   help="Send digest via ntfy")

    p_add = sub.add_parser("add", help="Add a todo")
    p_add.add_argument("title")
    p_add.add_argument("--desc", default="")
    p_add.add_argument("--category", default="action")
    p_add.add_argument("--priority", default="medium")

    p_done = sub.add_parser("done", help="Mark todo done")
    p_done.add_argument("id")

    p_snz = sub.add_parser("snooze", help="Snooze todo")
    p_snz.add_argument("id")
    p_snz.add_argument("until", help="ISO date e.g. 2026-03-08")

    args = ap.parse_args()

    if args.cmd == "list":
        pending = todo.get_pending()
        if not pending:
            print("No pending todos.")
            return
        for i, t in enumerate(pending, 1):
            print(f"{i}. [{t['priority'].upper()}/{t['category']}] [{t['id']}] {t['title']}")
            if t["description"]:
                print(f"   {t['description']}")
    elif args.cmd == "digest":
        print(todo.daily_digest())
    elif args.cmd == "ntfy":
        todo.send_digest_ntfy()
        print("Digest sent.")
    elif args.cmd == "add":
        t = todo.add_todo(
            title=args.title,
            description=args.desc,
            category=args.category,
            priority=args.priority,
        )
        print(f"Added [{t['id']}]: {t['title']}")
    elif args.cmd == "done":
        ok = todo.complete_todo(args.id)
        print("Done." if ok else f"Todo '{args.id}' not found.")
    elif args.cmd == "snooze":
        ok = todo.snooze_todo(args.id, args.until)
        print("Snoozed." if ok else f"Todo '{args.id}' not found.")


if __name__ == "__main__":
    _prepopulate()
    main()
