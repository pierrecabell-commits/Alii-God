#!/usr/bin/env python3
import subprocess, sys, os, json, urllib.request, time
import re

ALFRED = "http://127.0.0.1:7000"
BRAIN  = "http://127.0.0.1:8000"

def check(url):
    try: return json.loads(urllib.request.urlopen(url, timeout=2).read())
    except: return None

def ensure_up():
    if not check(f"{ALFRED}/status"):
        print("[alii] Starting Alfred..."); subprocess.run("systemctl --user start alfred", shell=True); time.sleep(3)
    if not check(f"{BRAIN}/health"):
        print("[alii] Starting Brain...")
        subprocess.run(["curl", "-s", "-X", "POST", "http://127.0.0.1:7000/control/distributed-brain", "-H", "Content-Type: application/json", "-d", "{\"action\":\"start\"}"])# -s -X POST http://127.0.0.1:7000/control/distributed-brain -H \"Content-Type: application/json\" -d \"{\\"action\\":\\"start\\"}\"", shell=True)
        time.sleep(4)

def send_to_alfred(prompt):
    data = json.dumps({"prompt": prompt}).encode()
    req = urllib.request.Request(f"{ALFRED}/task", data=data, headers={"Content-Type":"application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=10)
        resp = json.loads(r.read())
        return resp.get("response") or resp.get("result") or str(resp)
    except Exception as e: return f"[Alfred error: {e}]"

CODE_KW = ["code","function","class","debug","refactor","implement","script","build","fix","deploy","write","generate"]
OPS_KW = ["status", "health", "uptime", "ports", "cluster"]
LOCAL_KW = ["what is","who is","explain","define","how does","quick","tell me","summarize"]

def route(prompt):
    p = prompt.lower()
    if any(k in p for k in OPS_KW) and len(p.split()) < 4: return "ops", prompt
    if any(k in p for k in CODE_KW): return "claude", prompt
    if any(k in p for k in LOCAL_KW): return "local", prompt
    return "alfred", prompt

def run_claude(prompt): subprocess.run(["alii-claude", "-p", prompt])

def run_local(prompt): subprocess.run(["ollama", "run", "dolphin-phi:2.7b", prompt])

def banner():
    a = check(f"{ALFRED}/status"); b = check(f"{BRAIN}/health")
    a_st = a["services"]["distributed-brain"]["status"] if a else "DOWN"
    b_st = b["status"] if b else "DOWN"
    mem = b["memory_count"] if b else "?"
    print(f"\n  =================================")
    print(f"  |  A L I I  — Online          |")
    print(f"  |  Alfred: {a_st:<8}           |")
    print(f"  |  Brain:  {b_st:<8}  mem:{mem:<5}|")
    print(f"  =================================\n")

def main():
    ensure_up()
    banner()
    print("  Type your message. Alii routes to Claude, local LLM, or Alfred automatically.")
    print("  /status  /memory  /claude  /local  /quit\n")
    while True:
        try: prompt = input("\033[36mYou: \033[0m").strip()
        except (KeyboardInterrupt, EOFError): print("\n[alii] Goodbye."); break
        if not prompt: continue
        if prompt == "/quit": break
        if prompt == "/status": print(json.dumps(check(f"{ALFRED}/status"), indent=2)); continue
        if prompt == "/memory": print(json.dumps(check(f"{BRAIN}/health"), indent=2)); continue
        if prompt.startswith("/claude "): run_claude(prompt[8:]); continue
        if prompt.startswith("/local "): run_local(prompt[7:]); continue
        mode, p = route(prompt)
        print(f"\033[90m  [routing -> {mode}]\033[0m")
        if mode == "claude": run_claude(p)
        elif mode == "local": run_local(p)
        elif mode == "ops":
            print("\n[CLUSTER STATUS]")
            print(json.dumps(check(f"{ALFRED}/status"), indent=2))
            print(json.dumps(check(f"{BRAIN}/health"), indent=2))
        else:
            resp = send_to_alfred(p)
            print(f"\033[32mAlii: \033[0m{resp}")

if __name__ == "__main__": main()
