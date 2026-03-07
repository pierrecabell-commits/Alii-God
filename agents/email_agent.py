#!/usr/bin/env python3
"""
Email Agent — IMAP poller + SMTP replier for Alii command interface.
Polls imap.mail.me.com:993 every 30s. Parses 'alii: CMD' subjects.
Rate limit: 10 replies/hour. Intercepts verification emails for account_agent.
"""
import email, imaplib, json, logging, os, re, smtplib, subprocess, sys, time
import email.mime.text, email.mime.multipart
from collections import deque
from datetime import datetime, timezone
from email.header import decode_header
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
try:
    from vault.vault_client import get_secret
except ImportError:
    def get_secret(k, d=None): return os.getenv(k, d)

WORKDIR       = Path(os.environ.get("ALII_WORKDIR", str(_project_root)))
LOG_FILE      = WORKDIR / "logs" / "email_agent.log"
THREADS_FILE  = WORKDIR / "memory" / "email_threads.json"
VERIF_FILE    = WORKDIR / "memory" / "verification_emails.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [email] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("alii.email")

def _cfg(k, d=None): return get_secret(k, os.getenv(k, d))

# ── Rate Limiter ───────────────────────────────────────────────────────────────
_reply_times = deque()

def _can_reply() -> bool:
    now = time.time()
    while _reply_times and now - _reply_times[0] > 3600:
        _reply_times.popleft()
    return len(_reply_times) < 10

def _record_reply():
    _reply_times.append(time.time())

# ── Thread Context ─────────────────────────────────────────────────────────────
def _load_threads() -> dict:
    if THREADS_FILE.exists():
        try: return json.loads(THREADS_FILE.read_text())
        except (json.JSONDecodeError, OSError): pass
    return {}

def _save_threads(t: dict):
    THREADS_FILE.parent.mkdir(parents=True, exist_ok=True)
    THREADS_FILE.write_text(json.dumps(t, indent=2))

def _update_thread(thread_id: str, role: str, content: str):
    threads = _load_threads()
    if thread_id not in threads:
        threads[thread_id] = []
    threads[thread_id].append({"role": role, "content": content[:500],
                                "ts": datetime.now(timezone.utc).isoformat()})
    # Keep last 5
    threads[thread_id] = threads[thread_id][-5:]
    _save_threads(threads)

# ── Verification Intercept ─────────────────────────────────────────────────────
VERIF_PATTERNS = re.compile(
    r"verif|confirm|code|activate|one.?time|otp|magic.?link|sign.?in", re.I
)
NOREPLY_RE = re.compile(r"no.?reply|noreply|donotreply|notification", re.I)

def _is_verification(subject: str, from_addr: str) -> bool:
    return VERIF_PATTERNS.search(subject) is not None and NOREPLY_RE.search(from_addr) is not None

def _save_verification(subject: str, from_addr: str, body: str, ts: str):
    data = []
    if VERIF_FILE.exists():
        try: data = json.loads(VERIF_FILE.read_text())
        except (json.JSONDecodeError, OSError): pass
    data.append({"subject": subject, "from": from_addr, "body": body[:1000],
                 "received_at": ts, "processed": False})
    data = data[-50:]  # keep last 50
    VERIF_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERIF_FILE.write_text(json.dumps(data, indent=2))
    log.info(f"Saved verification email: {subject} from {from_addr}")

# ── IMAP ───────────────────────────────────────────────────────────────────────
def _decode_header_str(raw) -> str:
    parts = decode_header(raw or "")
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result)

