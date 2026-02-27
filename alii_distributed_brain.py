from datetime import timezone
import os
import time
import threading
import subprocess
from datetime import datetime, timedelta

import psutil
from flask import Flask, jsonify
from prometheus_client import start_http_server, Counter, Gauge

try:
    import ray
except Exception:
    ray = None

try:
    from alii_sqlite_memory import AliiSQLiteMemory
except Exception:
    AliiSQLiteMemory = None

ALII_HEARTBEAT = Counter('alii_heartbeats_total', 'Total loops run')
ALII_API_CALLS = Counter('alii_api_calls_total', 'Total external API requests')
ALII_MEMORY_ENTRIES = Gauge('alii_total_memory_entries', 'Count of sqlite memory rows')
NODE_RAM_USAGE_GB = Gauge('alii_ram_usage_gb', 'RAM usage in GB')
NODE_CPU_PERCENT = Gauge('alii_cpu_percent', 'CPU usage percent')
RAY_CONNECTED = Gauge('alii_ray_connected', '1 if connected to Ray, else 0')

app = Flask(__name__)

class _NullMemory:
    def _init_db(self):
        return None
    def add_memory(self, *_args, **_kwargs):
        return None
    def get_memory_count(self):
        return 0

memory = _NullMemory() if AliiSQLiteMemory is None else AliiSQLiteMemory()

@app.route('/health')
def health():
    try:
        mc = memory.get_memory_count()
    except Exception:
        mc = -1
    return jsonify({'status': 'awake', 'memory_count': mc})

@app.route('/status')
def status():
    vm = psutil.virtual_memory()
    return jsonify({
        'ram_usage_percent': vm.percent,
        'ram_used_gb': round(vm.used / (1024**3), 2),
        'cpu_usage_percent': psutil.cpu_percent(interval=0.1),
    })

def run_flask():
    # use_reloader=False prevents double-start under systemd
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def _try_ray_connect():
    if ray is None:
        RAY_CONNECTED.set(0)
        return False
    try:
        ray.init(address='auto', ignore_reinit_error=True)
        RAY_CONNECTED.set(1)
        return True
    except Exception:
        RAY_CONNECTED.set(0)
        return False

def _service_status(name: str) -> str:
    try:
        return subprocess.run(
            'systemctl --user is-active ' + name,
            shell=True,
            capture_output=True,
            text=True,
        ).stdout.strip() or 'unknown'
    except Exception:
        return 'unknown'

def optimization_loop():
    print('[Alii] Starting optimization loop...')
    # 2 hour cycle checkpoints
    end_time = datetime.now() + timedelta(hours=2)

    # best-effort DB init
    try:
        memory._init_db()
    except Exception:
        pass

    try:
        memory.add_memory('system_event', {'event': 'alii_brain_boot', 'ts': datetime.now(timezone.utc).isoformat()})
    except Exception:
        pass

    ray_ok = _try_ray_connect()

    while True:
        try:
            ALII_HEARTBEAT.inc()
            try:
                ALII_MEMORY_ENTRIES.set(memory.get_memory_count())
            except Exception:
                ALII_MEMORY_ENTRIES.set(-1)

            NODE_RAM_USAGE_GB.set(psutil.virtual_memory().used / (1024**3))
            NODE_CPU_PERCENT.set(psutil.cpu_percent(interval=0.1))

            # OpenClaw gateway check (non-fatal)
            claw = _service_status('openclaw-gateway')
            try:
                memory.add_memory('service_check', {'service': 'openclaw-gateway', 'status': claw, 'ts': datetime.now(timezone.utc).isoformat()})
            except Exception:
                pass

            # Ray status refresh (non-fatal)
            if ray is not None and (not ray_ok):
                ray_ok = _try_ray_connect()

            if datetime.now() >= end_time:
                try:
                    memory.add_memory('system_event', {'event': 'optimization_cycle_complete', 'duration': '2h', 'ts': datetime.now(timezone.utc).isoformat()})
                except Exception:
                    pass
                end_time = datetime.now() + timedelta(hours=2)

            # Adaptive sleep
            time.sleep(30)

        except Exception as e:
            try:
                memory.add_memory('loop_error', {'error': str(e), 'ts': datetime.now(timezone.utc).isoformat()})
            except Exception:
                pass
            print('[Alii] Loop Error:', e)
            time.sleep(5)

if __name__ == '__main__':
    start_http_server(8000)
    threading.Thread(target=run_flask, daemon=True).start()
    optimization_loop()
