#!/usr/bin/env python3
"""
agents/imessage_bridge.py — Two-way iMessage bridge (HTTP v2)
- Polls Mac controller HTTP API every 10s
- Deduplicates by rowid (seen_ids set, persisted to state file)
- Strict is_from_me=0 filter — no echo loops
- AI chain: anthropic haiku → litellm/smart → ollama/dolphin-phi
- Per-number conversation history (last 12 turns)
- Action tag execution: [SHELL: cmd], [NOTIFY: text], [OPEN: app]
- Flask health endpoint on :7010
"""
import os, re, sys, json, time, threading, logging
from pathlib import Path
from datetime import datetime, timezone
from flask import Flask, jsonify

try:
    import requests as _req
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request as _urllib_req

# ─── Paths (from centralized config) ───────────────────────────────────────────
from config import (WORKDIR, LOG_DIR, DATA_DIR, LITELLM_URL as _LITELLM_URL,
                    OLLAMA_URL as _OLLAMA_URL, MAC_CONTROLLER_PORT as _MAC_CTRL_PORT,
                    ENV_FILE, load_env)
PID_FILE    = LOG_DIR / "imessage_bridge.pid"
LOG_FILE    = LOG_DIR / "imessage_bridge.log"
STATE_FILE  = DATA_DIR / "imessage_bridge_state.json"
POLL_INTERVAL = 10
CONTACT_NUM   = "3308073932"
MAX_SEEN_IDS  = 2000   # cap seen_ids to avoid unbounded growth
HISTORY_TURNS = 12     # per-number conversation turns to keep

# ─── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(str(LOG_FILE)), logging.StreamHandler()],
)
log = logging.getLogger("imessage_bridge")

# ─── Load .env ─────────────────────────────────────────────────────────────────
load_env()
MAC_IP             = os.environ.get("MACBOOK_TAILSCALE_IP", "")
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")
LITELLM_URL        = _LITELLM_URL
OLLAMA_URL         = _OLLAMA_URL
MAC_CONTROLLER_PORT = _MAC_CTRL_PORT

def _mac_url(endpoint):
    return f"http://{MAC_IP}:{MAC_CONTROLLER_PORT}{endpoint}"

# ─── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    f"You are Alii, autonomous AI built by Pierre Cabell in Akron Ohio. "
    f"You control his MacBook and iPhone via mac_controller at {MAC_IP}:{MAC_CONTROLLER_PORT}. "
    f"You can run shell commands (POST /run), send iMessages (POST /imessage), "
    f"take screenshots (GET /screenshot), open apps (POST /open), "
    f"send notifications (POST /notify), run Shortcuts (POST /shortcut). "
    f"When asked to do something, DO IT. Be direct. Never echo user input. "
    f"To execute actions, embed tags in your response: "
    f"[SHELL: command] to run a shell command, "
    f"[NOTIFY: message] to send a macOS notification, "
    f"[OPEN: app_or_url] to open an app or URL. "
    f"Keep iMessage replies under 400 chars unless the user asks for more detail."
)

# ─── State ─────────────────────────────────────────────────────────────────────
_state_lock = threading.Lock()
_state = {
    "last_unix_ts": 0.0,
    "messages_handled": 0,
    "seen_ids": [],          # list of ints (serializable), converted to set in memory
}
_seen_ids: set = set()       # runtime set of processed rowids

def _load_state():
    global _state, _seen_ids
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if STATE_FILE.exists():
            loaded = json.loads(STATE_FILE.read_text())
            _state.update(loaded)
            _seen_ids = set(_state.get("seen_ids", []))
            log.info(f"State loaded: last_ts={_state['last_unix_ts']:.0f}, seen_ids={len(_seen_ids)}")
    except Exception as e:
        log.warning(f"state load error: {e}")

def _save_state():
    try:
        # Trim seen_ids to cap — keep most recent (they're ints so sort descending)
        ids_list = sorted(_seen_ids, reverse=True)[:MAX_SEEN_IDS]
        _state["seen_ids"] = ids_list
        STATE_FILE.write_text(json.dumps(_state, indent=2))
    except Exception as e:
        log.warning(f"state save error: {e}")

_load_state()

# ─── Conversation history per number ───────────────────────────────────────────
_conv_lock = threading.Lock()
_conv_history: dict[str, list] = {}   # number -> list of {role, content}

def _get_messages(number: str, user_text: str) -> list:
    """Build message list with system prompt + last N turns + new user message."""
    with _conv_lock:
        history = _conv_history.get(number, [])
        # Trim to last HISTORY_TURNS (each turn = user+assistant = 2 entries)
        history = history[-(HISTORY_TURNS * 2):]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})
        return messages, history

def _save_turn(number: str, user_text: str, assistant_text: str):
    with _conv_lock:
        hist = _conv_history.setdefault(number, [])
        hist.append({"role": "user", "content": user_text})
        hist.append({"role": "assistant", "content": assistant_text})
        # Trim
        _conv_history[number] = hist[-(HISTORY_TURNS * 2):]

