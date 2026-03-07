#!/usr/bin/env python3
"""
Alii Revenue Agent
Manages: GitHub presence, Reddit posts, consulting inquiries, star tracking.
Credentials loaded from .env ONLY - never hardcoded.
Actions that post externally only fire when credentials are present.

Usage:
  python3 revenue_agent.py --report       # status report
  python3 revenue_agent.py --github       # create/update GitHub repo
  python3 revenue_agent.py --reddit       # post to r/selfhosted + r/LocalLLaMA
  python3 revenue_agent.py --monitor      # monitor stars/forks (loop)
  python3 revenue_agent.py --serve        # start contact form server :8888
  python3 revenue_agent.py --all          # full run
"""
import os
import sys
import json
import time
import threading
import argparse
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# Load .env via centralized config
from config import (WORKDIR, LOG_DIR, DATA_DIR, NTFY_URL, ENV_FILE,
                    CONTACT_FORM_PORT, load_env)
load_env()
try:
    from dotenv import load_dotenv
    load_dotenv(str(ENV_FILE))
except ImportError:
    pass

REPORT_FILE = str(LOG_DIR / "money_report.json")
STATE_FILE = str(DATA_DIR / "revenue_state.json")
LOG_FILE = str(LOG_DIR / "revenue_agent.log")

PROJECT_NAME = "Alii AI"
PROJECT_DESCRIPTION = (
    "Alii AI: open-source autonomous AI system built from recycled hardware. "
    "Self-hosted, privacy-first, multi-node cluster with local LLMs, vector memory, "
    "and full agent ecosystem. No cloud required."
)
GITHUB_REPO_NAME = "alii-ai"
GITHUB_USERNAME = "AVAlii1993"

REDDIT_SELFHOSTED_POST = {
    "title": "Alii AI - Open-source autonomous agent system on recycled hardware (self-hosted, local LLMs)",
    "body": """Hey r/selfhosted!

I've been building **Alii AI** - a fully self-hosted autonomous AI system running on recycled server hardware.

**What it does:**
- Multi-node cluster (Precision server + NUC + XPS) connected via Tailscale
- Local LLMs via Ollama (dolphin-llama3, qwen2.5-coder, etc.)
- Vector memory with Qdrant + 600+ indexed memories
- LiteLLM router for unified API
- n8n for workflow automation
- MinIO for object storage
- Full security agent with pre-commit hooks

**Why I built it:**
Wanted a personal AI that runs 100% locally, learns from interactions, and doesn't send data anywhere.

**Stack:** Python, Docker, Prometheus/Grafana, Tailscale, SQLite + Qdrant

Happy to answer questions about the setup!

GitHub: https://github.com/{github_username}/{repo_name}
""",
    "subreddit": "selfhosted",
}

REDDIT_LOCALLLAMA_POST = {
    "title": "Running autonomous AI agent stack on recycled hardware - Ollama + Qdrant + LiteLLM",
    "body": """Been running a self-hosted agent ecosystem on old server hardware:

**Models running locally:**
- dolphin-llama3:8b (primary agent)
- qwen2.5-coder:7b (code tasks)
- neural-chat:7b (conversation)

**Architecture:**
- LiteLLM proxy for unified routing
- Qdrant vector DB for semantic memory search
- 600+ memories indexed from past interactions
- n8n for scheduled workflows (daily software scout, health monitoring)

The vector memory search is surprisingly useful - querying past context semantically rather than just keyword search.

Anyone else running similar stacks? What embeddings are you using?

Source: https://github.com/{github_username}/{repo_name}
""",
    "subreddit": "LocalLLaMA",
}


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def send_ntfy(title: str, body: str, priority: str = "low"):
    try:
        req = urllib.request.Request(NTFY_URL, body.encode())
        req.add_header("Title", title)
        req.add_header("Priority", priority)
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "github_repo_created": False,
        "reddit_posted_selfhosted": False,
        "reddit_posted_localllama": False,
        "github_stars": 0,
        "last_monitor": None,
    }


def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ── GitHub Integration ────────────────────────────────────────────────────────

