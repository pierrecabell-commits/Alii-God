#!/usr/bin/env python3
import os
import sys
import time
import json
import hashlib
import py_compile
import subprocess
from pathlib import Path
from datetime import datetime
import threading

class AliiOptimizer:
    def __init__(self):
        self.base_dirs = ["/home/avalii/Alii", "/home/avalii/alii-ai", "/home/avalii/alii_dashboard"]
        self.log_file = "/home/avalii/Alii/optimizer.log"
        self.state_file = "/home/avalii/Alii/optimizer_state.json"
        self.running = True
        self.scan_interval = 300
        self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file) as f:
                    self.state = json.load(f)
                return
            except Exception:
                pass
        self.state = {"last_scan": None, "files_analyzed": 0, "optimizations": 0, "deletions": 0}

    def save_state(self):
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"[AliiOptimizer] save_state failed: {e}")

    def log(self, msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {msg}"
        print(log_msg)
        try:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            with open(self.log_file, "a") as f:
                f.write(log_msg + "\n")
        except Exception:
            pass

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
            except Exception:
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
        except Exception:
            return []

    def check_syntax(self, pyfile):
        try:
            py_compile.compile(pyfile, doraise=True)
            return True
        except py_compile.PyCompileError:
            return False

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
        except Exception:
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
        except Exception:
            return False

    def run_optimization_cycle(self):
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

        self.log("Cycle complete. Optimizations: %d, Deletions: %d" % (self.state["optimizations"], self.state["deletions"]))
        self.log("=" * 60)

    def run(self):
        self.log("Alii Optimizer Agent starting...")
        while self.running:
            try:
                self.run_optimization_cycle()
                time.sleep(self.scan_interval)
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                self.log(f"Error: {e}")
                time.sleep(60)

        self.log("Alii Optimizer Agent stopped")

if __name__ == "__main__":
    optimizer = AliiOptimizer()
    optimizer.run()
