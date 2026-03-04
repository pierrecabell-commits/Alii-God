#!/usr/bin/env python3
"""
alii_core.py — Unified Alii Brain
Intelligent router: claude_api | claude_code | litellm | ollama
Memory: SQLite episodic/semantic/working
Tools: shell, alfred, file I/O, iMessage, ray
Streaming CLI with ANSI colors
"""
import os, sys, json, time, sqlite3, threading, subprocess, readline, re, shutil
from datetime import datetime, timezone
from pathlib import Path
import urllib.request, urllib.error

# ─── Paths & constants ────────────────────────────────────────────────────────
WORKDIR    = Path("/home/avalii/moltbot")
DB_PATH    = WORKDIR / "memory/alii_core.db"
PERF_LOG   = WORKDIR / "memory/logs/model_perf.json"
LOG_DIR    = WORKDIR / "logs"
HISTORY    = Path.home() / ".alii_history"
ALFRED_URL = "http://127.0.0.1:7000"
LITELLM    = "http://127.0.0.1:4000"
OLLAMA     = "http://127.0.0.1:11434"
VERSION    = "2.0.0"

# ─── Load .env ────────────────────────────────────────────────────────────────
def _load_env():
    env_file = WORKDIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

# ─── ANSI colors ──────────────────────────────────────────────────────────────
C = {
    "reset": "\033[0m", "bold": "\033[1m",
    "cyan": "\033[36m",  "green": "\033[32m",  "yellow": "\033[33m",
    "red": "\033[31m",   "blue": "\033[34m",   "grey": "\033[90m",
    "white": "\033[97m", "magenta": "\033[35m",
}
def c(color, text): return f"{C[color]}{text}{C['reset']}"

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)
_log_file = LOG_DIR / f"alii_core_{datetime.now().strftime('%Y%m%d')}.log"

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}][{level}] {msg}"
    try:
        with open(_log_file, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass

# ─── Memory (SQLite) ─────────────────────────────────────────────────────────
class AliiMemory:
    def __init__(self, path=DB_PATH):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._pragma()
        self._init()

    def _pragma(self):
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-32000")

    def _init(self):
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS episodic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT, content TEXT, backend TEXT,
            ts TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS semantic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE, value TEXT,
            ts TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS working (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT, value TEXT,
            ts TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS ep_ts ON episodic(ts);
        """)
        self._conn.commit()

    def save_turn(self, role, content, backend=""):
        with self._lock:
            self._conn.execute(
                "INSERT INTO episodic(role,content,backend) VALUES(?,?,?)",
                (role, content[:4000], backend))
            self._conn.commit()

    def get_context(self, n=8):
        with self._lock:
            rows = self._conn.execute(
                "SELECT role,content FROM episodic ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
        return list(reversed(rows))

    def count(self):
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM episodic").fetchone()[0]

    def save_fact(self, key, value):
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO semantic(key,value,ts) VALUES(?,?,datetime('now'))",
                (key, str(value)))
            self._conn.commit()

    def get_facts(self, limit=5):
        with self._lock:
            return self._conn.execute(
                "SELECT key,value FROM semantic ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()

_mem_singleton = None
def get_memory():
    global _mem_singleton
    if _mem_singleton is None:
        _mem_singleton = AliiMemory()
    return _mem_singleton

# ─── Performance tracker ──────────────────────────────────────────────────────
PERF_LOG.parent.mkdir(parents=True, exist_ok=True)
_perf_lock = threading.Lock()
_perf_data: dict = {}
_perf_last_save = 0.0

def _load_perf():
    global _perf_data
    try:
        _perf_data = json.loads(PERF_LOG.read_text())
    except Exception:
        _perf_data = {}

def _save_perf():
    global _perf_last_save
    now = time.time()
    if now - _perf_last_save < 60:
        return
    try:
        PERF_LOG.write_text(json.dumps(_perf_data, indent=2))
        _perf_last_save = now
    except OSError:
        pass

def _record_perf(backend, tps, success=True):
    with _perf_lock:
        d = _perf_data.setdefault(backend, {"samples": 0, "avg_tps": tps, "success_rate": 1.0})
        n = d["samples"]
        d["avg_tps"] = (d["avg_tps"] * n + tps) / (n + 1)
        rate_delta = 1.0 if success else 0.0
        d["success_rate"] = min(1.0, (d["success_rate"] * n + rate_delta) / (n + 1))
        d["samples"] = n + 1
        d["last_used"] = time.time()
        _save_perf()

_load_perf()

# ─── Routing logic ─────────────────────────────────────────────────────────────
CLAUDE_API_KW  = ["analyze", "explain why", "compare", "review", "architecture",
                   "design", "plan", "strategy", "assess", "evaluate", "summarize",
                   "research", "think", "understand", "breakdown"]
CLAUDE_CODE_KW = ["def ", "import ", "class ", "function", "script", "python",
                   "bash", "refactor", "implement", "deploy", "write a file",
                   "create a file", "edit file", "fix the bug", "debug", "code"]
LOCAL_FAST_KW  = ["what is", "who is", "quick", "tell me", "define", "hello",
                   "hi ", "hey ", "how are", "thanks", "help me"]
OPS_KW         = ["status", "health", "uptime", "cluster", "ray", "alfred",
                   "service", "agents", "running"]

# LiteLLM model aliases
LITELLM_MODELS = {
    "fast":    "dolphin-phi",
    "smart":   "qwen2.5",
    "code":    "qwen2.5-coder",
    "default": "dolphin-llama3",
}

def classify_prompt(prompt: str) -> tuple[str, str]:
    """Returns (backend, model_hint). backend in: claude_api|claude_code|litellm|ollama"""
    p = prompt.lower()
    # Ops queries -> just local fast
    if any(k in p for k in OPS_KW) and len(p.split()) < 6:
        return "ops", "fast"
    # Code keywords -> claude_code for actual code tasks, litellm code for quick
    if any(k in p for k in CLAUDE_CODE_KW):
        # if prompt mentions editing/writing file or complex code -> claude_code
        if any(k in p for k in ["write a file", "create file", "edit file", "implement",
                                  "deploy", "refactor", "fix the bug"]):
            return "claude_code", "code"
        return "litellm", "code"
    # Analysis/architecture -> claude_api
    if any(k in p for k in CLAUDE_API_KW):
        return "claude_api", "smart"
    # Quick local reply
    if any(k in p for k in LOCAL_FAST_KW) or len(prompt) < 60:
        return "litellm", "fast"
    # Long complex prompt -> claude_api
    if len(prompt) > 800:
        return "claude_api", "smart"
    # default -> litellm
    return "litellm", "default"

# ─── TOOLS ────────────────────────────────────────────────────────────────────
def tool_shell(cmd: str) -> str:
    log(f"shell: {cmd}")
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        out = (r.stdout + r.stderr).strip()
        return out[:4000] or "(no output)"
    except subprocess.TimeoutExpired:
        return "[shell timeout after 60s]"
    except Exception as e:
        return f"[shell error: {e}]"

def alfred_status() -> dict:
    try:
        with urllib.request.urlopen(f"{ALFRED_URL}/status", timeout=3) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def alfred_heal() -> str:
    try:
        data = json.dumps({"action": "heal"}).encode()
        req = urllib.request.Request(f"{ALFRED_URL}/heal", data=data,
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("status", "ok")
    except Exception as e:
        return f"[heal error: {e}]"

def file_read(path: str) -> str:
    try:
        return Path(path).read_text()[:8000]
    except Exception as e:
        return f"[read error: {e}]"

def file_write(path: str, content: str) -> str:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"[write error: {e}]"

def send_imessage(msg: str, number: str = "3308073932") -> str:
    mac_ip  = os.environ.get("MACBOOK_TAILSCALE_IP", "")
    mac_usr = os.environ.get("MACBOOK_SSH_USER", "")
    if not mac_ip or not mac_usr:
        return "[iMessage: MACBOOK_TAILSCALE_IP or MACBOOK_SSH_USER not set]"
    chunks = [msg[i:i+500] for i in range(0, len(msg), 500)]
    results = []
    for chunk in chunks:
        escaped = chunk.replace("\\", "\\\\").replace('"', '\\"')
        script = (
            f'tell application "Messages" to send "{escaped}" '
            f'to buddy "{number}" of service 1'
        )
        # Use list-form subprocess to avoid shell interpretation of pipe chars
        cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
               f"{mac_usr}@{mac_ip}", "osascript", "-e", script]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            results.append(r.stdout.strip() or r.stderr.strip() or "sent")
        except subprocess.TimeoutExpired:
            results.append("[ssh timeout]")
        except Exception as e:
            results.append(f"[ssh error: {e}]")
    return "; ".join(results) or "sent"


# ─── Mac Controller HTTP tools ────────────────────────────────────────────────
_MAC_CONTROLLER_PORT = 7020

def _get_mac_ip():
    return os.environ.get("MACBOOK_TAILSCALE_IP", "")

def tool_mac(endpoint: str, method: str = "GET", data: dict = None) -> str:
    """Call mac controller HTTP API at endpoint."""
    mac_ip = _get_mac_ip()
    if not mac_ip:
        return "[MACBOOK_TAILSCALE_IP not set]"
    url = f"http://{mac_ip}:{_MAC_CONTROLLER_PORT}{endpoint}"
    try:
        import urllib.request as _ur
        if method.upper() == "POST":
            payload = json.dumps(data or {}).encode()
            req = _ur.Request(url, payload, {"Content-Type": "application/json"})
        else:
            req = _ur.Request(url)
        with _ur.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return json.dumps(result)
    except Exception as e:
        return f"[mac_tool error {endpoint}: {e}]"

def mac_run(cmd: str) -> str:
    """Run shell command on Mac via controller."""
    return tool_mac("/run", "POST", {"cmd": cmd})

def mac_notify(title: str, body: str) -> str:
    """Send macOS notification."""
    return tool_mac("/notify", "POST", {"title": title, "body": body})

def mac_screenshot() -> str:
    """Take screenshot on Mac, return base64 PNG info."""
    result = tool_mac("/screenshot", "GET")
    # Return just metadata, not the full base64 blob
    try:
        d = json.loads(result)
        if "image_base64" in d:
            size = len(d["image_base64"])
            return f"[screenshot captured: {size} base64 chars, format={d.get('format','png')}]"
    except Exception:
        pass
    return result

def mac_open(target: str) -> str:
    """Open app or URL on Mac."""
    return tool_mac("/open", "POST", {"app": target})

def mac_shortcut(name: str, input_text: str = "") -> str:
    """Run macOS Shortcut by name."""
    return tool_mac("/shortcut", "POST", {"name": name, "input_text": input_text})

def mac_clipboard(content: str = None) -> str:
    """Get or set Mac clipboard."""
    if content is None:
        return tool_mac("/clipboard", "GET")
    return tool_mac("/clipboard", "POST", {"content": content})

def spawn_agent(name: str) -> str:
    agent_path = WORKDIR / "agents" / f"{name}.py"
    if not agent_path.exists():
        return f"[agent {name} not found]"
    try:
        p = subprocess.Popen([sys.executable, str(agent_path)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"spawned {name} pid={p.pid}"
    except Exception as e:
        return f"[spawn error: {e}]"

def ray_status() -> str:
    return tool_shell("python3 -c \"import ray; ray.init(address='auto',ignore_reinit_error=True); print(ray.cluster_resources())\" 2>&1")

# ─── Backends ─────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Alii, autonomous AI built by Pierre Cabell on recycled hardware in Akron Ohio.
You ARE the system. Your components: Ray cluster, Ollama LLMs, Claude API, Alfred orchestrator, LiteLLM proxy, iMessage bridge to 3308073932.
Pierre: systems thinker, builds by doing, wants coherence and transparency. Building self-evolving AI.
When asked to do something: DO IT. Fix problems. Use shell. Be direct. Be capable.
You are Alii."""

def _build_messages(prompt: str) -> list:
    mem = get_memory()
    ctx = mem.get_context(8)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for role, content in ctx:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})
    return messages

