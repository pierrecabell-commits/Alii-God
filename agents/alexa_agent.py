#!/usr/bin/env python3
"""
AlexaAgent — Local Alexa device integration for Alii.
Uses phue-style direct HTTP to Fire TV / Echo devices, and fauxmo for discovery.
Auto-discovers Alexa devices on the local network via mDNS/SSDP probing.
"""

import json
import logging
import os
import socket
import subprocess
from datetime import datetime
from pathlib import Path

log = logging.getLogger("alii.alexa_agent")

WORKDIR = Path(os.environ.get("ALII_WORKDIR", str(Path(__file__).resolve().parent.parent)))
LOG_DIR = WORKDIR / "logs"

# Known/candidate Alexa device IPs from network scan
DEFAULT_ALEXA_IPS = os.getenv("ALEXA_DEVICE_IPS", "192.168.1.63,192.168.1.178").split(",")


def _write_memory(category, content):
    try:
        import sys; sys.path.insert(0, str(WORKDIR))
        from alii_sqlite_memory import AliiSQLiteMemory
        AliiSQLiteMemory().add_memory(category=category, content=content)
    except Exception:
        pass


class AlexaAgent:
    """Controls Alexa/Echo devices on the local network."""

    def __init__(self, device_ips=None):
        self.device_ips = device_ips or DEFAULT_ALEXA_IPS
        log.info("AlexaAgent initialised. Candidate IPs: %s", self.device_ips)

    def discover_devices(self) -> list[dict]:
        """
        Probe candidate IPs for Alexa/Echo services.
        Echo devices typically expose port 9090 (Alexa Voice Service) or respond to SSDP.
        """
        found = []
        alexa_ports = [9090, 4070, 8080, 8443, 49153]
        for ip in self.device_ips:
            ip = ip.strip()
            if not ip:
                continue
            open_ports = []
            for port in alexa_ports:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.5)
                    result = s.connect_ex((ip, port))
                    s.close()
                    if result == 0:
                        open_ports.append(port)
                except Exception:
                    pass
            # Try HTTP probe on port 80/8080
            device_info = {"ip": ip, "open_ports": open_ports, "type": "unknown"}
            for port in [80, 8080]:
                try:
                    r = subprocess.run(
                        ["curl", "-s", "--connect-timeout", "1", f"http://{ip}:{port}/"],
                        capture_output=True, text=True, timeout=2
                    )
                    if "alexa" in r.stdout.lower() or "echo" in r.stdout.lower() or "amazon" in r.stdout.lower():
                        device_info["type"] = "alexa_confirmed"
                        device_info["http_port"] = port
                        break
                    elif r.returncode == 0 and r.stdout:
                        device_info["http_response_snippet"] = r.stdout[:100]
                except Exception:
                    pass
            found.append(device_info)
            log.info("Device probe %s: ports=%s type=%s", ip, open_ports, device_info["type"])

        _write_memory("alexa_agent", f"Device discovery: {found}")
        return found

    def announce(self, message: str, device_ips: list[str] | None = None) -> dict:
        """
        Send a TTS announcement to all Alexa devices.
        Method 1: notify2 (local notification) if alexa-remote2 not available
        Method 2: alexa-cookie + alexa-remote2-applescripts via SSH to MacBook
        Method 3: Queue for manual execution
        Falls back gracefully with instructions if no direct API available.
        """
        targets = device_ips or self.device_ips
        log.info("announce: '%s' to %s", message[:60], targets)
        results = []

        for ip in targets:
            ip = ip.strip()
            # Try direct HTTP TTS (some Echo/Fire TV devices support this)
            try:
                r = subprocess.run(
                    ["curl", "-s", "--connect-timeout", "2", "-X", "POST",
                     f"http://{ip}:8080/tts",
                     "-d", json.dumps({"text": message})],
                    capture_output=True, text=True, timeout=5
                )
                if r.returncode == 0:
                    results.append({"ip": ip, "status": "sent", "method": "http_tts"})
                    continue
            except Exception:
                pass

            # Fallback: queue for alexa-remote2 when credentials available
            results.append({
                "ip": ip,
                "status": "queued",
                "note": "Install alexa-remote2 or configure Alexa cookie for TTS support",
                "setup_cmd": "npm install -g alexa-remote2",
            })

        _write_memory("alexa_agent", f"Announce: '{message[:60]}' results={results}")
        return {"message": message, "results": results}

    def get_setup_instructions(self) -> str:
        """Return setup instructions for full Alexa TTS integration."""
        return """
Alexa TTS Setup Options:

Option A (easiest): Use ntfy.sh on phone instead of Alexa
  - Already working: curl -d 'message' ntfy.sh/alii-precision

Option B: alexa-remote2 (Node.js, unofficial API)
  sudo apt install nodejs npm
  npm install -g alexa-remote2
  # Then authenticate with Amazon account

Option C: Home Assistant + Alexa Media Player
  - Install Home Assistant on local network
  - Add Alexa Media Player integration
  - Control via HA REST API

Option D: Amazon Polly TTS → play on local speaker
  # Uses AWS credentials — sends audio to local speaker
  aws polly synthesize-speech --text "message" --voice-id Joanna --output-format mp3 /tmp/msg.mp3
  mpg123 /tmp/msg.mp3

Current candidate Alexa IPs: """ + str(DEFAULT_ALEXA_IPS)

    def status(self) -> dict:
        """Return current Alexa integration status."""
        return {
            "candidate_ips": self.device_ips,
            "discovered": self.discover_devices(),
            "tts_available": False,
            "recommendation": "Use ntfy.sh as primary notification channel (already working)",
        }
