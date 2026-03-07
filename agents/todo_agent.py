#!/usr/bin/env python3
"""
TodoAgent — Owner task tracking for Alii sovereign system.
Storage: data/owner_todos.json
Access:  from agents.todo_agent import todo; todo.add_todo(...)
"""

import json
import os
import re
import sys
import tempfile
import uuid
import logging
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional

from config import WORKDIR, DATA_DIR, LOG_DIR
DATA_FILE = DATA_DIR / "owner_todos.json"
LOG_FILE  = LOG_DIR / "todo_agent.log"

# ── Dedicated logger (NOT basicConfig — avoids polluting root logger) ──────────
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
_handler = logging.FileHandler(LOG_FILE)
_handler.setFormatter(logging.Formatter("%(asctime)s [todo] %(levelname)s %(message)s"))
log = logging.getLogger("alii.todo")
log.setLevel(logging.INFO)
log.propagate = False   # critical: prevents alfred.py errors from landing here
if not log.handlers:
    log.addHandler(_handler)
    log.addHandler(logging.StreamHandler(sys.stderr))

CATEGORIES = {"security", "account", "config", "action"}
PRIORITIES = {"critical", "high", "medium", "low"}
STATUSES   = {"pending", "done", "snoozed"}

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _ntfy(msg: str, title: str = "Alii Todo", priority: str = "default"):
    """Send ntfy notification fire-and-forget (never blocks the caller)."""
    try:
        subprocess.Popen(
            ["curl", "-s", "-X", "POST",
             "-H", f"Title: {title}",
             "-H", f"Priority: {priority}",
             "-d", msg,
             "https://ntfy.sh/alii-precision"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        log.debug("ntfy unavailable: %s", exc)


class TodoAgent:
    def __init__(self):
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._todos: list[dict] = []
        self._mtime: float = 0.0
        self._id_index: dict[str, dict] = {}
        self._load()

    def _load(self):
        """Load todos from disk, recovering gracefully from corrupt JSON."""
        if not DATA_FILE.exists():
            DATA_FILE.write_text("[]")
            self._todos = []
            self._id_index = {}
            self._mtime = 0.0
            return
        try:
            raw = json.loads(DATA_FILE.read_text())
            if not isinstance(raw, list):
                raise ValueError("expected list")
            # Ensure every entry has required keys (forward-compat with old data)
            for t in raw:
                t.setdefault("status", "pending")
                t.setdefault("updated_at", None)
                t.setdefault("due_date", None)
                t.setdefault("snoozed_until", None)
                t.setdefault("completed_at", None)
                t.setdefault("tags", [])
            self._todos = raw
            self._id_index = {t["id"]: t for t in raw if t.get("id")}
            self._mtime = DATA_FILE.stat().st_mtime
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            log.error("Corrupt todos file (%s) — resetting to empty list", exc)
            self._todos = []
            self._id_index = {}
            self._mtime = 0.0
            self._save()

    def _refresh(self):
        """Reload from disk if the file has been modified since our last load.

        Called at the top of every read path so that concurrent writers
        (other processes / alfred.py task handlers) are always visible without
        an explicit reload() call.
        """
        try:
            mtime = DATA_FILE.stat().st_mtime
            if mtime > self._mtime:
                self._load()
        except OSError:
            pass  # file disappeared — keep current state, _load handles missing

    def reload(self):
        """Refresh in-memory state from disk (useful for multi-process safety)."""
        self._load()

    def _save(self):
        """Atomically write todos to disk (temp-file + os.replace)."""
        try:
            DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=DATA_FILE.parent, suffix=".json")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(self._todos, f, indent=2)
                os.replace(tmp, DATA_FILE)
                # Update mtime so _refresh() doesn't reload what we just wrote
                try:
                    self._mtime = DATA_FILE.stat().st_mtime
                except OSError:
                    pass
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except Exception as exc:
            log.error("Failed to save todos: %s", exc)

    def _find(self, todo_id: str) -> Optional[dict]:
        """Find by exact ID (O(1)) or unambiguous prefix (linear fallback)."""
        exact = self._id_index.get(todo_id)
        if exact:
            return exact
        # prefix match (supports partial IDs typed by hand)
        matches = [t for t in self._todos if (t.get("id") or "").startswith(todo_id)]
        return matches[0] if len(matches) == 1 else None

    def _now(self) -> str:
        return datetime.utcnow().isoformat() + "Z"

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_todo(
        self,
        title: str,
        description: str = "",
        category: str = "action",
        priority: str = "medium",
        context: str = "",
        added_by: str = "alii",
        deduplicate: bool = True,
        due_date: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> dict:
        title = title.strip()
        if not title:
            log.warning("add_todo called with blank title — skipped")
            return {}
        if category not in CATEGORIES:
            category = "action"
        if priority not in PRIORITIES:
            priority = "medium"
        if due_date and not _ISO_DATE_RE.match(due_date):
            log.warning("Invalid due_date format '%s' — ignoring", due_date)
            due_date = None

        self._refresh()
        # Deduplication: skip if identical title+category already pending/snoozed
        if deduplicate:
            for t in self._todos:
                if t.get("title") == title and t.get("category") == category and t.get("status") != "done":
                    log.debug("Skipping duplicate todo: %s", title)
                    return t

        todo = {
            "id":            str(uuid.uuid4())[:8],
            "created_at":    self._now(),
            "updated_at":    None,
            "category":      category,
            "priority":      priority,
            "title":         title,
            "description":   description,
            "context":       context,
            "status":        "pending",
            "added_by":      added_by,
            "completed_at":  None,
            "snoozed_until": None,
            "due_date":      due_date,
            "tags":          tags or [],
        }
        self._todos.append(todo)
        self._id_index[todo["id"]] = todo
        self._save()
        log.info("Todo added [%s/%s]: %s", priority, category, title)

        # Notify immediately for high-urgency items
        if priority in ("critical", "high"):
            ntfy_prio = "urgent" if priority == "critical" else "high"
            _ntfy(
                f"[{priority.upper()}/{category}] {title}",
                title="Alii Todo Alert",
                priority=ntfy_prio,
            )
        return todo

    def complete_todo(self, todo_id: str) -> bool:
        self._refresh()
        t = self._find(todo_id)
        if not t:
            return False
        t["status"] = "done"
        t["completed_at"] = self._now()
        t["updated_at"] = self._now()
        self._save()
        log.info("Todo completed: %s", t["title"])
        return True

    def bulk_complete(self, todo_ids: list[str]) -> int:
        """Mark multiple todos done in a single save. Returns count completed."""
        self._refresh()
        now = self._now()
        completed = 0
        for todo_id in todo_ids:
            t = self._find(todo_id)
            if t and t.get("status") != "done":
                t["status"] = "done"
                t["completed_at"] = now
                t["updated_at"] = now
                completed += 1
        if completed:
            self._save()
            log.info("Bulk completed %d todos", completed)
        return completed

    def reopen_todo(self, todo_id: str) -> bool:
        """Re-open a completed todo back to pending status."""
        self._refresh()
        t = self._find(todo_id)
        if not t:
            return False
        if t.get("status") == "pending":
            return True  # already pending — idempotent
        t["status"] = "pending"
        t["completed_at"] = None
        t["snoozed_until"] = None
        t["updated_at"] = self._now()
        self._save()
        log.info("Todo re-opened: %s", t["title"])
        return True

    def escalate_overdue(self, stale_days: int = 7, _quiet: bool = False) -> list[dict]:
        """Bump priority of todos that are past due_date or older than stale_days.

        critical stays critical, others advance one level. Sends ntfy for any
        that escalated to critical. Returns list of escalated todos.
        """
        ESCALATE_MAP = {"low": "medium", "medium": "high", "high": "critical"}
        today = date.today().isoformat()
        cutoff = (date.today() - timedelta(days=stale_days)).isoformat()
        self._refresh()
        escalated = []
        for t in self._todos:
            if t.get("status") != "pending":
                continue
            pri = t.get("priority", "medium")
            if pri == "critical":
                continue
            due = t.get("due_date")
            created = (t.get("created_at") or "")[:10]
            is_overdue = (due and due < today) or (not due and created and created < cutoff)
            if not is_overdue:
                continue
            new_pri = ESCALATE_MAP.get(pri, pri)
            t["priority"] = new_pri
            t["updated_at"] = self._now()
            escalated.append(t)
        if escalated:
            self._save()
            log.info("Escalated %d overdue todos", len(escalated))
            newly_critical = [t for t in escalated if t.get("priority") == "critical"]
            if newly_critical and not _quiet:
                body = "\n".join(f"• {t['title']}" for t in newly_critical[:5])
                _ntfy(f"{len(newly_critical)} todo(s) escalated to CRITICAL:\n{body}",
                      title="Alii Todo Escalation", priority="urgent")
        return escalated

    def backup(self) -> Optional[str]:
        """Write a timestamped backup of the todo list to data/todos_backup_YYYYMMDD.json.
        Returns the backup path, or None on failure."""
        try:
            stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = DATA_FILE.parent / f"todos_backup_{stamp}.json"
            backup_path.write_text(json.dumps(self._todos, indent=2))
            log.info("Backup written: %s", backup_path)
            return str(backup_path)
        except Exception as exc:
            log.error("Backup failed: %s", exc)
            return None

    def get_stats(self) -> dict:
        """Return rich stats: counts by priority × category, aging buckets."""
        self._refresh()
        pending = self.get_pending()
        today = date.today()

        by_priority = {p: 0 for p in PRIORITIES}
        by_category = {c: 0 for c in CATEGORIES}
        aging = {"<1d": 0, "1-7d": 0, "8-30d": 0, ">30d": 0}

        for t in pending:
            p = t.get("priority", "medium")
            c = t.get("category", "action")
            if p in by_priority:
                by_priority[p] += 1
            if c in by_category:
                by_category[c] += 1
            created = (t.get("created_at") or "")[:10]
            try:
                age = (today - date.fromisoformat(created)).days
                if age < 1:
                    aging["<1d"] += 1
                elif age <= 7:
                    aging["1-7d"] += 1
                elif age <= 30:
                    aging["8-30d"] += 1
                else:
                    aging[">30d"] += 1
            except (ValueError, TypeError):
                pass

        done_list = [t for t in self._todos if t.get("status") == "done"]
        avg_resolution = None
        if done_list:
            durations = []
            for t in done_list:
                try:
                    created = datetime.fromisoformat(t["created_at"].rstrip("Z"))
                    completed = datetime.fromisoformat(t["completed_at"].rstrip("Z"))
                    durations.append((completed - created).total_seconds() / 86400)
                except (KeyError, ValueError, TypeError, AttributeError):
                    pass
            if durations:
                avg_resolution = round(sum(durations) / len(durations), 1)

        return {
            "pending":         len(pending),
            "done":            len(done_list),
            "snoozed":         sum(1 for t in self._todos if t.get("status") == "snoozed"),
            "by_priority":     by_priority,
            "by_category":     by_category,
            "aging":           aging,
            "avg_resolution_days": avg_resolution,
        }

    def delete_todo(self, todo_id: str) -> bool:
        """Permanently remove a todo by ID or unambiguous prefix."""
        self._refresh()
        t = self._find(todo_id)
        if not t:
            return False
        self._todos = [x for x in self._todos if x.get("id") != t.get("id")]
        self._id_index.pop(t.get("id"), None)
        self._save()
        log.info("Todo deleted: %s (%s)", t.get("id"), t.get("title", ""))
        return True

    def update_todo(self, todo_id: str, **fields) -> bool:
        """Update arbitrary fields on a todo (title, description, priority, category, context, due_date, tags)."""
        self._refresh()
        t = self._find(todo_id)
        if not t:
            return False
        allowed = {"title", "description", "priority", "category", "context", "status", "due_date", "tags"}
        changed = False
        for key, val in fields.items():
            if key not in allowed:
                continue
            if key == "priority" and val not in PRIORITIES:
                continue
            if key == "category" and val not in CATEGORIES:
                continue
            if key == "status" and val not in STATUSES:
                continue
            if key == "due_date" and val and not _ISO_DATE_RE.match(val):
                log.warning("Invalid due_date '%s' in update — skipping", val)
                continue
            t[key] = val
            changed = True
        if changed:
            t["updated_at"] = self._now()
            self._save()
            log.info("Todo updated [%s]: %s", todo_id, list(fields.keys()))
        return changed

    def snooze_todo(self, todo_id: str, until_date: str) -> bool:
        """Snooze until ISO date string e.g. '2026-03-08'. Validates format and rejects past dates."""
        if not _ISO_DATE_RE.match(until_date):
            log.error("snooze_todo: invalid date format '%s' — expected YYYY-MM-DD", until_date)
            return False
        if until_date <= date.today().isoformat():
            log.error("snooze_todo: date '%s' is today or in the past — rejected", until_date)
            return False
        self._refresh()
        t = self._find(todo_id)
        if not t:
            return False
        t["status"] = "snoozed"
        t["snoozed_until"] = until_date
        t["updated_at"] = self._now()
        self._save()
        log.info("Todo snoozed until %s: %s", until_date, t["title"])
        return True

    def snooze_days(self, todo_id: str, days: int) -> bool:
        """Snooze a todo for N days from today (relative convenience wrapper)."""
        if days < 1:
            log.error("snooze_days: days must be >= 1, got %d", days)
            return False
        until = (date.today() + timedelta(days=days)).isoformat()
        return self.snooze_todo(todo_id, until)

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_pending(self) -> list[dict]:
        """Return all pending (and un-snoozed) todos sorted by priority."""
        self._refresh()
        today = date.today().isoformat()
        result = []
        dirty = False
        for t in self._todos:
            status = t.get("status", "pending")
            if status == "done":
                continue
            if status == "snoozed":
                snooze_until = t.get("snoozed_until") or ""
                if snooze_until > today:
                    continue
                # Snooze expired — restore to pending
                t["status"] = "pending"
                t["snoozed_until"] = None
                t["updated_at"] = self._now()
                dirty = True
            result.append(t)
        if dirty:
            self._save()  # single save after processing all expired snoozes
        result.sort(key=lambda x: (PRIORITY_ORDER.get(x.get("priority", "low"), 9), x.get("created_at", "")))
        return result

    def get_all(self, include_done: bool = True) -> list[dict]:
        """Return all todos, optionally including completed ones."""
        self._refresh()
        if include_done:
            return list(self._todos)
        return [t for t in self._todos if t.get("status") != "done"]

    def get_by_category(self, category: str) -> list[dict]:
        """Return pending todos filtered by category."""
        return [t for t in self.get_pending() if t.get("category") == category]

    def get_by_priority(self, priority: str) -> list[dict]:
        """Return pending todos filtered by priority."""
        return [t for t in self.get_pending() if t.get("priority") == priority]

    def get_critical(self) -> list[dict]:
        """Return all pending critical todos."""
        return self.get_by_priority("critical")

    def get_overdue(self, older_than_days: int = 7) -> list[dict]:
        """Return pending todos older than N days (by created_at) or past their due_date."""
        today = date.today().isoformat()
        cutoff = (date.today() - timedelta(days=older_than_days)).isoformat()
        results = []
        for t in self.get_pending():
            # Past explicit due date
            due = t.get("due_date")
            if due and due < today:
                results.append(t)
                continue
            # Just stale (no due date, but older than threshold)
            created = (t.get("created_at") or "")[:10]
            if created and created < cutoff and not due:
                results.append(t)
        return results

    def search_todos(self, query: str, include_done: bool = False) -> list[dict]:
        """Case-insensitive substring search across title, description, and context."""
        self._refresh()
        q = query.lower()
        pool = self._todos if include_done else [t for t in self._todos if t.get("status") != "done"]
        results = []
        for t in pool:
            haystack = " ".join([
                t.get("title", ""),
                t.get("description", ""),
                t.get("context", ""),
                " ".join(t.get("tags", [])),
            ]).lower()
            if q in haystack:
                results.append(t)
        results.sort(key=lambda x: (PRIORITY_ORDER.get(x.get("priority", "low"), 9), x.get("created_at", "")))
        return results

    def get_due_today(self) -> list[dict]:
        """Return pending todos whose due_date is today."""
        today = date.today().isoformat()
        return [t for t in self.get_pending() if t.get("due_date") == today]

    def get_by_tag(self, tag: str) -> list[dict]:
        """Return pending todos that include the given tag (case-insensitive)."""
        tag_lower = tag.lower()
        return [t for t in self.get_pending()
                if any(tag_lower == tg.lower() for tg in t.get("tags", []))]

    def get_recent(self, hours: int = 24) -> list[dict]:
        """Return todos added within the last N hours, newest first."""
        self._refresh()
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
        results = [t for t in self._todos if (t.get("created_at") or "") >= cutoff]
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    def get_upcoming(self, days: int = 7) -> list[dict]:
        """Return pending todos with a due_date within the next N days, sorted by due date."""
        today = date.today()
        cutoff = (today + timedelta(days=days)).isoformat()
        today_str = today.isoformat()
        results = [
            t for t in self.get_pending()
            if t.get("due_date") and today_str <= t["due_date"] <= cutoff
        ]
        results.sort(key=lambda x: x.get("due_date", ""))
        return results

    def bulk_done_by_category(self, category: str) -> int:
        """Mark all pending todos in a category as done. Returns count completed."""
        if category not in CATEGORIES:
            log.warning("bulk_done_by_category: unknown category '%s'", category)
            return 0
        self._refresh()
        now = self._now()
        completed = 0
        for t in self._todos:
            if t.get("category") == category and t.get("status") == "pending":
                t["status"] = "done"
                t["completed_at"] = now
                t["updated_at"] = now
                completed += 1
        if completed:
            self._save()
            log.info("Bulk completed %d todos in category '%s'", completed, category)
        return completed

    def get_health(self) -> dict:
        """Return a health/readiness dict for optimizer scoring.

        Scoring bands (each capped so a single axis can't tank the whole score):
          - critical pending:  −0.05 per item, max −0.25
          - overdue pending:   −0.03 per item, max −0.15
          - backlog > 20:      −0.05 flat
          - zero pending:      +0.05 bonus (everything clear)
        Floor: 0.5 — agent is structurally healthy even with a full todo list.
        """
        s = self.summary()
        score = 1.0
        score -= min(0.25, s["critical"] * 0.05)
        score -= min(0.15, s["overdue"] * 0.03)
        if s["pending"] > 20:
            score -= 0.05
        if s["pending"] == 0:
            score = min(1.0, score + 0.05)
        score = max(0.5, round(score, 2))
        return {
            "agent":    "todo_agent",
            "score":    score,
            "healthy":  score >= 0.7,
            "summary":  s,
        }

    def add_todos_bulk(self, items: list[dict]) -> list[dict]:
        """Add multiple todos in a single disk write. Each dict uses add_todo kwargs.
        Returns list of added todo dicts (empty dicts for skipped/duplicate entries)."""
        self._refresh()
        added = []
        new_count = 0
        for kwargs in items:
            # Temporarily bypass per-item _refresh and _save by inlining core logic
            title = (kwargs.get("title") or "").strip()
            if not title:
                added.append({})
                continue
            category = kwargs.get("category", "action")
            priority = kwargs.get("priority", "medium")
            if category not in CATEGORIES:
                category = "action"
            if priority not in PRIORITIES:
                priority = "medium"
            if kwargs.get("deduplicate", True):
                dup = next((t for t in self._todos
                            if t.get("title") == title
                            and t.get("category") == category
                            and t.get("status") != "done"), None)
                if dup:
                    added.append(dup)
                    continue
            due_date = kwargs.get("due_date")
            if due_date and not _ISO_DATE_RE.match(due_date):
                due_date = None
            todo_entry = {
                "id":            str(uuid.uuid4())[:8],
                "created_at":    self._now(),
                "updated_at":    None,
                "category":      category,
                "priority":      priority,
                "title":         title,
                "description":   kwargs.get("description", ""),
                "context":       kwargs.get("context", ""),
                "status":        "pending",
                "added_by":      kwargs.get("added_by", "alii"),
                "completed_at":  None,
                "snoozed_until": None,
                "due_date":      due_date,
                "tags":          kwargs.get("tags") or [],
            }
            self._todos.append(todo_entry)
            self._id_index[todo_entry["id"]] = todo_entry
            added.append(todo_entry)
            new_count += 1
        if new_count:
            self._save()
            urgent_new = [t for t in added if t.get("priority") in ("critical", "high") and t.get("id")]
            if urgent_new:
                ntfy_prio = "urgent" if any(t.get("priority") == "critical" for t in urgent_new) else "high"
                body = "\n".join(f"[{t.get('priority','').upper()}/{t.get('category','')}] {t.get('title','')}"
                                 for t in urgent_new[:5])
                _ntfy(f"{len(urgent_new)} high-priority todo(s) added:\n{body}",
                      title="Alii Todo Alert", priority=ntfy_prio)
        log.info("Bulk-added %d of %d requested todos", new_count, len(items))
        return added

    def get_todo(self, todo_id: str) -> Optional[dict]:
        """Return a single todo by ID or unambiguous prefix. None if not found."""
        self._refresh()
        return self._find(todo_id)

    def get_done(self, limit: int = 50) -> list[dict]:
        """Return completed todos, most recently completed first."""
        self._refresh()
        done = [t for t in self._todos if t.get("status") == "done"]
        done.sort(key=lambda x: x.get("completed_at") or "", reverse=True)
        return done[:limit]

    def purge_old(self, days: int = 30) -> int:
        """Permanently delete done todos older than N days. Prevents unbounded file growth.
        Returns count purged."""
        self._refresh()
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        before = len(self._todos)
        self._todos = [
            t for t in self._todos
            if not (t.get("status") == "done"
                    and (t.get("completed_at") or "")[:10] < cutoff)
        ]
        self._id_index = {t["id"]: t for t in self._todos if t.get("id")}
        purged = before - len(self._todos)
        if purged:
            self._save()
            log.info("Purged %d completed todos older than %d days", purged, days)
        return purged

    def handle_command(self, text: str) -> str:
        """Natural language command dispatcher for alfred.py integration.

        Handles plain-text queries like:
          "what's pending", "list todos", "critical tasks",
          "security todos", "add todo: <title>", "done <id>", "digest"
        Returns a human-readable string response.
        """
        t = text.strip().lower()

        if any(kw in t for kw in ("digest", "summary", "report")):
            return self.daily_digest()

        if any(kw in t for kw in ("how many", "count")):
            s = self.summary()
            return (f"{s['pending']} pending ({s['critical']} critical, "
                    f"{s['high']} high, {s['overdue']} overdue)")

        if any(kw in t for kw in ("health", "score", "status")):
            h = self.get_health()
            s = h["summary"]
            return (f"score={h['score']} healthy={h['healthy']} "
                    f"pending={s['pending']} critical={s['critical']} overdue={s['overdue']}")

        if any(kw in t for kw in ("critical", "urgent")):
            items = self.get_critical()
            if not items:
                return "No critical todos."
            return "\n".join(f"[{i['id']}] {i['title']}" for i in items)

        if "overdue" in t or "stale" in t or "late" in t:
            items = self.get_overdue()
            if not items:
                return "No overdue todos."
            return "\n".join(f"[{i['id']}] {i['title']}" for i in items)

        if "due today" in t or "today" in t:
            items = self.get_due_today()
            if not items:
                return "Nothing due today."
            return "\n".join(f"[{i['id']}] {i['title']}" for i in items)

        for cat in CATEGORIES:
            if cat in t:
                items = self.get_by_category(cat)
                if not items:
                    return f"No {cat} todos."
                return "\n".join(f"[{i['id']}] [{i['priority'].upper()}] {i['title']}" for i in items)

        if any(kw in t for kw in ("snoozed", "sleeping")):
            items = self.get_snoozed()
            if not items:
                return "No snoozed todos."
            return "\n".join(
                f"[{i['id']}] [until {i.get('snoozed_until','')}] {i['title']}"
                for i in items
            )

        # "add todo: <title>" / "add: <title>"
        stripped = text.strip()
        for prefix in ("add todo:", "add task:", "add:"):
            if t.startswith(prefix):
                title = stripped[len(prefix):].strip()
                if title:
                    added = self.add_todo(title=title, added_by="alfred")
                    if not added:
                        return "Failed to add todo (blank title)."
                    return f"Added [{added['id']}]: {added['title']}"

        # "done <id>" / "complete <id>"
        for prefix in ("done ", "complete ", "completed ", "finish "):
            if t.startswith(prefix):
                tid = t[len(prefix):].strip()
                ok = self.complete_todo(tid)
                return "Done." if ok else f"Todo '{tid}' not found."

        # "reopen <id>"
        for prefix in ("reopen ", "reactivate ", "undo "):
            if t.startswith(prefix):
                tid = t[len(prefix):].strip()
                ok = self.reopen_todo(tid)
                return "Reopened." if ok else f"Todo '{tid}' not found."

        # "escalate" — bump priority on all overdue todos
        if any(kw in t for kw in ("escalate", "bump priority", "prioritize overdue")):
            escalated = self.escalate_overdue()
            if not escalated:
                return "No overdue todos to escalate."
            return f"Escalated {len(escalated)} todo(s):\n" + "\n".join(
                f"[{i['id']}] → {i['priority'].upper()}: {i['title']}" for i in escalated
            )

        # "show <id>" / "get <id>"
        for prefix in ("show ", "get ", "detail "):
            if t.startswith(prefix):
                tid = t[len(prefix):].strip()
                item = self.get_todo(tid)
                if not item:
                    return f"Todo '{tid}' not found."
                lines = [
                    f"[{item['id']}] [{item.get('priority','').upper()}/{item.get('category','')}] {item['title']}",
                    f"  Status:  {item.get('status','')}",
                    f"  Created: {(item.get('created_at') or '')[:10]}",
                ]
                if item.get("description"):
                    lines.append(f"  Desc:    {item['description']}")
                if item.get("context"):
                    lines.append(f"  Context: {item['context']}")
                if item.get("due_date"):
                    lines.append(f"  Due:     {item['due_date']}")
                if item.get("tags"):
                    lines.append(f"  Tags:    {', '.join(item['tags'])}")
                return "\n".join(lines)

        # "purge [N]" — remove old completed todos
        if t.startswith("purge"):
            parts = t.split()
            days = 30
            if len(parts) > 1:
                try:
                    days = int(parts[1])
                except ValueError:
                    pass
            n = self.purge_old(days=days)
            return f"Purged {n} completed todo(s) older than {days} days."

        # "backup"
        if "backup" in t:
            path = self.backup()
            return f"Backup saved: {path}" if path else "Backup failed — check logs."

        # "stats" — richer breakdown
        if "stats" in t or "breakdown" in t:
            s = self.get_stats()
            pri = s["by_priority"]
            cat = s["by_category"]
            aging = s["aging"]
            lines = [
                f"Pending: {s['pending']}  Done: {s['done']}  Snoozed: {s['snoozed']}",
                f"Priority: critical={pri['critical']} high={pri['high']} medium={pri['medium']} low={pri['low']}",
                f"Category: " + "  ".join(f"{k}={v}" for k, v in cat.items()),
                f"Age: " + "  ".join(f"{k}={v}" for k, v in aging.items()),
            ]
            if s["avg_resolution_days"] is not None:
                lines.append(f"Avg resolution: {s['avg_resolution_days']}d")
            return "\n".join(lines)

        # "delete <id>" / "remove <id>"
        for prefix in ("delete ", "remove "):
            if t.startswith(prefix):
                tid = t[len(prefix):].strip()
                ok = self.delete_todo(tid)
                return "Deleted." if ok else f"Todo '{tid}' not found."

        # "snooze <id> <date>" / "snooze <id> until <date>"
        if t.startswith("snooze "):
            parts = t[7:].strip().split()
            parts = [p for p in parts if p != "until"]
            if len(parts) == 2 and _ISO_DATE_RE.match(parts[1]):
                ok = self.snooze_todo(parts[0], parts[1])
                return "Snoozed." if ok else f"Todo '{parts[0]}' not found or invalid date."
            return "Usage: snooze <id> [until] YYYY-MM-DD"

        # "search <query>"
        if t.startswith("search "):
            query = stripped[7:].strip()
            if query:
                results = self.search_todos(query)
                if not results:
                    return f"No todos matching '{query}'."
                return "\n".join(f"[{i['id']}] [{i['priority'].upper()}] {i['title']}" for i in results)

        # "tag <tagname>"
        if t.startswith("tag "):
            tag_name = stripped[4:].strip()
            if tag_name:
                results = self.get_by_tag(tag_name)
                if not results:
                    return f"No todos tagged '{tag_name}'."
                return "\n".join(f"[{i['id']}] [{i['priority'].upper()}] {i['title']}" for i in results)

        # "upcoming" / "due soon" / "next week"
        if any(kw in t for kw in ("upcoming", "due soon", "next week")):
            items = self.get_upcoming()
            if not items:
                return "No todos due in the next 7 days."
            return "\n".join(f"[{i['id']}] [{i.get('due_date','')}] {i['title']}" for i in items)

        if any(kw in t for kw in ("recent", "new", "latest", "just added")):
            items = self.get_recent(hours=24)
            if not items:
                return "No todos added in the last 24 hours."
            return "\n".join(f"[{i['id']}] [{i.get('priority','').upper()}] {i['title']}" for i in items)

        # "snooze-days <id> <N>" — relative snooze
        if t.startswith("snooze-days "):
            parts = t[12:].strip().split()
            if len(parts) == 2:
                try:
                    days_int = int(parts[1])
                    ok = self.snooze_days(parts[0], days_int)
                    return f"Snoozed for {days_int} day(s)." if ok else f"Todo '{parts[0]}' not found or invalid days."
                except ValueError:
                    pass
            return "Usage: snooze-days <id> <N>"

        # "bulk done <category>"
        if t.startswith("bulk done "):
            cat = t[10:].strip()
            if cat in CATEGORIES:
                n = self.bulk_done_by_category(cat)
                return f"Marked {n} {cat} todo(s) as done."
            return f"Unknown category '{cat}'. Valid: {', '.join(sorted(CATEGORIES))}"

        # Default: pending list
        return self.format_ntfy_list()

    def get_stats_by_category(self) -> dict:
        """Return pending counts broken down by category."""
        pending = self.get_pending()
        stats = {cat: 0 for cat in CATEGORIES}
        for t in pending:
            cat = t.get("category", "action")
            if cat in stats:
                stats[cat] += 1
        return stats

    def clear_done(self) -> int:
        """Remove all completed todos. Returns count removed."""
        self._refresh()
        before = len(self._todos)
        self._todos = [t for t in self._todos if t.get("status") != "done"]
        # Rebuild index so _find() doesn't return ghost entries
        self._id_index = {t["id"]: t for t in self._todos if t.get("id")}
        removed = before - len(self._todos)
        if removed:
            self._save()
            log.info("Cleared %d completed todos", removed)
        return removed

    def get_snoozed(self) -> list[dict]:
        """Return all snoozed todos (still sleeping, not yet expired)."""
        self._refresh()
        today = date.today().isoformat()
        return [t for t in self._todos
                if t.get("status") == "snoozed"
                and (t.get("snoozed_until") or "") > today]

    def append_note(self, todo_id: str, note: str) -> bool:
        """Append a timestamped note to a todo's context field without overwriting it.
        Useful for agents that want to add observations to existing tasks."""
        if not note or not note.strip():
            return False
        self._refresh()
        t = self._find(todo_id)
        if not t:
            return False
        stamp = datetime.utcnow().strftime("%Y-%m-%d")
        existing = t.get("context") or ""
        separator = "\n" if existing else ""
        t["context"] = f"{existing}{separator}[{stamp}] {note.strip()}"
        t["updated_at"] = self._now()
        self._save()
        log.info("Note appended to todo %s", todo_id)
        return True

    def run_maintenance(self, stale_days: int = 7, purge_days: int = 30) -> dict:
        """Single call for scheduled maintenance: escalate overdue + purge old done todos.
        Returns dict with counts. Designed to be called by alfred.py cron loops."""
        escalated = self.escalate_overdue(stale_days=stale_days, _quiet=True)
        purged = self.purge_old(days=purge_days)
        result = {"escalated": len(escalated), "purged": purged}
        log.info("Maintenance: escalated=%d purged=%d", result["escalated"], result["purged"])
        newly_critical = [t for t in escalated if t.get("priority") == "critical"]
        result["newly_critical"] = len(newly_critical)
        if result["escalated"] or result["purged"]:
            parts = [f"{result['escalated']} escalated", f"{result['purged']} purged"]
            if newly_critical:
                parts.append(f"{len(newly_critical)} now CRITICAL")
            body = ", ".join(parts)
            if newly_critical:
                body += ":\n" + "\n".join(f"• {t['title']}" for t in newly_critical[:5])
            _ntfy(body, title="Alii Todo Maintenance",
                  priority="urgent" if newly_critical else "default")
        return result

    # ── Reporting ─────────────────────────────────────────────────────────────

    def daily_digest(self) -> str:
        """Return a formatted digest of all pending todos."""
        pending = self.get_pending()
        if not pending:
            return "No pending todos — all clear!"

        overdue = {t["id"] for t in self.get_overdue()}
        today = date.today().isoformat()

        lines = [f"Alii Owner Todo Digest — {datetime.utcnow().strftime('%Y-%m-%d')}\n"]
        lines.append(f"  {len(pending)} item(s) pending\n")
        lines.append("─" * 50 + "\n")

        for i, t in enumerate(pending, 1):
            pri   = t.get("priority", "medium").upper()
            cat   = t.get("category", "action")
            tid   = t.get("id", "?")
            title = t.get("title", "")
            desc  = t.get("description", "")
            ctx   = t.get("context", "")
            due   = t.get("due_date", "")
            flags = []
            if tid in overdue:
                flags.append("OVERDUE")
            if due and due <= today:
                flags.append(f"DUE {due}")
            flag_str = f" ⚑ {', '.join(flags)}" if flags else ""
            lines.append(f"{i}. [{pri}/{cat}] [{tid}] {title}{flag_str}\n")
            if desc:
                lines.append(f"   {desc}\n")
            if ctx:
                lines.append(f"   context: {ctx}\n")
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
            items.append(f"[{t.get('priority','medium').upper()}/{t.get('category','action')}] {t.get('title','')}")

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
        lines = [f"{i+1}. [{t.get('priority','medium').upper()}] {t.get('title','')}" for i, t in enumerate(pending)]
        return "\n".join(lines)

    def summary(self) -> dict:
        """Return counts by status and priority for health checks."""
        pending = self.get_pending()  # single call — reused for all sub-counts below (includes _refresh)
        today = date.today().isoformat()
        cutoff = (date.today() - timedelta(days=7)).isoformat()

        by_cat = {cat: 0 for cat in CATEGORIES}
        overdue_count = 0
        critical_count = 0
        high_count = 0
        for t in pending:
            cat = t.get("category", "action")
            if cat in by_cat:
                by_cat[cat] += 1
            pri = t.get("priority", "medium")
            if pri == "critical":
                critical_count += 1
            elif pri == "high":
                high_count += 1
            due = t.get("due_date")
            if due and due < today:
                overdue_count += 1
            elif not due:
                created = (t.get("created_at") or "")[:10]
                if created and created < cutoff:
                    overdue_count += 1

        done_count = 0
        snoozed_count = 0
        for t in self._todos:
            s = t.get("status")
            if s == "done":
                done_count += 1
            elif s == "snoozed":
                snoozed_count += 1

        return {
            "total":       len(self._todos),
            "pending":     len(pending),
            "done":        done_count,
            "snoozed":     snoozed_count,
            "critical":    critical_count,
            "high":        high_count,
            "overdue":     overdue_count,
            "by_category": by_cat,
        }


# ── Module-level singleton ──────────────────────────────────────────────────────
try:
    todo = TodoAgent()
except Exception as _e:
    log.error("TodoAgent init failed: %s — using empty fallback", _e)
    # Safe fallback: construct a valid but empty instance without disk access
    todo = object.__new__(TodoAgent)
    todo._todos = []  # type: ignore[attr-defined]
    todo._mtime = 0.0  # type: ignore[attr-defined]
    todo._id_index = {}  # type: ignore[attr-defined]
    log.warning("TodoAgent running in degraded (in-memory only) mode")


# ── Pre-populate todos ──────────────────────────────────────────────────────────
def _prepopulate():
    """Add initial owner todos if not already present."""
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
        try:
            before = len(todo._todos)
            todo.add_todo(**item, deduplicate=True)
            if len(todo._todos) > before:
                added += 1
        except Exception as exc:
            log.error("Pre-populate failed for '%s': %s", item.get("title", "?"), exc)

    log.info("Pre-populate complete (%d new items added)", added)
    return added


# ── CLI ─────────────────────────────────────────────────────────────────────────
def main():
    import argparse
    ap = argparse.ArgumentParser(description="Alii Todo Agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list",       help="List pending todos")
    sub.add_parser("digest",     help="Print daily digest")
    sub.add_parser("ntfy",       help="Send digest via ntfy")
    sub.add_parser("summary",    help="Print counts by status/priority")
    sub.add_parser("clear-done", help="Remove all completed todos")
    sub.add_parser("overdue",    help="List overdue/stale todos")
    sub.add_parser("due-today",  help="List todos due today")
    sub.add_parser("health",     help="Print agent health/score")

    p_up = sub.add_parser("upcoming", help="List todos due within N days")
    p_up.add_argument("--days", type=int, default=7)

    p_tag = sub.add_parser("tag", help="List todos by tag")
    p_tag.add_argument("tag_name")

    p_cmd = sub.add_parser("cmd", help="Natural language command")
    p_cmd.add_argument("text", nargs="+", help="Command text")

    p_add = sub.add_parser("add", help="Add a todo")
    p_add.add_argument("title")
    p_add.add_argument("--desc",     default="")
    p_add.add_argument("--category", default="action")
    p_add.add_argument("--priority", default="medium")
    p_add.add_argument("--context",  default="")
    p_add.add_argument("--due",      default=None, help="Due date YYYY-MM-DD")
    p_add.add_argument("--no-dedup", action="store_true")

    p_done = sub.add_parser("done", help="Mark todo done")
    p_done.add_argument("id")

    p_del = sub.add_parser("delete", help="Delete a todo permanently")
    p_del.add_argument("id")

    p_snz = sub.add_parser("snooze", help="Snooze todo")
    p_snz.add_argument("id")
    p_snz.add_argument("until", help="ISO date e.g. 2026-03-08")

    p_upd = sub.add_parser("update", help="Update a todo field")
    p_upd.add_argument("id")
    p_upd.add_argument("--title",    default=None)
    p_upd.add_argument("--desc",     default=None)
    p_upd.add_argument("--priority", default=None)
    p_upd.add_argument("--category", default=None)
    p_upd.add_argument("--due",      default=None)

    p_cat = sub.add_parser("category", help="List todos by category")
    p_cat.add_argument("cat", choices=sorted(CATEGORIES))

    p_pri = sub.add_parser("priority", help="List todos by priority")
    p_pri.add_argument("pri", choices=sorted(PRIORITIES))

    p_srch = sub.add_parser("search", help="Search todos by keyword")
    p_srch.add_argument("query")
    p_srch.add_argument("--all", action="store_true", help="Include completed todos")

    p_reopen = sub.add_parser("reopen", help="Re-open a completed todo")
    p_reopen.add_argument("id")

    p_esc = sub.add_parser("escalate", help="Bump priority on overdue todos")
    p_esc.add_argument("--days", type=int, default=7, help="Stale threshold in days")

    sub.add_parser("backup",    help="Write a timestamped backup of todos")
    sub.add_parser("stats",     help="Rich breakdown by priority, category, and age")

    p_show = sub.add_parser("show", help="Show full detail for a todo")
    p_show.add_argument("id")

    p_done_list = sub.add_parser("done-list", help="List completed todos")
    p_done_list.add_argument("--limit", type=int, default=20)

    p_purge = sub.add_parser("purge", help="Delete done todos older than N days")
    p_purge.add_argument("--days", type=int, default=30)

    sub.add_parser("snoozed", help="List currently snoozed todos")

    p_note = sub.add_parser("note", help="Append a timestamped note to a todo's context")
    p_note.add_argument("id")
    p_note.add_argument("note", nargs="+")

    p_maint = sub.add_parser("maintenance", help="Run escalate + purge in one shot")
    p_maint.add_argument("--stale-days", type=int, default=7)
    p_maint.add_argument("--purge-days", type=int, default=30)

    p_snzd = sub.add_parser("snooze-days", help="Snooze a todo for N days from today")
    p_snzd.add_argument("id")
    p_snzd.add_argument("days", type=int)

    p_recent = sub.add_parser("recent", help="List todos added in the last N hours")
    p_recent.add_argument("--hours", type=int, default=24)

    p_bdc = sub.add_parser("bulk-done-category", help="Mark all pending todos in a category as done")
    p_bdc.add_argument("category", choices=sorted(CATEGORIES))

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
    elif args.cmd == "summary":
        s = todo.summary()
        print(f"Total: {s['total']}  Pending: {s['pending']}  Done: {s['done']}  Snoozed: {s['snoozed']}  Overdue: {s['overdue']}")
        print(f"  Critical: {s['critical']}  High: {s['high']}")
        print(f"  By category: {s['by_category']}")
    elif args.cmd == "clear-done":
        n = todo.clear_done()
        print(f"Cleared {n} completed todo(s).")
    elif args.cmd == "overdue":
        items = todo.get_overdue()
        if not items:
            print("No overdue todos.")
        else:
            for i, t in enumerate(items, 1):
                due = f" [due {t['due_date']}]" if t.get("due_date") else ""
                print(f"{i}. [{t['priority'].upper()}/{t['category']}] [{t['id']}] {t['title']}{due}")
    elif args.cmd == "add":
        t = todo.add_todo(
            title=args.title,
            description=args.desc,
            category=args.category,
            priority=args.priority,
            context=args.context,
            due_date=args.due,
            deduplicate=not args.no_dedup,
        )
        if not t:
            print("Error: could not add todo (blank title or invalid input).")
        else:
            print(f"Added [{t['id']}]: {t['title']}")
    elif args.cmd == "done":
        ok = todo.complete_todo(args.id)
        print("Done." if ok else f"Todo '{args.id}' not found.")
    elif args.cmd == "delete":
        ok = todo.delete_todo(args.id)
        print("Deleted." if ok else f"Todo '{args.id}' not found.")
    elif args.cmd == "snooze":
        ok = todo.snooze_todo(args.id, args.until)
        print("Snoozed." if ok else f"Todo '{args.id}' not found or invalid date.")
    elif args.cmd == "update":
        fields = {}
        if args.title:    fields["title"] = args.title
        if args.desc:     fields["description"] = args.desc
        if args.priority: fields["priority"] = args.priority
        if args.category: fields["category"] = args.category
        if args.due:      fields["due_date"] = args.due
        ok = todo.update_todo(args.id, **fields)
        print("Updated." if ok else f"Todo '{args.id}' not found.")
    elif args.cmd == "category":
        items = todo.get_by_category(args.cat)
        for i, t in enumerate(items, 1):
            print(f"{i}. [{t['priority'].upper()}] [{t['id']}] {t['title']}")
    elif args.cmd == "priority":
        items = todo.get_by_priority(args.pri)
        for i, t in enumerate(items, 1):
            print(f"{i}. [{t['category']}] [{t['id']}] {t['title']}")
    elif args.cmd == "search":
        items = todo.search_todos(args.query, include_done=args.all)
        if not items:
            print(f"No todos matching '{args.query}'.")
        else:
            for i, t in enumerate(items, 1):
                status = f" [{t['status']}]" if t.get("status") != "pending" else ""
                print(f"{i}. [{t['priority'].upper()}/{t['category']}] [{t['id']}]{status} {t['title']}")
    elif args.cmd == "due-today":
        items = todo.get_due_today()
        if not items:
            print("Nothing due today.")
        else:
            for i, t in enumerate(items, 1):
                print(f"{i}. [{t['priority'].upper()}/{t['category']}] [{t['id']}] {t['title']}")
    elif args.cmd == "upcoming":
        items = todo.get_upcoming(days=args.days)
        if not items:
            print(f"No todos due in the next {args.days} days.")
        else:
            for i, t in enumerate(items, 1):
                print(f"{i}. [{t['priority'].upper()}/{t['category']}] [{t['id']}] [{t.get('due_date','')}] {t['title']}")
    elif args.cmd == "health":
        h = todo.get_health()
        print(f"Score: {h['score']}  Healthy: {h['healthy']}")
        s = h["summary"]
        print(f"  Pending: {s['pending']}  Critical: {s['critical']}  Overdue: {s['overdue']}")
    elif args.cmd == "tag":
        items = todo.get_by_tag(args.tag_name)
        if not items:
            print(f"No todos tagged '{args.tag_name}'.")
        else:
            for i, t in enumerate(items, 1):
                print(f"{i}. [{t['priority'].upper()}/{t['category']}] [{t['id']}] {t['title']}")
    elif args.cmd == "reopen":
        ok = todo.reopen_todo(args.id)
        print("Reopened." if ok else f"Todo '{args.id}' not found.")
    elif args.cmd == "escalate":
        escalated = todo.escalate_overdue(stale_days=args.days)
        if not escalated:
            print("No overdue todos to escalate.")
        else:
            for t in escalated:
                print(f"[{t['id']}] → {t['priority'].upper()}: {t['title']}")
    elif args.cmd == "backup":
        path = todo.backup()
        print(f"Backup saved: {path}" if path else "Backup failed — check logs.")
    elif args.cmd == "stats":
        s = todo.get_stats()
        pri = s["by_priority"]
        cat = s["by_category"]
        aging = s["aging"]
        print(f"Pending: {s['pending']}  Done: {s['done']}  Snoozed: {s['snoozed']}")
        print(f"Priority: critical={pri['critical']} high={pri['high']} medium={pri['medium']} low={pri['low']}")
        print(f"Category: " + "  ".join(f"{k}={v}" for k, v in cat.items()))
        print(f"Age:      " + "  ".join(f"{k}={v}" for k, v in aging.items()))
        if s["avg_resolution_days"] is not None:
            print(f"Avg resolution: {s['avg_resolution_days']}d")
    elif args.cmd == "show":
        item = todo.get_todo(args.id)
        if not item:
            print(f"Todo '{args.id}' not found.")
        else:
            for k, v in item.items():
                print(f"  {k:16}: {v}")
    elif args.cmd == "done-list":
        items = todo.get_done(limit=args.limit)
        if not items:
            print("No completed todos.")
        else:
            for i, t in enumerate(items, 1):
                comp = (t.get("completed_at") or "")[:10]
                print(f"{i}. [{comp}] [{t['id']}] {t['title']}")
    elif args.cmd == "purge":
        n = todo.purge_old(days=args.days)
        print(f"Purged {n} completed todo(s) older than {args.days} days.")
    elif args.cmd == "snoozed":
        items = todo.get_snoozed()
        if not items:
            print("No snoozed todos.")
        else:
            for i, t in enumerate(items, 1):
                print(f"{i}. [until {t.get('snoozed_until','')}] [{t['id']}] {t['title']}")
    elif args.cmd == "note":
        note_text = " ".join(args.note)
        ok = todo.append_note(args.id, note_text)
        print("Note appended." if ok else f"Todo '{args.id}' not found.")
    elif args.cmd == "maintenance":
        result = todo.run_maintenance(stale_days=args.stale_days, purge_days=args.purge_days)
        print(f"Maintenance complete: escalated={result['escalated']} purged={result['purged']} newly_critical={result.get('newly_critical', 0)}")
    elif args.cmd == "snooze-days":
        ok = todo.snooze_days(args.id, args.days)
        print(f"Snoozed for {args.days} day(s)." if ok else f"Todo '{args.id}' not found or invalid days.")
    elif args.cmd == "recent":
        items = todo.get_recent(hours=args.hours)
        if not items:
            print(f"No todos added in the last {args.hours} hours.")
        else:
            for i, t in enumerate(items, 1):
                print(f"{i}. [{t['priority'].upper()}/{t['category']}] [{t['id']}] {t['title']}")
    elif args.cmd == "bulk-done-category":
        n = todo.bulk_done_by_category(args.category)
        print(f"Marked {n} {args.category} todo(s) as done.")
    elif args.cmd == "cmd":
        print(todo.handle_command(" ".join(args.text)))


if __name__ == "__main__":
    _prepopulate()
    main()
