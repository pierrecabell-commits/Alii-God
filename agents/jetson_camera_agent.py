#!/usr/bin/env python3
"""
jetson_camera_agent.py — Jetson edge camera integration for Alii cluster.

Manages camera discovery and snapshot capture on the Jetson node via SSH.
Camera service runs on Jetson at port 8765 (deployed by alii_overhaul_tasks.py).

Usage from alii_core:
    from agents.jetson_camera_agent import JetsonCameraAgent
    cam = JetsonCameraAgent()
    snap = cam.capture_snapshot(save_path="/home/avalii/moltbot/snapshots/jetson_snap.jpg")
"""

from __future__ import annotations
import json, logging, os, subprocess, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

WORKDIR        = Path("/home/avalii/moltbot")
SNAPSHOTS_DIR  = WORKDIR / "snapshots"
DATA_DIR       = WORKDIR / "data"
LOGS_DIR       = WORKDIR / "logs"
LOG_FILE       = LOGS_DIR / "jetson_camera.log"

JETSON_IP      = "100.87.137.61"
JETSON_USER    = "avalii"
CAM_PORT       = 8765
CAM_SERVICE    = f"/home/avalii/jetson_camera_service.py"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [jetson_cam] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
log = logging.getLogger("alii.jetson_camera")


class JetsonCameraAgent:
    """
    Manages camera access on the Jetson edge node.
    All operations happen via SSH or HTTP to the camera service on port 8765.
    """

    def __init__(self):
        SNAPSHOTS_DIR.mkdir(exist_ok=True)
        self._last_snapshot: str | None = None
        self._service_running: bool = False

    # ── Connectivity ───────────────────────────────────────────────────────────

    def is_jetson_reachable(self) -> bool:
        import socket
        try:
            with socket.create_connection((JETSON_IP, 22), timeout=3):
                return True
        except Exception:
            return False

    def is_camera_service_up(self) -> bool:
        """Check if the camera HTTP service is running on Jetson:8765."""
        try:
            with urllib.request.urlopen(
                f"http://{JETSON_IP}:{CAM_PORT}/health", timeout=3
            ) as r:
                return r.read() == b"ok"
        except Exception:
            return False

    def start_camera_service(self) -> bool:
        """SSH to Jetson and start the camera service if not running."""
        if self.is_camera_service_up():
            return True

        log.info("Starting camera service on Jetson...")
        rc, out = self._ssh(
            f"nohup python3 {CAM_SERVICE} > /tmp/cam_service.log 2>&1 & sleep 2 && "
            f"curl -s --max-time 2 http://localhost:{CAM_PORT}/health"
        )
        if "ok" in out:
            log.info("Camera service started successfully")
            self._service_running = True
            return True
        log.warning("Camera service may not have started. Output: %s", out[:100])
        return False

    # ── Camera discovery ───────────────────────────────────────────────────────

    def discover_devices(self) -> dict:
        """Discover USB camera devices on the Jetson."""
        if not self.is_jetson_reachable():
            return {"error": "Jetson unreachable", "devices": []}

        rc, out = self._ssh(
            "ls /dev/video* 2>/dev/null; echo '---'; "
            "v4l2-ctl --list-devices 2>/dev/null | head -20"
        )

        parts = out.split("---")
        devices = [l.strip() for l in parts[0].splitlines() if "/dev/video" in l]
        details = parts[1].strip() if len(parts) > 1 else ""

        result = {
            "devices": devices,
            "primary": devices[0] if devices else None,
            "v4l2_info": details[:300],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Save discovery result
        (DATA_DIR / "jetson_camera_discovery.json").write_text(json.dumps(result, indent=2))
        log.info("Discovered %d camera devices: %s", len(devices), devices)
        return result

    # ── Snapshot capture ───────────────────────────────────────────────────────

    def capture_snapshot(self, save_path: str | None = None) -> str | None:
        """
        Capture a JPEG snapshot from the Jetson camera.
        Returns path to saved snapshot or None on failure.
        """
        if save_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = str(SNAPSHOTS_DIR / f"jetson_{ts}.jpg")

        # Ensure camera service is up
        if not self.is_camera_service_up():
            if not self.start_camera_service():
                log.error("Cannot start camera service")
                return None

        try:
            url = f"http://{JETSON_IP}:{CAM_PORT}/snapshot"
            with urllib.request.urlopen(url, timeout=10) as r:
                data = r.read()
                if len(data) > 1000:  # Valid JPEG will be much larger
                    Path(save_path).write_bytes(data)
                    self._last_snapshot = save_path
                    log.info("Snapshot saved: %s (%d bytes)", save_path, len(data))
                    return save_path
                else:
                    log.warning("Snapshot too small (%d bytes), may be invalid", len(data))
                    return None
        except Exception as e:
            log.error("Snapshot capture failed: %s", e)
            return None

    def capture_via_ssh(self, save_path: str | None = None) -> str | None:
        """Fallback: capture snapshot via SSH + ffmpeg directly (no service needed)."""
        if save_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = str(SNAPSHOTS_DIR / f"jetson_{ts}.jpg")

        remote_tmp = f"/tmp/alii_snap_{int(time.time())}.jpg"

        # Capture on Jetson
        rc, _ = self._ssh(
            f"ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 -q:v 2 {remote_tmp} -y -loglevel quiet 2>&1"
        )

        if rc != 0:
            log.error("ffmpeg capture failed on Jetson")
            return None

        # SCP back to Precision
        r = subprocess.run(
            ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
             f"{JETSON_USER}@{JETSON_IP}:{remote_tmp}", save_path],
            capture_output=True, timeout=15
        )

        if r.returncode == 0:
            log.info("Snapshot transferred via SCP: %s", save_path)
            self._last_snapshot = save_path
            # Cleanup remote tmp
            self._ssh(f"rm -f {remote_tmp}")
            return save_path

        log.error("SCP transfer failed: %s", r.stderr.decode()[:100])
        return None

    def get_camera_info(self) -> dict:
        """Get camera device info from Jetson."""
        if self.is_camera_service_up():
            try:
                with urllib.request.urlopen(
                    f"http://{JETSON_IP}:{CAM_PORT}/info", timeout=5
                ) as r:
                    return json.loads(r.read())
            except Exception:
                pass
        # Fallback to SSH
        rc, out = self._ssh("v4l2-ctl --device=/dev/video0 --info 2>/dev/null | head -15")
        return {"raw": out, "ip": JETSON_IP, "port": CAM_PORT}

    @property
    def last_snapshot_path(self) -> str | None:
        return self._last_snapshot

    # ── Private helpers ────────────────────────────────────────────────────────

    def _ssh(self, cmd: str, timeout: int = 12) -> tuple[int, str]:
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
             "-o", "StrictHostKeyChecking=no",
             f"{JETSON_USER}@{JETSON_IP}", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, (r.stdout + r.stderr).strip()


# ── Singleton ──────────────────────────────────────────────────────────────────

_instance: JetsonCameraAgent | None = None

def get_camera() -> JetsonCameraAgent:
    global _instance
    if _instance is None:
        _instance = JetsonCameraAgent()
    return _instance


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    cam = JetsonCameraAgent()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "discover"

    if cmd == "discover":
        result = cam.discover_devices()
        print(json.dumps(result, indent=2))

    elif cmd == "snapshot":
        path = cam.capture_snapshot()
        if path:
            print(f"Snapshot: {path}")
        else:
            print("Snapshot failed. Trying SSH fallback...")
            path = cam.capture_via_ssh()
            print(f"SSH snapshot: {path or 'failed'}")

    elif cmd == "status":
        print(f"Jetson reachable:   {cam.is_jetson_reachable()}")
        print(f"Camera service up:  {cam.is_camera_service_up()}")
        print(f"Last snapshot:      {cam.last_snapshot_path}")

    elif cmd == "info":
        info = cam.get_camera_info()
        print(json.dumps(info, indent=2))
