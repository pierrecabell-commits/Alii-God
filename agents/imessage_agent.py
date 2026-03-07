#!/usr/bin/env python3
"""
iMessage Agent — BlueBubbles REST API primary, SSH AppleScript fallback.
Polls every 10s for new messages from owner's phone. Routes as commands.

BlueBubbles setup: https://bluebubbles.app — run on macOS host, expose on Tailscale.
"""

import json, logging, os, subprocess, sys, time, requests
from datetime import datetime
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
try:
    from vault.vault_client import get_secret
except ImportError:
    def get_secret(k, d=None): return os.getenv(k, d)

try:
    from config import WORKDIR as _CFG_WORKDIR, LOG_DIR, MEMORY_DIR
    WORKDIR    = _CFG_WORKDIR
    LOG_FILE   = LOG_DIR / "imessage_agent.log"
    STATE_FILE = MEMORY_DIR / "imessage_bb_state.json"
except ImportError:
    WORKDIR    = _project_root
    LOG_FILE   = _project_root / "logs" / "imessage_agent.log"
    STATE_FILE = _project_root / "memory" / "imessage_bb_state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [imessage] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("alii.imessage")

def _cfg(key, default=None):
    return get_secret(key, os.getenv(key, default))

def _state() -> dict:
    if STATE_FILE.exists():
        try: return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError): pass
    return {}

def _save_state(s: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(s, indent=2))

def ntfy(msg: str, title: str = "iMessage"):
    try:
        requests.post("http://localhost:8080/alii-imessage",
                      data=msg.encode(), headers={"Title": title}, timeout=3)
    except requests.RequestException: pass

# ── BlueBubbles API ────────────────────────────────────────────────────────────

