#!/usr/bin/env python3
"""
Alii Inventory Agent
Scans system state, writes JSON, diffs vs previous run, sends ntfy digest.
Register as: alii-inventory.service + alii-inventory.timer (every 6h)
"""
import os
import json
import subprocess
import hashlib
from datetime import datetime
from pathlib import Path

INVENTORY_FILE = "/home/avalii/moltbot/data/system_inventory.json"
PREV_INVENTORY_FILE = "/home/avalii/moltbot/data/system_inventory_prev.json"
LOG_FILE = "/home/avalii/moltbot/logs/inventory_agent.log"
NTFY_URL = "http://localhost:8080/alii-alerts"


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def run(cmd: list, timeout: int = 30) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


def send_ntfy(title: str, body: str, priority: str = "low"):
    import urllib.request
    try:
        req = urllib.request.Request(NTFY_URL, body.encode())
        req.add_header("Title", title)
        req.add_header("Priority", priority)
        req.add_header("Tags", "package,computer")
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        log(f"[ntfy] {e}")


def parse_pip_packages() -> dict:
    out = run(["pip3", "list", "--format=json"])
    try:
        return {p["name"]: p["version"] for p in json.loads(out)}
    except Exception:
        return {}


def parse_dpkg_packages() -> list:
    out = run(["dpkg", "-l"])
    pkgs = []
    for line in out.splitlines():
        if line.startswith("ii"):
            parts = line.split()
            if len(parts) >= 3:
                pkgs.append({"name": parts[1], "version": parts[2]})
    return pkgs


def parse_snap_packages() -> list:
    out = run(["snap", "list"])
    pkgs = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if parts:
            pkgs.append({"name": parts[0], "version": parts[1] if len(parts) > 1 else "?"})
    return pkgs


def parse_docker_containers() -> list:
    out = run(["docker", "ps", "-a", "--format", "{{.Names}}|{{.Image}}|{{.Status}}"])
    containers = []
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) == 3:
            containers.append({"name": parts[0], "image": parts[1], "status": parts[2]})
    return containers


def parse_ollama_models() -> list:
    out = run(["ollama", "list"])
    models = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if parts:
            models.append({"name": parts[0], "size": parts[3] if len(parts) > 3 else "?"})
    return models


def parse_systemd_units() -> list:
    out = run(["systemctl", "--user", "list-units", "--all", "--no-pager",
               "--output=json"])
    try:
        units = json.loads(out)
        return [{"unit": u.get("unit", ""), "active": u.get("active", ""),
                 "sub": u.get("sub", "")} for u in units]
    except Exception:
        # Fallback: parse text output
        out2 = run(["systemctl", "--user", "list-units", "--all", "--no-pager"])
        units = []
        for line in out2.splitlines():
            if ".service" in line or ".timer" in line or ".socket" in line:
                parts = line.split()
                if parts:
                    units.append({"unit": parts[0], "active": parts[2] if len(parts) > 2 else "?",
                                  "sub": parts[3] if len(parts) > 3 else "?"})
        return units


def parse_listening_ports() -> list:
    out = run(["ss", "-lntp"])
    ports = []
    import re
    for line in out.splitlines()[1:]:
        m = re.search(r':(\d+)\s', line)
        if m:
            port = int(m.group(1))
            process = ""
            pm = re.search(r'users:\(\("([^"]+)"', line)
            if pm:
                process = pm.group(1)
            if port not in [p["port"] for p in ports]:
                ports.append({"port": port, "process": process})
    return sorted(ports, key=lambda x: x["port"])


def parse_disk_usage() -> dict:
    out = run(["df", "-h", "--output=target,size,used,avail,pcent"])
    rows = {}
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 5:
            rows[parts[0]] = {"size": parts[1], "used": parts[2],
                               "avail": parts[3], "use_pct": parts[4]}
    return rows


def parse_memory() -> dict:
    out = run(["free", "-h"])
    result = {}
    for line in out.splitlines():
        if line.startswith("Mem:"):
            parts = line.split()
            result = {"total": parts[1], "used": parts[2], "free": parts[3]}
    return result


def collect_inventory() -> dict:
    log("Collecting system inventory...")
    inventory = {
        "timestamp": datetime.now().isoformat(),
        "hostname": run(["hostname"]),
        "pip_packages": parse_pip_packages(),
        "dpkg_packages": parse_dpkg_packages(),
        "snap_packages": parse_snap_packages(),
        "docker_containers": parse_docker_containers(),
        "ollama_models": parse_ollama_models(),
        "systemd_user_units": parse_systemd_units(),
        "listening_ports": parse_listening_ports(),
        "disk_usage": parse_disk_usage(),
        "memory": parse_memory(),
    }
    log(f"Inventory complete: {len(inventory['pip_packages'])} pip, "
        f"{len(inventory['dpkg_packages'])} dpkg, "
        f"{len(inventory['docker_containers'])} docker containers")
    return inventory


