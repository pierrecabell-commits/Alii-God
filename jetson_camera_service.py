#!/usr/bin/env python3
"""
jetson_camera_service.py — Lightweight camera HTTP server (stdlib only, no pip deps).

Runs on Jetson at port 8765.
Endpoints:
  GET /health    → "ok"
  GET /snapshot  → JPEG image
  GET /info      → JSON device info

Deploy:
  scp jetson_camera_service.py avalii@$JETSON_IP:/home/avalii/jetson_camera_service.py
  ssh avalii@$JETSON_IP "nohup python3 /home/avalii/jetson_camera_service.py > /tmp/cam_service.log 2>&1 &"
"""

import http.server, json, os, subprocess, threading, time
from pathlib import Path

PORT   = 8765
DEVICE = "/dev/video0"
TMP    = "/tmp/alii_snap.jpg"

_last_snap_time  = 0.0
_last_snap_bytes = b""
_snap_lock       = threading.Lock()
SNAP_CACHE_TTL   = 3.0  # seconds — don't re-capture more than once per 3s


def _capture() -> bytes:
    """Capture a JPEG from the camera device using ffmpeg."""
    global _last_snap_time, _last_snap_bytes
    now = time.time()
    with _snap_lock:
        if now - _last_snap_time < SNAP_CACHE_TTL and _last_snap_bytes:
            return _last_snap_bytes

        result = subprocess.run(
            ["ffmpeg", "-f", "v4l2", "-input_format", "mjpeg",
             "-i", DEVICE, "-frames:v", "1", "-q:v", "3",
             "-vf", "scale=640:480", TMP, "-y", "-loglevel", "quiet"],
            timeout=10, capture_output=True
        )

        if result.returncode != 0:
            # Try without mjpeg input format (some cameras need this)
            result = subprocess.run(
                ["ffmpeg", "-f", "v4l2", "-i", DEVICE,
                 "-frames:v", "1", "-q:v", "3",
                 "-vf", "scale=640:480", TMP, "-y", "-loglevel", "quiet"],
                timeout=10, capture_output=True
            )

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[:200]}")

        data = Path(TMP).read_bytes()
        _last_snap_time  = time.time()
        _last_snap_bytes = data
        return data


def _get_device_info() -> dict:
    """Get v4l2 device info."""
    try:
        out = subprocess.run(
            ["v4l2-ctl", "--device=" + DEVICE, "--info"],
            capture_output=True, text=True, timeout=5
        ).stdout[:500]
    except Exception:
        out = "v4l2-ctl not available"

    # List devices
    devs = [str(p) for p in Path("/dev").glob("video*")]
    return {
        "device":    DEVICE,
        "port":      PORT,
        "devices":   devs,
        "primary":   devs[0] if devs else None,
        "v4l2_info": out,
        "status":    "ok" if Path(DEVICE).exists() else "no_device",
    }


class CamHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Keep logs clean — captured to file

    def do_GET(self):
        try:
            if self.path == "/health":
                self._send_text(200, b"ok")

            elif self.path == "/snapshot":
                data = _capture()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(data)

            elif self.path == "/info":
                info = _get_device_info()
                data = json.dumps(info, indent=2).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            elif self.path == "/thumb":
                # Tiny 160x120 thumbnail for ASCII art display
                data = _capture()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            else:
                self._send_text(404, b"not found")

        except Exception as e:
            err = str(e).encode()
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)

    def _send_text(self, code: int, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    # Verify device exists
    if not Path(DEVICE).exists():
        print(f"WARNING: {DEVICE} not found. Server will start but snapshots will fail.")

    import socket as _socket
    server = http.server.HTTPServer(("0.0.0.0", PORT), CamHandler)
    server.socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    print(f"Camera service listening on 0.0.0.0:{PORT}")
    print(f"Device: {DEVICE}")
    print(f"Endpoints: /health  /snapshot  /info  /thumb")
    server.serve_forever()


if __name__ == "__main__":
    main()
