#!/usr/bin/env python3
"""
mac_controller.py — Alii MacBook Companion Service
===================================================
Runs on the MacBook (macOS). Wraps Messages.app via:
  - Read: SQLite ~/Library/Messages/chat.db (no Apple approval needed)
  - Send: osascript AppleScript

Pierre: copy this file to the Mac and run:
  pip3 install flask && python3 mac_controller.py

Or install as a LaunchAgent (see com.alii.mac_controller.plist in same directory).

Endpoints:
  GET  /health                        → {"status": "ok", "platform": "macos"}
  GET  /messages/new?since_rowid=N    → list of new messages
  POST /send  {"handle":"+1...", "text":"..."}  → sends via AppleScript
  GET  /status                        → full system status

Port: 7020 (matches MACBOOK_CONTROLLER_PORT on precision)
"""

import os
import sys
import json
import sqlite3
import subprocess
import logging
import time
from pathlib import Path
from datetime import datetime, timezone

# ── Flask (install with: pip3 install flask) ─────────────────────────────────
try:
    from flask import Flask, request, jsonify
except ImportError:
    print("ERROR: flask not installed. Run: pip3 install flask")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
PORT        = int(os.environ.get("MAC_CONTROLLER_PORT", 7020))
CHAT_DB     = Path.home() / "Library" / "Messages" / "chat.db"
LOG_FILE    = Path.home() / "Library" / "Logs" / "alii_mac_controller.log"
START_TIME  = time.time()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(LOG_FILE), mode="a"),
    ],
)
log = logging.getLogger("mac_controller")

app = Flask(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _db_connect() -> sqlite3.Connection:
    """Open chat.db in read-only mode."""
    if not CHAT_DB.exists():
        raise FileNotFoundError(f"Messages database not found at {CHAT_DB}")
    uri = f"file:{CHAT_DB}?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=5)


def _get_new_messages(since_rowid: int = 0, limit: int = 50) -> list[dict]:
    """Return messages newer than since_rowid from chat.db."""
    results = []
    try:
        conn = _db_connect()
        cur  = conn.cursor()
        cur.execute("""
            SELECT
                m.rowid,
                m.text,
                m.is_from_me,
                datetime(m.date/1000000000 + strftime('%s','2001-01-01'), 'unixepoch') AS sent_at,
                h.id AS handle
            FROM message m
            LEFT JOIN handle h ON m.handle_id = h.rowid
            WHERE m.rowid > ?
              AND m.text IS NOT NULL
              AND m.text != ''
            ORDER BY m.rowid ASC
            LIMIT ?
        """, (since_rowid, limit))
        for row in cur.fetchall():
            results.append({
                "rowid":       row[0],
                "text":        row[1] or "",
                "is_from_me":  bool(row[2]),
                "sent_at":     row[3],
                "handle":      row[4] or "",
            })
        conn.close()
    except Exception as exc:
        log.error("DB read error: %s", exc)
    return results


def _send_imessage(handle: str, text: str) -> bool:
    """Send a message via AppleScript."""
    # Sanitise text — escape backslashes and quotes for AppleScript
    safe_text   = text.replace("\\", "\\\\").replace('"', '\\"')
    safe_handle = handle.replace('"', '\\"')
    script = f'''
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy "{safe_handle}" of targetService
        send "{safe_text}" to targetBuddy
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            log.info("Sent to %s: %s", handle, text[:60])
            return True
        else:
            log.error("AppleScript error: %s", result.stderr[:200])
            return False
    except Exception as exc:
        log.error("Send error: %s", exc)
        return False

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    db_ok = CHAT_DB.exists()
    return jsonify({
        "status":   "ok",
        "platform": "macos",
        "db_accessible": db_ok,
        "uptime_s": round(time.time() - START_TIME),
        "port":     PORT,
    })


@app.route("/messages/new")
def messages_new():
    try:
        since = int(request.args.get("since_rowid", 0))
    except ValueError:
        since = 0
    msgs = _get_new_messages(since_rowid=since)
    return jsonify({
        "messages": msgs,
        "count":    len(msgs),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/send", methods=["POST"])
def send():
    data   = request.get_json(force=True, silent=True) or {}
    handle = data.get("handle", "").strip()
    text   = data.get("text",   "").strip()
    if not handle or not text:
        return jsonify({"ok": False, "error": "handle and text required"}), 400
    ok = _send_imessage(handle, text)
    return jsonify({"ok": ok, "handle": handle, "length": len(text)})


@app.route("/status")
def status():
    try:
        conn = _db_connect()
        cur  = conn.cursor()
        cur.execute("SELECT MAX(rowid) FROM message")
        max_rowid = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM message WHERE date > (strftime('%s','now') - strftime('%s','2001-01-01') - 86400) * 1000000000")
        msgs_24h = cur.fetchone()[0]
        conn.close()
    except Exception:
        max_rowid = -1
        msgs_24h  = -1
    return jsonify({
        "status":    "ok",
        "platform":  "macos",
        "db_path":   str(CHAT_DB),
        "max_rowid": max_rowid,
        "msgs_24h":  msgs_24h,
        "uptime_s":  round(time.time() - START_TIME),
    })


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("Alii mac_controller starting on 0.0.0.0:%d", PORT)
    log.info("Messages DB: %s (exists=%s)", CHAT_DB, CHAT_DB.exists())
    if not CHAT_DB.exists():
        log.warning("chat.db not found — send will work but read will return empty")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