def _get_body(msg) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body += payload.decode("utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="replace")
    return body.strip()

def fetch_unread(imap_user: str, imap_pass: str) -> list:
    msgs = []
    try:
        mail = imaplib.IMAP4_SSL("imap.mail.me.com", 993)
        mail.login(imap_user, imap_pass)
        mail.select("INBOX")
        _, ids = mail.search(None, "UNSEEN")
        for uid in (ids[0].split() if ids[0] else []):
            _, data = mail.fetch(uid, "(RFC822)")
            raw = data[0][1]
            msg   = email.message_from_bytes(raw)
            subj  = _decode_header_str(msg.get("Subject", ""))
            frm   = _decode_header_str(msg.get("From", ""))
            msg_id= msg.get("Message-ID", "")
            in_reply= msg.get("In-Reply-To", "")
            ts    = msg.get("Date", datetime.now(timezone.utc).isoformat())
            body  = _get_body(msg)
            msgs.append({"uid": uid, "subject": subj, "from": frm,
                         "msg_id": msg_id, "in_reply_to": in_reply,
                         "body": body, "ts": ts, "raw_msg": msg})
        mail.logout()
    except Exception as e:
        log.error(f"IMAP error: {e}")
    return msgs

# ── SMTP Reply ─────────────────────────────────────────────────────────────────
def send_reply(smtp_user: str, smtp_pass: str, to_addr: str,
               subject: str, body: str, in_reply_to: str = ""):
    try:
        msg = email.mime.multipart.MIMEMultipart()
        msg["From"]    = smtp_user
        msg["To"]      = to_addr
        msg["Subject"] = subject
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"]  = in_reply_to
        msg.attach(email.mime.text.MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP("smtp.mail.me.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_addr, msg.as_string())
        log.info(f"Reply sent to {to_addr}: {subject}")
        _record_reply()
        return True
    except Exception as e:
        log.error(f"SMTP error: {e}")
        return False

# ── Command Processor ──────────────────────────────────────────────────────────
def process_command(cmd: str, body: str = "") -> str:
    cmd = cmd.strip()
    low = cmd.lower()

    if low == "status":
        try:
            r = subprocess.run(["systemctl", "--user", "list-units", "--state=running", "--no-pager"],
                               capture_output=True, text=True, timeout=10)
            lines = [l for l in r.stdout.splitlines() if "alii-" in l.lower()][:10]
            return "=== Running Services ===\n" + "\n".join(lines)
        except Exception as e:
            return f"Status error: {e}"

    elif low.startswith("run "):
        shell_cmd = cmd[4:].strip()
        try:
            r = subprocess.run(shell_cmd, shell=True, capture_output=True,
                               text=True, timeout=60, cwd=str(WORKDIR))
            out = (r.stdout + r.stderr).strip()[:2000]
            return f"$ {shell_cmd}\n{out or '(no output)'}"
        except Exception as e:
            return f"Error running command: {e}"

    elif low == "report":
        try:
            sf = WORKDIR / "data/alii_status.json"
            if sf.exists():
                data = json.loads(sf.read_text())
                return f"=== System Report ===\n{json.dumps(data, indent=2)[:1500]}"
        except (json.JSONDecodeError, OSError): pass
        return "No report file found."

    elif low in ("money", "revenue"):
        try:
            rf = WORKDIR / "data/revenue_live.json"
            if rf.exists():
                data = json.loads(rf.read_text())
                return f"=== Revenue ===\n{json.dumps(data, indent=2)[:1000]}"
        except (json.JSONDecodeError, OSError): pass
        return "No revenue data available yet."

    elif low == "secure":
        try:
            r = subprocess.run(["python3", str(WORKDIR / "security_agent.py"), "--quick"],
                               capture_output=True, text=True, timeout=60)
            return r.stdout.strip()[:1500] or "Security scan complete (no output)"
        except Exception as e:
            return f"Security scan error: {e}"

    elif low == "help":
        return (
            "Alii Command Interface\n"
            "======================\n"
            "Send email with subject: alii: <command>\n\n"
            "Commands:\n"
            "  status   — list running services\n"
            "  run CMD  — execute shell command\n"
            "  report   — full system report\n"
            "  money    — revenue summary\n"
            "  secure   — quick security scan\n"
            "  help     — this message\n"
            "  <anything else> — ask Alii (via Ollama)\n"
        )

    else:
        # Ask Ollama
        import requests as req
        try:
            context = f"User email body: {body[:300]}\n\nQuestion: {cmd}"
            r = req.post("http://localhost:11434/api/generate",
                         json={"model": "llama3.2:3b", "prompt": context, "stream": False},
                         timeout=45)
            if r.ok:
                return r.json().get("response", "")[:1500]
        except Exception: pass
        return f"Received command: {cmd}\n(Ollama not available for AI response)"

# ── Main Poll Loop ─────────────────────────────────────────────────────────────
def main():
    log.info("Email agent starting. Polling imap.mail.me.com:993 every 30s")
    imap_user = _cfg("APPLE_EMAIL", "")
    imap_pass = _cfg("APPLE_APP_PASSWORD", "")

    if not imap_user or not imap_pass:
        log.warning("APPLE_EMAIL or APPLE_APP_PASSWORD not set — email agent in dry-run mode")

    while True:
        try:
            if imap_user and imap_pass:
                messages = fetch_unread(imap_user, imap_pass)
                for m in messages:
                    subject = m["subject"]
                    frm     = m["from"]
                    body    = m["body"]
                    ts      = m["ts"]
                    msg_id  = m["msg_id"]

                    # Intercept verification emails
                    if _is_verification(subject, frm):
                        _save_verification(subject, frm, body, ts)
                        continue

                    # Process alii: commands
                    if not re.match(r"^(re:\s*)?alii:\s*", subject, re.I):
                        continue

                    cmd_match = re.match(r"^(re:\s*)?alii:\s*(.+)$", subject, re.I)
                    if not cmd_match:
                        continue

                    cmd = cmd_match.group(2).strip()
                    thread_id = m.get("in_reply_to") or msg_id

                    _update_thread(thread_id, "user", f"[CMD: {cmd}]\n{body[:200]}")
                    log.info(f"Processing command '{cmd}' from {frm}")

                    if not _can_reply():
                        log.warning("Rate limit reached — skipping reply")
                        continue

                    response = process_command(cmd, body)
                    _update_thread(thread_id, "assistant", response)

                    reply_subject = f"Re: alii: {cmd}" if not subject.lower().startswith("re:") else subject

                    # Extract clean email address
                    to_match = re.search(r"<([^>]+)>", frm)
                    to_addr  = to_match.group(1) if to_match else frm.strip()

                    send_reply(imap_user, imap_pass, to_addr,
                               reply_subject, response, msg_id)

        except KeyboardInterrupt:
            log.info("Email agent stopping")
            break
        except Exception as e:
            log.error(f"Poll error: {e}")

        time.sleep(30)

if __name__ == "__main__":
    main()
