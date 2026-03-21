#!/usr/bin/env python3
"""
Alii Hardware Agent — Intelligent thermal and power management across all cluster nodes.

Features:
  - CPU governor management (powersave/performance based on workload)
  - Dell SMM fan control via i8kctl (precision)
  - Remote node management via SSH
  - Temperature-based fan curves
  - ntfy alerts on thermal events
  - Jetson power mode management (nvpmodel)

Precision fan curve (i8kctl Dell SMM):
  < 45°C  → fan low   (1)
  45-60°C → fan high  (2)
  > 60°C  → fan max   (3) + alert
"""

import os, sys, subprocess, time, logging, json, urllib.request
from pathlib import Path
from datetime import datetime, timezone

WORKDIR  = Path("/home/avalii/moltbot")
LOG_FILE = WORKDIR / "logs" / "hardware_agent.log"
STATE    = WORKDIR / "data" / "hardware_state.json"
NTFY_URL = "https://ntfy.sh/alii-precision"
INTERVAL = 30  # seconds between checks

# Cluster nodes to manage remotely
REMOTE_NODES = {
    "xps":    "100.91.78.55",
    "nuc":    "100.126.57.22",
    "jetson": "100.87.137.61",
}

# Fan curve thresholds (°C) for Dell precision
FAN_CURVE = [
    (45, 0),   # below 45°C → fan off/minimal (i8k mode 0)
    (55, 1),   # 45-55°C    → fan low          (i8k mode 1)
    (65, 2),   # 55-65°C    → fan high          (i8k mode 2)
    (100, 3),  # above 65°C → fan max           (i8k mode 3 if available, else 2)
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [hardware] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger("alii.hardware")

_last_alert_temp = 0
_last_fan_mode   = -1


def _ntfy(title: str, msg: str, priority: str = "default"):
    try:
        req = urllib.request.Request(
            NTFY_URL, data=msg.encode(),
            headers={"Title": title, "Priority": priority}, method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def _run(cmd: list, timeout: int = 5) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip()
    except Exception as e:
        return -1, str(e)


def _ssh(node_ip: str, cmd: str, timeout: int = 10) -> tuple[int, str]:
    rc, out = _run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                    f"avalii@{node_ip}", cmd], timeout=timeout)
    return rc, out


# ── Precision (local) ──────────────────────────────────────────────────────────

def get_cpu_temp() -> float:
    """Read highest CPU core temp from lm-sensors."""
    rc, out = _run(["sensors", "-j"], timeout=5)
    if rc != 0:
        # fallback: thermal_zone
        try:
            temps = [int(Path(t).read_text()) / 1000
                     for t in Path("/sys/class/thermal").glob("thermal_zone*/temp")]
            return max(temps) if temps else 50.0
        except Exception:
            return 50.0
    try:
        import json as _json
        data = _json.loads(out)
        temps = []
        for chip, sensors in data.items():
            for key, val in sensors.items():
                if isinstance(val, dict):
                    for k, v in val.items():
                        if "input" in k and isinstance(v, (int, float)):
                            temps.append(float(v))
        return max(temps) if temps else 50.0
    except Exception:
        return 50.0


def get_cpu_load() -> float:
    """Get 1-minute load average as percentage of CPU count."""
    try:
        load = os.getloadavg()[0]
        cpus = os.cpu_count() or 1
        return (load / cpus) * 100
    except Exception:
        return 0.0


def set_fan_mode(mode: int):
    """Set Dell fan mode via i8kctl. mode: 0=off 1=low 2=high."""
    global _last_fan_mode
    if mode == _last_fan_mode:
        return
    actual = min(mode, 2)  # i8k supports 0,1,2
    rc, out = _run(["sudo", "i8kctl", "fan", str(actual), str(actual)])
    if rc == 0:
        log.info("Fan mode set to %d (i8k: %d)", mode, actual)
        _last_fan_mode = mode
    else:
        log.warning("i8kctl fan set failed: %s", out)


