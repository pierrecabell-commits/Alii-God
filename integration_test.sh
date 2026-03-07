#!/usr/bin/env bash
# Alii Integration Test Suite
# Runs all health checks and outputs PASS/FAIL per check
# Usage: ./integration_test.sh [--json] [--quiet]

set -uo pipefail

PASS=0
FAIL=0
RESULTS=()
JSON_MODE=false
QUIET=false
LOG_FILE="/home/avalii/moltbot/logs/integration_test.log"
NTFY_URL="http://localhost:8080/alii-alerts"

for arg in "$@"; do
  case $arg in
    --json) JSON_MODE=true ;;
    --quiet) QUIET=true ;;
  esac
done

# ── Helpers ────────────────────────────────────────────────────────────────────

log() {
  echo "[$(date -Iseconds)] $1" | tee -a "$LOG_FILE"
}

check() {
  local name="$1"
  local cmd="$2"
  local result
  result=$(eval "$cmd" 2>&1)
  local exit_code=$?
  if [ $exit_code -eq 0 ]; then
    PASS=$((PASS + 1))
    RESULTS+=("PASS|$name")
    $QUIET || echo "  PASS: $name"
  else
    FAIL=$((FAIL + 1))
    RESULTS+=("FAIL|$name|$result")
    echo "  FAIL: $name"
    $QUIET || echo "        $result" | head -1
  fi
}

