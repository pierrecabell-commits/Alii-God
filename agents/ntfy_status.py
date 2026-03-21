#!/usr/bin/env python3
"""
ntfy_status.py — Comprehensive Alii Intelligence Digest  v3.0

Sends two types of notifications:
  1. Hourly cluster digest — FULL system intelligence (every detail you need)
  2. 5-hour todo digest   — all pending tasks grouped by priority + auto count
  3. Instant alerts       — temp > 75°C, service crash, camera offline

Notification format is information-dense: Pierre should feel fully informed
from a single glance at ntfy, no need to open a terminal.
"""

from __future__ import annotations
import json, logging, os, socket, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

WORKDIR    = Path("/home/avalii/moltbot")
LOGS_DIR   = WORKDIR / "logs"
DATA_DIR   = WORKDIR / "data"
TODOS_FILE = DATA_DIR / "owner_todos.json"
LOG_FILE   = LOGS_DIR / "ntfy_status.log"

LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ntfy] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
log = logging.getLogger("alii.ntfy")

CLUSTER_INTERVAL = 3600
TODO_INTERVAL    = 18000
ALERT_INTERVAL   = 60

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "alii-precision")
NTFY_URL   = f"https://ntfy.sh/{NTFY_TOPIC}"

SERVICES = {
    11434: "ollama",
    4000:  "litellm",
    7000:  "alfred",
    18789: "openclaw",
    3000:  "open-webui",
    5678:  "n8n",
    9101:  "mixpost",
    6333:  "qdrant",
    9000:  "minio",
    8888:  "searxng",
    7030:  "visionclaw",
}

NODES = {
    "XPS":    "100.91.78.55",
    "NUC":    "100.126.57.22",
    "JETSON": "100.87.137.61",
}

PRIORITY_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}


# ── Data Collection ───────────────────────────────────────────────────────────

