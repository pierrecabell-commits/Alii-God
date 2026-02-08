import os
import sys
import json
import subprocess
import tempfile
import psutil
import socket
from datetime import datetime
from pathlib import Path
from persistence_module import PersistenceManager

class EnhancedAlii:
    def __init__(self):
        self.memory_file = "memory/enhanced_memory.json"
        self.upgrades_loaded = []
        self.active_capabilities = {}
        self.ensure_directories()
        self.persistence = PersistenceManager()
        print("[Alii] Loading saved upgrades...")
        self.upgrades_loaded = self.persistence.load_all_upgrades()
        print(f"[Alii] {len(self.upgrades_loaded)} upgrades restored from disk")
        self.activate_loaded_upgrades()
        
    def ensure_directories(self):
        os.makedirs("memory", exist_ok=True)
        os.makedirs("upgrades", exist_ok=True)
        os.makedirs("documents", exist_ok=True)
        
    def activate_loaded_upgrades(self):
        """Activate all loaded upgrades and register their capabilities"""
        self.active_capabilities = {}
        for u in self.upgrades_loaded:
            self.active_capabilities[u["name"]] = {
                "v": u["version"],
                "c": u["data"].get("capabilities", [])
            }
            print(f"  Active: {u[name]} v{u[version]} - {len(u[data].get(capabilities,[]))} caps")
        print(f"[Alii] {len(self.active_capabilities)} upgrades activated")
        
    def get_system_stats(self):
        """Enhanced hardware monitoring"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(/)
        net = psutil.net_io_counters()
        
        return {
            "cpu_usage": f"{cpu_percent}%",
            "memory_total": f"{memory.total / (1024**3):.2f} GB",
            "memory_used": f"{memory.used / (1024**3):.2f} GB",
            "memory_percent": f"{memory.percent}%",
            "disk_total": f"{disk.total / (1024**3):.2f} GB",
            "disk_used": f"{disk.used / (1024**3):.2f} GB",
            "disk_percent": f"{disk.percent}%",
            "network_sent": f"{net.bytes_sent / (1024**2):.2f} MB",
            "network_recv": f"{net.bytes_recv / (1024**2):.2f} MB"
        }
    
    def get_process_list(self):
        """List running processes"""
        processes = []
        for proc in psutil.process_iter([pid, name, cpu_percent, memory_percent]):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return sorted(processes, key=lambda x: x[cpu_percent] or 0, reverse=True)[:10]
    
    def network_scan(self):
        """Basic network information"""
        hostname = socket.gethostname()
        try:
            local_ip = socket.gethostbyname(hostname)
        except:
            local_ip = "Unable to determine"
        
        interfaces = psutil.net_if_addrs()
        return {
            "hostname": hostname,
            "local_ip": local_ip,
            "interfaces": list(interfaces.keys())
        }
    
    def execute_shell(self, command):
        """Execute shell commands safely"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
