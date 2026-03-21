#!/usr/bin/env python3
"""
alii_tui_cluster.py — Async cluster data poller for the Alii TUI.

Collects live data from all cluster nodes concurrently.
Used by both alii_tui.py (header + cluster panel) and ntfy_status.py (notifications).
"""

from __future__ import annotations
import asyncio, json, os, socket, subprocess, time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

WORKDIR   = Path("/home/avalii/moltbot")
DATA_DIR  = WORKDIR / "data"

CLUSTER_NODES = {
    "xps":    "100.91.78.55",
    "nuc":    "100.126.57.22",
    "jetson": "100.87.137.61",
}

SERVICES = {
    "openclaw":      ("127.0.0.1", 18789),
    "litellm":       ("127.0.0.1", 4000),
    "ollama":        ("127.0.0.1", 11434),
    "alfred":        ("127.0.0.1", 7000),
    "n8n":           ("127.0.0.1", 5678),
    "mixpost":       ("127.0.0.1", 9101),
    "qdrant":        ("127.0.0.1", 6333),
    "minio":         ("127.0.0.1", 9000),
    "open-webui":    ("127.0.0.1", 3000),
    "searxng":       ("127.0.0.1", 8888),
    "jetson-ollama": ("100.87.137.61", 11434),
    "visionclaw":    ("127.0.0.1", 7030),
}


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class NodeState:
    name: str
    ip: str
    online: bool = False
    temp_c: float = 0.0
    load_1m: float = 0.0
    ram_used_mb: int = 0
    ram_total_mb: int = 0
    last_seen: float = 0.0

    @property
    def ram_pct(self) -> int:
        if self.ram_total_mb == 0:
            return 0
        return int(self.ram_used_mb / self.ram_total_mb * 100)

    @property
    def status_icon(self) -> str:
        if not self.online:
            return "●"
        if self.temp_c > 70:
            return "🔥"
        return "●"

    @property
    def temp_color(self) -> str:
        if self.temp_c > 70:
            return "red"
        elif self.temp_c > 55:
            return "yellow"
        return "bright_green"


@dataclass
class PrecisionState:
    temp_c: float = 0.0
    load_1m: float = 0.0
    load_5m: float = 0.0
    cpus: int = 1
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    disk_used: str = "?"
    disk_total: str = "?"
    disk_pct: str = "?"
    fan: str = "?"

    @property
    def load_pct(self) -> int:
        if self.cpus == 0:
            return 0
        return min(int(self.load_1m / self.cpus * 100), 100)

    @property
    def temp_color(self) -> str:
        if self.temp_c > 70:
            return "red"
        elif self.temp_c > 55:
            return "yellow"
        return "bright_green"


@dataclass
class ClusterState:
    precision: PrecisionState = field(default_factory=PrecisionState)
    nodes: Dict[str, NodeState] = field(default_factory=dict)
    services: Dict[str, bool] = field(default_factory=dict)
    todo_count: int = 0
    ollama_models: list = field(default_factory=list)
    ray_nodes: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def services_up(self) -> int:
        return sum(1 for v in self.services.values() if v)

    @property
    def services_total(self) -> int:
        return len(self.services)

    @property
    def all_nodes_online(self) -> bool:
        return all(n.online for n in self.nodes.values())

    @property
    def timestamp_str(self) -> str:
        return datetime.fromtimestamp(self.timestamp, tz=timezone.utc).strftime("%H:%M UTC")


# ── Sync collectors (run in threads) ──────────────────────────────────────────