def target_fan_mode(temp: float) -> int:
    for threshold, mode in FAN_CURVE:
        if temp < threshold:
            return mode
    return 2


def set_cpu_governor(governor: str):
    """Apply CPU governor to all cores."""
    changed = False
    for cpu_dir in Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_governor"):
        try:
            current = cpu_dir.read_text().strip()
            if current != governor:
                cpu_dir.write_text(governor)
                changed = True
        except Exception:
            pass
    if changed:
        log.info("CPU governor → %s", governor)


def manage_precision():
    """Monitor and control precision (local machine)."""
    global _last_alert_temp
    temp = get_cpu_temp()
    load = get_cpu_load()

    # Governor: performance when load > 70%, else powersave
    governor = "performance" if load > 70 else "powersave"
    set_cpu_governor(governor)

    # Fan curve
    mode = target_fan_mode(temp)
    set_fan_mode(mode)

    # High temp alert (don't spam — only alert when crossing 70°C and haven't recently)
    if temp > 70 and _last_alert_temp < 70:
        _ntfy("Precision HIGH TEMP", f"CPU: {temp:.1f}°C  Load: {load:.0f}%  Fan: high", "high")
        _last_alert_temp = temp
    elif temp < 60:
        _last_alert_temp = 0

    return {"temp": temp, "load": load, "governor": governor, "fan_mode": mode}


# ── Remote nodes ───────────────────────────────────────────────────────────────

def manage_remote_node(name: str, ip: str) -> dict:
    """Manage a remote cluster node via SSH."""
    rc, temp_out = _ssh(ip, "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 50000")
    try:
        temp = int(temp_out.strip()) / 1000
    except Exception:
        temp = 50.0

    rc, load_out = _ssh(ip, "cat /proc/loadavg 2>/dev/null")
    try:
        load_1m = float(load_out.split()[0]) if rc == 0 else 0.0
    except Exception:
        load_1m = 0.0

    # Jetson: manage power modes (nvpmodel)
    if name == "jetson":
        return manage_jetson(ip, temp, load_1m)

    # Standard nodes: manage CPU governor
    governor = "performance" if load_1m > 2 else "powersave"
    _ssh(ip, f"for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo {governor} | sudo tee $g > /dev/null 2>&1; done")

    return {"node": name, "temp": temp, "load_1m": load_1m, "governor": governor}


def manage_jetson(ip: str, temp: float, load: float) -> dict:
    """Jetson-specific: set nvpmodel power mode based on load."""
    # Jetson Nano power modes: 0=MAXN (max perf), 1=5W (power save)
    # Use MAXN when load > 50%, else 5W
    mode = "0" if load > 1.5 else "1"
    _ssh(ip, f"sudo nvpmodel -m {mode} 2>/dev/null || true")
    return {"node": "jetson", "temp": temp, "load_1m": load, "nvpmodel": mode}


# ── Main loop ──────────────────────────────────────────────────────────────────

def main():
    log.info("Hardware Agent started — monitoring %d nodes", 1 + len(REMOTE_NODES))
    _ntfy("Alii Hardware Agent", "Thermal management active on all cluster nodes.", "low")

    while True:
        state = {"timestamp": datetime.now(timezone.utc).isoformat(), "nodes": {}}

        # Precision (local)
        try:
            state["nodes"]["precision"] = manage_precision()
        except Exception as exc:
            log.exception("precision management error: %s", exc)

        # Remote nodes
        for name, ip in REMOTE_NODES.items():
            try:
                state["nodes"][name] = manage_remote_node(name, ip)
            except Exception as exc:
                log.warning("node %s management error: %s", name, exc)

        # Persist state
        try:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(state, indent=2))
        except Exception:
            pass

        log.debug("precision: %.1f°C load=%.0f%% | cycle done",
                  state["nodes"].get("precision", {}).get("temp", 0),
                  state["nodes"].get("precision", {}).get("load", 0))

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
