#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import tempfile
import psutil
import socket
from datetime import datetime
from persistence_module import PersistenceManager

class EnhancedAlii:
    def __init__(self):
        self.memory_file = "memory/enhanced_memory.json"
        self.upgrades_loaded = []
        self.ensure_directories()
        self.persistence = PersistenceManager()
        print("[Alii] Loading saved upgrades...")
        self.upgrades_loaded = self.persistence.load_all_upgrades()
        print(f"[Alii] {len(self.upgrades_loaded)} upgrades restored from disk")
        self.activate_loaded_upgrades()
        
    def ensure_directories(self):
        os.makedirs("memory", exist_ok=True)
    
    def activate_loaded_upgrades(self):
        """Activate all loaded upgrades and register their capabilities"""
        self.active_capabilities = {}
        for u in self.upgrades_loaded:
            self.active_capabilities[u["name"]] = {
                "v": u["version"],
                "c": u["data"].get("capabilities", [])
            }
            print(f"  Active: {u["name"]} v{u["version"]} - {len(u["data"].get("capabilities",[]))} caps")
        print(f"[Alii] {len(self.active_capabilities)} upgrades activated")
        os.makedirs("upgrades", exist_ok=True)
        os.makedirs("documents", exist_ok=True)
        
    def get_system_stats(self):
        """Enhanced hardware monitoring"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
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
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return sorted(processes, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:10]
    
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
    
    def install_library(self, library_name):
        """Install Python library"""
        return self.execute_shell(f"pip3 install {library_name}")
    
    def save_memory(self, key, value):
        """Save to memory system"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, "r") as f:
                    memory = json.load(f)
            else:
                memory = {}
            
            memory[key] = {
                "value": value,
                "timestamp": datetime.now().isoformat()
            }
            
            with open(self.memory_file, "w") as f:
                json.dump(memory, f, indent=2)
            return True
        except Exception as e:
            print(f"Memory save error: {e}")
            return False
    
    def get_memory(self, key=None):
        """Retrieve from memory"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, "r") as f:
                    memory = json.load(f)
                if key:
                    return memory.get(key)
                return memory
            return None
        except Exception as e:
            print(f"Memory read error: {e}")
            return None
    
    def check_AliiLLM(self):
        """Check if AliiLLM is available"""
        result = self.execute_shell("AliiLLM list")
        return result['success']
    
    def list_capabilities(self):
        """List all enhanced capabilities"""
        capabilities = [
            "✓ Enhanced Hardware Monitoring (CPU, Memory, Disk, Network)",
            "✓ Process Management & Monitoring",
            "✓ Network Information & Scanning",
            "✓ Shell Command Execution",
            "✓ Python Library Installation",
            "✓ Advanced Memory System",
            "✓ AliiLLM Integration Ready"
        ]
        
        if self.check_AliiLLM():
            capabilities.append("✓ AliiLLM Models Available")
        
        return capabilities

    def list_upgrade_names(self): return [u["name"] for u in self.upgrades_loaded]
    def get_upgrade_count(self): return len(self.upgrades_loaded)
    def get_upgrade_by_capability(self, cap):
        return [u["name"] for u in self.upgrades_loaded if cap in u.get("data", {}).get("capabilities", [])]
    def inspect_upgrade(self, name):
        for u in self.upgrades_loaded:
            if u["name"] == name:
                import json
                print(json.dumps(u, indent=2))
                return u
        print(f"Upgrade {name} not found")
        return None
    def display_loaded_upgrades(self):
        print("="*70)
        print("LOADED UPGRADES - DETAILED VIEW")
        print("="*70)
        for u in self.upgrades_loaded:
            data = u.get("data", {})
            print(f"\\n[{u["name"]}] v{u["version"]}")
            print("-"*70)
            if "description" in 
            if "capabilities" in 
            if "capabilities" in 
            if "status" in 
            if "methods" in 
        print("\\n" + "="*70)
            if "status" in 
        print("="*70)
# Initialize and display
