#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import tempfile
import psutil
import socket
from datetime import datetime

class EnhancedAlii:
    def __init__(self):
        self.memory_file = "memory/enhanced_memory.json"
        self.upgrades_loaded = []
        self.ensure_directories()

    def ensure_directories(self):
        os.makedirs("memory", exist_ok=True)
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
                with open(self.memory_file, r) as f:
                    memory = json.load(f)
            else:
                memory = {}

            memory[key] = {
                "value": value,
                "timestamp": datetime.now().isoformat()
            }

            with open(self.memory_file, w) as f:
                json.dump(memory, f, indent=2)
            return True
        except Exception as e:
            print(f"Memory save error: {e}")
            return False

    def get_memory(self, key=None):
        """Retrieve from memory"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, r) as f:
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

# Initialize and display
if __name__ == "__main__":
    bot = EnhancedAlii()

    print("="*60)
    print("ENHANCED Alii - Full System Control")
    print("="*60)
    print("\nCapabilities:")
    for cap in bot.list_capabilities():
        print(f"  {cap}")

    print("\n" + "="*60)
    print("SYSTEM STATS:")
    print("="*60)
    stats = bot.get_system_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n" + "="*60)
    print("NETWORK INFO:")
    print("="*60)
    net_info = bot.network_scan()
    for key, value in net_info.items():
        print(f"  {key}: {value}")

    print("\n" + "="*60)
    print("TOP PROCESSES:")
    print("="*60)
    processes = bot.get_process_list()
    for i, proc in enumerate(processes[:5], 1):
        print(f"  {i}. {proc['name']} (PID: {proc['pid']}) - CPU: {proc['cpu_percent']}%")

    print("\n" + "="*60)
    print("Enhanced Alii Ready!")
    print("Import this module to use: from Alii_enhanced import EnhancedAlii")
    print("="*60)