def _stream_print(text: str):
    """Print text streaming-style, flushing each chunk."""
    sys.stdout.write(text)
    sys.stdout.flush()

# ── Claude API (anthropic SDK, streaming) ─────────────────────────────────────
def call_claude_api(prompt: str) -> str:
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return "[claude_api: ANTHROPIC_API_KEY not set, falling back]"
        client = anthropic.Anthropic(api_key=api_key)
        messages = _build_messages(prompt)
        # Remove system from messages list (pass separately)
        sys_msg = messages[0]["content"]
        user_msgs = messages[1:]
        print(c("grey", "  [claude-api streaming]"), end="\n", flush=True)
        print(c("green", "Alii: "), end="", flush=True)
        collected = []
        start = time.time()
        token_count = 0
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=sys_msg,
            messages=user_msgs,
        ) as stream:
            for text in stream.text_stream:
                _stream_print(text)
                collected.append(text)
                token_count += 1
        print()
        elapsed = max(time.time() - start, 0.1)
        tps = token_count / elapsed
        _record_perf("claude_api", tps, True)
        return "".join(collected)
    except ImportError:
        return "[anthropic SDK not installed]"
    except Exception as e:
        _record_perf("claude_api", 0, False)
        log(f"claude_api error: {e}", "ERROR")
        return f"[claude_api error: {e}]"