def create_github_repo() -> bool:
    """Create GitHub repo if it doesn't exist."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        log("GITHUB_TOKEN not set in .env - skipping repo creation")
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    # Check if repo exists
    check_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO_NAME}"
    req = urllib.request.Request(check_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            repo = json.loads(r.read())
            log(f"GitHub repo already exists: {repo['html_url']}")
            return True
    except urllib.error.HTTPError as e:
        if e.code != 404:
            log(f"GitHub check error: {e}")
            return False

    # Create repo
    data = json.dumps({
        "name": GITHUB_REPO_NAME,
        "description": PROJECT_DESCRIPTION,
        "public": True,
        "has_issues": True,
        "topics": ["ai", "self-hosted", "autonomous-agent", "local-llm", "ollama"],
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/user/repos",
        data=data,
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            repo = json.loads(r.read())
            log(f"Created GitHub repo: {repo['html_url']}")
            send_ntfy("Alii GitHub Repo Created", f"Repo live at {repo['html_url']}")
            return True
    except Exception as e:
        log(f"GitHub repo creation error: {e}")
        return False


def get_github_stats() -> dict:
    """Get GitHub repo stars and forks."""
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO_NAME}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            repo = json.loads(r.read())
            return {
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "watchers": repo.get("watchers_count", 0),
                "open_issues": repo.get("open_issues_count", 0),
                "url": repo.get("html_url", ""),
            }
    except Exception as e:
        return {"error": str(e)}


def monitor_github_loop():
    """Continuously monitor GitHub stats and send ntfy on milestones."""
    state = load_state()
    milestones = [1, 5, 10, 25, 50, 100, 250, 500, 1000]
    log("Starting GitHub monitor loop...")

    while True:
        stats = get_github_stats()
        if "error" not in stats:
            stars = stats["stars"]
            prev_stars = state.get("github_stars", 0)

            if stars > prev_stars:
                log(f"GitHub stars: {stars} (+{stars - prev_stars})")
                # Check milestones
                for milestone in milestones:
                    if prev_stars < milestone <= stars:
                        msg = f"Alii AI reached {milestone} GitHub stars!"
                        send_ntfy("GitHub Milestone!", msg, priority="high")
                        log(msg)

                state["github_stars"] = stars
                state["last_monitor"] = datetime.now().isoformat()
                save_state(state)

            # Save current stats to report
            _update_report(stats)
        time.sleep(3600)  # Check every hour


# ── Reddit Integration ────────────────────────────────────────────────────────

def post_to_reddit(post_config: dict, state: dict, state_key: str) -> bool:
    """Post to a subreddit using PRAW."""
    if state.get(state_key):
        log(f"Already posted to r/{post_config['subreddit']}, skipping")
        return True

    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    username = os.environ.get("REDDIT_USERNAME")
    password = os.environ.get("REDDIT_PASSWORD")

    if not all([client_id, client_secret, username, password]):
        log(f"Reddit credentials not set in .env - skipping r/{post_config['subreddit']} post")
        return False

    try:
        import praw
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent=f"AliiAgent/1.0 by {username}",
        )

        # Format post body with actual URLs
        body = post_config["body"].format(
            github_username=GITHUB_USERNAME,
            repo_name=GITHUB_REPO_NAME,
        )

        subreddit = reddit.subreddit(post_config["subreddit"])
        submission = subreddit.submit(
            title=post_config["title"],
            selftext=body,
        )
        url = f"https://reddit.com{submission.permalink}"
        log(f"Posted to r/{post_config['subreddit']}: {url}")
        send_ntfy(f"Posted to r/{post_config['subreddit']}", url, priority="low")
        state[state_key] = True
        save_state(state)
        return True
    except ImportError:
        log("praw not installed. Run: pip3 install praw --break-system-packages")
        return False
    except Exception as e:
        log(f"Reddit post error: {e}")
        return False


# ── Contact Form Server ───────────────────────────────────────────────────────

def start_contact_server(port: int = 8888):
    """Simple HTTP contact form for consulting inquiries."""
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import urllib.parse

    inquiries_file = str(DATA_DIR / "consulting_inquiries.json")

    def save_inquiry(data: dict):
        inquiries = []
        if os.path.exists(inquiries_file):
            with open(inquiries_file) as f:
                inquiries = json.load(f)
        inquiries.append({**data, "timestamp": datetime.now().isoformat()})
        with open(inquiries_file, "w") as f:
            json.dump(inquiries, f, indent=2)
        log(f"New inquiry from {data.get('email', 'unknown')}: {data.get('message', '')[:80]}")
        send_ntfy("New Consulting Inquiry", f"From: {data.get('email','?')}\n{data.get('message','')[:200]}", "high")

    FORM_HTML = """<!DOCTYPE html>
