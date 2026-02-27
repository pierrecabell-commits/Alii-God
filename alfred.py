#!/usr/bin/env python3
"""
Alfred — Master Orchestration System for Alii
Manages lifecycle, health, task routing, and recovery of all subsystems.
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
from aiohttp import web

# ── Paths ──────────────────────────────────────────────────────────────────────
WORKDIR   = Path("/home/avalii/moltbot")
LOG_DIR   = WORKDIR / "logs"
LOG_FILE  = LOG_DIR / "alfred.log"
STATE_FILE = WORKDIR / "memory" / "alfred_state.json"

LOG_DIR.mkdir(parents=True, exist_ok=True)
(WORKDIR / "memory").mkdir(parents=True, exist_ok=True)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ALFRED] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("alfred")

# ── Service registry ───────────────────────────────────────────────────────────
@dataclass
class ServiceSpec:
    name: str
    cmd: list[str]
    cwd: str = str(WORKDIR)
    health_url: Optional[str] = None   # HTTP URL to GET for liveness check
    health_port: Optional[int] = None  # TCP port to probe (fallback)
    restart_delay: float = 5.0
    max_restarts: int = 10
    # runtime state
    pid: Optional[int] = None
    restarts: int = 0
    started_at: Optional[float] = None
    status: str = "stopped"            # stopped | starting | running | failed


# Canonical services Alfred can manage
DEFAULT_SERVICES: list[ServiceSpec] = [
    ServiceSpec(
        name="distributed-brain",
        cmd=[sys.executable, "alii_distributed_brain.py"],
        health_url="http://127.0.0.1:5000/health",
    ),
    ServiceSpec(
        name="alii-ui",
        cmd=["chainlit", "run", "alii_ui.py", "--host", "0.0.0.0", "--port", "8001"],
        health_port=8001,
    ),
]


# ── Task types ─────────────────────────────────────────────────────────────────
TASK_KEYWORDS = {
    "code":     ["code", "function", "class", "debug", "refactor", "implement", "script"],
    "analysis": ["analyze", "explain", "why", "how", "compare", "review"],
    "plan":     ["plan", "design", "architect", "strategy", "roadmap"],
    "quick":    ["what", "who", "when", "simple", "quick", "fast"],
}

def classify_task(prompt: str) -> str:
    p = prompt.lower()
    for task_type, keywords in TASK_KEYWORDS.items():
        if any(k in p for k in keywords):
            return task_type
    return "general"


# ── Process guard ──────────────────────────────────────────────────────────────
class ProcessGuard:
    """Launches and auto-restarts a single service subprocess."""

    def __init__(self, spec: ServiceSpec):
        self.spec = spec
        self._proc: Optional[subprocess.Popen] = None
        self._stop_event = asyncio.Event()

    async def start(self):
        self._stop_event.clear()
        asyncio.create_task(self._run_loop(), name=f"guard-{self.spec.name}")

    async def stop(self):
        self._stop_event.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._proc.wait, 5
                )
            except Exception:
                self._proc.kill()
        self.spec.status = "stopped"
        self.spec.pid = None
        log.info("Service '%s' stopped.", self.spec.name)

    async def restart(self):
        await self.stop()
        await asyncio.sleep(self.spec.restart_delay)
        await self.start()

    async def _run_loop(self):
        while not self._stop_event.is_set():
            if self.spec.restarts >= self.spec.max_restarts:
                self.spec.status = "failed"
                log.error(
                    "Service '%s' exceeded max restarts (%d). Giving up.",
                    self.spec.name, self.spec.max_restarts,
                )
                return

            log.info("Starting service '%s' (restart #%d).", self.spec.name, self.spec.restarts)
            self.spec.status = "starting"

            log_path = LOG_DIR / f"{self.spec.name}.log"
            with open(log_path, "a") as lf:
                self._proc = subprocess.Popen(
                    self.spec.cmd,
                    cwd=self.spec.cwd,
                    stdout=lf,
                    stderr=lf,
                    env=os.environ.copy(),
                )

            self.spec.pid = self._proc.pid
            self.spec.started_at = time.time()
            self.spec.status = "running"
            log.info("Service '%s' running as PID %d.", self.spec.name, self._proc.pid)

            # Wait for process to exit
            await asyncio.get_event_loop().run_in_executor(None, self._proc.wait)

            if self._stop_event.is_set():
                break

            exit_code = self._proc.returncode
            log.warning(
                "Service '%s' (PID %d) exited with code %d. Restarting in %.1fs…",
                self.spec.name, self.spec.pid, exit_code, self.spec.restart_delay,
            )
            self.spec.status = "stopped"
            self.spec.pid = None
            self.spec.restarts += 1
            await asyncio.sleep(self.spec.restart_delay)


# ── Health checker ─────────────────────────────────────────────────────────────
async def check_health(spec: ServiceSpec, session: aiohttp.ClientSession) -> bool:
    """Return True if the service appears healthy."""
    if spec.health_url:
        try:
            async with session.get(spec.health_url, timeout=aiohttp.ClientTimeout(total=3)) as r:
                return r.status < 500
        except Exception:
            return False
    if spec.health_port:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", spec.health_port), timeout=3
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False
    # No probe configured — trust process exit code
    return spec.pid is not None and spec.status == "running"


# ── Model router proxy ─────────────────────────────────────────────────────────
async def route_to_model(prompt: str, session: aiohttp.ClientSession) -> str:
    """Route prompt through AliiModelRouter (via Ollama), return response text."""
    # Import lazily so Alfred boots even if router has import errors
    try:
        sys.path.insert(0, str(WORKDIR))
        from alii_model_router import AliiModelRouter
        router = AliiModelRouter()
        task_type = classify_task(prompt)
        model = router.select_model(task_type)
        response = router.generate(prompt, model)
        return response or "[no response]"
    except Exception as exc:
        log.exception("Model routing error: %s", exc)
        return f"[routing error: {exc}]"


# ── Memory integration ─────────────────────────────────────────────────────────
def record_event(category: str, content: str):
    """Persist an event to SQLite memory (non-blocking best-effort)."""
    try:
        sys.path.insert(0, str(WORKDIR))
        from alii_sqlite_memory import AliiSQLiteMemory
        mem = AliiSQLiteMemory()
        mem.add_memory(category=category, content=content)
    except Exception as exc:
        log.debug("Memory record failed (non-critical): %s", exc)


# ── Alfred orchestrator ────────────────────────────────────────────────────────
class Alfred:
    """Master orchestration system."""

    CONTROL_PORT = 7000

    def __init__(self, services: list[ServiceSpec] | None = None):
        self.services: dict[str, ServiceSpec] = {}
        self.guards:   dict[str, ProcessGuard] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._health_task: Optional[asyncio.Task] = None
        self._start_time = time.time()

        for spec in (services or DEFAULT_SERVICES):
            self.register(spec)

    # ── Service management ────────────────────────────────────────────────────

    def register(self, spec: ServiceSpec):
        self.services[spec.name] = spec
        self.guards[spec.name]   = ProcessGuard(spec)
        log.info("Registered service: %s", spec.name)

    async def start_service(self, name: str) -> bool:
        if name not in self.guards:
            return False
        await self.guards[name].start()
        record_event("alfred", f"Started service: {name}")
        return True

    async def stop_service(self, name: str) -> bool:
        if name not in self.guards:
            return False
        await self.guards[name].stop()
        record_event("alfred", f"Stopped service: {name}")
        return True

    async def restart_service(self, name: str) -> bool:
        if name not in self.guards:
            return False
        await self.guards[name].restart()
        record_event("alfred", f"Restarted service: {name}")
        return True

    async def start_all(self):
        for name in self.services:
            await self.start_service(name)

    async def stop_all(self):
        for name in self.services:
            await self.stop_service(name)

    # ── Periodic health loop ──────────────────────────────────────────────────

    async def _health_loop(self, interval: float = 30.0):
        log.info("Health loop started (interval=%.0fs).", interval)
        async with aiohttp.ClientSession() as session:
            self._session = session
            while True:
                for name, spec in self.services.items():
                    if spec.status != "running":
                        continue
                    healthy = await check_health(spec, session)
                    if not healthy:
                        log.warning(
                            "Health check FAILED for '%s'. Triggering restart.", name
                        )
                        record_event("alfred_health", f"Health check failed: {name} — restarting")
                        await self.restart_service(name)
                await asyncio.sleep(interval)

    # ── HTTP control API ──────────────────────────────────────────────────────

    def _build_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/health",              self._handle_health)
        app.router.add_get("/status",              self._handle_status)
        app.router.add_post("/task",               self._handle_task)
        app.router.add_post("/control/{service}",  self._handle_control)
        app.router.add_get("/services",            self._handle_services)
        return app

    async def _handle_health(self, _request: web.Request) -> web.Response:
        uptime = time.time() - self._start_time
        running = sum(1 for s in self.services.values() if s.status == "running")
        total   = len(self.services)
        ok = running == total
        return web.json_response({
            "status": "ok" if ok else "degraded",
            "uptime_s": round(uptime, 1),
            "services_running": running,
            "services_total": total,
        }, status=200 if ok else 207)

    async def _handle_status(self, _request: web.Request) -> web.Response:
        payload = {
            "alfred_uptime_s": round(time.time() - self._start_time, 1),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "services": {},
        }
        for name, spec in self.services.items():
            payload["services"][name] = {
                "status":     spec.status,
                "pid":        spec.pid,
                "restarts":   spec.restarts,
                "started_at": datetime.utcfromtimestamp(spec.started_at).isoformat() + "Z"
                              if spec.started_at else None,
            }
        return web.json_response(payload)

    async def _handle_services(self, _request: web.Request) -> web.Response:
        return web.json_response(list(self.services.keys()))

    async def _handle_task(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)

        prompt = body.get("prompt", "").strip()
        if not prompt:
            return web.json_response({"error": "prompt required"}, status=400)

        task_type = classify_task(prompt)
        log.info("Task received (type=%s): %.80s…", task_type, prompt)

        async with aiohttp.ClientSession() as session:
            response = await route_to_model(prompt, session)

        record_event("alfred_task", f"[{task_type}] {prompt[:120]}")
        return web.json_response({"task_type": task_type, "response": response})

    async def _handle_control(self, request: web.Request) -> web.Response:
        name   = request.match_info["service"]
        try:
            body   = await request.json()
        except Exception:
            body = {}
        action = body.get("action", "status")

        if name not in self.services:
            return web.json_response({"error": f"unknown service: {name}"}, status=404)

        if action == "start":
            await self.start_service(name)
        elif action == "stop":
            await self.stop_service(name)
        elif action == "restart":
            await self.restart_service(name)
        elif action == "status":
            pass  # just return current state below
        else:
            return web.json_response({"error": f"unknown action: {action}"}, status=400)

        spec = self.services[name]
        return web.json_response({
            "service": name,
            "action":  action,
            "status":  spec.status,
            "pid":     spec.pid,
        })

    # ── Main run ──────────────────────────────────────────────────────────────

    async def run(self):
        log.info("Alfred starting — control API on port %d.", self.CONTROL_PORT)

        # Graceful shutdown on SIGINT / SIGTERM
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self._shutdown()))

        # Start all managed services
        await self.start_all()

        # Start health monitoring
        self._health_task = asyncio.create_task(self._health_loop(), name="alfred-health")

        # Schedule daily morning briefing at 07:00
        asyncio.create_task(self._briefing_scheduler(), name="alfred-briefing")

        # Schedule 09:00 daily agent runs (social sync, legal + business briefings)
        asyncio.create_task(self._daily_agent_scheduler(), name="alfred-daily-agents")

        # Start self-improvement loop (every 6 hours)
        asyncio.create_task(self._learn_loop(), name="alfred-learn")

        # Start HTTP API
        app = self._build_app()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.CONTROL_PORT)
        await site.start()
        log.info("Alfred is LIVE. Endpoints: /health /status /services /task /control/{service}")
        record_event("alfred", "Alfred orchestrator started.")

        # Persist state periodically
        while True:
            self._save_state()
            await asyncio.sleep(60)

    async def _shutdown(self):
        log.info("Alfred shutting down…")
        if self._health_task:
            self._health_task.cancel()
        await self.stop_all()
        self._save_state()
        record_event("alfred", "Alfred orchestrator stopped.")
        asyncio.get_event_loop().stop()

    # ── Morning briefing ──────────────────────────────────────────────────────

    def morning_briefing(self) -> str:
        """
        Collect full system stats and write a rich status report to logs/morning_briefing.log.
        Called automatically at 7am via the _briefing_scheduler task.
        """
        import platform
        import shutil

        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        # Service statuses
        svc_lines = []
        for name, spec in self.services.items():
            uptime_str = ""
            if spec.started_at:
                secs = int(time.time() - spec.started_at)
                uptime_str = f" (up {secs//3600}h {(secs%3600)//60}m)"
            svc_lines.append(
                f"  {name:<25} {spec.status:<10} restarts={spec.restarts}{uptime_str}"
            )

        # Disk usage
        try:
            disk = shutil.disk_usage(str(WORKDIR))
            disk_str = (
                f"{disk.used/1e9:.1f} GB used / {disk.total/1e9:.1f} GB total "
                f"({100*disk.used/disk.total:.0f}%)"
            )
        except Exception:
            disk_str = "unavailable"

        # Memory
        try:
            with open("/proc/meminfo") as fh:
                meminfo = dict(
                    line.split(":", 1)
                    for line in fh.read().splitlines()
                    if ":" in line
                )
            mem_total = int(meminfo["MemTotal"].split()[0]) / 1024
            mem_avail = int(meminfo["MemAvailable"].split()[0]) / 1024
            mem_str   = f"{mem_avail:.0f} MB free / {mem_total:.0f} MB total"
        except Exception:
            mem_str = "unavailable"

        # Load average
        try:
            load = os.getloadavg()
            load_str = f"{load[0]:.2f} {load[1]:.2f} {load[2]:.2f}"
        except Exception:
            load_str = "unavailable"

        # Alfred uptime
        uptime_s = time.time() - self._start_time
        alfred_uptime = f"{int(uptime_s)//3600}h {(int(uptime_s)%3600)//60}m"

        # Recent git commits
        try:
            r = subprocess.run(
                ["git", "-C", str(WORKDIR), "log", "--oneline", "-5"],
                capture_output=True, text=True, timeout=5
            )
            commits = r.stdout.strip() or "(none)"
        except Exception:
            commits = "(git unavailable)"

        # Todo summary
        try:
            tasks = json.loads((WORKDIR / "alfred_todo.json").read_text())
            done_count  = sum(1 for t in tasks if t.get("done"))
            total_count = len(tasks)
            todo_str    = f"{done_count}/{total_count} tasks done"
        except Exception:
            todo_str = "unavailable"

        report = (
            f"╔══════════════════════════════════════════════════╗\n"
            f"║        Alii Morning Briefing — {ts}   ║\n"
            f"╚══════════════════════════════════════════════════╝\n"
            f"\n[Alfred]\n"
            f"  Uptime : {alfred_uptime}\n"
            f"  Port   : {self.CONTROL_PORT}\n"
            f"\n[Managed Services]\n"
            + "\n".join(svc_lines) +
            f"\n\n[System Resources]\n"
            f"  Memory : {mem_str}\n"
            f"  Disk   : {disk_str}\n"
            f"  Load   : {load_str}\n"
            f"  Host   : {platform.node()}\n"
            f"\n[Recent Commits]\n{commits}\n"
            f"\n[Todo]\n  {todo_str}\n"
            f"\n{'='*52}\n"
        )

        briefing_log = LOG_DIR / "morning_briefing.log"
        try:
            with open(briefing_log, "a") as fh:
                fh.write(report)
        except Exception as exc:
            log.warning("Could not write morning_briefing.log: %s", exc)

        record_event("alfred", f"Morning briefing written: {ts}")
        log.info("Morning briefing written to %s", briefing_log)
        return report

    async def _briefing_scheduler(self):
        """Fire morning_briefing() every day at 07:00 local time."""
        while True:
            now = datetime.now()
            # Seconds until next 07:00
            target = now.replace(hour=7, minute=0, second=0, microsecond=0)
            if now >= target:
                # Already past 7am today — aim for tomorrow
                from datetime import timedelta
                target += timedelta(days=1)
            wait_s = (target - now).total_seconds()
            log.info("Morning briefing scheduled in %.0f seconds.", wait_s)
            await asyncio.sleep(wait_s)
            self.morning_briefing()

    async def _daily_agent_scheduler(self):
        """Fire social sync + legal + business briefings every day at 09:00."""
        from datetime import timedelta
        while True:
            now = datetime.now()
            target = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            await asyncio.sleep((target - now).total_seconds())
            log.info("09:00 daily agent run starting.")
            await asyncio.get_event_loop().run_in_executor(None, self._run_daily_agents)

    def _run_daily_agents(self):
        try:
            sys.path.insert(0, str(WORKDIR))
            from agents.social_agent import SocialAgent
            SocialAgent().cross_platform_sync()
            log.info("cross_platform_sync complete.")
        except Exception as exc:
            log.warning("cross_platform_sync error: %s", exc)
        try:
            from agents.law_agent import LawAgent
            LawAgent().daily_legal_briefing()
            log.info("daily_legal_briefing complete.")
        except Exception as exc:
            log.warning("daily_legal_briefing error: %s", exc)
        try:
            from agents.business_agent import BusinessAgent
            BusinessAgent().daily_business_briefing()
            log.info("daily_business_briefing complete.")
        except Exception as exc:
            log.warning("daily_business_briefing error: %s", exc)

    async def _learn_loop(self):
        """Self-improvement: reads logs every 6h, updates outcome weights in memory."""
        while True:
            await asyncio.sleep(6 * 3600)
            await asyncio.get_event_loop().run_in_executor(None, self.learn_from_outcomes)

    def learn_from_outcomes(self) -> dict:
        """
        Read recent logs, count restart events and health failures per service,
        adjust restart_delay weights, persist updated weights to alfred_state.json.
        """
        weights: dict[str, dict] = {}
        log_dir = LOG_DIR

        # Parse all service logs for ERROR/WARN patterns
        for name, spec in self.services.items():
            log_path = log_dir / f"{name}.log"
            restarts   = spec.restarts
            errors     = 0
            recoveries = 0
            if log_path.exists():
                try:
                    lines = log_path.read_text(errors="replace").splitlines()[-500:]
                    errors     = sum(1 for l in lines if "ERROR" in l or "CRITICAL" in l)
                    recoveries = sum(1 for l in lines if "recovered" in l.lower() or "OK:" in l)
                except Exception:
                    pass

            # Adaptive restart delay: more restarts → longer delay (back-off)
            base_delay = 5.0
            adaptive   = min(base_delay * (1 + restarts * 0.5), 60.0)
            spec.restart_delay = adaptive

            weights[name] = {
                "restarts":      restarts,
                "log_errors":    errors,
                "log_recoveries": recoveries,
                "adaptive_restart_delay": round(adaptive, 1),
            }

        record_event("alfred_learn", json.dumps(weights))
        log.info("learn_from_outcomes: updated weights for %d services.", len(weights))

        # Persist to state file
        state = {}
        if STATE_FILE.exists():
            try:
                state = json.loads(STATE_FILE.read_text())
            except Exception:
                pass
        state["learned_weights"] = weights
        state["last_learn"]      = datetime.utcnow().isoformat() + "Z"
        try:
            STATE_FILE.write_text(json.dumps(state, indent=2))
        except Exception as exc:
            log.debug("State write failed: %s", exc)
        return weights

    def _save_state(self):
        state = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "uptime_s":  round(time.time() - self._start_time, 1),
            "services":  {
                name: {
                    "status":   spec.status,
                    "pid":      spec.pid,
                    "restarts": spec.restarts,
                }
                for name, spec in self.services.items()
            },
        }
        try:
            STATE_FILE.write_text(json.dumps(state, indent=2))
        except Exception as exc:
            log.debug("State save failed (non-critical): %s", exc)


# ── CLI entry point ────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Alfred — Alii Master Orchestrator")
    parser.add_argument(
        "--services", nargs="*", metavar="NAME",
        help="Restrict which services Alfred manages (default: all)"
    )
    parser.add_argument(
        "--no-services", action="store_true",
        help="Start Alfred API only, without launching any managed services"
    )
    args = parser.parse_args()

    services = DEFAULT_SERVICES
    if args.no_services:
        services = []
    elif args.services:
        services = [s for s in DEFAULT_SERVICES if s.name in args.services]

    alfred = Alfred(services=services)
    asyncio.run(alfred.run())


if __name__ == "__main__":
    main()