# ── Claude Code (subprocess, streaming via pty) ────────────────────────────────
def call_claude_code(prompt: str) -> str:
    ctx = get_memory().get_context(4)
    ctx_str = ""
    if ctx:
        ctx_str = "\n\nRECENT CONTEXT:\n" + "\n".join(f"{r}: {c_}" for r, c_ in ctx)
    full_prompt = SYSTEM_PROMPT + ctx_str + f"\n\nUser: {prompt}"
    print(c("grey", "  [claude-code subprocess]"), end="\n", flush=True)
    print(c("green", "Alii: "), end="", flush=True)
    start = time.time()
    try:
        proc = subprocess.Popen(
            ["claude", "--dangerously-skip-permissions", "-p", full_prompt],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
        )
        collected = []
        for line in proc.stdout:
            _stream_print(line)
            collected.append(line)
        proc.wait(timeout=300)
        print()
        elapsed = max(time.time() - start, 0.1)
        _record_perf("claude_code", len("".join(collected).split()) / elapsed, True)
        return "".join(collected)
    except FileNotFoundError:
        print(c("red", "[claude binary not found, falling back to claude_api]"))
        return call_claude_api(prompt)
    except Exception as e:
        _record_perf("claude_code", 0, False)
        log(f"claude_code error: {e}", "ERROR")
        return f"[claude_code error: {e}]"

