from datetime import timezone
with open("Alii_master_unified.py", "r") as f:
    lines = f.readlines()
pos = next((i for i, ln in enumerate(lines) if "# Initialize" in ln), None)
if pos:
    m = "    def inspect_upgrade(self, name):\n        for u in self.upgrades_loaded:\n            if u[\"name\"] == name:\n                import json\n                print(json.dumps(u, indent=2))\n                return u\n        print(f\"Upgrade {name} not found\")\n        return None\n"
    lines.insert(pos, m)
    with open("Alii_master_unified.py", "w") as f: f.writelines(lines)
    print("Added inspect_upgrade()")