class BlueBubblesClient:
    def __init__(self):
        self.url      = _cfg("BLUEBUBBLES_URL", "").rstrip("/")
        self.password = _cfg("BLUEBUBBLES_PASSWORD", "")
        self.timeout  = 10

    def _get(self, path: str, **params) -> dict | None:
        if not self.url:
            return None
        try:
            r = requests.get(f"{self.url}{path}",
                             params={"password": self.password, **params},
                             timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.debug(f"BlueBubbles GET {path} error: {e}")
            return None

    def _post(self, path: str, data: dict) -> dict | None:
        if not self.url:
            return None
        try:
            r = requests.post(f"{self.url}{path}",
                              json={**data, "password": self.password},
                              timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.debug(f"BlueBubbles POST {path} error: {e}")
            return None

    def available(self) -> bool:
        r = self._get("/api/v1/server/info")
        return r is not None

    def message_count(self) -> int | None:
        r = self._get("/api/v1/message/count")
        if r and "data" in r:
            return r["data"].get("total", 0)
        return None

    def recent_chats(self, limit: int = 10) -> list:
        r = self._get("/api/v1/chat/query", limit=limit, offset=0, sort="lastmessage")
        if r and "data" in r:
            return r["data"] if isinstance(r["data"], list) else r["data"].get("chats", [])
        return []

    def messages(self, chat_guid: str, limit: int = 20) -> list:
        r = self._get("/api/v1/message/query", chatGuid=chat_guid, limit=limit, offset=0)
        if r and "data" in r:
            d = r["data"]
            return d if isinstance(d, list) else d.get("messages", [])
        return []

    def send(self, chat_guid: str, message: str) -> bool:
        r = self._post("/api/v1/message/text", {"chatGuid": chat_guid, "message": message})
        return r is not None and r.get("status") in (200, 201, "ok", True)

# ── SSH AppleScript Fallback ────────────────────────────────────────────────────

def _ssh_run(script: str) -> str | None:
    for host in [_cfg("MACBOOK_LOCAL_IP"), _cfg("MACBOOK_TAILSCALE_IP")]:
        if not host:
            continue
        try:
            r = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=5",
                 f"{_cfg('MACBOOK_SSH_USER', 'pierre')}@{host}",
                 f"osascript -e '{script}'"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception as e:
            log.debug(f"SSH to {host} failed: {e}")
    return None

def ssh_send(phone: str, message: str) -> bool:
    escaped = message.replace("'", "\\'")
    script  = f'tell application "Messages" to send "{escaped}" to buddy "{phone}" of service "iMessage"'
    result  = _ssh_run(script)
    return result is not None

# ── Command Processor ──────────────────────────────────────────────────────────

def process_command(text: str, chat_guid: str, bb: BlueBubblesClient) -> str:
    txt = text.strip().lower()
    phone = _cfg("ALII_PHONE_NUMBER", "")

    if txt == "status":
        try:
            r = subprocess.run(["systemctl", "--user", "list-units", "--state=running", "--no-pager"],
                               capture_output=True, text=True, timeout=10)
            lines = [l for l in r.stdout.splitlines() if "alii-" in l.lower()][:8]
            return "Services running:\n" + "\n".join(lines) if lines else "No alii services running"
        except (OSError, subprocess.TimeoutExpired):
            return "Status check failed"

    elif txt.startswith("run "):
        cmd = text[4:].strip()
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            out = (r.stdout + r.stderr).strip()[:500] or "(no output)"
            return f"$ {cmd}\n{out}"
        except Exception as e:
            return f"Error: {e}"

    elif txt == "report":
        try:
            status_file = WORKDIR / "data" / "alii_status.json"
            if status_file.exists():
                data = json.loads(status_file.read_text())
                return f"System report:\n{json.dumps(data, indent=2)[:500]}"
        except (json.JSONDecodeError, OSError): pass
        return "No report available"

    elif txt in ("money", "revenue"):
        try:
            rev_file = WORKDIR / "data" / "revenue_live.json"
            if rev_file.exists():
                data = json.loads(rev_file.read_text())
                return f"Revenue: {json.dumps(data, indent=2)[:400]}"
        except (json.JSONDecodeError, OSError): pass
        return "No revenue data available"

    elif txt == "secure":
        try:
            r = subprocess.run(["python3", str(WORKDIR / "security_agent.py"), "--quick"],
                               capture_output=True, text=True, timeout=30)
            return r.stdout.strip()[:400] or "Security check complete"
        except (OSError, subprocess.TimeoutExpired):
            return "Security check failed"

    elif txt == "help":
        return ("Commands: status | run <cmd> | report | money | secure | help\n"
                "Or ask me anything!")

    else:
        # Ask Ollama
        try:
            r = requests.post("http://localhost:11434/api/generate",
                              json={"model": "llama3.2:3b", "prompt": text, "stream": False},
                              timeout=30)
            if r.ok:
                return r.json().get("response", "")[:500]
        except (requests.RequestException, ValueError, KeyError): pass
        return f"Got: {text}"

# ── Main Poll Loop ─────────────────────────────────────────────────────────────

def main():
    log.info("iMessage agent starting (BlueBubbles primary, SSH fallback)")
    bb    = BlueBubblesClient()
    state = _state()
    owner_phone = _cfg("ALII_PHONE_NUMBER", "")

    if not bb.url:
        log.warning("BLUEBUBBLES_URL not set — SSH-only mode")
    elif bb.available():
        log.info(f"BlueBubbles available at {bb.url}")
    else:
        log.warning(f"BlueBubbles not reachable at {bb.url} — SSH fallback mode")

    while True:
        try:
            if bb.url and bb.available():
                chats = bb.recent_chats(limit=20)
                for chat in chats:
                    guid = chat.get("guid", "")
                    participants = chat.get("participants", [])

                    # Check if this is the owner's chat
                    is_owner_chat = False
                    if owner_phone:
                        for p in participants:
                            handle = p.get("address", p.get("id", ""))
                            if owner_phone.replace("+1", "").replace("-", "").replace(" ", "") in \
                               handle.replace("+1", "").replace("-", "").replace(" ", ""):
                                is_owner_chat = True
                                break

                    # Get last message count from state
                    last_count = state.get(guid, {}).get("last_count", 0)
                    msgs = bb.messages(guid, limit=5)

                    if not msgs:
                        continue

                    # Check for new messages
                    new_msgs = [m for m in msgs
                                if not m.get("isFromMe", True)
                                and m.get("dateCreated", 0) > state.get(guid, {}).get("last_ts", 0)]

                    state_dirty = False
                    for msg in new_msgs:
                        text = msg.get("text", "").strip()
                        ts   = msg.get("dateCreated", 0)
                        if not text:
                            continue
                        log.info(f"New message from chat {guid}: {text[:60]}")
                        response = process_command(text, guid, bb)
                        if response:
                            sent = bb.send(guid, response)
                            if not sent and is_owner_chat and owner_phone:
                                ssh_send(owner_phone, response)
                            log.info(f"Replied: {response[:60]}")

                        # Update state
                        if guid not in state:
                            state[guid] = {}
                        state[guid]["last_ts"] = max(state[guid].get("last_ts", 0), ts)
                        state_dirty = True

                    if state_dirty:
                        _save_state(state)

        except KeyboardInterrupt:
            log.info("Stopping iMessage agent")
            break
        except Exception as e:
            log.error(f"Poll error: {e}")

        time.sleep(10)

if __name__ == "__main__":
    main()