# ── LiteLLM proxy (streaming) ─────────────────────────────────────────────────
def call_litellm(prompt: str, model_hint: str = "default") -> str:
    model = LITELLM_MODELS.get(model_hint, LITELLM_MODELS["default"])
    messages = _build_messages(prompt)
    payload = json.dumps({"model": model, "messages": messages, "stream": True}).encode()
    master_key = os.environ.get("LITELLM_MASTER_KEY", "")
    headers = {"Content-Type": "application/json"}
    if master_key:
        headers["Authorization"] = f"Bearer {master_key}"
    req = urllib.request.Request(f"{LITELLM}/chat/completions", payload, headers)
    print(c("grey", f"  [litellm/{model} streaming]"), end="\n", flush=True)
    print(c("green", "Alii: "), end="", flush=True)
    collected = []
    start = time.time()
    token_count = 0
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0].get("delta", {})
                        text = delta.get("content", "")
                        if text:
                            _stream_print(text)
                            collected.append(text)
                            token_count += 1
                    except Exception:
                        continue
        print()
        elapsed = max(time.time() - start, 0.1)
        _record_perf(f"litellm/{model}", token_count / elapsed, True)
        return "".join(collected)
    except Exception as e:
        print(c("red", f"\n  [litellm failed: {e}, falling back to ollama]"))
        _record_perf(f"litellm/{model}", 0, False)
        log(f"litellm error: {e}", "WARN")
        return call_ollama(prompt)