def _run(cmd: list, timeout: int = 5) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _ssh(ip: str, cmd: str, timeout: int = 8) -> str:
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=4", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=no", f"avalii@{ip}", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _check_port(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def sync_collect_precision() -> PrecisionState:
    s = PrecisionState()
    # Temp
    try:
        temps = [int(Path(t).read_text()) / 1000
                 for t in Path("/sys/class/thermal").glob("thermal_zone*/temp")]
        s.temp_c = round(max(temps), 1) if temps else 0.0
    except Exception:
        pass
    # Load + CPU count
    try:
        load = os.getloadavg()
        s.load_1m = round(load[0], 2)
        s.load_5m = round(load[1], 2)
        s.cpus = os.cpu_count() or 1
    except Exception:
        pass
    # RAM
    try:
        meminfo = Path("/proc/meminfo").read_text()
        total = int(next(l for l in meminfo.splitlines() if "MemTotal" in l).split()[1])
        avail = int(next(l for l in meminfo.splitlines() if "MemAvailable" in l).split()[1])
        s.ram_used_gb = round((total - avail) / 1048576, 1)
        s.ram_total_gb = round(total / 1048576, 1)
    except Exception:
        pass
    # Fan
    fan_out = _run(["sudo", "-n", "i8kctl", "fan"], timeout=3)
    s.fan = fan_out if fan_out else "—"
    # Disk
    df_out = _run(["df", "-h", "/"], timeout=3)
    if df_out:
        parts = df_out.splitlines()
        if len(parts) > 1:
            cols = parts[1].split()
            s.disk_used  = cols[2] if len(cols) > 2 else "?"
            s.disk_total = cols[1] if len(cols) > 1 else "?"
            s.disk_pct   = cols[4] if len(cols) > 4 else "?"
    return s


def sync_collect_node(name: str, ip: str) -> NodeState:
    node = NodeState(name=name, ip=ip)
    out = _ssh(ip,
        "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null; "
        "cat /proc/loadavg 2>/dev/null; "
        "free -m 2>/dev/null | grep ^Mem",
        timeout=6
    )
    if not out:
        return node
    node.online = True
    node.last_seen = time.time()
    lines = out.splitlines()
    try:
        node.temp_c = round(int(lines[0].strip()) / 1000, 1)
    except Exception:
        pass
    try:
        node.load_1m = float(lines[1].split()[0]) if len(lines) > 1 else 0.0
    except Exception:
        pass
    try:
        parts = lines[2].split() if len(lines) > 2 else []
        node.ram_total_mb = int(parts[1]) if len(parts) > 1 else 0
        node.ram_used_mb  = int(parts[2]) if len(parts) > 2 else 0
    except Exception:
        pass
    return node


def sync_collect_services() -> Dict[str, bool]:
    return {name: _check_port(host, port) for name, (host, port) in SERVICES.items()}


def sync_collect_todos() -> int:
    """Count pending todos from owner_todos.json."""
    try:
        data = json.loads((DATA_DIR / "owner_todos.json").read_text())
        todos = data if isinstance(data, list) else data.get("todos", [])
        return sum(1 for t in todos if t.get("status", "pending") == "pending")
    except Exception:
        pass
    return 0


def sync_collect_ollama_models() -> list:
    """Get loaded Ollama model names."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            data = json.loads(r.read())
            return [m["name"].split(":")[0] for m in data.get("models", [])]
    except Exception:
        return []


def sync_collect_ray_nodes() -> int:
    ray_bin = Path("/home/avalii/.venv/ray/bin/ray")
    if not ray_bin.exists():
        return 0
    out = _run([str(ray_bin), "status"], timeout=8)
    return sum(1 for l in out.splitlines() if "node_" in l)


def sync_collect_all() -> ClusterState:
    """Collect everything synchronously (call via asyncio.to_thread)."""
    state = ClusterState()
    state.precision    = sync_collect_precision()
    state.services     = sync_collect_services()
    state.todo_count   = sync_collect_todos()
    state.ollama_models = sync_collect_ollama_models()
    state.ray_nodes    = sync_collect_ray_nodes()
    state.timestamp    = time.time()

    for name, ip in CLUSTER_NODES.items():
        state.nodes[name] = sync_collect_node(name, ip)

    return state


# ── Async poller ───────────────────────────────────────────────────────────────

class ClusterPoller:
    """
    Background poller that refreshes ClusterState asynchronously.
    Usage:
        poller = ClusterPoller()
        state = await poller.get_state()
    """

    def __init__(self, interval: float = 30.0):
        self._interval = interval
        self._state: ClusterState = ClusterState()
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start background polling loop."""
        # Do first poll immediately
        await self._poll()
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll(self):
        try:
            new_state = await asyncio.to_thread(sync_collect_all)
            async with self._lock:
                self._state = new_state
        except Exception:
            pass

    async def _loop(self):
        while True:
            await asyncio.sleep(self._interval)
            await self._poll()

    async def get_state(self) -> ClusterState:
        async with self._lock:
            return self._state

    async def force_refresh(self) -> ClusterState:
        await self._poll()
        return await self.get_state()


# ── Standalone test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Collecting cluster state...")
    state = sync_collect_all()
    print(f"Precision: {state.precision.temp_c}°C  load {state.precision.load_1m}  "
          f"RAM {state.precision.ram_used_gb}/{state.precision.ram_total_gb}GB")
    for name, node in state.nodes.items():
        status = f"ONLINE {node.temp_c}°C L:{node.load_1m}" if node.online else "OFFLINE"
        print(f"  {name.upper()}: {status}")
    print(f"Services: {state.services_up}/{state.services_total} up")
    print(f"Todos: {state.todo_count} pending")
    print(f"Ollama models: {state.ollama_models}")
