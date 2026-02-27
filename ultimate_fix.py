from datetime import timezone
lines=open("Alii_master_unified.py").readlines()
lines[185]="            if \"description\" in \n"
lines[187]="            if \"capabilities\" in \n"
lines[189]="            if \"methods\" in \n"
lines[191]="            if \"status\" in \n"
open("Alii_master_unified.py","w").writelines(lines)
print("DONE!")