# ── Ollama fallback (streaming) ────────────────────────────────────────────────
def call_ollama(prompt: str, model: str = "dolphin-phi:2.7b") -> str:
    ctx = get_memory().get_context(4)
    ctx_str = "\n".join(f"{r}: {c_}" for r, c_ in ctx)
    full = f"{SYSTEM_PROMPT}\n\n{ctx_str}\n\nUser: {prompt}" if ctx_str else f"{SYSTEM_PROMPT}\n\nUser: {prompt}"
    payload = json.dumps({
        "model": model, "prompt": full[:6000], "stream": True,
        "options": {"num_thread": 16, "num_ctx": 4096, "num_gpu": 99}
    }).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/generate", payload,
                                  {"Content-Type": "application/json"})
    print(c("grey", f"  [ollama/{model} streaming]"), end="\n", flush=True)
    print(c("green", "Alii: "), end="", flush=True)
    collected = []
    start = time.time()
    token_count = 0
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                try:
                    chunk = json.loads(raw_line.decode("utf-8"))
                    text = chunk.get("response", "")
                    if text:
                        _stream_print(text)
                        collected.append(text)
                        token_count += 1
                    if chunk.get("done"):
                        break
                except Exception:
                    continue
        print()
        elapsed = max(time.time() - start, 0.1)
        _record_perf(f"ollama/{model}", token_count / elapsed, True)
        return "".join(collected)
    except Exception as e:
        print()
        _record_perf(f"ollama/{model}", 0, False)
        return f"[ollama error: {e}]"

# ─── Main router ──────────────────────────────────────────────────────────────
def route_and_respond(prompt: str) -> str:
    backend, model_hint = classify_prompt(prompt)
    if backend == "ops":
        st = alfred_status()
        return json.dumps(st, indent=2)
    if backend == "claude_api":
        resp = call_claude_api(prompt)
        if resp.startswith("[") and "error" in resp.lower():
            resp = call_litellm(prompt, "smart")
    elif backend == "claude_code":
        resp = call_claude_code(prompt)
        if resp.startswith("[") and "error" in resp.lower():
            resp = call_litellm(prompt, "code")
    elif backend == "litellm":
        resp = call_litellm(prompt, model_hint)
    else:
        resp = call_ollama(prompt)
    mem = get_memory()
    mem.save_turn("user", prompt, backend)
    mem.save_turn("assistant", resp, backend)
    return resp

# ─── CLI commands ─────────────────────────────────────────────────────────────
def cmd_status():
    st = alfred_status()
    print(c("cyan", json.dumps(st, indent=2)))

def cmd_memory():
    mem = get_memory()
    n = mem.count()
    ctx = mem.get_context(5)
    facts = mem.get_facts(5)
    print(c("cyan", f"  Episodic turns: {n}"))
    if ctx:
        print(c("cyan", "  Recent context:"))
        for role, content in ctx:
            print(f"    {c('yellow', role)}: {content[:100]}")
    if facts:
        print(c("cyan", "  Semantic facts:"))
        for k, v in facts:
            print(f"    {c('magenta', k)}: {v[:80]}")

