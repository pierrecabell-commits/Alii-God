#!/usr/bin/env python3
"""
Cluster scanner - SSH to each node, run basic inventory, write JSON.
Credentials loaded from cluster_credentials.json (600 permissions).
"""
import os
import json
import subprocess
from datetime import datetime
from pathlib import Path

CREDENTIALS_FILE = "/home/avalii/moltbot/cluster_credentials.json"
OUTPUT_DIR = "/home/avalii/moltbot/data"
LOG_FILE = "/home/avalii/moltbot/logs/cluster_scan.log"

NODE_MAP = {
    "precision": {"output": "node1_inventory.json", "is_local": True},
    "xps": {"output": "node2_inventory.json", "is_local": False},
    "nuc": {"output": "node3_inventory.json", "is_local": False},
    "jetson01": {"output": "node4_inventory.json", "is_local": False},
}


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_credentials() -> dict:
    with open(CREDENTIALS_FILE) as f:
        data = json.load(f)
    return data.get("credentials", {})


INVENTORY_SCRIPT = """
python3 - << 'PYEOF'
import json, subprocess, socket, platform
from datetime import datetime

def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
        return r.stdout.strip()
    except Exception:
        return "ERROR"

inventory = {
    "timestamp": datetime.now().isoformat(),
    "hostname": socket.gethostname(),
    "platform": platform.platform(),
    "pip_count": len(run("pip3 list 2>/dev/null").splitlines()),
    "dpkg_count": len([l for l in run("dpkg -l 2>/dev/null").splitlines() if l.startswith("ii")]),
    "docker_containers": run("docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}' 2>/dev/null").splitlines(),
    "ollama_models": run("ollama list 2>/dev/null").splitlines()[1:] if run("which ollama") else [],
    "disk_usage": {
        row.split()[0]: {"size": row.split()[1], "use": row.split()[-1]}
        for row in run("df -h --output=target,size,avail,pcent 2>/dev/null").splitlines()[1:]
        if len(row.split()) >= 4
    },
    "memory": run("free -h | head -2 | tail -1 2>/dev/null"),
    "services": run("systemctl list-units --state=active --type=service --no-pager -q 2>/dev/null | head -20"),
    "listening_ports": run("ss -lntp 2>/dev/null | grep LISTEN"),
    "tailscale_ip": run("tailscale ip 2>/dev/null | head -1"),
}
print(json.dumps(inventory))
PYEOF
"""


def scan_remote_node(name: str, ip: str, user: str, password: str) -> dict:
    """SSH to node and run inventory script."""
    log(f"Scanning {name} ({ip})...")
    try:
        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            ip,
            username=user,
            password=password,
            timeout=15,
            banner_timeout=15,
            look_for_keys=True,
            allow_agent=True,
        )
        stdin, stdout, stderr = client.exec_command(INVENTORY_SCRIPT, timeout=60)
        output = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        client.close()

        # Find JSON in output
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except Exception:
                    pass
        log(f"  {name}: Could not parse JSON from output")
        log(f"  output[:200]: {output[:200]}")
        if err:
            log(f"  stderr: {err[:200]}")
        return {"hostname": name, "error": "JSON parse failed", "raw": output[:500]}
    except Exception as e:
        log(f"  {name}: SSH error - {e}")
        return {"hostname": name, "error": str(e), "timestamp": datetime.now().isoformat()}


def scan_local_node() -> dict:
    """Inventory the local node."""
    import socket
    import platform

    def run(cmd):
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
            return r.stdout.strip()
        except Exception:
            return "ERROR"

    return {
        "timestamp": datetime.now().isoformat(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "pip_count": len(run("pip3 list 2>/dev/null").splitlines()),
        "dpkg_count": len([l for l in run("dpkg -l 2>/dev/null").splitlines() if l.startswith("ii")]),
        "docker_containers": run("docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}' 2>/dev/null").splitlines(),
        "ollama_models": run("ollama list 2>/dev/null").splitlines()[1:] if run("which ollama") else [],
        "listening_ports": run("ss -lntp 2>/dev/null | grep LISTEN"),
        "tailscale_ip": run("tailscale ip 2>/dev/null | head -1"),
        "memory": run("free -h | sed -n '2p'"),
        "services_active": int(run("systemctl list-units --state=active --type=service --no-pager -q 2>/dev/null | wc -l") or 0),
    }


def build_cluster_map(inventories: dict) -> dict:
    """Build unified cluster map comparing all nodes."""
    cluster_map = {
        "timestamp": datetime.now().isoformat(),
        "nodes": {},
        "summary": {},
    }

    for name, inv in inventories.items():
        has_error = "error" in inv
        node_info = {
            "hostname": inv.get("hostname", name),
            "tailscale_ip": inv.get("tailscale_ip", "unknown"),
            "reachable": not has_error,
            "error": inv.get("error"),
            "docker_containers": inv.get("docker_containers", []),
            "ollama_models": inv.get("ollama_models", []),
            "pip_packages": inv.get("pip_count", 0),
            "dpkg_packages": inv.get("dpkg_count", 0),
        }
        cluster_map["nodes"][name] = node_info

    reachable = [n for n, v in cluster_map["nodes"].items() if v["reachable"]]
    cluster_map["summary"] = {
        "total_nodes": len(inventories),
        "reachable": len(reachable),
        "unreachable": len(inventories) - len(reachable),
        "reachable_nodes": reachable,
    }

    return cluster_map


def main():
    log("=== Cluster Scan START ===")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    try:
        creds = load_credentials()
    except FileNotFoundError:
        log(f"ERROR: credentials file not found: {CREDENTIALS_FILE}")
        return
    except Exception as e:
        log(f"ERROR: failed to load credentials: {e}")
        return
    inventories = {}

    for node_name, node_cfg in NODE_MAP.items():
        if node_cfg.get("is_local"):
            log(f"Scanning local node: {node_name}")
            inv = scan_local_node()
        else:
            cred = creds.get(node_name, {})
            if not cred:
                log(f"No credentials for {node_name}, skipping")
                continue
            inv = scan_remote_node(
                node_name,
                cred["ip"],
                cred["user"],
                cred["password"],
            )

        # Save individual node inventory
        outfile = os.path.join(OUTPUT_DIR, node_cfg["output"])
        with open(outfile, "w") as f:
            json.dump(inv, f, indent=2)
        log(f"  {node_name}: saved to {outfile}")
        inventories[node_name] = inv

    # Build and save cluster map
    cluster_map = build_cluster_map(inventories)
    map_file = os.path.join(OUTPUT_DIR, "cluster_map.json")
    with open(map_file, "w") as f:
        json.dump(cluster_map, f, indent=2)
    log(f"Cluster map saved: {map_file}")
    log(f"Summary: {cluster_map['summary']}")
    log("=== Cluster Scan DONE ===")


if __name__ == "__main__":
    main()
