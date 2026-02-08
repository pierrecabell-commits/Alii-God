#!/usr/bin/env python3
import os
import sys
import time
import json
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
import threading

class AliiProtectionAgent:
    def __init__(self):
        self.base_dirs = ["/home/avalii/Alii", "/home/avalii/alii-ai", "/home/avalii/alii_dashboard"]
        self.log_file = "/home/avalii/Alii/protection.log"
        self.state_file = "/home/avalii/Alii/protection_state.json"
        self.running = True
        self.scan_interval = 300
        self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                self.state = json.load(f)
        else:
            self.state = {"last_scan": None, "files_analyzed": 0, "optimizations": 0, "deletions": 0}

    def save_state(self):
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def log(self, msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {msg}"
        print(log_msg)
        with open(self.log_file, "a") as f:
            f.write(log_msg + "\n")

    def scan_codebase(self):
        self.log("Starting codebase scan...")
        files = []
        for base_dir in self.base_dirs:
            if os.path.exists(base_dir):
                for root, dirs, filenames in os.walk(base_dir):
                    if "venv" in root or "__pycache__" in root or ".git" in root or "deleted_archive" in root:
                        continue
                    for fname in filenames:
                        if fname.endswith((".py", ".sh", ".json", ".txt")):
                            files.append(os.path.join(root, fname))
        self.log(f"Found {len(files)} files to analyze")
        return files

    def find_duplicates(self, files):
        hashes = {}
        duplicates = []
        for fpath in files:
            try:
                with open(fpath, "rb") as f:
                    h = hashlib.md5(f.read()).hexdigest()
                    if h in hashes:
                        duplicates.append((fpath, hashes[h]))
                    else:
                        hashes[h] = fpath
            except:
                pass
        return duplicates

    def find_backup_files(self, files):
        backups = [f for f in files if any(x in f for x in [".bak", ".backup", "_old", "_backup", "backup_"])]
        return backups

    def analyze_imports(self, pyfile):
        try:
            with open(pyfile) as f:
                content = f.read()
                imports = [line for line in content.split("\n") if line.strip().startswith(("import ", "from "))]
                return imports
        except:
            return []

    def check_syntax(self, pyfile):
        result = subprocess.run(["python3", "-m", "py_compile", pyfile], capture_output=True, text=True)
        return result.returncode == 0

    def optimize_file(self, fpath):
        if not fpath.endswith(".py"):
            return False
        try:
            with open(fpath) as f:
                content = f.read()

            original = content
            lines = content.split("\n")
            optimized_lines = []

            for line in lines:
                stripped = line.rstrip()
                if stripped or not optimized_lines or optimized_lines[-1].strip():
                    optimized_lines.append(stripped)

            optimized = "\n".join(optimized_lines)

            if optimized != original and self.check_syntax(fpath):
                with open(fpath, "w") as f:
                    f.write(optimized)
                self.log(f"Optimized: {fpath}")
                return True
        except:
            pass
        return False

    def safe_delete(self, fpath):
        archive_dir = "/home/avalii/Alii/deleted_archive"
        os.makedirs(archive_dir, exist_ok=True)

        fname = os.path.basename(fpath)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = os.path.join(archive_dir, f"{timestamp}_{fname}")

        try:
            os.rename(fpath, archive_path)
            self.log(f"Archived: {fpath} -> {archive_path}")
            return True
        except:
            return False

    def scan_open_ports(self):
        self.log("Scanning open ports...")
        connections=__import__("psutil").net_connections(kind="inet")
        listening=[{"port":c.laddr.port,"pid":c.pid}for c in connections if c.status=="LISTEN"]
        self.log(f"Found {len(listening)} listening ports")
        return listening

    def check_suspicious_processes(self):
        self.log("Checking suspicious processes...")
        patterns=["nc","ncat","telnet","tftp"]
        suspicious=[]
        for proc in __import__("psutil").process_iter(["pid","name","cmdline"]):
            try:
                name=proc.info["name"]
                if any(p in name.lower()for p in patterns):suspicious.append({"pid":proc.info["pid"],"name":name})
            except:pass
        if suspicious:self.log(f"Found {len(suspicious)} suspicious","WARNING")
        return suspicious

    def scan_file_permissions(self):
        issues=[]
        for f in["config.json",".credentials_vault.enc"]:
            fpath=f"{self.base_dirs[0]}/{f}"
            if os.path.exists(fpath):
                mode=oct(os.stat(fpath).st_mode)[-3:]
                if mode in["777","666"]:os.chmod(fpath,0o600);issues.append(f)
        return issues

    def run_optimization_cycle(self):
        ports=self.scan_open_ports()
        suspicious=self.check_suspicious_processes()
        perm_issues=self.scan_file_permissions()
        if perm_issues:self.log(f"Fixed permissions on {len(perm_issues)} files")
        self.log("=" * 60)
        self.log("Starting optimization cycle")

        files = self.scan_codebase()
        self.state["files_analyzed"] = len(files)

        duplicates = self.find_duplicates(files)
        self.log(f"Found {len(duplicates)} duplicate files")

        backups = self.find_backup_files(files)
        self.log(f"Found {len(backups)} backup files")

        for dup, original in duplicates:
            if "backup" in dup or "old" in dup or ".bak" in dup:
                if self.safe_delete(dup):
                    self.state["deletions"] += 1

        old_backups = [b for b in backups if os.path.getmtime(b) < time.time() - 604800]
        for backup in old_backups:
            if self.safe_delete(backup):
                self.state["deletions"] += 1

        py_files = [f for f in files if f.endswith(".py")]
        for pyfile in py_files:
            if self.optimize_file(pyfile):
                self.state["optimizations"] += 1

        self.state["last_scan"] = datetime.now().isoformat()
        self.save_state()

        self.log(f"Cycle complete. Optimizations: {self.state[optimizations]}, Deletions: {self.state[deletions]}")
        self.log("=" * 60)

    def run(self):
        self.log("Alii Protection Agent Agent starting...")
        while self.running:
            try:
                self.run_optimization_cycle()
                time.sleep(self.scan_interval)
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                self.log(f"Error: {e}")
                time.sleep(60)

        self.log("Alii Protection Agent Agent stopped")

if __name__ == "__main__":
    optimizer = AliiProtectionAgent()
    optimizer.run()