def get_precision_stats() -> dict:
    stats = {
        "temp_c": 0.0, "load_1m": 0.0, "load_5m": 0.0, "load_15m": 0.0,
        "ram_used_gb": 0.0, "ram_total_gb": 0.0, "ram_pct": 0,
        "swap_used_gb": 0.0, "swap_total_gb": 0.0, "uptime": "unknown",
    }
    try:
        for p in ["/sys/class/thermal/thermal_zone0/temp",
                  "/sys/class/thermal/thermal_zone1/temp"]:
            if Path(p).exists():
                stats["temp_c"] = int(Path(p).read_text()) / 1000.0
                break
        try:
            out = subprocess.run(["sudo", "-n", "sensors", "-u"],
                                  capture_output=True, text=True, timeout=3).stdout
            for line in out.splitlines():
                if "temp1_input" in line:
                    temp = float(line.split()[-1])
                    if 20 < temp < 120:
                        stats["temp_c"] = temp
                        break
        except Exception:
            pass
    except Exception:
        pass
    try:
        parts = Path("/proc/loadavg").read_text().split()
        stats["load_1m"]  = float(parts[0])
        stats["load_5m"]  = float(parts[1])
        stats["load_15m"] = float(parts[2])
    except Exception:
        pass
    try:
        mem = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                try:
                    mem[k.strip()] = int(v.strip().split()[0])
                except ValueError:
                    pass
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", 0)
        used  = total - avail
        stats["ram_total_gb"] = round(total / 1024**2, 1)
        stats["ram_used_gb"]  = round(used  / 1024**2, 1)
        stats["ram_pct"]      = int(used / total * 100) if total else 0
        sw_t = mem.get("SwapTotal", 0)
        sw_f = mem.get("SwapFree", 0)
        stats["swap_used_gb"]  = round((sw_t - sw_f) / 1024**2, 1)
        stats["swap_total_gb"] = round(sw_t / 1024**2, 1)
    except Exception:
        pass
    try:
        secs = float(Path("/proc/uptime").read_text().split()[0])
        d, r = divmod(int(secs), 86400)
        h, m = divmod(r // 60, 60)
        stats["uptime"] = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
    except Exception:
        pass
    return stats


def check_service(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except Exception:
        return False


def get_services_status() -> dict[str, bool]:
    return {name: check_service(port) for port, name in SERVICES.items()}


def check_node(ip: str) -> dict:
    try:
        result = subprocess.run(
            ["ssh", "-i", "/home/avalii/.ssh/id_rsa",
             "-o", "BatchMode=yes", "-o", "ConnectTimeout=4",
             "-o", "StrictHostKeyChecking=no", f"avalii@{ip}",
             "cat /proc/loadavg; cat /proc/meminfo | grep -E 'MemTotal|MemAvailable'; "
             "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0"],
            capture_output=True, text=True, timeout=8
        )
        if result.returncode != 0:
            return {"online": False}
        lines = result.stdout.strip().splitlines()
        load = float(lines[0].split()[0]) if lines else 0.0
        mem_total = mem_avail = 0
        temp = 0.0
        for line in lines[1:]:
            if "MemTotal" in line:
                mem_total = int(line.split()[1])
            elif "MemAvailable" in line:
                mem_avail = int(line.split()[1])
            elif line.strip().lstrip("-").isdigit():
                t = int(line.strip())
                temp = t / 1000.0 if t > 1000 else float(t)
        mem_pct = int((mem_total - mem_avail) / mem_total * 100) if mem_total else 0
        return {"online": True, "load": load, "temp_c": temp, "mem_pct": mem_pct}
    except Exception:
        return {"online": False}


def get_ollama_models() -> list[str]:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=4) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return []


def get_ollama_loaded() -> list[str]:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/ps", timeout=4) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return []


def get_disk_usage() -> list[tuple[str, str, int]]:
    results = []
    try:
        out = subprocess.run(
            ["df", "-h", "--output=target,used,pcent"],
            capture_output=True, text=True, timeout=5
        ).stdout
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 3:
                mount = parts[0]
                if any(m in mount for m in ["/mnt/", "/home", "/"]) and "loop" not in mount:
                    pct_s = parts[2].rstrip("%")
                    pct = int(pct_s) if pct_s.isdigit() else 0
                    results.append((mount, parts[1], pct))
    except Exception:
        pass
    return results[:6]


def get_todos() -> dict:
    try:
        raw = TODOS_FILE.read_text()
        todos = json.loads(raw)
        if not isinstance(todos, list):
            todos = todos.get("todos", [])
    except Exception:
        return {"total": 0, "pending": [], "critical": [], "high": [], "auto": [], "by_cat": {}}
    pending  = [t for t in todos if t.get("status", "pending") == "pending"]
    critical = [t for t in pending if t.get("priority") == "critical"]
    high     = [t for t in pending if t.get("priority") == "high"]
    auto     = [t for t in pending if t.get("can_alii_execute")]
    by_cat   = {}
    for t in pending:
        k = t.get("category", "other")
        by_cat.setdefault(k, []).append(t)
    return {"total": len(todos), "pending": pending, "critical": critical,
            "high": high, "auto": auto, "by_cat": by_cat}


def get_camera_status() -> dict:
    try:
        with urllib.request.urlopen("http://100.87.137.61:8765/health", timeout=3) as r:
            return {"online": r.read() == b"ok"}
    except Exception:
        return {"online": False}


def get_recent_errors() -> list[str]:
    errors = []
    for log_name in ["alfred.log", "ntfy_status.log", "litellm.log"]:
        path = LOGS_DIR / log_name
        if not path.exists():
            continue
        try:
            for line in path.read_text().splitlines()[-200:]:
                if " ERROR " in line or " CRITICAL " in line:
                    errors.append(f"{log_name}: {line.strip()[-100:]}")
        except Exception:
            pass
    return errors[-4:]


def get_git_status() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(WORKDIR), "status", "--short"],
            capture_output=True, text=True, timeout=5
        )
        n = len([l for l in result.stdout.splitlines() if l.strip()])
        return f"{n} modified" if n else "clean ✓"
    except Exception:
        return "unknown"


# ── Formatters ────────────────────────────────────────────────────────────────

