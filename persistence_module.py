from datetime import timezone
#!/usr/bin/env python3
import json
import os
import hashlib
from datetime import datetime

class PersistenceManager:
    def __init__(self):
        self.upgrades_dir = "upgrades"
        self.memory_dir = "memory"
        self.documents_dir = "documents"
        self.memory_file = os.path.join(self.memory_dir, "enhanced_memory.json")
        self.state_file = os.path.join(self.memory_dir, "system_state.json")
        os.makedirs(self.upgrades_dir, exist_ok=True)
        os.makedirs(self.memory_dir, exist_ok=True)
        os.makedirs(self.documents_dir, exist_ok=True)
        print("[Persistence] Directories ready")

    def save_upgrade(self, name, data, version="1.0"):
        try:
            checksum = self._generate_checksum(data)
            upgrade_data = {
                "name": name,
                "version": version,
                "timestamp": datetime.now().isoformat(),
                "data": data,
                "checksum": checksum
            }
            filepath = os.path.join(self.upgrades_dir, f"{name}.json")
            with open(filepath, "w") as f:
                json.dump(upgrade_data, f, indent=2)
            print(f"[Persistence] Saved: {name} v{version}")
            return True
        except Exception as e:
            print(f"[Persistence] Failed: {name}: {e}")
            return False

    def load_all_upgrades(self):
        upgrades = []
        try:
            if not os.path.exists(self.upgrades_dir):
                print("[Persistence] No upgrades directory")
                return upgrades
            files = [f for f in os.listdir(self.upgrades_dir) if f.endswith(".json")]
            if not files:
                print("[Persistence] No upgrades found")
                return upgrades
            for filename in files:
                filepath = os.path.join(self.upgrades_dir, filename)
                with open(filepath, "r") as f:
                    upgrade = json.load(f)
                    upgrades.append(upgrade)
                    print(f"[Persistence] Loaded: {upgrade['name']} v{upgrade['version']}")
            print(f"[Persistence] Total: {len(upgrades)} upgrades")
            return upgrades
        except Exception as e:
            print(f"[Persistence] Error: {e}")
            return upgrades

    def save_memory(self, context_data):
        try:
            existing = self.load_memory()
            if existing:
                if "history" not in existing:
                    existing["history"] = []
                existing["history"].append({
                    "timestamp": datetime.now().isoformat(),
                    "context": context_data
                })
                memory_data = existing
            else:
                memory_data = {
                    "created": datetime.now().isoformat(),
                    "history": [{"timestamp": datetime.now().isoformat(), "context": context_data}]
                }
            with open(self.memory_file, "w") as f:
                json.dump(memory_data, f, indent=2)
            print(f"[Persistence] Memory saved: {len(memory_data['history'])} entries")
            return True
        except Exception as e:
            print(f"[Persistence] Memory save failed: {e}")
            return False

    def load_memory(self):
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, "r") as f:
                    return json.load(f)
            return None
        except Exception as e:
            print(f"[Persistence] Memory load error: {e}")
            return None

    def save_state(self, state_data):
        try:
            state = {"timestamp": datetime.now().isoformat(), "state": state_data}
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
            print("[Persistence] State saved")
            return True
        except Exception as e:
            print(f"[Persistence] State save failed: {e}")
            return False

    def load_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    return data["state"]
            return None
        except Exception as e:
            print(f"[Persistence] State load error: {e}")
            return None

    def _generate_checksum(self, data):
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

if __name__ == "__main__":
    print("Testing PersistenceManager...")
    pm = PersistenceManager()
    test = {"desc": "test upgrade", "code": "def test(): pass"}
    pm.save_upgrade("test_upgrade", test, "1.0")
    upgrades = pm.load_all_upgrades()
    pm.save_memory({"task": "test", "status": "success"})
    pm.save_state({"cpu": "1.2%"})
    print("\n[Persistence] Test complete!")
