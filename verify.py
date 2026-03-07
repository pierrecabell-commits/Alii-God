#!/usr/bin/env python3
"""
Cluster verification — runs a lightweight health check on every Ray worker node.
"""
import os
import socket
import subprocess

try:
    import ray
    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False
    print("[verify] ray not installed; skipping remote checks")


if RAY_AVAILABLE:
    @ray.remote
    def check() -> dict:
        result = {"host": socket.gethostname()}

        try:
            import sqlite3
            result["sql"] = sqlite3.sqlite_version
        except ImportError:
            result["sql"] = "NO"

        try:
            result["df"] = subprocess.check_output(
                ["df", "-h"], timeout=5
            ).decode().split("\n")[:5]
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            result["df"] = [f"error: {e}"]

        result["writable"] = {
            p: os.access(p, os.W_OK) for p in ["/home/avalii", "/tmp"]
        }
        return result


def main():
    if not RAY_AVAILABLE:
        return

    try:
        ray.init(address="auto", ignore_reinit_error=True)
    except Exception as e:
        print(f"[verify] ray.init failed — cluster may not be running: {e}")
        return
    # Dispatch one task per live node instead of a hardcoded count
    nodes = [n for n in ray.nodes() if n.get("Alive")]
    n_tasks = max(len(nodes), 1)
    futures = [check.remote() for _ in range(n_tasks)]
    try:
        results = ray.get(futures, timeout=30)
    except ray.exceptions.GetTimeoutError:
        print("[verify] ray.get timed out -- some workers may be unresponsive")
        return
    for i, x in enumerate(results, 1):
        print(
            f"Node {i}: {x['host']} | "
            f"SQL: {x.get('sql')} | "
            f"Writable: {x.get('writable')}"
        )


if __name__ == "__main__":
    main()
