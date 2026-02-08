with open("Alii_master_unified.py", "r") as f:
    lines = f.readlines()
pos = next((i for i, ln in enumerate(lines) if "# Initialize" in ln), None)
if pos:
    methods = "    def list_upgrade_names(self): return [u[\"name\"] for u in self.upgrades_loaded]\n"
    lines.insert(pos, methods)
    with open("Alii_master_unified.py", "w") as f: f.writelines(lines)
    print("Added methods")
