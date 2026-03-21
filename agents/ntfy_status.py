#!/usr/bin/env python3
"""
Alii ntfy Status Broadcaster v2 — upgraded notification system.

Schedule:
  - Every 60 min : cluster health digest (all nodes, temps, load, services, models)
  - Every 5 hours: full TODO digest (all pending items grouped by category)
  - On threshold : immediate critical alerts (high temp, service crash)

Subscribe: https://ntfy.sh/alii-precision
"""

import json, logging, os, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Use local cluster data module ──────────────────────────────────────────────
WORKDIR  = Path("/home/avalii/moltbot")
sys.path.insert(0, str(WORKDIR))
from alii_tui_cluster import (
    sync_collect_precision, sync_collect_node, sync_collect_services,
    sync_collect_ollama_models, sync_collect_ray_nodes, ClusterState,
    CLUSTER_NODES
)

LOG_FILE = WORKDIR / "logs" / "ntfy_status.log"
DATA_DIR = WORKDIR / "data"
NTFY_URL = os.environ.get("NTFY_URL", "https://ntfy.sh/alii-precision")

CLUSTER_INTERVAL = 3600   # 1 hour
TODO_INTERVAL    = 18000  # 5 hours
ALERT_LOOP_SEC   = 60     # check alerts every 60s

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ntfy] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger("alii.ntfy")


# ── ntfy helper ────────────────────────────────────────────────────────────────

def _ntfy(title: str, msg: str, priority: str = "default", tags: str = ""):
    try:
        headers = {"Title": title.encode(), "Priority": priority.encode()}
        if tags:
            headers["Tags"] = tags.encode()
        req = urllib.request.Request(
            NTFY_URL, data=msg.encode(), headers={
                "Title": title, "Priority": priority,
                **({"Tags": tags} if tags else {})
            }, method="POST"
        )
        urllib.request.urlopen(req, timeout=8)
        log.info("ntfy sent: %s", title)
    except Exception as e:
        log.warning("ntfy failed: %s", e)


# ── Todo collector ─────────────────────────────────────────────────────────────

def collect_all_todos() -> list[dict]:
    """Load all todos from owner_todos.json (the todo_agent's storage)."""
    try:
        path = DATA_DIR / "owner_todos.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return data
        return data.get("todos", [])
    except Exception as e:
        log.warning("collect_todos error: %s", e)
        return []


# ── Formatters ─────────────────────────────────────────────────────────────────

def format_cluster_health() -> tuple[str, str, str]:
    """1-hour cluster digest."""
    precision  = sync_collect_precision()
    services   = sync_collect_services()
    models     = sync_collect_ollama_models()
    ray_nodes  = sync_collect_ray_nodes()
    nodes      = {name: sync_collect_node(name, ip) for name, ip in CLUSTER_NODES.items()}

    now   = datetime.now(timezone.utc).strftime("%H:%M UTC")
    up    = [k for k, v in services.items() if v]
    down  = [k for k, v in services.items() if not v]

    lines = [
        f"━━ PRECISION ━━",
        f"🖥  Temp: {precision.temp_c}°C  Load: {precision.load_1m} ({precision.load_pct}%)"
        f"  RAM: {precision.ram_used_gb}/{precision.ram_total_gb}GB  Disk: {precision.disk_pct}",
    ]

    for name, node in nodes.items():
        if node.online:
            ram_gb = round(node.ram_used_mb / 1024, 1)
            ram_total_gb = round(node.ram_total_mb / 1024, 1)
            lines.append(
                f"🔹 {name.upper()}: {node.temp_c}°C  L:{node.load_1m}  RAM:{ram_gb}/{ram_total_gb}GB"
            )
        else:
            lines.append(f"🔴 {name.upper()}: OFFLINE")

    lines.append("")
    lines.append(f"━━ SERVICES ({len(up)}/{len(services)}) ━━")
    if down:
        lines.append(f"❌ DOWN: {', '.join(down)}")
    else:
        lines.append("✅ All services healthy")
    lines.append(f"✅ UP: {', '.join(up[:8])}")

    lines.append("")
    lines.append(f"━━ MODELS ━━")
    lines.append(f"🤖 Loaded: {', '.join(models) if models else 'none'}")
    if ray_nodes:
        lines.append(f"⚡ Ray: {ray_nodes} nodes")

    # Todos count
    todos = collect_all_todos()
    pending = [t for t in todos if t.get("status", "pending") == "pending"]
    critical = [t for t in pending if t.get("priority") == "critical"]
    if pending:
        lines.append("")
        lines.append(f"📋 Todos: {len(pending)} pending ({len(critical)} critical)")
        if critical:
            for t in critical[:3]:
                lines.append(f"  🚨 [{t.get('priority','?')}] {t.get('title','?')}")

    priority = "high" if down or critical else "low"
    tags = "warning" if down else ("white_check_mark" if not critical else "rotating_light")
    title = f"Alii Cluster {now} — {len(up)}/{len(services)}✓" + (" 🔴" if down else "")
    return title, "\n".join(lines), priority