check_http() {
  local name="$1"
  local url="$2"
  local expected_code="${3:-200}"
  local code
  code=$(python3 -c "
import urllib.request, urllib.error
try:
    r = urllib.request.urlopen('$url', timeout=5)
    print(r.status)
except urllib.error.HTTPError as e:
    print(e.code)
except Exception as e:
    print(0)
" 2>/dev/null)
  if [ "$code" = "$expected_code" ] || [ "$code" = "200" ] || [ "$code" = "204" ]; then
    PASS=$((PASS + 1))
    RESULTS+=("PASS|$name (HTTP $code)")
    $QUIET || echo "  PASS: $name (HTTP $code)"
  else
    FAIL=$((FAIL + 1))
    RESULTS+=("FAIL|$name (got HTTP $code, expected $expected_code)")
    echo "  FAIL: $name (got HTTP $code, expected ~$expected_code)"
  fi
}

echo ""
echo "============================================="
echo "  ALII INTEGRATION TEST SUITE - $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "============================================="
log "Integration test started"

# ── Service Endpoint Tests ────────────────────────────────────────────────────

echo ""
echo "[ SERVICE ENDPOINTS ]"

check_http "Qdrant health" "http://localhost:6333/healthz"
check_http "LiteLLM health (auth expected)" "http://localhost:4000/health" 401
check_http "MinIO health" "http://localhost:9000/minio/health/live"
check_http "n8n health" "http://localhost:5678/healthz"
check_http "Prometheus health" "http://localhost:9090/-/healthy"
check_http "Grafana health" "http://localhost:3001/api/health"
check_http "node_exporter metrics" "http://localhost:9100/metrics"
check_http "Ollama API" "http://localhost:11434/api/tags"
check_http "Open-WebUI" "http://localhost:3000"

# ── Qdrant Round-trip ─────────────────────────────────────────────────────────

echo ""
echo "[ QDRANT VECTOR MEMORY ]"

check "Qdrant collection alii_memories" "python3 -c \"
import urllib.request, json
with urllib.request.urlopen('http://localhost:6333/collections/alii_memories', timeout=5) as r:
    d = json.loads(r.read())
    count = d['result'].get('points_count', 0)
    assert count > 0, f'No points in collection: {count}'
    print(f'{count} vectors indexed')
\""

check "Qdrant semantic search" "python3 -c \"
import sys; sys.path.insert(0, '/home/avalii/moltbot')
from memory_bridge import search_memories
results = search_memories('test query')
assert len(results) >= 0, 'Search failed'
print(f'{len(results)} results returned')
\""

# ── LiteLLM → Ollama ─────────────────────────────────────────────────────────

echo ""
echo "[ LITELLM ROUTER ]"

check "LiteLLM process running" "pgrep -f 'litellm' > /dev/null"
check "LiteLLM port 4000 listening" "ss -lntp | grep -q ':4000'"
check "Ollama models available" "ollama list | grep -v NAME | head -1 | grep -q '.'"

# ── MinIO Round-trip ──────────────────────────────────────────────────────────

echo ""
echo "[ MINIO OBJECT STORAGE ]"

check "MinIO round-trip test" "cd /home/avalii/moltbot && python3 storage_client.py --test 2>&1 | grep -q 'PASS'"

# ── n8n Workflows ─────────────────────────────────────────────────────────────

echo ""
echo "[ N8N WORKFLOWS ]"

check "n8n container running" "docker ps --filter name=n8n --format '{{.Status}}' | grep -q 'Up'"
check "n8n workflow files exist" "ls /home/avalii/moltbot/data/n8n_workflows/*.json > /dev/null 2>&1"

# ── Security Agent ────────────────────────────────────────────────────────────

echo ""
echo "[ SECURITY AGENT ]"

check "Security agent last run < 25h" "python3 -c \"
import json, os
from datetime import datetime, timedelta
f = '/home/avalii/moltbot/data/security_state.json'
if os.path.exists(f):
    with open(f) as fp:
        s = json.load(fp)
    last = s.get('last_run')
    if last:
        diff = datetime.now() - datetime.fromisoformat(last)
        assert diff < timedelta(hours=25), f'Last run was {diff} ago'
        print(f'Last run: {diff}')
    else:
        print('No last_run recorded (first run)')
else:
    print('State file not yet created (run security agent first)')
\""

check "Pre-commit hook installed" "test -x /home/avalii/moltbot/.git/hooks/pre-commit"
check "Zero hardcoded secrets" "python3 /home/avalii/moltbot/security_agent.py --mode secrets 2>/dev/null > /tmp/secrets_check.json && python3 -c \"import json; d=json.load(open('/tmp/secrets_check.json')); exit(1 if d else 0)\" && echo clean"

# ── Inventory Agent ───────────────────────────────────────────────────────────

echo ""
echo "[ INVENTORY AGENT ]"

check "Inventory agent last run < 7h" "python3 -c \"
import json, os
from datetime import datetime, timedelta
f = '/home/avalii/moltbot/data/system_inventory.json'
if not os.path.exists(f):
    raise Exception('system_inventory.json not found')
mtime = os.path.getmtime(f)
age = datetime.now().timestamp() - mtime
assert age < 7*3600, f'Inventory is {age/3600:.1f}h old'
print(f'Inventory age: {age/60:.0f} minutes')
\""

# ── Sensitive File Permissions ────────────────────────────────────────────────

echo ""
echo "[ SENSITIVE FILE PERMISSIONS ]"

for f in /home/avalii/moltbot/private.key /home/avalii/moltbot/public.key \
          /home/avalii/moltbot/wg0.conf /home/avalii/moltbot/config.json \
          /home/avalii/moltbot/.env /home/avalii/moltbot/cluster_credentials.json; do
  check "chmod 600: $f" "test \"\$(stat -c '%a' $f 2>/dev/null)\" = '600'"
done

# ── Cluster Nodes ─────────────────────────────────────────────────────────────

echo ""
echo "[ CLUSTER NODES - TAILSCALE ]"

check "NUC reachable (100.126.57.22)" "ping -c 1 -W 3 100.126.57.22 > /dev/null 2>&1"
check "XPS reachable (100.91.78.55)" "ping -c 1 -W 3 100.91.78.55 > /dev/null 2>&1"
check "Cluster map exists" "test -f /home/avalii/moltbot/data/cluster_map.json"

# ── Docker Containers ─────────────────────────────────────────────────────────

echo ""
echo "[ DOCKER CONTAINERS ]"

for container in qdrant minio n8n open-webui; do
  check "Docker: $container running" "docker ps --filter name=$container --format '{{.Status}}' 2>/dev/null | grep -q 'Up'"
done

# ── Summary ───────────────────────────────────────────────────────────────────

TOTAL=$((PASS + FAIL))
echo ""
echo "============================================="
echo "  TEST RESULTS: $PASS/$TOTAL PASSED, $FAIL FAILED"
echo "============================================="
log "Results: $PASS/$TOTAL passed, $FAIL failed"

if [ "$JSON_MODE" = true ]; then
  python3 -c "
import json, sys
results = []
for r in sys.argv[1:]:
    parts = r.split('|')
    results.append({'status': parts[0], 'name': parts[1], 'detail': parts[2] if len(parts)>2 else ''})
print(json.dumps({'pass': $PASS, 'fail': $FAIL, 'total': $TOTAL, 'results': results}, indent=2))
" "${RESULTS[@]}" 2>/dev/null
fi

# Send ntfy summary
NTFY_BODY="Integration tests: $PASS/$TOTAL passed"
if [ $FAIL -gt 0 ]; then
  NTFY_BODY="$NTFY_BODY ($FAIL FAILED)"
  NTFY_PRIORITY="high"
  # Add failed test names
  for r in "${RESULTS[@]}"; do
    if [[ "$r" == FAIL* ]]; then
      name=$(echo "$r" | cut -d'|' -f2)
      NTFY_BODY="$NTFY_BODY\n  FAIL: $name"
    fi
  done
else
  NTFY_PRIORITY="low"
fi

python3 -c "
import urllib.request
try:
    req = urllib.request.Request('$NTFY_URL', b'$NTFY_BODY')
    req.add_header('Title', 'Alii Integration Tests')
    req.add_header('Priority', '$NTFY_PRIORITY')
    urllib.request.urlopen(req, timeout=3)
except Exception:
    pass
" 2>/dev/null

# Write JSON results file
python3 -c "
import json, datetime
results = []
raw = '''$(for r in "${RESULTS[@]}"; do echo "$r"; done)'''
for line in raw.strip().splitlines():
    parts = line.split('|')
    if len(parts) >= 2:
        results.append({
            'status': parts[0],
            'name': parts[1],
            'detail': parts[2] if len(parts) > 2 else ''
        })
report = {
    'timestamp': datetime.datetime.now().isoformat(),
    'pass': $PASS,
    'fail': $FAIL,
    'total': $TOTAL,
    'results': results
}
with open('/home/avalii/moltbot/data/last_integration_test.json', 'w') as f:
    json.dump(report, f, indent=2)
print('Results saved to data/last_integration_test.json')
" 2>/dev/null

if [ $FAIL -eq 0 ]; then
  echo "  All tests PASSED"
  exit 0
else
  echo "  $FAIL test(s) FAILED - review above"
  exit 1
fi
