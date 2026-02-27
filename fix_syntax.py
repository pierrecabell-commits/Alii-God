from datetime import timezone
with open("Alii_master_unified.py", "r") as f:
    lines = f.readlines()

lines[185] = "            if \"description\" in \n"
lines[187] = "            if \"capabilities\" in \n"
lines[189] = "            if \"methods\" in \n"
lines[191] = "            if \"status\" in \n"

with open("Alii_master_unified.py", "w") as f:
    f.writelines(lines)

print("Syntax fixed!")
