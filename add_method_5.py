with open("Alii_master_unified.py", "r") as f:
    lines = f.readlines()
pos = next((i for i, ln in enumerate(lines) if "# Initialize" in ln), None)
if pos:
    m = """    def display_loaded_upgrades(self):\n        print(\"=\"*70)\n        print(\"LOADED UPGRADES - DETAILED VIEW\")\n        print(\"=\"*70)\n        for u in self.upgrades_loaded:\n            data = u.get(\"data\", {})\n            print(f\"\\\\n[{u[\"name\"]}] v{u[\"version\"]}\")\n            print(\"-\"*70)\n            if \"description\" in \n                print(f\"  Description: {data[\"description\"]}\")\n            if \"capabilities\" in \n                print(f\"  Capabilities: {data[\"capabilities\"]}\")\n            if \"methods\" in \n                print(f\"  Methods: {data[\"methods\"]}\")\n            if \"status\" in \n                print(f\"  Status: {data[\"status\"].upper()}\")\n            print(f\"  Loaded: {u.get(\"timestamp\", \"N/A\")}\")\n        print(\"\\\\n\" + \"=\"*70)\n        print(f\"Total: {len(self.upgrades_loaded)} upgrades\")\n        print(\"=\"*70)\n"""
    lines.insert(pos, m)
    with open("Alii_master_unified.py", "w") as f: f.writelines(lines)
    print("Added display_loaded_upgrades()")
