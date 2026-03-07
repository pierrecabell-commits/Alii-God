"""
Alii-God — Base Agent SDK

Provides ``BaseAgent``, a lifecycle-managed base class that every Alii agent
can inherit from.  Handles signals, health-check HTTP, periodic scheduling,
structured logging, and state tracking — all using stdlib only.

Usage:
    from base_agent import BaseAgent

    class OptimizerAgent(BaseAgent):
        name = "optimizer"

        def on_start(self):
            self.schedule(3600, self.cleanup)

        def cleanup(self):
            self.log.info("Running cleanup")

        def on_health_check(self):
            return {"status": "ok", "last_cleanup": "..."}

    if __name__ == "__main__":
        OptimizerAgent().run()
"""

from __future__ import annotations

import enum
import json
import signal
import sys
import threading
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Callable, Dict, List, Optional

from alii_logging import get_logger, set_correlation_id


# ---------------------------------------------------------------------------
# Agent state machine
# ---------------------------------------------------------------------------

class AgentState(str, enum.Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Scheduled task wrapper
# ---------------------------------------------------------------------------

class _ScheduledTask:
    """Repeating task executed on a daemon thread."""

    def __init__(
        self,
        interval: float,
        callback: Callable[[], Any],
        logger: Any,
        stop_event: threading.Event,
    ) -> None:
        self.interval = interval
        self.callback = callback
        self.logger = logger
        self._stop = stop_event
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(timeout=self.interval):
            try:
                self.callback()
            except Exception:
                self.logger.exception("Scheduled task %s failed", self.callback.__qualname__)

    def join(self, timeout: float = 5.0) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)


# ---------------------------------------------------------------------------
# Minimal health-check HTTP handler
# ---------------------------------------------------------------------------

def _make_health_handler(agent: "BaseAgent") -> type:
    """Build a request handler class bound to *agent*."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/health", "/healthz", "/"):
                try:
                    body = agent.on_health_check()
                except Exception as exc:
                    body = {"status": "error", "error": str(exc)}
                body.setdefault("state", agent.state.value)
                body.setdefault("name", agent.name)
                payload = json.dumps(body, default=str).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                self.send_error(404)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            # Silence default stderr access logging; use structured logger.
            agent.log.debug("health-http: %s", format % args)

    return _Handler


# ---------------------------------------------------------------------------
# BaseAgent
# ---------------------------------------------------------------------------

class BaseAgent:
    """Lifecycle-managed base class for all Alii agents.

    Subclasses **must** set ``name`` and **should** override at least
    ``on_start()`` and ``on_health_check()``.
    """

    name: str = "unnamed-agent"
    health_port: Optional[int] = None  # Set to an int to enable the health endpoint.

    def __init__(self) -> None:
        self.log = get_logger(self.name)
        self._state: AgentState = AgentState.STOPPED
        self._stop_event = threading.Event()
        self._tasks: List[_ScheduledTask] = []
        self._health_server: Optional[HTTPServer] = None
        self._health_thread: Optional[threading.Thread] = None

    # -- state property -----------------------------------------------------

    @property
    def state(self) -> AgentState:
        return self._state

    @state.setter
    def state(self, new: AgentState) -> None:
        old = self._state
        self._state = new
        self.log.info("State transition: %s -> %s", old.value, new.value)

    # -- lifecycle hooks (override in subclass) -----------------------------

    def on_start(self) -> None:
        """Called once after signal handlers are installed, before the main
        loop begins.  Override to set up resources and schedule tasks."""

    def on_stop(self) -> None:
        """Called during graceful shutdown.  Override to release resources."""

    def on_health_check(self) -> Dict[str, Any]:
        """Return a JSON-serialisable dict for the ``/health`` endpoint."""
        return {"status": "ok"}

    # -- scheduling ---------------------------------------------------------

    def schedule(self, interval_seconds: float, callback: Callable[[], Any]) -> None:
        """Register *callback* to run every *interval_seconds*.

        Must be called during ``on_start()`` (or any time before ``run()``
        returns).  Tasks are automatically stopped on shutdown.
        """
        task = _ScheduledTask(interval_seconds, callback, self.log, self._stop_event)
        self._tasks.append(task)
        # If agent is already running, start immediately.
        if self._state in (AgentState.STARTING, AgentState.RUNNING):
            task.start()

    # -- health HTTP --------------------------------------------------------

    def _start_health_server(self) -> None:
        if self.health_port is None:
            return
        handler_cls = _make_health_handler(self)
        try:
            self._health_server = HTTPServer(("0.0.0.0", self.health_port), handler_cls)
            self._health_thread = threading.Thread(
                target=self._health_server.serve_forever, daemon=True
            )
            self._health_thread.start()
            self.log.info("Health endpoint listening on :%d", self.health_port)
        except OSError as exc:
            self.log.warning("Could not start health server on :%d — %s", self.health_port, exc)

    def _stop_health_server(self) -> None:
        if self._health_server is not None:
            self._health_server.shutdown()
            if self._health_thread is not None:
                self._health_thread.join(timeout=3.0)
            self.log.info("Health endpoint stopped")

    # -- signal handling ----------------------------------------------------

    def _install_signals(self) -> None:
        """Install SIGTERM / SIGINT handlers that trigger graceful stop."""

        def _handler(signum: int, _frame: Any) -> None:
            sig_name = signal.Signals(signum).name
            self.log.info("Received %s — initiating graceful shutdown", sig_name)
            self._stop_event.set()

        try:
            signal.signal(signal.SIGTERM, _handler)
            signal.signal(signal.SIGINT, _handler)
        except (OSError, ValueError):
            # signal() can only be called from the main thread; if we're not
            # on the main thread, we skip installing handlers.
            self.log.warning("Cannot install signal handlers (not on main thread)")

    # -- main entry point ---------------------------------------------------

    def run(self) -> None:
        """Run the agent lifecycle.  Blocks until shutdown is requested."""
        set_correlation_id()
        self.state = AgentState.STARTING

        try:
            self._install_signals()
            self._start_health_server()
            self.on_start()

            # Start any tasks registered during on_start().
            for task in self._tasks:
                if task._thread is None:
                    task.start()

            self.state = AgentState.RUNNING
            self.log.info("Agent '%s' is running (PID %d)", self.name, _pid())

            # Block until stop is requested.
            while not self._stop_event.is_set():
                self._stop_event.wait(timeout=1.0)

        except Exception:
            self.state = AgentState.FAILED
            self.log.exception("Agent '%s' failed during startup/run", self.name)
            self._cleanup()
            sys.exit(1)

        # Graceful shutdown path.
        self._shutdown()

    # -- internal helpers ---------------------------------------------------

    def _shutdown(self) -> None:
        self.state = AgentState.STOPPING
        self._cleanup()
        try:
            self.on_stop()
        except Exception:
            self.log.exception("Error during on_stop()")
        self.state = AgentState.STOPPED
        self.log.info("Agent '%s' stopped cleanly", self.name)

    def _cleanup(self) -> None:
        """Stop scheduled tasks and health server."""
        self._stop_event.set()
        for task in self._tasks:
            task.join(timeout=3.0)
        self._stop_health_server()


def _pid() -> int:
    import os
    return os.getpid()
