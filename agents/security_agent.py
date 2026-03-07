#!/usr/bin/env python3
"""
SecurityAgent — Local system security monitoring for Alii.
Scans localhost and local subnet only. No external targets.
"""

import json
import logging
import os
import shutil
import socket
import subprocess
from datetime import datetime
from pathlib import Path

log = logging.getLogger("alii.security_agent")

WORKDIR   = Path("/home/avalii/moltbot")
NET_MAP   = WORKDIR / "memory" / "network_map.json"
REPORT    = WORKDIR / "memory" / "threat_report.json"


def _write_memory(category: str, content: str):
    try:
        import sys
        sys.path.insert(0, str(WORKDIR))
        from alii_sqlite_memory import AliiSQLiteMemory
        AliiSQLiteMemory().add_memory(category=category, content=content)
    except Exception as exc:
        log.debug("Memory write skipped: %s", exc)


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    """Run a subprocess and return (returncode, combined output)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return -1, f"Timed out after {timeout}s"
    except FileNotFoundError:
        return -2, f"Command not found: {cmd[0]}"
    except Exception as exc:
        return -3, str(exc)


def _local_subnet() -> str:
    """Detect the local /24 subnet by connecting to a public IP (no traffic sent)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        parts = ip.split(".")
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    except Exception:
        return "192.168.1.0/24"


class SecurityAgent:
    """Local security monitoring — operates only on localhost and LAN."""

    def __init__(self):
        (WORKDIR / "memory").mkdir(parents=True, exist_ok=True)
        log.info("SecurityAgent initialised.")
        _write_memory("security_agent", "SecurityAgent initialised.")

    def scan_network(self) -> dict:
        """Run a basic TCP connect scan on the local subnet (no root needed)."""
        subnet = _local_subnet()
        log.info("scan_network: subnet=%s", subnet)

        if shutil.which("nmap"):
            rc, out = _run(["nmap", "-sn", "-T4", subnet], timeout=60)
            result = {"method": "nmap_ping", "subnet": subnet, "output": out, "rc": rc}
        else:
            result = {
                "method": "nmap_unavailable",
                "subnet": subnet,
                "note": "Install nmap: sudo apt install nmap",
            }

        NET_MAP.write_text(json.dumps(result, indent=2))
        _write_memory("security_agent", f"Network scan: {subnet} ({result['method']})")
        return result

    def monitor_crontab(self) -> dict:
        """Return current crontab entries and flag any suspicious patterns."""
        log.info("monitor_crontab called.")
        rc, out = _run(["crontab", "-l"])
        entries = [l for l in out.splitlines() if l.strip() and not l.startswith("#")]

        suspicious_patterns = [".sys", "/tmp/", "wget", "curl", "base64", "eval", "nc "]
        flagged = []
        for entry in entries:
            hits = [p for p in suspicious_patterns if p in entry]
            if hits:
                flagged.append({"entry": entry, "patterns": hits})

        result = {
            "entries": entries,
            "flagged": flagged,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        if flagged:
            log.warning("Suspicious crontab entries detected: %s", flagged)
            _write_memory("security_alert", f"Suspicious cron: {flagged}")
        else:
            _write_memory("security_agent", "Crontab clean.")
        return result

    def watch_ssh_keys(self) -> dict:
        """List authorized_keys and report any unexpected entries."""
        log.info("watch_ssh_keys called.")
        auth_keys = Path.home() / ".ssh" / "authorized_keys"
        if not auth_keys.exists():
            result = {"file": str(auth_keys), "exists": False, "keys": []}
        else:
            lines = [l.strip() for l in auth_keys.read_text().splitlines()
                     if l.strip() and not l.startswith("#")]
            result = {"file": str(auth_keys), "exists": True, "key_count": len(lines), "keys": lines}
        _write_memory("security_agent", f"SSH keys check: {result.get('key_count', 0)} keys found.")
        return result

    def scan_tmp_executables(self) -> dict:
        """Find executable files in /tmp (common malware staging location)."""
        log.info("scan_tmp_executables called.")
        found = []
        try:
            for f in Path("/tmp").iterdir():
                if f.is_file() and os.access(f, os.X_OK):
                    found.append(str(f))
        except PermissionError:
            pass

        result = {"executables_in_tmp": found, "count": len(found)}
        if found:
            log.warning("Executable files in /tmp: %s", found)
            _write_memory("security_alert", f"Executables in /tmp: {found}")
        else:
            _write_memory("security_agent", "/tmp clean — no executables found.")
        return result

    def run_nmap_sweep(self, target: str | None = None) -> dict:
        """
        Run an nmap service scan on localhost or the local subnet.
        Target must be localhost or a RFC-1918 address/subnet.
        """
        if target is None:
            target = "127.0.0.1"

        # Safety: only allow loopback or RFC-1918
        safe_prefixes = ("127.", "10.", "192.168.", "172.16.", "172.17.",
                         "172.18.", "172.19.", "172.20.", "172.21.", "172.22.",
                         "172.23.", "172.24.", "172.25.", "172.26.", "172.27.",
                         "172.28.", "172.29.", "172.30.", "172.31.")
        if not any(target.startswith(p) for p in safe_prefixes):
            log.error("run_nmap_sweep: rejected non-local target %s", target)
            return {"error": "Only localhost and RFC-1918 targets are permitted."}

        log.info("run_nmap_sweep: target=%s", target)
        if not shutil.which("nmap"):
            return {"error": "nmap not installed. Run: sudo apt install nmap"}

        rc, out = _run(["nmap", "-sV", "--open", "-T4", target], timeout=120)
        result = {"target": target, "rc": rc, "output": out}
        NET_MAP.write_text(json.dumps(result, indent=2))
        _write_memory("security_agent", f"nmap sweep: {target}")
        return result

    def bluetooth_scan(self) -> dict:
        """Scan for nearby Bluetooth devices (requires bluetoothctl)."""
        log.info("bluetooth_scan called.")
        if not shutil.which("bluetoothctl"):
            return {"error": "bluetoothctl not available."}

        rc, out = _run(["bluetoothctl", "scan", "on"], timeout=10)
        rc2, devices = _run(["bluetoothctl", "devices"])
        result = {"scan_rc": rc, "devices_raw": devices}
        _write_memory("security_agent", f"Bluetooth scan: {devices[:200]}")
        return result

    def generate_threat_report(self) -> dict:
        """Run all checks and produce a consolidated threat report."""
        log.info("generate_threat_report called.")
        report = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "crontab":         self.monitor_crontab(),
            "ssh_keys":        self.watch_ssh_keys(),
            "tmp_executables": self.scan_tmp_executables(),
            "network_scan":    self.scan_network(),
        }

        threat_level = "low"
        if report["crontab"]["flagged"]:
            threat_level = "high"
        elif report["tmp_executables"]["count"] > 0:
            threat_level = "medium"

        report["threat_level"] = threat_level
        REPORT.write_text(json.dumps(report, indent=2))
        log.info("Threat report written. Level: %s", threat_level)
        _write_memory("security_agent", f"Threat report generated. Level: {threat_level}")
        return report
