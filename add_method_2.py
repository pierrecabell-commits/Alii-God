with open("Alii_master_unified.py", "r") as f:
    lines = f.readlines()
pos = next((i for i, ln in enumerate(lines) if "# Initialize" in ln), None)
if pos:
    method = "    def get_upgrade_count(self): return len(self.upgrades_loaded)\n"
    lines.insert(pos, method)
    with open("Alii_master_unified.py", "w") as f: f.writelines(lines)
    print("Added get_upgrade_count()")
