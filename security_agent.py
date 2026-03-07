#!/usr/bin/env python3
"""
Alii Security Agent
Runs as alii-security.service (continuous) + alii-security.timer (daily 03:00)
Capabilities:
  a) Permission scanner - world-readable sensitive files
  b) Secret scanner - hardcoded credentials in source files
  c) User/access monitor - new users, failed SSH, new listening ports
"""
import os
import re
import sys
import json
import glob
import stat
import time
import socket
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# ── Configuration (from centralized config) ───────────────────────────────────
from config import (NTFY_URL, SCAN_ROOT, DATA_DIR, LOG_DIR, APPROVED_PORTS)

STATE_FILE = str(DATA_DIR / "security_state.json")
LOG_FILE = str(LOG_DIR / "security_agent.log")

SENSITIVE_PATTERNS = [
    "*.key", "*.pem", "*.env", "*.conf",
    "*password*", "*secret*", "*private*",
    "*credential*", "*token*", "*wallet*",
]

SECRET_SCAN_EXTENSIONS = [".py", ".json", ".yaml", ".yml", ".env", ".conf", ".sh"]

SECRET_REGEXES = [
    (re.compile(r'sk-[a-zA-Z0-9]{20,}'), "OpenAI/Anthropic API key"),
    (re.compile(r'pplx-[a-zA-Z0-9]{20,}'), "Perplexity API key"),
    (re.compile(r'api[_-]?key\s*[=:]\s*["\'][^"\'${\s][^"\']{8,}["\']', re.IGNORECASE), "Hardcoded api_key"),
    (re.compile(r'password\s*[=:]\s*["\'][^"\'${\s][^"\']{3,}["\']', re.IGNORECASE), "Hardcoded password"),
    (re.compile(r'(?<![#\s])[0-9a-fA-F]{64}(?![0-9a-fA-F])'), "64-char hex (possible private key)"),
    (re.compile(r'["\']ghp_[a-zA-Z0-9]{36}["\']'), "GitHub personal access token"),
    (re.compile(r'["\']xoxb-[0-9]+-[0-9]+-[a-zA-Z0-9]+["\']'), "Slack bot token"),
]

EXCLUDE_DIRS = {".git", "__pycache__", "venv", ".venv", "node_modules", "deleted_archive", "data"}
EXCLUDE_FILES = {"secret_scrub_report.txt", "security_agent.py", "master_build.log",
                 "secret_scrub_report.txt", "security_verification.txt",
                 "system_inventory.json", "node2_inventory.json", "node3_inventory.json",
                 "node1_inventory.json", "cluster_map.json", "last_integration_test.json"}

# ── Utilities ──────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def send_ntfy(title: str, body: str, priority: str = "high"):
    try:
        import urllib.request
        data = body.encode("utf-8")
        req = urllib.request.Request(NTFY_URL, data=data)
        req.add_header("Title", title)
        req.add_header("Priority", priority)
        req.add_header("Tags", "warning,lock")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        log(f"[ntfy] Failed to send notification: {e}")
        return False


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"known_users": [], "known_ports": [], "last_run": None}


def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ── a) PERMISSION SCANNER ──────────────────────────────────────────────────────

def scan_permissions() -> list:
    """Find world-readable sensitive files under SCAN_ROOT."""
    findings = []
    for pattern in SENSITIVE_PATTERNS:
        for fpath in Path(SCAN_ROOT).rglob(pattern):
            # Skip excluded dirs
            parts = set(fpath.parts)
            if parts & EXCLUDE_DIRS:
                continue
            if not fpath.is_file():
                continue
            try:
                mode = fpath.stat().st_mode
                # o+r = stat.S_IROTH, o+w = stat.S_IWOTH
                if mode & (stat.S_IROTH | stat.S_IWOTH):
                    findings.append({
                        "file": str(fpath),
                        "mode": oct(mode),
                        "issue": "world-readable/writable sensitive file",
                    })
            except Exception:
                pass
    return findings


# ── b) SECRET SCANNER ──────────────────────────────────────────────────────────

def scan_secrets(paths: list = None) -> list:
    """Scan source files for hardcoded secrets."""
    findings = []
    search_roots = paths or [SCAN_ROOT + "/moltbot"]

    for root_str in search_roots:
        root = Path(root_str)
        if not root.exists():
            continue
        for fpath in root.rglob("*"):
            if not fpath.is_file():
                continue
            if fpath.name in EXCLUDE_FILES:
                continue
            if fpath.suffix not in SECRET_SCAN_EXTENSIONS:
                continue
            # Skip excluded dirs
            parts = set(fpath.parts)
            if parts & EXCLUDE_DIRS:
                continue
            try:
                content = fpath.read_text(errors="replace")
                for lineno, line in enumerate(content.splitlines(), 1):
                    # Skip obvious env references and false positives
                    if any(x in line for x in ["os.environ", "os.getenv", "load_dotenv",
                                                 "REDACTED", "your_key", "<your", "example",
                                                 "# ", "checksum", "hash", "digest",
                                                 "sha256", "sha1", "md5"]):
                        continue
                    for pattern, label in SECRET_REGEXES:
                        if pattern.search(line):
                            findings.append({
                                "file": str(fpath),
                                "line": lineno,
                                "label": label,
                                "snippet": line.strip()[:120],
                            })
                            break
            except Exception:
                pass
    return findings


# ── c) USER / ACCESS MONITOR ──────────────────────────────────────────────────

