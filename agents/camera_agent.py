#!/usr/bin/env python3
"""
CameraAgent — RTSP camera integration for Alii.
Discovers cameras on the local network, tests streams, and captures snapshots.

Network note: if no RTSP ports are found open, the camera may be offline,
behind NAT, or using a non-standard port. This agent checks common alternatives.
"""

import json
import logging
import os
import subprocess
import socket
import datetime
from pathlib import Path

log = logging.getLogger("alii.camera_agent")

WORKDIR      = Path("/home/avalii/moltbot")
SNAPSHOT_DIR = WORKDIR / "snapshots"

# Ports commonly used by IP cameras:
# 554   — standard RTSP
# 8554  — alternate RTSP
# 8080  — HTTP/ONVIF
# 37777 — Dahua TCP
# 34567 — older Dahua / clone DVRs
# 80    — HTTP (ONVIF, web UI)
CAMERA_PORTS = [554, 8554, 8080, 37777, 34567, 80]

# Populate from environment variable CAMERA_IPS if set (comma-separated).
# Falls back to an empty list; discover_cameras() will probe the subnet.
_env_ips = os.environ.get("CAMERA_IPS", "").strip()
DEFAULT_CAMERA_IPS: list[str] = [ip.strip() for ip in _env_ips.split(",") if ip.strip()]

# Common RTSP path patterns used by major camera brands.
RTSP_PATH_PATTERNS = [
    "/stream1",
    "/live",
    "/h264",
    "/cam/realmonitor?channel=1&subtype=0",
    "/0/1/main",
    "/video1",
    "/Streaming/Channels/101",
    "/ch0_0.264",
]

FFMPEG_TIMEOUT  = 15   # seconds to wait for ffmpeg snapshot
FFPROBE_TIMEOUT = 10   # seconds to wait for ffprobe stream check
PORT_TIMEOUT    = 1.0  # seconds per TCP probe


def _write_memory(category: str, content: str) -> None:
    """Persist an event to Alii's SQLite memory if available."""
    try:
        import sys
        sys.path.insert(0, str(WORKDIR))
        from alii_sqlite_memory import AliiSQLiteMemory  # type: ignore
        AliiSQLiteMemory().add_memory(category=category, content=content)
    except Exception as exc:
        log.debug("Memory write skipped: %s", exc)


