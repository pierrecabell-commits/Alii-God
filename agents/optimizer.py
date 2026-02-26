import os
import time
print("ALII Optimizer Agent - ACTIVE")
while True:
    # Storage cleanup
    os.system("docker system prune -f 2>/dev/null")
    print("Storage optimized")
    time.sleep(3600)
