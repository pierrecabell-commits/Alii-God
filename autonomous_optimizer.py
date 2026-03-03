import subprocess, time, json, urllib.request
print(">> Starting Alii Autonomous Reconciler Loop")
def check_status(url):
    try: return json.loads(urllib.request.urlopen(url, timeout=3).read().decode("utf-8"))
    except Exception: return None
def kill_port(p):
    try:
        o = subprocess.check_output(f"fuser {p}/tcp 2>/dev/null", shell=True).decode().strip()
        if o: subprocess.run(f"kill -9 {o}", shell=True)
    except: pass
def run_claude(prompt):
    print(f"[AUTONOMY] Triggering Claude Code: {prompt}")
    try:
        res = subprocess.run(["alii-claude", "-p", prompt], capture_output=True, text=True)
        with open("autonomy_logs.txt", "a") as f: f.write(res.stdout)
    except Exception as e: print(e)
c = 0
while True:
    time.sleep(15)
    c += 1
    a = check_status("http://127.0.0.1:7000/status")
    b = check_status("http://127.0.0.1:8000/health")
    if not a:
        subprocess.run("systemctl --user restart alfred", shell=True)
        continue
    spec = a.get("services", {}).get("distributed-brain", {})
    a_ok = spec.get("status") == "running"
    a_res = spec.get("restarts", 0)
    b_ok = b is not None and b.get("status") == "awake"
    if b_ok and not a_ok:
        kill_port(8000); kill_port(8002)
        subprocess.run("systemctl --user restart alfred", shell=True)
        time.sleep(3)
        subprocess.run("curl -s -X POST http://127.0.0.1:7000/control/distributed-brain -H \"Content-Type: application/json\" -d \"{\\\"action\\\":\\\"start\\\"}\"", shell=True)
    elif not b_ok:
        if a_res >= 10:
            run_claude("The distributed-brain service crashed and hit max restarts. Review /home/avalii/moltbot/logs/alfred.log and /home/avalii/moltbot/alii_distributed_brain.py, find the crash reason, and fix it directly.")
            subprocess.run("systemctl --user restart alfred", shell=True)
        else:
            subprocess.run("curl -s -X POST http://127.0.0.1:7000/control/distributed-brain -H \"Content-Type: application/json\" -d \"{\\\"action\\\":\\\"start\\\"}\"", shell=True)
    if c >= 960:
        run_claude("Review the python scripts in this repository. Look for any bottlenecks in Ray or vLLM usage, or any unhandled exceptions. If you find any, refactor them directly for optimal performance and write a summary.")
        c = 0