def _append_context(number: str, context_note: str):
    """Append a system-level note to history (action results)."""
    with _conv_lock:
        hist = _conv_history.setdefault(number, [])
        hist.append({"role": "user", "content": f"[action result]: {context_note}"})
        hist.append({"role": "assistant", "content": "Got it."})
        _conv_history[number] = hist[-(HISTORY_TURNS * 2):]

# ─── HTTP helpers ──────────────────────────────────────────────────────────────
def _http_get(url, timeout=5):
    if HAS_REQUESTS:
        r = _req.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    else:
        with _urllib_req.urlopen(_urllib_req.Request(url), timeout=timeout) as resp:
            return json.loads(resp.read())

def _http_post(url, data, headers=None, timeout=15):
    if HAS_REQUESTS:
        r = _req.post(url, json=data, headers=headers or {}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    else:
        payload = json.dumps(data).encode()
        h = {"Content-Type": "application/json"}
        if headers:
            h.update(headers)
        req = _urllib_req.Request(url, payload, h)
        with _urllib_req.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

# ─── Mac online / send / poll ───────────────────────────────────────────────────
def mac_is_online() -> bool:
    if not MAC_IP:
        return False
    try:
        _http_get(_mac_url("/health"), timeout=2)
        return True
    except Exception:
        return False

def send_imessage(number: str, msg: str) -> str:
    if not mac_is_online():
        log.debug("Mac offline — skipping send")
        return "[mac offline]"
    try:
        result = _http_post(_mac_url("/imessage"), {"number": number, "message": msg})
        log.info(f"→ iMessage {number}: {msg[:60]}")
        return str(result)
    except Exception as e:
        log.warning(f"send_imessage failed: {e}")
        return f"[send error: {e}]"

def poll_messages() -> list:
    """Return new incoming messages (is_from_me=0, unseen rowid) from contact."""
    if not mac_is_online():
        return []
    last_ts = _state.get("last_unix_ts", 0.0) or (time.time() - 1800)
    try:
        result = _http_get(_mac_url(f"/imessage/poll?since={last_ts}"), timeout=10)
        if "error" in result:
            log.warning(f"poll error: {result['error']}")
            return []
        messages = result.get("messages", [])
        filtered = []
        for m in messages:
            # Hard filter: skip outgoing messages
            if m.get("is_from_me"):
                continue
            # Hard filter: must be from our contact
            handle = str(m.get("handle", ""))
            if CONTACT_NUM not in handle:
                continue
            # Must have text
            if not m.get("text"):
                continue
            # Dedup by rowid
            rowid = m.get("id")
            if rowid is not None and rowid in _seen_ids:
                continue
            filtered.append(m)
        return filtered
    except Exception as e:
        log.warning(f"poll_messages error: {e}")
        return []

# ─── Action tag execution ───────────────────────────────────────────────────────
ACTION_RE = re.compile(
    r'\[(SHELL|NOTIFY|OPEN):\s*(.*?)\]',
    re.IGNORECASE | re.DOTALL
)

def execute_actions(response_text: str, number: str) -> str:
    """Find and execute [SHELL:], [NOTIFY:], [OPEN:] tags. Returns cleaned text."""
    if not mac_is_online():
        # Strip tags but don't execute
        return ACTION_RE.sub('', response_text).strip()

    clean = response_text
    for match in ACTION_RE.finditer(response_text):
        tag, arg = match.group(1).upper(), match.group(2).strip()
        arg_short = arg[:80]
        try:
            if tag == "SHELL":
                log.info(f"[ACTION] SHELL: {arg_short}")
                result = _http_post(_mac_url("/run"), {"cmd": arg})
                out = result.get("stdout", "") or result.get("stderr", "")
                out = out[:300].strip()
                log.info(f"[ACTION] SHELL result: {out[:80]}")
                _append_context(number, f"SHELL `{arg_short}` → {out}")
            elif tag == "NOTIFY":
                log.info(f"[ACTION] NOTIFY: {arg_short}")
                _http_post(_mac_url("/notify"), {"title": "Alii", "body": arg})
                _append_context(number, f"NOTIFY sent: {arg_short}")
            elif tag == "OPEN":
                log.info(f"[ACTION] OPEN: {arg_short}")
                _http_post(_mac_url("/open"), {"app": arg})
                _append_context(number, f"OPEN: {arg_short}")
        except Exception as e:
            log.warning(f"[ACTION] {tag} failed: {e}")
        # Remove the tag from the reply text
        clean = clean.replace(match.group(0), "").strip()

    return clean.strip()

# ─── AI routing chain ───────────────────────────────────────────────────────────
def _call_anthropic(messages: list) -> str:
    """Try claude-3-5-haiku-20241022 via anthropic SDK."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic SDK not installed")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    # Extract system message, pass rest
    sys_content = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_msgs = [m for m in messages if m["role"] != "system"]
    resp = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=512,
        system=sys_content,
        messages=user_msgs,
    )
    return resp.content[0].text.strip()

def _call_litellm(messages: list) -> str:
    """Try litellm proxy model=smart."""
    headers = {"Content-Type": "application/json"}
    if LITELLM_MASTER_KEY:
        headers["Authorization"] = f"Bearer {LITELLM_MASTER_KEY}"
    data = {"model": "smart", "messages": messages, "max_tokens": 512, "stream": False}
    result = _http_post(f"{LITELLM_URL}/chat/completions", data, headers=headers, timeout=30)
    return result["choices"][0]["message"]["content"].strip()

def _call_ollama(messages: list) -> str:
    """Fallback: ollama dolphin-phi via /api/chat."""
    data = {"model": "dolphin-phi", "messages": messages, "stream": False}
    result = _http_post(f"{OLLAMA_URL}/api/chat", data, timeout=60)
    return result["message"]["content"].strip()

def handle_message(number: str, text: str) -> str:
    """Route to AI chain with conversation history. Returns reply text."""
    messages, _ = _get_messages(number, text)

    # 1. Try Anthropic haiku
    try:
        reply = _call_anthropic(messages)
        log.info(f"AI: anthropic haiku ({len(reply)} chars)")
        _save_turn(number, text, reply)
        return reply
    except Exception as e:
        log.warning(f"anthropic failed: {e}, trying litellm")

    # 2. Try LiteLLM smart
    try:
        reply = _call_litellm(messages)
        log.info(f"AI: litellm/smart ({len(reply)} chars)")
        _save_turn(number, text, reply)
        return reply
    except Exception as e:
        log.warning(f"litellm failed: {e}, trying ollama")

    # 3. Fallback ollama
    try:
        reply = _call_ollama(messages)
        log.info(f"AI: ollama/dolphin-phi ({len(reply)} chars)")
        _save_turn(number, text, reply)
        return reply
    except Exception as e:
        log.error(f"all AI backends failed: {e}")
        return "[Alii: all AI backends unavailable]"

# ─── Poll loop ─────────────────────────────────────────────────────────────────
_bridge_status = {
    "running": False, "last_poll": None,
    "messages_handled": 0, "errors": 0,
    "last_backend": None,
}

def poll_loop():
    _bridge_status["running"] = True
    log.info(f"iMessage bridge v2 starting — poll every {POLL_INTERVAL}s")
    log.info(f"Mac controller: {_mac_url('')} | seen_ids loaded: {len(_seen_ids)}")

    while True:
        try:
            msgs = poll_messages()
            _bridge_status["last_poll"] = datetime.now(timezone.utc).isoformat()

            if msgs:
                max_ts = _state.get("last_unix_ts", 0.0)
                for m in msgs:
                    rowid   = m.get("id")
                    text    = m.get("text", "").strip()
                    unix_ts = m.get("unix_ts", 0)
                    handle  = m.get("handle", "unknown")

                    log.info(f"← id={rowid} from={handle} is_from_me={m.get('is_from_me')} text={text[:80]}")

                    # Generate reply
                    reply = handle_message(CONTACT_NUM, text)

                    # Execute any action tags, get clean text
                    clean_reply = execute_actions(reply, CONTACT_NUM)

                    # Send reply (only if there's actual text after stripping tags)
                    if clean_reply:
                        send_imessage(CONTACT_NUM, clean_reply)
                    else:
                        log.info("Reply was action-only, no text to send")

                    # Mark as seen
                    if rowid is not None:
                        _seen_ids.add(rowid)
                    if unix_ts and unix_ts > max_ts:
                        max_ts = unix_ts

                    _bridge_status["messages_handled"] += 1

                # Persist state once per batch
                with _state_lock:
                    _state["last_unix_ts"] = max_ts
                    _state["messages_handled"] = _bridge_status["messages_handled"]
                    _save_state()

        except Exception as e:
            _bridge_status["errors"] += 1
            log.error(f"poll_loop error: {e}", exc_info=True)

        time.sleep(POLL_INTERVAL)

# ─── Flask health endpoint ──────────────────────────────────────────────────────
app = Flask("imessage_bridge")

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "running": _bridge_status["running"],
        "last_poll": _bridge_status["last_poll"],
        "messages_handled": _bridge_status["messages_handled"],
        "errors": _bridge_status["errors"],
        "mac_ip": MAC_IP or "NOT_SET",
        "mac_online": mac_is_online(),
        "seen_ids": len(_seen_ids),
        "contact": CONTACT_NUM,
        "mode": "http_v2",
        "ai_chain": "anthropic-haiku → litellm/smart → ollama/dolphin-phi",
    })

# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))
    log.info(f"PID {os.getpid()} written to {PID_FILE}")
    log.info(f"AI chain: anthropic-haiku → litellm/smart → ollama/dolphin-phi")
    log.info(f"ANTHROPIC_API_KEY: {'set' if ANTHROPIC_API_KEY else 'NOT SET'}")

    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()

    log.info("Flask health endpoint on :7010")
    app.run(host="0.0.0.0", port=7010, use_reloader=False, threaded=True)

if __name__ == "__main__":
    main()