def diff_inventories(prev: dict, curr: dict) -> dict:
    changes = {}

    # pip packages
    prev_pip = prev.get("pip_packages", {})
    curr_pip = curr.get("pip_packages", {})
    added_pip = {k: v for k, v in curr_pip.items() if k not in prev_pip}
    removed_pip = {k: v for k, v in prev_pip.items() if k not in curr_pip}
    updated_pip = {k: (prev_pip[k], curr_pip[k]) for k in curr_pip
                   if k in prev_pip and curr_pip[k] != prev_pip[k]}
    if added_pip or removed_pip or updated_pip:
        changes["pip"] = {"added": added_pip, "removed": removed_pip, "updated": updated_pip}

    # docker containers
    prev_dc = {c["name"]: c for c in prev.get("docker_containers", [])}
    curr_dc = {c["name"]: c for c in curr.get("docker_containers", [])}
    new_containers = [c for name, c in curr_dc.items() if name not in prev_dc]
    removed_containers = [c for name, c in prev_dc.items() if name not in curr_dc]
    if new_containers or removed_containers:
        changes["docker"] = {"added": new_containers, "removed": removed_containers}

    # listening ports
    prev_ports = {p["port"] for p in prev.get("listening_ports", [])}
    curr_ports = {p["port"] for p in curr.get("listening_ports", [])}
    new_ports = curr_ports - prev_ports
    closed_ports = prev_ports - curr_ports
    if new_ports or closed_ports:
        changes["ports"] = {"opened": list(new_ports), "closed": list(closed_ports)}

    # ollama models
    prev_models = {m["name"] for m in prev.get("ollama_models", [])}
    curr_models = {m["name"] for m in curr.get("ollama_models", [])}
    new_models = curr_models - prev_models
    removed_models = prev_models - curr_models
    if new_models or removed_models:
        changes["ollama"] = {"added": list(new_models), "removed": list(removed_models)}

    return changes


def format_digest(changes: dict) -> str:
    if not changes:
        return "No changes detected since last run."
    lines = ["System inventory changes:"]
    if "pip" in changes:
        p = changes["pip"]
        if p.get("added"):
            lines.append(f"  PIP added: {', '.join(p['added'].keys())}")
        if p.get("removed"):
            lines.append(f"  PIP removed: {', '.join(p['removed'].keys())}")
        if p.get("updated"):
            for k, (old, new) in p["updated"].items():
                lines.append(f"  PIP updated: {k} {old} -> {new}")
    if "docker" in changes:
        d = changes["docker"]
        if d.get("added"):
            lines.append(f"  Docker new: {', '.join(c['name'] for c in d['added'])}")
        if d.get("removed"):
            lines.append(f"  Docker removed: {', '.join(c['name'] for c in d['removed'])}")
    if "ports" in changes:
        pt = changes["ports"]
        if pt.get("opened"):
            lines.append(f"  Ports opened: {pt['opened']}")
        if pt.get("closed"):
            lines.append(f"  Ports closed: {pt['closed']}")
    if "ollama" in changes:
        om = changes["ollama"]
        if om.get("added"):
            lines.append(f"  Ollama models added: {om['added']}")
        if om.get("removed"):
            lines.append(f"  Ollama models removed: {om['removed']}")
    return "\n".join(lines)


def main():
    log("=== Inventory Agent START ===")
    os.makedirs("/home/avalii/moltbot/data", exist_ok=True)

    # Load previous inventory if exists
    prev_inventory = {}
    if os.path.exists(INVENTORY_FILE):
        import shutil
        shutil.copy(INVENTORY_FILE, PREV_INVENTORY_FILE)
        with open(INVENTORY_FILE) as f:
            prev_inventory = json.load(f)

    # Collect current inventory
    inventory = collect_inventory()

    # Save to file
    with open(INVENTORY_FILE, "w") as f:
        json.dump(inventory, f, indent=2)
    log(f"Inventory saved to {INVENTORY_FILE}")

    # Diff and send digest
    if prev_inventory:
        changes = diff_inventories(prev_inventory, inventory)
        digest = format_digest(changes)
        log(f"Changes: {digest}")
        if changes:
            send_ntfy("Alii Inventory Update", digest, priority="low")
    else:
        log("First run - no previous inventory to compare")
        send_ntfy("Alii Inventory", f"Initial inventory complete on {inventory['hostname']}", priority="low")

    log("=== Inventory Agent DONE ===")


if __name__ == "__main__":
    main()
