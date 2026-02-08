#!/usr/bin/env python3
import subprocess, time
print("Alii AutoScale - ACTIVE")
while True:
    try:
        pods = int(subprocess.check_output("kubectl get pods | grep AliiServe | grep Running | wc -l", shell=True).decode().strip() or "25")
        cpu = int(subprocess.check_output("kubectl top pods 2>/dev/null | grep AliiServe | head -1 | awk '{print $3}' | cut -d% -f1 || echo 75", shell=True).decode().strip() or "75")
        if cpu > 85 and pods < 50:
            target = min(50, pods + 5)
            subprocess.run(f"kubectl scale deployment alii-AliiServe --replicas={target}", shell=True, capture_output=True)
            print(f"UP: {pods}->{target} (CPU:{cpu}%)")
        elif cpu < 40 and pods > 10:
            target = max(10, pods - 3)
            subprocess.run(f"kubectl scale deployment alii-AliiServe --replicas={target}", shell=True, capture_output=True)
            print(f"DOWN: {pods}->{target} (CPU:{cpu}%)")
        else:
            print(f"OK: {pods} pods @ {cpu}% CPU")
        time.sleep(30)
    except Exception as e:
        print(f"ERROR: {e}")
        time.sleep(30)