def cmd_models():
    print(c("cyan", "  Model performance:"))
    for k, v in _perf_data.items():
        rate = v.get("success_rate", 1.0)
        tps  = v.get("avg_tps", 0)
        n    = v.get("samples", 0)
        print(f"    {c('yellow', k)}: tps={tps:.1f} ok={rate:.0%} n={n}")
    print(c("cyan", "\n  Routing table:"))
    print(f"    {c('green','claude_api')} — analyze/explain/architecture/planning")
    print(f"    {c('green','claude_code')} — write file/implement/deploy/refactor")
    print(f"    {c('green','litellm')} — fast/smart/code aliases")
    print(f"    {c('green','ollama')} — fallback (dolphin-phi:2.7b)")

def cmd_agents():
    agents = list((WORKDIR / "agents").glob("*.py"))
    print(c("cyan", f"  Agents ({len(agents)}):"))
    for a in sorted(agents):
        print(f"    {c('yellow', a.stem)}")

def cmd_heal():
    print(c("cyan", "  Healing Alfred..."))
    result = alfred_heal()
    print(c("green", f"  {result}"))

def cmd_shell(args: str):
    if not args.strip():
        print(c("red", "  Usage: /shell <command>"))
        return
    out = tool_shell(args)
    print(c("cyan", out))

def cmd_imessage(args: str):
    if not args.strip():
        print(c("red", "  Usage: /imessage <message>"))
        return
    result = send_imessage(args)
    print(c("green", f"  iMessage: {result}"))

def cmd_clear():
    os.system("clear")
    banner()

# ─── Banner ───────────────────────────────────────────────────────────────────
def banner():
    mem_count = get_memory().count()
    alfred_ok = "UP" if alfred_status().get("status") == "ok" else "?"
    print(c("cyan", f"""
  ╔══════════════════════════════════════════╗
  ║  {c('bold','A  L  I  I')}  —  Unified Brain  v{VERSION}        ║
  ║  Alfred:{alfred_ok:<4}  Memory:{mem_count:<6}  Akron OH   ║
  ║  route: claude_api|claude_code|litellm   ║
  ╚══════════════════════════════════════════╝
"""))

# ─── CLI entrypoint ───────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(prog="alii", description="Alii Unified AI")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--status",  action="store_true")
    parser.add_argument("-p", "--prompt", type=str, default=None)
    args = parser.parse_args()

    if args.version:
        print(f"alii v{VERSION}")
        return
    if args.status:
        cmd_status()
        return
    if args.prompt:
        resp = route_and_respond(args.prompt)
        if not resp.strip():
            pass  # already printed via streaming
        return

    # Interactive REPL
    # Readline history
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    try:
        readline.read_history_file(str(HISTORY))
    except FileNotFoundError:
        pass
    readline.set_history_length(1000)

    banner()
    print(c("grey", "  Commands: /status /memory /models /agents /heal /shell /imessage /clear /quit"))
    print(c("grey", "  Press Ctrl+C to interrupt, Ctrl+D to quit.\n"))

    while True:
        try:
            prompt_str = c("cyan", "Alii> ")
            user_input = input(prompt_str).strip()
        except EOFError:
            print(c("grey", "\n  [bye]"))
            break
        except KeyboardInterrupt:
            print()
            continue

        if not user_input:
            continue

        # Slash commands
        if user_input == "/quit" or user_input == "/exit":
            print(c("grey", "  [bye]"))
            break
        elif user_input == "/status":
            cmd_status()
        elif user_input == "/memory":
            cmd_memory()
        elif user_input == "/models":
            cmd_models()
        elif user_input == "/agents":
            cmd_agents()
        elif user_input == "/heal":
            cmd_heal()
        elif user_input.startswith("/shell "):
            cmd_shell(user_input[7:])
        elif user_input.startswith("/imessage "):
            cmd_imessage(user_input[10:])
        elif user_input == "/clear":
            cmd_clear()
        else:
            backend, hint = classify_prompt(user_input)
            print(c("grey", f"  [→ {backend}/{hint}]"))
            route_and_respond(user_input)

    try:
        readline.write_history_file(str(HISTORY))
    except OSError:
        pass

if __name__ == "__main__":
    main()
