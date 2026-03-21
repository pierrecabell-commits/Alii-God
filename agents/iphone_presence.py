#!/usr/bin/env python3
"""
iphone_presence.py — Alii iPhone Integration Agent
====================================================
Detects when iPhone joins the Tailscale mesh and integrates it as a cluster endpoint.

iPhone 14 Pro Max capabilities when connected:
  - Mobile notification relay (ntfy iOS app)
  - iOS Shortcuts webhook → POST /trigger on Alfred to run Alii actions
  - VisionClaw camera input (if VisionClaw iOS app installed, port 7030)
  - Network failover indicator (iPhone on 5G when precision loses internet)

Polls every 60s. Sends ntfy on connect/disconnect events.
"""

import os
import sys
import json
import time
import asyncio
import socket
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
WORKDIR        = Path(__file__).resolve().parent.parent
LOG_DIR        = WORKDIR / "logs"
DATA_DIR       = WORKDIR / "data"
STATE_FILE     = DATA_DIR / "iphone_online.json"
CLUSTER_MAP    = DATA_DIR / "cluster_map.json"

IPHONE_IP      = os.environ.get("IPHONE_TAILSCALE_IP", "100.111.40.78")
CHECK_INTERVAL = 60   # seconds

NTFY_URL   = "https://ntfy.sh/alii-precision"
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "")

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(LOG_DIR / "iphone_presence.log"), mode="a"),
    ],
)
log = logging.getLogger("iphone_presence")


def ping(ip: str, timeout: float = 3.0) -> bool:
    """Return True if IP responds to ICMP ping."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(int(timeout * 1000)), ip],
            capture_output=True, timeout=timeout + 2
        )
        return result.returncode == 0
    except Exception:
        return False


def probe_port(ip: str, port: int, timeout: float = 2.0) -> bool:
    """Return True if TCP port is open."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def ntfy(title: str, body: str, tags: str = "iphone"):
    """Send ntfy notification."""
    try:
        subprocess.run([
            "curl", "-s", "-X", "POST",
            "-H", f"Title: {title}",
            "-H", f"Tags: {tags}",
            "-d", body,
            NTFY_URL,
        ], capture_output=True, timeout=8)
    except Exception:
        pass


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_state(data: dict):
    STATE_FILE.write_text(json.dumps(data, indent=2))


def remove_state():
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def update_cluster_map(online: bool, capabilities: list[str]):
    """Update cluster_map.json with iPhone node info."""
    try:
        cm = {}
        if CLUSTER_MAP.exists():
            cm = json.loads(CLUSTER_MAP.read_text())
        nodes = cm.get("nodes", cm.get("cluster", {}))
        if isinstance(nodes, list):
            # list format — find or append iphone entry
            found = False
            for n in nodes:
                if n.get("ip") == IPHONE_IP or n.get("name") == "iphone":
                    n.update({
                        "name": "iphone",
                        "ip":   IPHONE_IP,
                        "os":   "iOS",
                        "role": "mobile-gateway",
                        "online": online,
                        "capabilities": capabilities,
                        "last_seen": datetime.now(timezone.utc).isoformat(),
                    })
                    found = True
                    break
            if not found and online:
                nodes.append({
                    "name": "iphone",
                    "ip":   IPHONE_IP,
                    "os":   "iOS",
                    "role": "mobile-gateway",
                    "online": online,
                    "capabilities": capabilities,
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                })
            cm["nodes"] = nodes
        else:
            cm["iphone"] = {
                "ip":   IPHONE_IP,
                "os":   "iOS",
                "role": "mobile-gateway",
                "online": online,
                "capabilities": capabilities,
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }
        CLUSTER_MAP.write_text(json.dumps(cm, indent=2))
    except Exception as e:
        log.warning("cluster_map update failed: %s", e)


def on_connect():
    """Called when iPhone is detected online."""
    log.info("iPhone %s is ONLINE", IPHONE_IP)
    capabilities = []

    # Probe for VisionClaw (iOS app on port 7030)
    has_vision = probe_port(IPHONE_IP, 7030)
    if has_vision:
        capabilities.append("visionclaw-camera")
        log.info("VisionClaw app detected on iPhone")

    # Probe Shortcuts webhook listener (custom port 8080 if configured)
    has_shortcuts = probe_port(IPHONE_IP, 8080, timeout=1.5)
    if has_shortcuts:
        capabilities.append("shortcuts-webhook")

    # Always capable of: ntfy push notifications, mobile network indicator
    capabilities += ["ntfy-push", "mobile-network-indicator"]

    save_state({
        "ip":          IPHONE_IP,
        "online":      True,
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "capabilities": capabilities,
        "has_visionclaw": has_vision,
    })
    update_cluster_map(online=True, capabilities=capabilities)

    caps_str = ", ".join(capabilities) if capabilities else "ntfy push"
    ntfy(
        title="📱 iPhone connected to cluster",
        body=f"iPhone 14 Pro Max online ({IPHONE_IP}) | Capabilities: {caps_str}",
        tags="iphone,white_check_mark",
    )
    log.info("iPhone integration complete. Capabilities: %s", capabilities)


def on_disconnect():
    """Called when iPhone is detected offline."""
    log.info("iPhone %s is OFFLINE", IPHONE_IP)
    prev = load_state()
    remove_state()
    update_cluster_map(online=False, capabilities=[])
    ntfy(
        title="📵 iPhone disconnected",
        body=f"iPhone 14 Pro Max offline ({IPHONE_IP}). Mobile gateway unavailable.",
        tags="iphone,warning",
    )


def run():
    """Main polling loop."""
    log.info("iphone_presence starting — watching %s every %ds", IPHONE_IP, CHECK_INTERVAL)
    ntfy(
        title="📱 iPhone presence agent started",
        body=f"Watching {IPHONE_IP} for iPhone integration",
        tags="iphone",
    )

    was_online = STATE_FILE.exists()
    # Verify previous state against current reality
    if was_online and not ping(IPHONE_IP):
        log.info("Startup: clearing stale online state")
        was_online = False
        remove_state()

    while True:
        try:
            is_online = ping(IPHONE_IP)
            if is_online and not was_online:
                on_connect()
                was_online = True
            elif not is_online and was_online:
                on_disconnect()
                was_online = False
            elif is_online:
                # Still online — refresh capabilities every 10 checks
                state = load_state()
                state["last_seen"] = datetime.now(timezone.utc).isoformat()
                save_state(state)
                log.debug("iPhone still online (%s)", IPHONE_IP)
            else:
                log.debug("iPhone still offline (%s)", IPHONE_IP)
        except Exception as exc:
            log.error("Poll error: %s", exc)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run()