def format_cluster_health() -> tuple[str, str, str]:
    now    = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prec   = get_precision_stats()
    svcs   = get_services_status()
    models = get_ollama_models()
    loaded = get_ollama_loaded()
    todos  = get_todos()
    disk   = get_disk_usage()
    cam    = get_camera_status()
    errors = get_recent_errors()
    git    = get_git_status()
    nodes  = {name: check_node(ip) for name, ip in NODES.items()}

    svcs_up   = sum(1 for v in svcs.values() if v)
    svcs_down = [n for n, v in svcs.items() if not v]
    priority  = "urgent" if (prec["temp_c"] > 80 or svcs_down or todos["critical"]) else "default"

    status_icon = "🚨" if priority == "urgent" else ("⚠️" if (svcs_down or todos["critical"]) else "✅")
    temp_icon   = "🔥" if prec["temp_c"] > 75 else ("🌡️" if prec["temp_c"] > 60 else "❄️")
    cam_icon    = "📷✅" if cam["online"] else "📷❌"

    title = (
        f"{status_icon} Alii │ {temp_icon}{prec['temp_c']:.0f}°C "
        f"│ {svcs_up}/{len(svcs)} svcs │ {cam_icon} │ {len(todos['pending'])} todos"
    )

    lines = [f"🕐 {now}\n"]

    lines.append("💻 PRECISION")
    lines.append(f"  {temp_icon} {prec['temp_c']:.1f}°C  ⏱️ up {prec['uptime']}")
    lines.append(f"  Load: {prec['load_1m']} / {prec['load_5m']} / {prec['load_15m']}"
                 + (" ⚠️" if prec["load_1m"] > 4 else ""))
    lines.append(f"  RAM:  {prec['ram_used_gb']}/{prec['ram_total_gb']}GB ({prec['ram_pct']}%)"
                 + (" ⚠️" if prec["ram_pct"] > 85 else ""))
    if prec["swap_total_gb"] > 0:
        lines.append(f"  Swap: {prec['swap_used_gb']}/{prec['swap_total_gb']}GB")

    if disk:
        lines.append("\n💾 DISK")
        for mount, used, pct in disk:
            lines.append(f"  {mount:<22} {used:>6}  {pct}%" + (" ⚠️" if pct > 85 else ""))

    lines.append("\n🖥️ NODES")
    for name, info in nodes.items():
        if info.get("online"):
            t  = f" {info['temp_c']:.0f}°C" if info.get("temp_c") else ""
            lines.append(f"  {name:<8} ✅ load:{info['load']:.2f}{t} mem:{info['mem_pct']}%")
        else:
            lines.append(f"  {name:<8} ❌ OFFLINE")

    lines.append(f"\n{cam_icon} CAMERA  Jetson:8765")
    if not cam["online"]:
        lines.append("  ❌ Camera service is down — TUI [4] to restart")

    lines.append(f"\n🔧 SERVICES  {svcs_up}/{len(svcs)}")
    if svcs_down:
        lines.append(f"  ❌ DOWN: {', '.join(svcs_down)}")
    else:
        lines.append("  ✅ All services up")
    lines.append(f"  Up: {', '.join(name for name, up in svcs.items() if up)[:80]}")

    lines.append(f"\n🤖 OLLAMA  {len(models)} models")
    lines.append(f"  Available: {', '.join(models[:5]) or 'none'}")
    lines.append(f"  Hot: {', '.join(loaded) or 'none (cold)'}")

    lines.append(f"\n📋 TODOS  {len(todos['pending'])} pending")
    if todos["critical"]:
        lines.append(f"  🔴 CRITICAL:")
        for t in todos["critical"][:3]:
            lines.append(f"    • {t['title']}")
    if todos["high"]:
        lines.append(f"  🟠 HIGH:")
        for t in todos["high"][:2]:
            lines.append(f"    • {t['title']}")
    if todos["auto"]:
        lines.append(f"  ⚡ {len(todos['auto'])} auto-executable by Alii (TUI [0])")

    lines.append(f"\n📦 Git: {git}")

    if errors:
        lines.append(f"\n⚠️ ERRORS ({len(errors)}):")
        for e in errors[:3]:
            lines.append(f"  {e[:90]}")

    return title, "\n".join(lines), priority


def format_todo_digest() -> tuple[str, str, str]:
    todos   = get_todos()
    pending = todos["pending"]
    now     = datetime.now(timezone.utc).strftime("%H:%M UTC")

    if not pending:
        return "✅ Todos — All Clear", f"No pending todos at {now}.", "min"

    priority = "urgent" if todos["critical"] else ("high" if todos["high"] else "default")
    icon     = "🚨" if todos["critical"] else "📋"
    title    = f"{icon} Todos — {len(pending)} pending | {len(todos['critical'])} crit | {now}"

    lines = [f"📋 TODO DIGEST  {now}\n"]
    for pri in ["critical", "high", "medium", "low"]:
        group = [t for t in pending if t.get("priority") == pri]
        if not group:
            continue
        lines.append(f"\n{PRIORITY_ICON[pri]} {pri.upper()} ({len(group)})")
        for t in group[:5]:
            auto_tag = "⚡" if t.get("can_alii_execute") else ""
            lines.append(f"  {auto_tag}[{t.get('category','?')}] {t['title']}")

    if todos["auto"]:
        lines.append(f"\n⚡ Alii can auto-run {len(todos['auto'])} of these.")
        lines.append("  TUI → [0] Todos → Auto-run All")

    return title, "\n".join(lines), priority