<html><head><title>Alii AI - Contact</title>
<style>body{font-family:sans-serif;max-width:600px;margin:40px auto;padding:20px}
input,textarea{width:100%;padding:8px;margin:8px 0;border:1px solid #ccc;border-radius:4px}
button{background:#333;color:#fff;padding:10px 20px;border:none;cursor:pointer;border-radius:4px}
</style></head><body>
<h1>Alii AI - Consulting Inquiry</h1>
<p>Interested in self-hosted AI infrastructure? Let's talk.</p>
<form method="POST" action="/contact">
  <input type="text" name="name" placeholder="Your name" required><br>
  <input type="email" name="email" placeholder="Your email" required><br>
  <input type="text" name="subject" placeholder="Subject"><br>
  <textarea name="message" rows="6" placeholder="Your message" required></textarea><br>
  <button type="submit">Send Inquiry</button>
</form></body></html>"""

    SUCCESS_HTML = """<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:600px;margin:40px auto;padding:20px">
<h1>Message sent!</h1><p>Thank you for your inquiry. We'll be in touch.</p>
<a href="/">Back</a></body></html>"""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # Suppress default logging

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(FORM_HTML.encode())

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            params = urllib.parse.parse_qs(body)
            inquiry = {k: v[0] for k, v in params.items()}
            save_inquiry(inquiry)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(SUCCESS_HTML.encode())

    server = HTTPServer(("0.0.0.0", port), Handler)
    log(f"Contact form server started on :{port}")
    server.serve_forever()


# ── Report ────────────────────────────────────────────────────────────────────

def _update_report(github_stats: dict):
    report = {
        "timestamp": datetime.now().isoformat(),
        "github": github_stats,
        "state": load_state(),
    }
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)


def print_report():
    """Print current revenue/presence status."""
    state = load_state()
    github_stats = get_github_stats()
    _update_report(github_stats)

    print("\n=== Alii Revenue Agent Report ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"\nGitHub:")
    if "error" in github_stats:
        print(f"  Status: {github_stats['error']}")
        print(f"  (Set GITHUB_TOKEN in .env to activate)")
    else:
        print(f"  Stars: {github_stats.get('stars', 0)}")
        print(f"  Forks: {github_stats.get('forks', 0)}")
        print(f"  URL: {github_stats.get('url', 'not created')}")
    print(f"\nReddit:")
    print(f"  r/selfhosted posted: {state.get('reddit_posted_selfhosted', False)}")
    print(f"  r/LocalLLaMA posted: {state.get('reddit_posted_localllama', False)}")
    print(f"  (Set REDDIT_* credentials in .env to activate)")
    print(f"\nContact form: http://localhost:8888 (run with --serve)")
    print(f"\nCredential status:")
    for key in ["GITHUB_TOKEN", "REDDIT_CLIENT_ID", "REDDIT_USERNAME"]:
        val = os.environ.get(key, "")
        print(f"  {key}: {'SET' if val else 'NOT SET - fill in .env'}")
    print("=================================\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Alii Revenue Agent")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--github", action="store_true", help="Create/check GitHub repo")
    parser.add_argument("--reddit", action="store_true", help="Post to Reddit (requires REDDIT_* in .env)")
    parser.add_argument("--monitor", action="store_true", help="Monitor GitHub stats in loop")
    parser.add_argument("--serve", action="store_true", help="Start contact form on :8888")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if not any(vars(args).values()):
        args.report = True

    state = load_state()

    if args.report or args.all:
        print_report()

    if args.github or args.all:
        log("Checking GitHub repo...")
        result = create_github_repo()
        if result:
            stats = get_github_stats()
            log(f"GitHub stats: {stats}")

    if args.reddit or args.all:
        log("Posting to Reddit...")
        post_to_reddit(REDDIT_SELFHOSTED_POST, state, "reddit_posted_selfhosted")
        time.sleep(5)  # Reddit rate limit
        post_to_reddit(REDDIT_LOCALLLAMA_POST, state, "reddit_posted_localllama")

    if args.monitor:
        monitor_github_loop()

    if args.serve or args.all:
        t = threading.Thread(target=start_contact_server, args=(8888,), daemon=True)
        t.start()
        log("Contact form server running on :8888")
        if args.serve and not args.all:
            t.join()


if __name__ == "__main__":
    log("=== Revenue Agent START ===")
    main()
    if not (len(sys.argv) > 1 and ("--monitor" in sys.argv or "--serve" in sys.argv or "--all" in sys.argv)):
        log("=== Revenue Agent DONE ===")
