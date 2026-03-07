#\!/usr/bin/env python3
"""
Storage verification — checks disk space, path writability, and SQLite connectivity
on every live Ray worker node, or locally if Ray is unavailable.
"""
from datetime import timezone
import subprocess
import socket
import os

try:
    import ray
    RAY_AVAILABLE = True
except ImportError:
    ray = None
    RAY_AVAILABLE = False


def _local_storage_check() -> dict:
    result = {"host": socket.gethostname()}

    # Disk usage on key paths
    disk_info = {}
    for path in ["/", "/home/avalii", "/tmp"]:
        try:
            st = os.statvfs(path)
            free_gb  = st.f_bavail * st.f_frsize / 1024**3
            total_gb = st.f_blocks * st.f_frsize / 1024**3
            disk_info[path] = {
                "free_gb":  round(free_gb, 2),
                "total_gb": round(total_gb, 2),
                "pct_used": round(100 * (1 - st.f_bavail / st.f_blocks), 1) if st.f_blocks else 0,
            }
        except OSError as e:
            disk_info[path] = {"error": str(e)}
    result["disk"] = disk_info

    # Writability
    result["writable"] = {
        p: os.access(p, os.W_OK)
        for p in ["/home/avalii", "/tmp", "/home/avalii/moltbot/memory"]
    }

    # SQLite connectivity
    try:
        import sqlite3
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE t (x INTEGER)")
        con.close()
        result["sqlite"] = "ok"
    except Exception as e:
        result["sqlite"] = f"ERROR: {e}"

    return result


if RAY_AVAILABLE:
    @ray.remote
    def _remote_storage_check() -> dict:
        return _local_storage_check()


def main():
    if not RAY_AVAILABLE:
        print("[verify_storage] Ray not installed — running local check only.")
        r = _local_storage_check()
        _print_result(1, r)
        return

    try:
        ray.init(address="auto", ignore_reinit_error=True)
    except Exception as e:
        print(f"[verify_storage] ray.init failed — falling back to local check: {e}")
        r = _local_storage_check()
        _print_result(1, r)
        return

    nodes = [n for n in ray.nodes() if n.get("Alive")]
    n_tasks = max(len(nodes), 1)
    futures = [_remote_storage_check.remote() for _ in range(n_tasks)]
    try:
        results = ray.get(futures, timeout=30)
    except ray.exceptions.GetTimeoutError:
        print("[verify_storage] ray.get timed out — some workers may be unresponsive")
        return

    for i, r in enumerate(results, 1):
        _print_result(i, r)


def _print_result(i: int, r: dict):
    host   = r.get("host", "?")
    sqlite = r.get("sqlite", "?")
    disk   = r.get("disk", {})
    root   = disk.get("/", {})
    print(
        f"Node {i}: {host} | "
        f"SQLite: {sqlite} | "
        f"/ disk: {root.get("free_gb", "?")} GB free "
        f"({root.get("pct_used", "?")}% used) | "
        f"Writable: {r.get("writable", {})}"
    )


if __name__ == "__main__":
    main()
