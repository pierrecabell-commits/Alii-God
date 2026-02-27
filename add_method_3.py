from datetime import timezone
with open("Alii_master_unified.py", "r") as f:
    lines = f.readlines()
pos = next((i for i, ln in enumerate(lines) if "# Initialize" in ln), None)
if pos:
    m = "    def get_upgrade_by_capability(self, cap):\n        return [u[\"name\"] for u in self.upgrades_loaded if cap in u.get(\"data\", {}).get(\"capabilities\", [])]\n"
    lines.insert(pos, m)
    with open("Alii_master_unified.py", "w") as f: f.writelines(lines)
    print("Added get_upgrade_by_capability()")