# ── Sender ────────────────────────────────────────────────────────────────────

def send_ntfy(title: str, body: str, priority: str = "default", tags: str = "robot"):
    try:
        data = body.encode("utf-8")
        req  = urllib.request.Request(
            NTFY_URL, data=data,
            headers={
                "Title": title[:100], "Priority": priority,
                "Tags": tags, "Content-Type": "text/plain; charset=utf-8",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            log.info(f"ntfy sent: '{title[:60]}' [{priority}] → {r.status}")
    except Exception as e:
        log.error(f"ntfy failed: {e}")


# ── Alert Checker ─────────────────────────────────────────────────────────────

_alert_state: dict = {
    "last_temp_alert": 0.0,
    "last_svc_alert":  {},
    "last_cam_alert":  0.0,
}


def check_alerts():
    now  = time.time()
    prec = get_precision_stats()
    svcs = get_services_status()
    cam  = get_camera_status()

    if prec["temp_c"] > 75 and (now - _alert_state["last_temp_alert"]) > 1800:
        log.warning(f"Temp alert: {prec['temp_c']}°C")
        send_ntfy(
            f"🔥 HIGH TEMP {prec['temp_c']:.0f}°C",
            f"Precision CPU: {prec['temp_c']:.1f}°C\n"
            f"Load: {prec['load_1m']} RAM: {prec['ram_used_gb']}GB\n"
            f"Fix: sudo i8kctl fan 1 2",
            "urgent", "warning,thermometer"
        )
        _alert_state["last_temp_alert"] = now

    for svc_name, up in svcs.items():
        last = _alert_state["last_svc_alert"].get(svc_name, 0)
        if not up and (now - last) > 3600:
            send_ntfy(
                f"❌ Down: {svc_name}",
                f"Service {svc_name} not responding.\n"
                f"Fix: sudo systemctl restart alii-{svc_name}",
                "high", "warning"
            )
            _alert_state["last_svc_alert"][svc_name] = now
        elif up:
            _alert_state["last_svc_alert"].pop(svc_name, None)

    if not cam["online"] and (now - _alert_state["last_cam_alert"]) > 7200:
        send_ntfy(
            "📷❌ Camera offline",
            "Jetson camera service at :8765 is down.\n"
            "TUI [4] → Restart Service, or:\n"
            "ssh avalii@100.87.137.61 'sudo systemctl restart alii-camera'",
            "default", "warning"
        )
        _alert_state["last_cam_alert"] = now


# ── Main Loop ─────────────────────────────────────────────────────────────────

def main():
    log.info("ntfy_status v3.0 starting")
    send_ntfy(
        "🟢 Alii ntfy v3 Online",
        f"Started {datetime.now(timezone.utc).strftime('%H:%M UTC')}\n"
        f"Hourly full digest | 5hr todo digest | Instant alerts",
        "min", "tada"
    )

    last_cluster = 0.0
    last_todos   = 0.0

    while True:
        now = time.time()

        try:
            check_alerts()
        except Exception as e:
            log.error(f"Alert check error: {e}")

        if (now - last_cluster) >= CLUSTER_INTERVAL:
            log.info("Sending cluster health digest...")
            try:
                title, body, priority = format_cluster_health()
                send_ntfy(title, body, priority, "computer,chart_with_upwards_trend")
                last_cluster = now
            except Exception as e:
                log.error(f"Cluster digest error: {e}")

        if (now - last_todos) >= TODO_INTERVAL:
            log.info("Sending todo digest...")
            try:
                title, body, priority = format_todo_digest()
                send_ntfy(title, body, priority, "clipboard")
                last_todos = now
            except Exception as e:
                log.error(f"Todo digest error: {e}")

        time.sleep(ALERT_INTERVAL)


if __name__ == "__main__":
    main()