def format_todo_digest() -> tuple[str, str, str]:
    """5-hour full TODO digest for Pierre — grouped by category."""
    todos = collect_all_todos()
    pending = [t for t in todos if t.get("status", "pending") == "pending"]

    if not pending:
        return ("Alii Todos — All Clear",
                "✅ No pending todos! Everything is handled.", "low")

    # Group by category
    categories: dict[str, list] = {}
    for t in pending:
        cat = t.get("category", "action")
        categories.setdefault(cat, []).append(t)

    # Priority order for display
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    for cat in categories:
        categories[cat].sort(key=lambda x: priority_order.get(x.get("priority", "low"), 3))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    has_critical = any(t.get("priority") == "critical" for t in pending)

    lines = [f"📋 {len(pending)} pending todos as of {now}", ""]

    for cat in ["security", "account", "config", "action"]:
        items = categories.get(cat, [])
        if not items:
            continue
        cat_emoji = {"security": "🔒", "account": "👤", "config": "⚙️", "action": "🎯"}.get(cat, "•")
        lines.append(f"━━ {cat_emoji} {cat.upper()} ({len(items)}) ━━")
        for t in items[:8]:  # max 8 per category
            pri = t.get("priority", "?")
            title_txt = t.get("title", "?")
            desc = t.get("description", "")[:80]
            added = t.get("added_at", t.get("created_at", ""))[:10]
            lines.append(f"[{pri.upper()}] {title_txt}")
            if desc:
                lines.append(f"  → {desc}")
            if added:
                lines.append(f"  Added: {added}")
        lines.append("")

    ntfy_priority = "urgent" if has_critical else ("high" if pending else "default")
    ntfy_tags = "rotating_light" if has_critical else "clipboard"
    title = f"Alii TODOs — {len(pending)} pending" + (" 🚨 CRITICAL" if has_critical else "")
    return title, "\n".join(lines), ntfy_priority


# ── Alert checker ──────────────────────────────────────────────────────────────

def check_alerts():
    """Immediate alerts for critical conditions."""
    try:
        precision = sync_collect_precision()
        if precision.temp_c > 75:
            _ntfy(
                "🔥 PRECISION HIGH TEMP",
                f"CPU temp critical: {precision.temp_c}°C\nCheck cooling immediately.",
                priority="urgent", tags="fire"
            )
    except Exception:
        pass

    # Check remote nodes
    for name, ip in CLUSTER_NODES.items():
        try:
            node = sync_collect_node(name, ip)
            if node.online and node.temp_c > 80:
                _ntfy(
                    f"🔥 {name.upper()} HIGH TEMP",
                    f"{name}: {node.temp_c}°C — check cooling",
                    priority="high", tags="fire"
                )
        except Exception:
            pass


# ── Main loop ──────────────────────────────────────────────────────────────────

def main():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log.info("ntfy Broadcaster v2 started — cluster:%ds todos:%ds",
             CLUSTER_INTERVAL, TODO_INTERVAL)

    _ntfy(
        "Alii Status Broadcaster",
        f"ntfy v2 active. Cluster health: every 1h. Todo digest: every 5h.\n"
        f"Subscribe: {NTFY_URL}",
        priority="low"
    )

    last_cluster = 0.0
    last_todo    = 0.0

    while True:
        now = time.time()

        # Cluster health (every 1 hour)
        if now - last_cluster >= CLUSTER_INTERVAL:
            try:
                title, msg, priority = format_cluster_health()
                _ntfy(title, msg, priority)
                last_cluster = now
            except Exception as e:
                log.exception("Cluster health error: %s", e)

        # Todo digest (every 5 hours)
        if now - last_todo >= TODO_INTERVAL:
            try:
                title, msg, priority = format_todo_digest()
                _ntfy(title, msg, priority, tags="clipboard")
                last_todo = now
            except Exception as e:
                log.exception("Todo digest error: %s", e)

        # Alert check (every loop iteration = every 60s)
        try:
            check_alerts()
        except Exception as e:
            log.debug("Alert check error: %s", e)

        time.sleep(ALERT_LOOP_SEC)


if __name__ == "__main__":
    main()
