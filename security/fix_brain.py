
import re, subprocess
f = '/home/avalii/moltbot/alii_distributed_brain.py'
c = open(f).read()
lines_8000 = [(i+1,l.strip()) for i,l in enumerate(c.splitlines()) if '8000' in l]
print('[BRAIN] Lines referencing 8000:', lines_8000)
fixed = re.sub(r'start_http_server\(8000\)', 'start_http_server(8002)', c)
if fixed != c:
    open(f,'w').write(fixed)
    print('[FIXED] brain metrics port 8000->8002 - gunicorn still serves on 8000')
else:
    print('[INFO] No start_http_server(8000) found - gunicorn IS the brain, no fix needed')
import urllib.request, json
req = urllib.request.Request(
    "http://127.0.0.1:7000/control/distributed-brain",
    data=json.dumps({"action":"stop"}).encode(),
    headers={"Content-Type":"application/json"}, method="POST"
)
try:
    r = urllib.request.urlopen(req, timeout=5)
    print("[ALFRED] stopped distributed-brain subprocess:", r.read().decode())
except Exception as e:
    print("[ALFRED] control call:", e)