def _tcp_open(host: str, port: int, timeout: float = PORT_TIMEOUT) -> bool:
    """Return True if a TCP connection to host:port succeeds within timeout."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class CameraAgent:
    """
    Handles RTSP camera discovery, stream testing, and snapshot capture.

    Usage
    -----
    agent = CameraAgent()
    results = agent.scan_and_capture_all()
    print(results)
    """

    def __init__(self) -> None:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self._inventory: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_cameras(self, subnet: str = "192.168.1.0/24") -> list[str]:
        """
        Ping-sweep the subnet and check each live host for known camera ports.

        Parameters
        ----------
        subnet : str
            CIDR notation subnet to scan (default "192.168.1.0/24").

        Returns
        -------
        list[str]
            IP addresses that responded to ping AND had at least one camera
            port open.
        """
        log.info("Starting camera discovery on subnet %s", subnet)

        # If the user pre-configured specific IPs, skip the subnet sweep.
        if DEFAULT_CAMERA_IPS:
            log.info("Using pre-configured camera IPs: %s", DEFAULT_CAMERA_IPS)
            return DEFAULT_CAMERA_IPS

        live_hosts = self._ping_sweep(subnet)
        log.info("Ping sweep found %d live hosts", len(live_hosts))

        candidates: list[str] = []
        for host in live_hosts:
            open_ports = [p for p in CAMERA_PORTS if _tcp_open(host, p)]
            if open_ports:
                log.info("Camera candidate: %s  (open ports: %s)", host, open_ports)
                candidates.append(host)
            else:
                log.debug("Host %s alive but no camera ports open", host)

        _write_memory(
            "camera_discovery",
            f"Scanned {subnet}: {len(live_hosts)} live hosts, "
            f"{len(candidates)} camera candidates: {candidates}",
        )
        return candidates

    def _ping_sweep(self, subnet: str) -> list[str]:
        """
        Use nmap (if available) or a raw ping loop to find live hosts.
        Returns a list of IP strings.
        """
        # Try nmap first — it is far faster for a /24.
        if self._cmd_available("nmap"):
            return self._nmap_ping(subnet)

        # Fallback: derive the /24 prefix and ping .1–.254 individually.
        return self._manual_ping(subnet)

    def _nmap_ping(self, subnet: str) -> list[str]:
        """Run nmap -sn (ping scan) and parse the results."""
        try:
            result = subprocess.run(
                ["nmap", "-sn", "--open", subnet],
                capture_output=True, text=True, timeout=60,
            )
            live: list[str] = []
            for line in result.stdout.splitlines():
                if "Nmap scan report for" in line:
                    parts = line.split()
                    ip = parts[-1].strip("()")
                    if self._is_ip(ip):
                        live.append(ip)
            return live
        except Exception as exc:
            log.warning("nmap ping sweep failed: %s", exc)
            return []

    def _manual_ping(self, subnet: str) -> list[str]:
        """
        Derive the /24 prefix from the CIDR string and ping .1–.254.
        Works even without nmap.
        """
        try:
            prefix = ".".join(subnet.split("/")[0].split(".")[:3])
        except (IndexError, AttributeError):
            prefix = "192.168.1"

        live: list[str] = []
        procs: list[tuple[str, subprocess.Popen]] = []

        for last_octet in range(1, 255):
            ip = f"{prefix}.{last_octet}"
            proc = subprocess.Popen(
                ["ping", "-c", "1", "-W", "1", ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            procs.append((ip, proc))

        for ip, proc in procs:
            if proc.wait() == 0:
                live.append(ip)

        return live

    # ------------------------------------------------------------------
    # RTSP URL helpers
    # ------------------------------------------------------------------

    def get_rtsp_url(
        self,
        camera_ip: str,
        user: str = "admin",
        password: str = "",
    ) -> str | None:
        """
        Try common RTSP URL patterns for the given camera IP.

        Attempts both port 554 and 8554.  Returns the first URL that passes
        test_stream(), or None if none succeed.

        Parameters
        ----------
        camera_ip : str
            IP address of the camera.
        user : str
            RTSP username (default "admin").
        password : str
            RTSP password (default empty string).

        Returns
        -------
        str | None
            A working RTSP URL or None.
        """
        auth = f"{user}:{password}@" if user else ""
        ports_to_try = [554, 8554]

        for port in ports_to_try:
            for path in RTSP_PATH_PATTERNS:
                url = f"rtsp://{auth}{camera_ip}:{port}{path}"
                log.debug("Testing RTSP URL: %s", url)
                if self.test_stream(url):
                    log.info("Working RTSP URL found: %s", url)
                    return url

        log.warning("No working RTSP URL found for %s", camera_ip)
        return None

    def test_stream(self, rtsp_url: str) -> bool:
        """
        Use ffprobe to check whether an RTSP stream is accessible.

        Parameters
        ----------
        rtsp_url : str
            The RTSP URL to probe.

        Returns
        -------
        bool
            True if ffprobe can read stream metadata within the timeout.
        """
        if not self._cmd_available("ffprobe"):
            log.warning("ffprobe not found; cannot test stream %s", rtsp_url)
            return False

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "quiet",
                    "-rtsp_transport", "tcp",
                    "-i", rtsp_url,
                    "-show_entries", "stream=codec_name",
                    "-of", "json",
                ],
                capture_output=True,
                text=True,
                timeout=FFPROBE_TIMEOUT,
            )
            if result.returncode == 0 and "codec_name" in result.stdout:
                log.debug("ffprobe OK for %s", rtsp_url)
                return True
        except subprocess.TimeoutExpired:
            log.debug("ffprobe timed out for %s", rtsp_url)
        except Exception as exc:
            log.debug("ffprobe error for %s: %s", rtsp_url, exc)

        return False

    # ------------------------------------------------------------------
    # Snapshot capture
    # ------------------------------------------------------------------

    def capture_snapshot(
        self,
        camera_ip: str,
        rtsp_url: str | None = None,
    ) -> dict:
        """
        Grab a single JPEG frame from the camera's RTSP stream.

        If rtsp_url is not provided, get_rtsp_url() is called automatically.
        If ffmpeg is unavailable, a JSON status file is written instead.

        Parameters
        ----------
        camera_ip : str
            IP address of the camera (used for file naming).
        rtsp_url : str | None
            Explicit RTSP URL to use.  If None, auto-detected.

        Returns
        -------
        dict
            {
                "camera_ip": ...,
                "rtsp_url": ...,
                "snapshot_path": ... or None,
                "status_file": ... or None,
                "success": bool,
                "error": ... or None,
                "timestamp": ...,
            }
        """
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        result: dict = {
            "camera_ip":     camera_ip,
            "rtsp_url":      rtsp_url,
            "snapshot_path": None,
            "status_file":   None,
            "success":       False,
            "error":         None,
            "timestamp":     ts,
        }

        # Resolve RTSP URL if not supplied.
        if not rtsp_url:
            rtsp_url = self.get_rtsp_url(camera_ip)
            result["rtsp_url"] = rtsp_url

        if not rtsp_url:
            result["error"] = "No working RTSP URL found"
            self._write_status_file(camera_ip, ts, result)
            result["status_file"] = str(SNAPSHOT_DIR / f"{camera_ip}_{ts}_status.json")
            return result

        output_path = SNAPSHOT_DIR / f"{camera_ip}_{ts}.jpg"

        if not self._cmd_available("ffmpeg"):
            result["error"] = "ffmpeg not available"
            log.warning("ffmpeg not found; writing status file for %s", camera_ip)
            self._write_status_file(camera_ip, ts, result)
            result["status_file"] = str(SNAPSHOT_DIR / f"{camera_ip}_{ts}_status.json")
            return result

        try:
            cmd = [
                "ffmpeg",
                "-y",                         # overwrite without asking
                "-rtsp_transport", "tcp",
                "-i", rtsp_url,
                "-frames:v", "1",             # capture exactly one frame
                "-q:v", "2",                  # JPEG quality (2 = near-lossless)
                str(output_path),
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=FFMPEG_TIMEOUT,
            )

            if proc.returncode == 0 and output_path.exists():
                result["snapshot_path"] = str(output_path)
                result["success"] = True
                log.info("Snapshot saved: %s", output_path)
                _write_memory(
                    "camera_snapshot",
                    f"Snapshot captured from {camera_ip} -> {output_path}",
                )
            else:
                result["error"] = (proc.stderr or "ffmpeg returned non-zero").strip()
                log.warning("ffmpeg failed for %s: %s", camera_ip, result["error"])
                self._write_status_file(camera_ip, ts, result)
                result["status_file"] = str(SNAPSHOT_DIR / f"{camera_ip}_{ts}_status.json")

        except subprocess.TimeoutExpired:
            result["error"] = f"ffmpeg timed out after {FFMPEG_TIMEOUT}s"
            log.warning("ffmpeg timeout for %s", camera_ip)
            self._write_status_file(camera_ip, ts, result)
            result["status_file"] = str(SNAPSHOT_DIR / f"{camera_ip}_{ts}_status.json")
        except Exception as exc:
            result["error"] = str(exc)
            log.error("Unexpected error capturing %s: %s", camera_ip, exc)
            self._write_status_file(camera_ip, ts, result)
            result["status_file"] = str(SNAPSHOT_DIR / f"{camera_ip}_{ts}_status.json")

        return result

    def _write_status_file(self, camera_ip: str, ts: str, data: dict) -> None:
        """Write a JSON status file when a real snapshot cannot be captured."""
        path = SNAPSHOT_DIR / f"{camera_ip}_{ts}_status.json"
        try:
            path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as exc:
            log.error("Could not write status file %s: %s", path, exc)

    # ------------------------------------------------------------------
    # Aggregate operations
    # ------------------------------------------------------------------

    def scan_and_capture_all(
        self, subnet: str = "192.168.1.0/24"
    ) -> dict[str, dict]:
        """
        Discover cameras on the subnet and attempt a snapshot from each.

        Parameters
        ----------
        subnet : str
            CIDR subnet to scan.

        Returns
        -------
        dict[str, dict]
            Mapping of camera_ip -> capture_snapshot() result dict.
        """
        cameras = self.discover_cameras(subnet)
        if not cameras:
            log.info("No cameras discovered on %s", subnet)
            return {}

        results: dict[str, dict] = {}
        for ip in cameras:
            log.info("Attempting capture from %s", ip)
            results[ip] = self.capture_snapshot(ip)

        self._inventory.update(results)
        return results

    # ------------------------------------------------------------------
    # Status / inventory
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """
        Return the current camera inventory derived from the snapshots directory.

        Scans SNAPSHOT_DIR for JPEG files and JSON status files, groups them
        by camera IP, and returns a summary dict.

        Returns
        -------
        dict
            {
                "snapshot_dir": str,
                "cameras": {
                    "<ip>": {
                        "snapshots": [list of .jpg paths],
                        "status_files": [list of _status.json paths],
                        "latest_snapshot": str | None,
                    },
                    ...
                },
                "total_cameras": int,
                "total_snapshots": int,
            }
        """
        cameras: dict[str, dict] = {}

        for entry in sorted(SNAPSHOT_DIR.iterdir()):
            if not entry.is_file():
                continue

            name = entry.name
            # File names follow the pattern: {ip}_{timestamp}.jpg
            # or {ip}_{timestamp}_status.json
            parts = name.split("_")
            if len(parts) < 2:
                continue

            ip = parts[0]  # first segment is always the IP
            cameras.setdefault(ip, {"snapshots": [], "status_files": [], "latest_snapshot": None})

            if name.endswith(".jpg"):
                cameras[ip]["snapshots"].append(str(entry))
            elif name.endswith("_status.json"):
                cameras[ip]["status_files"].append(str(entry))

        for ip, info in cameras.items():
            if info["snapshots"]:
                info["latest_snapshot"] = max(info["snapshots"])

        total_snapshots = sum(len(v["snapshots"]) for v in cameras.values())

        return {
            "snapshot_dir":    str(SNAPSHOT_DIR),
            "cameras":         cameras,
            "total_cameras":   len(cameras),
            "total_snapshots": total_snapshots,
        }

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cmd_available(cmd: str) -> bool:
        """Return True if the given command exists on PATH."""
        try:
            subprocess.run(
                [cmd, "-version"],
                capture_output=True,
                timeout=3,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    @staticmethod
    def _is_ip(s: str) -> bool:
        """Return True if s looks like a dotted-quad IPv4 address."""
        parts = s.split(".")
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False


# ---------------------------------------------------------------------------
# CLI entry-point (python -m agents.camera_agent  or  ./camera_agent.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    )

    import argparse

    parser = argparse.ArgumentParser(description="Alii CameraAgent CLI")
    parser.add_argument("--subnet",    default="192.168.1.0/24", help="Subnet to scan")
    parser.add_argument("--capture",   metavar="IP",             help="Capture snapshot from a specific IP")
    parser.add_argument("--rtsp",      metavar="URL",            help="Explicit RTSP URL for --capture")
    parser.add_argument("--status",    action="store_true",      help="Show snapshot inventory")
    parser.add_argument("--scan-all",  action="store_true",      help="Discover and capture from all cameras")
    args = parser.parse_args()

    agent = CameraAgent()

    if args.status:
        print(json.dumps(agent.status(), indent=2))
    elif args.capture:
        print(json.dumps(agent.capture_snapshot(args.capture, rtsp_url=args.rtsp), indent=2, default=str))
    elif args.scan_all:
        print(json.dumps(agent.scan_and_capture_all(subnet=args.subnet), indent=2, default=str))
    else:
        parser.print_help()