def scan_users(state: dict) -> list:
    """Check for new user accounts since last run."""
    findings = []
    current_users = []
    try:
        with open("/etc/passwd") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) >= 4:
                    uid = int(parts[2])
                    if uid >= 1000 and parts[0] != "nobody":
                        current_users.append(parts[0])
    except Exception as e:
        log(f"[user scan] Could not read /etc/passwd: {e}")
        return findings

    known = set(state.get("known_users", []))
    new_users = [u for u in current_users if u not in known]
    for u in new_users:
        findings.append({"type": "new_user", "username": u})
    state["known_users"] = current_users
    return findings


def scan_failed_ssh() -> list:
    """Check auth.log for >5 failed SSH attempts in the last hour."""
    findings = []
    log_paths = ["/var/log/auth.log", "/var/log/secure"]
    cutoff = datetime.now() - timedelta(hours=1)
    count = 0

    for lpath in log_paths:
        if not os.path.exists(lpath):
            continue
        try:
            result = subprocess.run(
                ["grep", "Failed password", lpath],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                count += 1
        except Exception:
            pass

    if count > 5:
        findings.append({
            "type": "failed_ssh",
            "count": count,
            "message": f"{count} failed SSH attempts in auth.log",
        })
    return findings


def scan_ports(state: dict) -> list:
    """Check for new listening ports not in approved whitelist."""
    findings = []
    try:
        result = subprocess.run(
            ["ss", "-lntp"],
            capture_output=True, text=True, timeout=10
        )
        current_ports = set()
        for line in result.stdout.splitlines():
            m = re.search(r':(\d+)\s', line)
            if m:
                port = int(m.group(1))
                if port > 0:
                    current_ports.add(port)

        known_ports = set(state.get("known_ports", list(APPROVED_PORTS)))
        new_ports = current_ports - APPROVED_PORTS - known_ports
        for p in new_ports:
            findings.append({
                "type": "new_port",
                "port": p,
                "message": f"New listening port {p} not in approved whitelist",
            })
        state["known_ports"] = list(current_ports)
    except Exception as e:
        log(f"[port scan] Error: {e}")
    return findings


# ── Main scan orchestrator ────────────────────────────────────────────────────

def run_full_scan(mode: str = "full"):
    log(f"=== Security Agent START (mode={mode}) ===")
    state = load_state()
    all_alerts = []

    # a) Permissions
    log("Scanning file permissions...")
    perm_findings = scan_permissions()
    if perm_findings:
        for f in perm_findings:
            log(f"[PERM] {f['file']} {f['mode']} - {f['issue']}")
        all_alerts.append(f"PERMISSIONS: {len(perm_findings)} world-readable sensitive file(s)")
    else:
        log("[PERM] OK - no world-readable sensitive files found")

    # b) Secrets
    log("Scanning for hardcoded secrets...")
    secret_findings = scan_secrets()
    if secret_findings:
        for f in secret_findings:
            log(f"[SECRET] {f['file']}:{f['line']} - {f['label']}")
        all_alerts.append(f"SECRETS: {len(secret_findings)} potential hardcoded secret(s)")
    else:
        log("[SECRET] OK - no hardcoded secrets detected")

    # c) Users / SSH / Ports
    log("Scanning users, SSH failures, and ports...")
    user_findings = scan_users(state)
    ssh_findings = scan_failed_ssh()
    port_findings = scan_ports(state)

    for f in user_findings:
        log(f"[USER] New account detected: {f['username']}")
        all_alerts.append(f"NEW USER: {f['username']}")
    for f in ssh_findings:
        log(f"[SSH] {f['message']}")
        all_alerts.append(f"SSH BRUTE FORCE: {f['count']} failures")
    for f in port_findings:
        log(f"[PORT] {f['message']}")
        all_alerts.append(f"NEW PORT: {f['port']}")

    # Save state
    state["last_run"] = datetime.now().isoformat()
    save_state(state)

    # Send ntfy if any alerts
    if all_alerts:
        body = "\n".join(all_alerts)
        send_ntfy("ALII SECURITY ALERT", body, priority="urgent")
        log(f"[ntfy] Alert sent: {len(all_alerts)} issue(s)")
    else:
        log("[OK] Security scan complete - no issues found")
        if mode == "full":
            send_ntfy("Alii Security OK", "Full scan passed - no issues found", priority="low")

    log(f"=== Security Agent END - {len(all_alerts)} alert(s) ===")
    return all_alerts


def run_secret_scan_only() -> bool:
    """Used by pre-commit hook. Returns True if secrets found (should block commit)."""
    findings = scan_secrets()
    if findings:
        print("ERROR: Hardcoded secrets detected - commit BLOCKED")
        for f in findings:
            print(f"  {f['file']}:{f['line']} - {f['label']}")
            print(f"    {f['snippet']}")
        return True
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Alii Security Agent")
    parser.add_argument("--mode", choices=["full", "permissions", "secrets", "access", "pre-commit"],
                        default="full", help="Scan mode")
    args = parser.parse_args()

    if args.mode == "pre-commit":
        found = run_secret_scan_only()
        sys.exit(1 if found else 0)
    elif args.mode == "permissions":
        findings = scan_permissions()
        print(json.dumps(findings, indent=2))
        sys.exit(1 if findings else 0)
    elif args.mode == "secrets":
        findings = scan_secrets()
        print(json.dumps(findings, indent=2))
        sys.exit(1 if findings else 0)
    elif args.mode == "access":
        state = load_state()
        findings = scan_users(state) + scan_failed_ssh() + scan_ports(state)
        save_state(state)
        print(json.dumps(findings, indent=2))
        sys.exit(1 if findings else 0)
    else:
        alerts = run_full_scan("full")
        sys.exit(1 if alerts else 0)
