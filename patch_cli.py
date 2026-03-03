import os, json
p = "/home/avalii/moltbot/alii_cli.py"
s = open(p).read()
if "OPS_KW =" not in s:
    s = s.replace("LOCAL_KW = [", "OPS_KW = [\"status\", \"health\", \"uptime\", \"ports\", \"cluster\"]\nLOCAL_KW = [")
if "return \"ops\", prompt" not in s:
    s = s.replace("if any(k in p for k in CODE_KW):", "if any(k in p for k in OPS_KW) and len(p.split()) < 4: return \"ops\", prompt\n    if any(k in p for k in CODE_KW):")
if "elif mode == \"ops\":" not in s:
    ops = "elif mode == \"ops\":\n            print(\"\\n[CLUSTER STATUS]\")\n            print(json.dumps(check(f\"{ALFRED}/status\"), indent=2))\n            print(json.dumps(check(f\"{BRAIN}/health\"), indent=2))"
    s = s.replace("elif mode == \"local\": run_local(p)", f"elif mode == \"local\": run_local(p)\n        {ops}")
open(p, "w").write(s)
