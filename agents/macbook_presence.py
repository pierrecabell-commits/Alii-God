#!/usr/bin/env python3
"""
MacBook Presence Detector — auto-integrates MacBook into Alii cluster when online.

When MacBook (Tailscale IP) is reachable:
  - Writes data/macbook_online.json
  - Attempts to add macbook-ollama route to LiteLLM
  - Sends ntfy notification
  - Verifies mac_controller availability on port 7020

When MacBook goes offline:
  - Removes macbook_online.json
  - Sends ntfy notification
"""

import os, sys, json, time, logging, urllib.request, urllib.error, subprocess
from pathlib import Path
from datetime import datetime, timezone

WORKDIR       = Path("/home/avalii/moltbot")
LOG_FILE      = WORKDIR / "logs" / "macbook_presence.log"
STATE_FILE    = WORKDIR / "data" / "macbook_online.json"

MACBOOK_IP    = os.environ.get("MACBOOK_TAILSCALE_IP", "100.111.127.89")
MAC_CTRL_PORT = 7020
OLLAMA_PORT   = 11434
LITELLM_URL   = "http://127.0.0.1:4000"
LITELLM_KEY   = os.environ.get("LITELLM_MASTER_KEY", "")
NTFY_URL      = "https://ntfy.sh/alii-precision"
CHECK_INTERVAL = 60  # seconds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [macbook_presence] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger("alii.macbook_presence")


def _ntfy(title: str, msg: str, priority: str = "default"):
    try:
        req = urllib.request.Request(
            NTFY_URL, data=msg.encode(),
            headers={"Title": title, "Priority": priority}, method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        log.debug("ntfy failed: %s", e)


def _ping(ip: str, timeout: int = 3) -> bool:
    """Return True if the IP responds to ping."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            capture_output=True, timeout=timeout + 2
        )
        return result.returncode == 0
    except Exception:
        return False


def _check_port(ip: str, port: int, timeout: int = 3) -> bool:
    """Return True if TCP port is open."""
    import socket
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def _macbook_online() -> dict:
    """Check MacBook presence and return status dict."""
    reachable = _ping(MACBOOK_IP)
    if not reachable:
        return {"online": False}

    mac_ctrl = _check_port(MACBOOK_IP, MAC_CTRL_PORT)
    ollama   = _check_port(MACBOOK_IP, OLLAMA_PORT)
    return {
        "online":      True,
        "ip":          MACBOOK_IP,
        "mac_ctrl":    mac_ctrl,
        "ollama":      ollama,
        "checked_at":  datetime.now(timezone.utc).isoformat(),
    }


def _write_state(status: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(status, indent=2))


def _clear_state():
    STATE_FILE.unlink(missing_ok=True)


def _add_macbook_ollama():
    """Register macbook-ollama model in LiteLLM if Ollama is reachable."""
    if not LITELLM_KEY:
        return
    try:
        payload = json.dumps({
            "model_name": "macbook-ollama",
            "litellm_params": {
                "model": f"ollama/qwen2.5:7b",
                "api_base": f"http://{MACBOOK_IP}:{OLLAMA_PORT}",
            },
        }).encode()
        req = urllib.request.Request(
            f"{LITELLM_URL}/model/new",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LITELLM_KEY}",
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        log.info("macbook-ollama route added to LiteLLM")
    except Exception as e:
        log.debug("LiteLLM macbook route add failed (may already exist): %s", e)


if __name__ == "__main__":
    log.info("MacBook presence detector started — watching %s", MACBOOK_IP)
    _ntfy("Alii MacBook Monitor", f"Presence detector started — watching {MACBOOK_IP}", "low")

    was_online = False

    while True:
        status = _macbook_online()
        is_online = status["online"]

        if is_online and not was_online:
            log.info("MacBook ONLINE — ip=%s mac_ctrl=%s ollama=%s",
                     MACBOOK_IP, status.get("mac_ctrl"), status.get("ollama"))
            _write_state(status)
            msg = f"MacBook online at {MACBOOK_IP}"
            if status.get("ollama"):
                msg += " | Ollama: active"
                _add_macbook_ollama()
            if status.get("mac_ctrl"):
                msg += " | mac_controller: active"
            _ntfy("MacBook Online", msg, "default")
            was_online = True

        elif not is_online and was_online:
            log.info("MacBook OFFLINE")
            _clear_state()
            _ntfy("MacBook Offline", f"{MACBOOK_IP} no longer reachable", "low")
            was_online = False

        time.sleep(CHECK_INTERVAL)
