#!/usr/bin/env python3
"""
alii_overhaul_tasks.py — Autonomous hardware + integration task runner.

Alii runs this to complete physical discovery tasks and populate the todo list
with anything requiring Pierre's manual action.

Run from Chat panel: /shell python3 /home/avalii/moltbot/scripts/alii_overhaul_tasks.py
Or directly:        python3 /home/avalii/moltbot/scripts/alii_overhaul_tasks.py

Tasks:
  1. Jetson camera discovery (USB v4l2 device detection)
  2. /dev/sdd storage inspection (500GB HDD)
  3. GitHub repo status report
  4. Service health snapshot
  5. Jetson camera service deployment (if camera found)
"""

from __future__ import annotations
import json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

WORKDIR     = Path("/home/avalii/moltbot")
DATA_DIR    = WORKDIR / "data"
LOGS_DIR    = WORKDIR / "logs"
JETSON_IP   = "100.87.137.61"
NTFY_URL    = os.environ.get("NTFY_URL", "https://ntfy.sh/alii-precision")

sys.path.insert(0, str(WORKDIR))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run(cmd: str, timeout: int = 15) -> tuple[int, str, str]:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       timeout=timeout, cwd=str(WORKDIR))
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _ssh(cmd: str, timeout: int = 12) -> tuple[int, str]:
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
         "-o", "StrictHostKeyChecking=no", f"avalii@{JETSON_IP}", cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return r.returncode, (r.stdout + r.stderr).strip()


def _ntfy(title: str, msg: str, priority: str = "default"):
    import urllib.request
    try:
        req = urllib.request.Request(
            NTFY_URL, data=msg.encode(),
            headers={"Title": title, "Priority": priority}, method="POST"
        )
        urllib.request.urlopen(req, timeout=6)
    except Exception as e:
        print(f"  [ntfy failed: {e}]")


def _add_todo(title: str, description: str, category: str = "action", priority: str = "high"):
    """Add to owner_todos.json directly (safe import path)."""
    try:
        from agents.todo_agent import todo
        todo.add_todo(title=title, description=description,
                      category=category, priority=priority,
                      added_by="alii_overhaul_tasks")
        print(f"  ✓ Todo created: [{priority.upper()}] {title}")
    except Exception as e:
        print(f"  ! Todo creation failed ({e}), writing directly to JSON")
        _write_todo_direct(title, description, category, priority)


