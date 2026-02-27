#!/usr/bin/env python3
"""
System Optimizer — Alii hardware and OS tuning.
Sets CPU governor, swappiness, clears old logs, checks disk/memory.
Writes optimization_report.json.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [optimizer] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/home/avalii/moltbot/logs/optimizer_run.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("system_optimizer")

WORKDIR = Path("/home/avalii/moltbot")
REPORT  = WORKDIR / "memory" / "optimization_report.json"
LOG_MAX_DAYS = 7


def _run(cmd: list[str], timeout: int = 15) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except FileNotFoundError:
        return -2, f"not found: {cmd[0]}"
    except Exception as exc:
        return -3, str(exc)


# ── CPU governor ───────────────────────────────────────────────────────────────

def set_cpu_governor(governor: str = "performance") -> dict:
    """
    Attempt to set CPU frequency governor.
    Requires write access to /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor.
    Falls back gracefully if not writable (needs root).
    """
    cpu_paths = list(Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_governor"))
    results = []
    for p in cpu_paths:
        current = p.read_text().strip() if p.exists() else "unknown"
        if current == governor:
            results.append({"cpu": p.parts[-3], "status": "already_set", "governor": governor})
            continue
        try:
            p.write_text(governor)
            results.append({"cpu": p.parts[-3], "status": "set", "governor": governor})
        except PermissionError:
            results.append({
                "cpu": p.parts[-3], "status": "permission_denied",
                "current": current, "note": "Run as root or via sudo to change governor"
            })
        except Exception as exc:
            results.append({"cpu": p.parts[-3], "status": "error", "error": str(exc)})

    if not cpu_paths:
        log.info("No cpufreq paths found (may be a VM or locked kernel).")
        return {"status": "unavailable", "note": "cpufreq not exposed"}

    success = sum(1 for r in results if r.get("status") in ("set", "already_set"))
    log.info("CPU governor: %d/%d cores set to '%s'.", success, len(results), governor)
    return {"governor": governor, "cores": results, "success_count": success}


# ── Swappiness ─────────────────────────────────────────────────────────────────

def set_swappiness(value: int = 10) -> dict:
    """
    Set vm.swappiness via sysctl. Reduces swapping for better LLM performance.
    Needs root; if unavailable, reads current value and documents the command.
    """
    swappiness_file = Path("/proc/sys/vm/swappiness")
    current = int(swappiness_file.read_text().strip()) if swappiness_file.exists() else -1

    if current == value:
        log.info("Swappiness already %d.", value)
        return {"current": current, "target": value, "status": "already_set"}

    rc, out = _run(["sudo", "-n", "sysctl", f"vm.swappiness={value}"])
    if rc == 0:
        log.info("Swappiness set to %d.", value)
        return {"current": value, "target": value, "status": "set"}
    else:
        log.info("Cannot set swappiness without sudo (current=%d). To fix: sudo sysctl vm.swappiness=%d", current, value)
        return {
            "current": current, "target": value,
            "status": "permission_denied",
            "fix_cmd": f"sudo sysctl vm.swappiness={value}",
            "persist_cmd": f"echo 'vm.swappiness={value}' | sudo tee -a /etc/sysctl.conf",
        }


# ── Log rotation ───────────────────────────────────────────────────────────────

def clear_old_logs(max_days: int = LOG_MAX_DAYS) -> dict:
    """Delete log files older than max_days in the logs/ directory."""
    log_dir  = WORKDIR / "logs"
    now      = time.time()
    cutoff   = now - max_days * 86400
    deleted  = []
    kept     = []
    freed_bytes = 0

    if not log_dir.exists():
        return {"status": "logs_dir_missing"}

    for f in log_dir.iterdir():
        if not f.is_file():
            continue
        age = now - f.stat().st_mtime
        if f.stat().st_mtime < cutoff:
            size = f.stat().st_size
            try:
                f.unlink()
                deleted.append({"file": f.name, "age_days": round(age/86400, 1), "bytes": size})
                freed_bytes += size
            except Exception as exc:
                log.warning("Could not delete %s: %s", f, exc)
        else:
            kept.append(f.name)

    log.info("Log cleanup: deleted %d files (%.1f KB freed), kept %d.", len(deleted), freed_bytes/1024, len(kept))
    return {
        "deleted": deleted,
        "kept_count": len(kept),
        "freed_kb": round(freed_bytes / 1024, 1),
    }


# ── Disk check ─────────────────────────────────────────────────────────────────

def check_disk() -> dict:
    disk = shutil.disk_usage(str(WORKDIR))
    pct  = 100 * disk.used / disk.total
    result = {
        "path":       str(WORKDIR),
        "total_gb":   round(disk.total / 1e9, 1),
        "used_gb":    round(disk.used  / 1e9, 1),
        "free_gb":    round(disk.free  / 1e9, 1),
        "used_pct":   round(pct, 1),
        "status":     "critical" if pct > 90 else "warning" if pct > 75 else "ok",
    }
    log.info("Disk: %.1f GB free / %.1f GB total (%.0f%%)", result["free_gb"], result["total_gb"], pct)
    return result


# ── Memory check ───────────────────────────────────────────────────────────────

def check_memory() -> dict:
    try:
        with open("/proc/meminfo") as fh:
            lines = fh.read().splitlines()
        info = {}
        for line in lines:
            k, v = line.split(":", 1)
            info[k.strip()] = int(v.split()[0])  # kB

        total_mb = info["MemTotal"] / 1024
        avail_mb = info["MemAvailable"] / 1024
        used_mb  = total_mb - avail_mb
        pct      = 100 * used_mb / total_mb

        result = {
            "total_mb":  round(total_mb, 0),
            "used_mb":   round(used_mb, 0),
            "free_mb":   round(avail_mb, 0),
            "used_pct":  round(pct, 1),
            "status":    "critical" if pct > 90 else "warning" if pct > 80 else "ok",
        }
        log.info("Memory: %.0f MB free / %.0f MB total (%.0f%%)", avail_mb, total_mb, pct)
        return result
    except Exception as exc:
        return {"error": str(exc)}


# ── Main ───────────────────────────────────────────────────────────────────────

def run_optimization() -> dict:
    log.info("=== System Optimizer starting ===")
    ts = datetime.utcnow().isoformat() + "Z"

    report = {
        "timestamp":   ts,
        "cpu_governor": set_cpu_governor("performance"),
        "swappiness":   set_swappiness(10),
        "log_cleanup":  clear_old_logs(LOG_MAX_DAYS),
        "disk":         check_disk(),
        "memory":       check_memory(),
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2))
    log.info("Optimization report written to %s", REPORT)
    log.info("=== System Optimizer complete ===")
    return report


if __name__ == "__main__":
    result = run_optimization()
    print(json.dumps(result, indent=2))