def _write_todo_direct(title: str, description: str, category: str, priority: str):
    """Fallback: write todo directly to JSON file."""
    todo_file = DATA_DIR / "owner_todos.json"
    try:
        existing = json.loads(todo_file.read_text()) if todo_file.exists() else []
        if isinstance(existing, dict):
            todos = existing.get("todos", [])
        else:
            todos = existing
        todos.append({
            "id": f"overhaul_{int(time.time())}",
            "title": title,
            "description": description,
            "category": category,
            "priority": priority,
            "status": "pending",
            "added_by": "alii_overhaul_tasks",
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
        todo_file.write_text(json.dumps(todos if isinstance(existing, list) else {**existing, "todos": todos}, indent=2))
    except Exception as e:
        print(f"  ! Direct todo write failed: {e}")


def _log_result(task: str, result: dict):
    """Write task result to data/ for TUI display."""
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"overhaul_{task}.json"
    path.write_text(json.dumps({**result, "timestamp": datetime.now(timezone.utc).isoformat()}, indent=2))


# ══════════════════════════════════════════════════════════════════════════════
# Task 1 — Jetson Camera Discovery
# ══════════════════════════════════════════════════════════════════════════════

def task_jetson_camera():
    print("\n[1/4] Jetson Camera Discovery")
    print(f"  SSH → jetson @ {JETSON_IP}")

    # Test SSH connectivity first
    rc, out = _ssh("echo 'ssh_ok'", timeout=8)
    if rc != 0 or "ssh_ok" not in out:
        print(f"  ✗ Cannot reach Jetson via SSH")
        _add_todo(
            "Verify Jetson is online and SSH accessible",
            f"SSH to {JETSON_IP} failed during camera discovery. "
            "Check: (1) Jetson is powered on, (2) Tailscale is running on Jetson. "
            f"Test: ssh avalii@{JETSON_IP}",
            category="action", priority="high"
        )
        result = {"status": "ssh_failed", "jetson_ip": JETSON_IP}
        _log_result("jetson_camera", result)
        return result

    # Discover video devices
    rc, out = _ssh(
        "ls /dev/video* 2>/dev/null; echo '---'; "
        "v4l2-ctl --list-devices 2>/dev/null || echo 'v4l2-ctl not installed'; echo '---'; "
        "dmesg 2>/dev/null | tail -5 | grep -iE 'camera|video|uvc|usb' || echo 'no recent usb events'"
    )

    video_devices = [l for l in out.splitlines() if l.startswith("/dev/video")]

    if not video_devices:
        print(f"  ✗ No /dev/video* devices found on Jetson")
        print(f"  Output: {out[:200]}")
        _add_todo(
            "Check USB camera physical connection on Jetson",
            f"No /dev/video* devices detected on Jetson ({JETSON_IP}). "
            "Possible fixes: (1) Re-seat the USB camera cable, "
            "(2) Check camera compatibility (UVC required), "
            f"(3) SSH in and run: ls /dev/video* && dmesg | grep -i uvc. "
            f"Raw output: {out[:200]}",
            category="action", priority="high"
        )
        result = {"status": "no_camera", "jetson_output": out}
        _log_result("jetson_camera", result)
        return result

    print(f"  ✓ Camera found! Devices: {video_devices}")
    _ntfy("Alii Camera Found", f"Jetson camera detected: {video_devices[0]}", "default")

    # Get camera info
    rc2, cam_info = _ssh(f"v4l2-ctl --device={video_devices[0]} --info 2>/dev/null || echo 'no v4l2-ctl'")

    # Deploy camera service
    _deploy_jetson_camera_service(video_devices[0])

    result = {
        "status": "found",
        "devices": video_devices,
        "primary_device": video_devices[0],
        "camera_info": cam_info[:300],
    }
    _log_result("jetson_camera", result)
    return result


def _deploy_jetson_camera_service(device: str):
    """Deploy the camera HTTP service to Jetson."""
    service_script = '''#!/usr/bin/env python3
"""
jetson_camera_service.py — Lightweight HTTP camera server.
Runs on Jetson, exposes: GET /snapshot → JPEG, GET /info → device info
"""
import subprocess, json
from http.server import HTTPServer, BaseHTTPRequestHandler
DEVICE = "DEVICE_PLACEHOLDER"
PORT = 8765

class CamHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass  # suppress logs
    def do_GET(self):
        if self.path == "/snapshot":
            try:
                r = subprocess.run(
                    ["ffmpeg", "-f", "v4l2", "-i", DEVICE,
                     "-frames:v", "1", "-q:v", "2", "-f", "mjpeg", "pipe:1"],
                    capture_output=True, timeout=5
                )
                if r.returncode == 0:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.end_headers()
                    self.wfile.write(r.stdout)
                else:
                    self.send_error(500, "ffmpeg failed")
            except Exception as e:
                self.send_error(500, str(e))
        elif self.path == "/info":
            info = {"device": DEVICE, "port": PORT, "status": "running"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(info).encode())
        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_error(404)

if __name__ == "__main__":
    print(f"Camera service: {DEVICE} on :{PORT}")
    HTTPServer(("0.0.0.0", PORT), CamHandler).serve_forever()
'''.replace("DEVICE_PLACEHOLDER", device)

    # Write service script to Jetson
    script_path = "/home/avalii/jetson_camera_service.py"
    subprocess.run(
        ["ssh", "-o", "BatchMode=yes", f"avalii@{JETSON_IP}",
         f"cat > {script_path} << 'PYEOF'\n{service_script}\nPYEOF"],
        capture_output=True, timeout=15
    )

    # Try to start it (nohup, background)
    rc, out = _ssh(
        f"pkill -f jetson_camera_service.py 2>/dev/null || true; "
        f"nohup python3 {script_path} > /tmp/cam_service.log 2>&1 &"
    )

    # Verify it started
    time.sleep(2)
    rc2, check = _ssh("curl -s --max-time 2 http://localhost:8765/health || echo 'not_yet'")

    if "ok" in check:
        print(f"  ✓ Camera service deployed and running on Jetson:8765")
        _ntfy("Alii Camera Service", f"Camera service running on Jetson ({JETSON_IP}:8765)", "default")
    else:
        print(f"  ! Camera service started but health check pending. Check /tmp/cam_service.log on Jetson.")
        _add_todo(
            "Verify Jetson camera service is running",
            f"Camera service deployed to {script_path}. "
            f"Check status: ssh avalii@{JETSON_IP} 'curl http://localhost:8765/health'",
            category="config", priority="medium"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Task 2 — Storage /dev/sdd Discovery
# ══════════════════════════════════════════════════════════════════════════════

def task_storage_discovery():
    print("\n[2/4] Storage Discovery (/dev/sdd)")

    rc, lsblk_out, _ = _run("lsblk -J 2>/dev/null", timeout=10)
    try:
        lsblk_data = json.loads(lsblk_out)
        devices = [d["name"] for d in lsblk_data.get("blockdevices", [])]
        print(f"  Block devices found: {devices}")
    except Exception:
        devices = []
        print(f"  lsblk output: {lsblk_out[:200]}")

    if "sdd" not in devices:
        print("  ✗ /dev/sdd not found in lsblk")
        _add_todo(
            "Physically verify and seat 500GB HDD",
            "lsblk shows no /dev/sdd. The 500GB HDD may not be detected. "
            "Steps: (1) Power off Precision, (2) Re-seat the SATA cable and power connector, "
            "(3) Power on, (4) Run: lsblk | grep sdd. "
            "If still missing, check BIOS/UEFI storage detection. "
            f"Current devices: {devices}",
            category="action", priority="high"
        )
        result = {"status": "not_present", "devices": devices}
        _log_result("storage_sdd", result)
        return result

    print("  ✓ /dev/sdd found!")

    # Check what's on it
    rc1, fdisk, _ = _run("sudo -n fdisk -l /dev/sdd 2>/dev/null", timeout=8)
    rc2, blkid, _ = _run("sudo -n blkid /dev/sdd 2>/dev/null", timeout=5)
    rc3, file_out, _ = _run("sudo -n file -s /dev/sdd 2>/dev/null | head -3", timeout=5)

    print(f"  fdisk: {fdisk[:150]}")
    print(f"  blkid: {blkid}")
    print(f"  file:  {file_out}")

    result = {
        "status": "present",
        "fdisk": fdisk,
        "blkid": blkid,
        "file": file_out,
    }

    # Determine if drive is empty or has data
    has_partition = "sdd1" in fdisk or "Disk label type" in fdisk
    has_filesystem = bool(blkid.strip())

    if has_filesystem and has_partition:
        print(f"  ! Drive has existing filesystem — inspection needed before wiping")
        _add_todo(
            "Inspect /dev/sdd before wiping — drive has data",
            f"500GB /dev/sdd has existing filesystem. DO NOT wipe without reviewing. "
            f"Inspect: sudo mount -o ro /dev/sdd1 /mnt/tmp_inspect && ls /mnt/tmp_inspect. "
            f"If safe to wipe: sudo mkfs.ext4 -L storage4 /dev/sdd. "
            f"Then add to fstab: UUID=$(sudo blkid -s UUID -o value /dev/sdd1) — "
            f"mount as /mnt/storage4. blkid output: {blkid[:100]}",
            category="action", priority="high"
        )
    else:
        print(f"  Drive appears empty — generating mount instructions")
        # Get UUID if available
        rc_uuid, uuid_out, _ = _run("sudo -n blkid -s UUID -o value /dev/sdd 2>/dev/null", timeout=5)
        uuid = uuid_out.strip()

        mount_cmds = (
            "sudo parted /dev/sdd mklabel gpt\n"
            "sudo parted /dev/sdd mkpart primary ext4 0% 100%\n"
            "sudo mkfs.ext4 -L storage4 /dev/sdd1\n"
            "sudo mkdir -p /mnt/storage4\n"
            "UUID=$(sudo blkid -s UUID -o value /dev/sdd1)\n"
            'echo "UUID=$UUID /mnt/storage4 ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab\n'
            "sudo mount -a && df -h /mnt/storage4\n"
            "# Then add NFS export:\n"
            'echo "/mnt/storage4 100.0.0.0/8(rw,sync,no_subtree_check)" | sudo tee -a /etc/exports\n'
            "sudo exportfs -ra"
        )
        result["mount_commands"] = mount_cmds
        _add_todo(
            "Format and mount /dev/sdd as /mnt/storage4",
            f"/dev/sdd (500GB) is present and appears empty. Ready to format. "
            f"Run these commands:\n{mount_cmds}",
            category="action", priority="medium"
        )

    _log_result("storage_sdd", result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Task 3 — GitHub Repo Status
# ══════════════════════════════════════════════════════════════════════════════

def task_github_status():
    print("\n[3/4] GitHub Repository Status")

    repos = {
        "moltbot": "/home/avalii/moltbot",
        "alii-core": "/home/avalii/alii",
        "alii-public": "/home/avalii/alii_public",
    }

    results = {}
    for name, path in repos.items():
        if not Path(path).exists():
            results[name] = {"status": "not_found"}
            continue

        rc_s, status, _ = _run(f"git -C {path} status --short", timeout=10)
        rc_l, log_out, _ = _run(f"git -C {path} log --oneline -3", timeout=10)
        rc_f, fetch, _ = _run(f"git -C {path} fetch --dry-run 2>&1", timeout=15)
        rc_r, remote, _ = _run(f"git -C {path} remote -v | head -2", timeout=5)

        modified = len([l for l in status.splitlines() if l.strip()])
        behind   = "behind" in fetch.lower()
        ahead    = "ahead" in fetch.lower()

        results[name] = {
            "path": path,
            "modified_files": modified,
            "behind": behind,
            "ahead": ahead,
            "recent_commits": log_out,
            "remote": remote.split("\n")[0] if remote else "unknown",
        }

        icon = "⚠️" if modified > 0 or behind else "✓"
        print(f"  {icon} {name}: {modified} modified, {'behind' if behind else 'up-to-date'}")

        if modified > 0:
            details_rc, details, _ = _run(f"git -C {path} status --short", timeout=5)
            _add_todo(
                f"Review and commit {name} changes ({modified} modified files)",
                f"Repo at {path} has {modified} modified files. "
                f"Review: git -C {path} diff --stat HEAD\n"
                f"Commit: git -C {path} add -A && git -C {path} commit -m 'feat: alii overhaul updates'\n"
                f"Push: git -C {path} push origin main\n"
                f"⚠️  Do NOT commit: .env, *.key, cluster_credentials.json (already gitignored)\n"
                f"Modified: {details[:200]}",
                category="config", priority="medium"
            )

        if behind:
            _add_todo(
                f"Pull latest changes for {name}",
                f"Repo {name} is behind remote. Run: git -C {path} pull --rebase",
                category="config", priority="low"
            )

    _log_result("github_status", results)
    return results


# ══════════════════════════════════════════════════════════════════════════════
# Task 4 — Service Health Snapshot
# ══════════════════════════════════════════════════════════════════════════════

def task_service_health():
    print("\n[4/4] Service Health Snapshot")

    sys.path.insert(0, str(WORKDIR))
    from alii_tui_cluster import sync_collect_services, sync_collect_ollama_models

    services = sync_collect_services()
    models   = sync_collect_ollama_models()

    down = [k for k, v in services.items() if not v]
    up   = [k for k, v in services.items() if v]

    print(f"  Services: {len(up)}/{len(services)} up")
    if down:
        print(f"  DOWN: {', '.join(down)}")
        _add_todo(
            f"Restart down services: {', '.join(down)}",
            f"These Alii services are not responding: {', '.join(down)}. "
            "Restart with: sudo systemctl restart <service-name>. "
            "Check logs: journalctl -u <service-name> -n 30",
            category="action", priority="high"
        )

    print(f"  Ollama models: {models}")

    result = {
        "services_up": up,
        "services_down": down,
        "ollama_models": models,
    }
    _log_result("service_health", result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def run_all():
    start = time.time()
    print("=" * 60)
    print("  ALII OVERHAUL TASKS — Autonomous Discovery")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    _ntfy("Alii Overhaul", "Starting autonomous discovery tasks...", "default")

    r1 = task_jetson_camera()
    r2 = task_storage_discovery()
    r3 = task_github_status()
    r4 = task_service_health()

    elapsed = round(time.time() - start, 1)

    summary = (
        f"Camera: {r1.get('status', '?')} | "
        f"Storage: {r2.get('status', '?')} | "
        f"Repos checked: {len(r3)} | "
        f"Services: {len(r4.get('services_up', []))}/{len(r4.get('services_up', [])) + len(r4.get('services_down', []))} up"
    )

    print("\n" + "=" * 60)
    print(f"  DONE in {elapsed}s")
    print(f"  {summary}")
    print(f"  Results in: /home/avalii/moltbot/data/overhaul_*.json")
    print(f"  Todos created for all items needing your attention.")
    print("=" * 60)

    _ntfy(
        "Alii Overhaul Complete",
        f"Discovery tasks done in {elapsed}s.\n{summary}\nCheck todos and ntfy for details.",
        "default"
    )


if __name__ == "__main__":
    run_all()
