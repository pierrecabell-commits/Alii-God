#!/usr/bin/env python3
"""
alii_tui.py — Unified Alii Terminal Hub  v3.0

The single entry point for all things Alii. Type "alii" to launch.

Panels:
  [0] Todos      — autonomous task center, Alii can execute/ask/track
  [1] Chat / AI  — intelligent streaming chat (Ollama-first, tool-aware)
  [2] Agents     — all agent status, start/stop/restart
  [3] Cluster    — live node stats for all 4 nodes
  [4] Camera     — live Jetson camera feed (ASCII art, auto-refresh)
  [5] Social     — MixPost queue + social agent status
  [6] Systems    — disk, docker, ollama models, ray, logs
  [7] Config     — edit .env settings, model tiers
  [8] Help       — full instruction manual

Author: Alii / Pierre Cabell
"""

from __future__ import annotations
import asyncio, json, os, re, subprocess, sys, time, textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Ensure venv is active ──────────────────────────────────────────────────────
WORKDIR     = Path("/home/avalii/moltbot")
VENV_PYTHON = WORKDIR / "venv" / "bin" / "python3"

if sys.executable != str(VENV_PYTHON) and VENV_PYTHON.exists():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

# ── Textual imports ────────────────────────────────────────────────────────────
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Static, ListView, ListItem, DataTable, RichLog,
    Input, Button, TabbedContent, TabPane, ContentSwitcher, Label, Footer
)
from textual.widget import Widget
from textual.reactive import reactive
from textual import work
from textual.message import Message
from rich.text import Text
from rich.style import Style

# ── Local imports ──────────────────────────────────────────────────────────────
sys.path.insert(0, str(WORKDIR))
from alii_tui_cluster import ClusterPoller, ClusterState, sync_collect_all
from alii_tui_chat import ChatBackend, get_backend, classify_prompt

# ── Constants ──────────────────────────────────────────────────────────────────
DATA_DIR    = WORKDIR / "data"
LOGS_DIR    = WORKDIR / "logs"
ENV_FILE    = WORKDIR / ".env"
AGENTS_DIR  = WORKDIR / "agents"
TODOS_FILE  = DATA_DIR / "owner_todos.json"
MIXPOST_URL = "http://100.75.36.73:9101"
JETSON_IP   = "100.87.137.61"
CAM_PORT    = 8765

PANEL_IDS = [
    "panel-todos", "panel-chat", "panel-agents", "panel-cluster",
    "panel-camera", "panel-social", "panel-systems", "panel-config", "panel-help"
]

MENU_ITEMS = [
    ("[0] ◈ Todos",        "panel-todos"),
    ("[1] Chat / AI",      "panel-chat"),
    ("[2] Agents",         "panel-agents"),
    ("[3] Cluster",        "panel-cluster"),
    ("[4] 📷 Camera",      "panel-camera"),
    ("[5] Social",         "panel-social"),
    ("[6] Systems",        "panel-systems"),
    ("[7] Config",         "panel-config"),
    ("[8] Help / Manual",  "panel-help"),
]

ALII_BANNER = """[bold cyan]
  ╔═══════════════════════════════════════════════════════╗
  ║     ◈  A L I I  —  Sovereign AI  v3.0  ◈             ║
  ║     Precision Cluster · Akron, OH                     ║
  ╚═══════════════════════════════════════════════════════╝[/bold cyan]
[dim]  Routing: Ollama-first · Claude: /escalate only[/dim]
[dim]  Tool-aware chat: mention camera/todo/status/shell — I route automatically[/dim]
[dim]  Commands: /shell /memory /agents /status /todos /camera /clear /escalate[/dim]
"""

PRIORITY_COLORS = {"critical": "red", "high": "yellow", "medium": "cyan", "low": "dim"}


# ══════════════════════════════════════════════════════════════════════════════
# ── Helpers ───────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def load_todos() -> list[dict]:
    try:
        raw = TODOS_FILE.read_text()
        data = json.loads(raw)
        return data if isinstance(data, list) else data.get("todos", [])
    except Exception:
        return []

def save_todos(todos: list[dict]):
    TODOS_FILE.write_text(json.dumps(todos, indent=2))

def mark_todo_done(todo_id: str):
    todos = load_todos()
    for t in todos:
        if t.get("id", "") == todo_id:
            t["status"] = "done"
            t["completed_at"] = datetime.now(timezone.utc).isoformat()
    save_todos(todos)

def todo_priority_rank(t: dict) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(t.get("priority", "low"), 3)

def jpeg_to_ascii(data: bytes, width: int = 72, height: int = 28) -> str:
    """Convert JPEG bytes to ASCII art string using Pillow."""
    try:
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(data)).convert("L")
        img = img.resize((width, height))
        chars = " ·-+*%#@"
        lines = []
        pixels = list(img.getdata())
        for y in range(height):
            row = ""
            for x in range(width):
                px = pixels[y * width + x]
                idx = int(px / 256 * len(chars))
                row += chars[min(idx, len(chars)-1)]
            lines.append(row)
        return "\n".join(lines)
    except Exception as e:
        return f"[ASCII art failed: {e}]"

def fetch_camera_snapshot() -> tuple[bytes, str]:
    """Fetch JPEG from Jetson camera service. Returns (bytes, error_msg)."""
    import urllib.request
    try:
        url = f"http://{JETSON_IP}:{CAM_PORT}/snapshot"
        with urllib.request.urlopen(url, timeout=8) as r:
            data = r.read()
            if len(data) > 1000:
                return data, ""
            return b"", f"snapshot too small ({len(data)} bytes)"
    except Exception as e:
        return b"", str(e)


# ══════════════════════════════════════════════════════════════════════════════
# ── Header Widget ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class AliiHeader(Widget):
    """Live-updating 4-line header showing cluster status."""

    DEFAULT_CSS = ""
    _state: Optional[ClusterState] = None

    def compose(self) -> ComposeResult:
        yield Static("", id="header-line1")
        yield Static("", id="header-line2")
        yield Static("", id="header-line3")

    def on_mount(self):
        self.set_interval(10, self._refresh_header)
        self.set_timer(0.5, self._refresh_header)

    def update_state(self, state: ClusterState):
        self._state = state
        self._render_header()

    def _refresh_header(self):
        app = self.app
        if hasattr(app, "_cluster_state") and app._cluster_state:
            self._state = app._cluster_state
        self._render_header()

    def _render_header(self):
        s = self._state
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if s is None:
            self.query_one("#header-line1", Static).update(
                f"[bold cyan]◈ ALII v3[/bold cyan]  [dim]initializing cluster scan...[/dim]  [dim]{now}[/dim]"
            )
            return

        p = s.precision

        def node_badge(name: str) -> str:
            node = s.nodes.get(name)
            if not node:
                return f"[dim]●{name.upper()}?[/dim]"
            if not node.online:
                return f"[red]●{name.upper()}:OFF[/red]"
            color = node.temp_color
            return f"[{color}]●{name.upper()}:{node.temp_c:.0f}°[/{color}]"

        p_color = p.temp_color
        prec_badge = (
            f"[bold {p_color}]●PRECISION:{p.temp_c:.0f}°C[/bold {p_color}]"
            f"[dim] L:{p.load_1m} RAM:{p.ram_used_gb}/{p.ram_total_gb}G[/dim]"
        )
        nodes_str = "  ".join(node_badge(n) for n in ["xps", "nuc", "jetson"])

        models = s.ollama_models[:4]
        models_str = " ".join(f"[green]{m}✓[/green]" for m in models) if models else "[dim]none[/dim]"

        svc_color = "green" if s.services_up == s.services_total else "yellow"
        svc_str = f"[{svc_color}]{s.services_up}/{s.services_total}✓[/{svc_color}]"

        todos = load_todos()
        pending = [t for t in todos if t.get("status", "pending") == "pending"]
        critical = [t for t in pending if t.get("priority") == "critical"]
        todo_color = "red" if critical else ("yellow" if pending else "dim")
        todo_str = f"[{todo_color}]{'⚠ ' if critical else ''}{len(pending)} todo{'s' if len(pending) != 1 else ''}[/{todo_color}]"

        cam_badge = "[green]📷CAM[/green]" if getattr(self.app, "_cam_ok", False) else "[dim]📷?[/dim]"

        self.query_one("#header-line1", Static).update(
            f"[bold cyan]◈ ALII v3[/bold cyan]  {prec_badge}  {nodes_str}  {cam_badge}"
        )
        self.query_one("#header-line2", Static).update(
            f"[dim]Models:[/dim] {models_str}  [dim]│[/dim]  [dim]Claude:/escalate[/dim]  [dim]│[/dim]  [dim]LiteLLM/Ollama:default[/dim]"
        )
        self.query_one("#header-line3", Static).update(
            f"[dim]Svcs:[/dim] {svc_str}  [dim]│[/dim]  {todo_str}  [dim]│[/dim]  [dim]{now}[/dim]  [dim]│  0=Todos 1=Chat 4=Cam[/dim]"
        )


# ══════════════════════════════════════════════════════════════════════════════
# ── Menu Widget ───────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class AliiMenu(Widget):
    """Left sidebar navigation menu."""

    class Selected(Message):
        def __init__(self, panel_id: str):
            super().__init__()
            self.panel_id = panel_id

    def compose(self) -> ComposeResult:
        yield Static("  ◈ NAVIGATION", id="menu-title")
        lv = ListView()
        for label, panel_id in MENU_ITEMS:
            item = ListItem(Label(f"  {label}"), id=f"menu-{panel_id}")
            lv.append(item)
        yield lv
        yield Static("")
        yield Static("  [dim]─────────────────[/dim]")
        yield Static("  [dim][Q] Quit  [R] Refresh[/dim]")
        yield Static("  [dim][?] Help  [0] Todos[/dim]")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.id:
            panel_id = event.item.id.replace("menu-", "")
            self.post_message(self.Selected(panel_id))


# ══════════════════════════════════════════════════════════════════════════════
# ── Todos Panel ───────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class TodosPanel(Widget):
    """
    Autonomous task center. Alii can execute tasks, ask for info, or flag for Pierre.
    Panel [0] — most prominent, always accessible.
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="panel-todos"):
            yield Static(
                "[bold cyan]◈ TODOS[/bold cyan]  [dim]Autonomous task center — Alii executes what he can, asks for the rest[/dim]",
                id="todos-header"
            )
            yield Static("", id="todos-summary")
            table = DataTable(id="todos-table", cursor_type="row")
            table.add_columns("Pri", "Category", "Title", "Status", "Auto?")
            yield table
            yield Static("", id="todos-detail")
            with Horizontal():
                yield Button("↻ Refresh", id="btn-todos-refresh", variant="primary")
                yield Button("⚡ Execute Selected", id="btn-todos-execute", variant="success")
                yield Button("✓ Done Selected", id="btn-todos-done")
                yield Button("🤖 Auto-run All", id="btn-todos-autorun")
                yield Button("+ Add Todo", id="btn-todos-add")
            yield RichLog(id="todos-exec-log", wrap=True, markup=True, max_lines=20)

    def on_mount(self):
        self.set_timer(0.3, self._populate)
        self.set_interval(60, self._populate)

    def _populate(self):
        todos = load_todos()
        pending = sorted(
            [t for t in todos if t.get("status", "pending") == "pending"],
            key=todo_priority_rank
        )
        done_count = len([t for t in todos if t.get("status") == "done"])

        table = self.query_one("#todos-table", DataTable)
        table.clear()

        self._todo_ids = []
        for t in pending:
            pri   = t.get("priority", "?")
            cat   = t.get("category", "?")
            title = t.get("title", "?")[:55]
            status = t.get("status", "pending")
            can_auto = "✓ AUTO" if t.get("can_alii_execute") else ("❓ needs info" if t.get("needs_info") else "— Pierre")
            color = PRIORITY_COLORS.get(pri, "white")
            table.add_row(
                Text.from_markup(f"[{color}]{pri.upper()[:4]}[/{color}]"),
                cat, title,
                Text.from_markup(f"[{'green' if status == 'done' else 'yellow'}]{status}[/{'green' if status == 'done' else 'yellow'}]"),
                Text.from_markup(f"[{'green' if t.get('can_alii_execute') else 'dim'}]{can_auto}[/{'green' if t.get('can_alii_execute') else 'dim'}]")
            )
            self._todo_ids.append(t.get("id"))

        crit = len([t for t in pending if t.get("priority") == "critical"])
        hi   = len([t for t in pending if t.get("priority") == "high"])
        self.query_one("#todos-summary", Static).update(
            f"[red]{crit} critical[/red]  [yellow]{hi} high[/yellow]  "
            f"[cyan]{len(pending)} total pending[/cyan]  [dim]{done_count} done[/dim]  "
            f"[green]{len([t for t in pending if t.get('can_alii_execute')])} Alii can auto-execute[/green]"
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        todos = load_todos()
        pending = sorted(
            [t for t in todos if t.get("status", "pending") == "pending"],
            key=todo_priority_rank
        )
        idx = event.cursor_row
        if idx < len(pending):
            t = pending[idx]
            steps = t.get("autonomous_steps", [])
            needs = t.get("needs_info", [])
            detail = f"[bold]{t.get('title')}[/bold]\n"
            detail += f"[dim]{t.get('description','No description')}[/dim]\n"
            if steps:
                detail += f"\n[cyan]Alii can execute:[/cyan]\n"
                for s in steps:
                    detail += f"  [dim]$[/dim] {s}\n"
            if needs:
                detail += f"\n[yellow]Needs info from Pierre:[/yellow]\n"
                for n in needs:
                    detail += f"  [dim]?[/dim] {n}\n"
            self.query_one("#todos-detail", Static).update(detail)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-todos-refresh":
            self._populate()
        elif event.button.id == "btn-todos-execute":
            self._execute_selected()
        elif event.button.id == "btn-todos-done":
            self._mark_done_selected()
        elif event.button.id == "btn-todos-autorun":
            self._autorun_all()
        elif event.button.id == "btn-todos-add":
            self._show_add_prompt()

    def _get_selected_todo(self) -> Optional[dict]:
        table = self.query_one("#todos-table", DataTable)
        idx = table.cursor_row
        if idx is None:
            return None
        todos = load_todos()
        pending = sorted(
            [t for t in todos if t.get("status", "pending") == "pending"],
            key=todo_priority_rank
        )
        if idx < len(pending):
            return pending[idx]
        return None

    @work(thread=True)
    def _execute_selected(self):
        log = self.query_one("#todos-exec-log", RichLog)
        t = self._get_selected_todo()
        if not t:
            log.write("[yellow]Select a todo row first.[/yellow]")
            return

        steps = t.get("autonomous_steps", [])
        if not steps:
            log.write(f"[yellow]Todo '{t.get('title')}' has no autonomous steps defined.[/yellow]")
            needs = t.get("needs_info", [])
            if needs:
                log.write("[cyan]Needs info:[/cyan]")
                for n in needs:
                    log.write(f"  ? {n}")
            return

        log.write(f"\n[bold cyan]⚡ Executing:[/bold cyan] {t.get('title')}")
        all_ok = True
        for step in steps:
            log.write(f"[dim]$ {step}[/dim]")
            try:
                result = subprocess.run(
                    step, shell=True, capture_output=True, text=True,
                    timeout=60, cwd=str(WORKDIR)
                )
                out = (result.stdout + result.stderr).strip()[:300]
                if result.returncode == 0:
                    log.write(f"[green]✓ {out or '(done)'}[/green]")
                else:
                    log.write(f"[red]✗ {out or 'failed'}[/red]")
                    all_ok = False
            except subprocess.TimeoutExpired:
                log.write("[red]✗ timed out[/red]")
                all_ok = False
            except Exception as e:
                log.write(f"[red]✗ {e}[/red]")
                all_ok = False

        if all_ok:
            mark_todo_done(t.get("id", ""))
            log.write(f"[bold green]✓ Marked done: {t.get('title')}[/bold green]")
            self._populate()
        else:
            log.write("[yellow]Some steps failed — todo NOT marked done. Review above.[/yellow]")

    @work(thread=True)
    def _autorun_all(self):
        log = self.query_one("#todos-exec-log", RichLog)
        todos = load_todos()
        pending = [t for t in todos if t.get("status", "pending") == "pending" and t.get("can_alii_execute") and t.get("autonomous_steps")]
        if not pending:
            log.write("[dim]No auto-executable todos with defined steps found.[/dim]")
            return

        log.write(f"\n[bold cyan]🤖 Auto-running {len(pending)} executable todos...[/bold cyan]")
        for t in pending:
            log.write(f"\n[cyan]→ {t.get('title')}[/cyan]")
            all_ok = True
            for step in t.get("autonomous_steps", []):
                log.write(f"[dim]$ {step}[/dim]")
                try:
                    r = subprocess.run(step, shell=True, capture_output=True, text=True, timeout=60, cwd=str(WORKDIR))
                    out = (r.stdout + r.stderr).strip()[:200]
                    if r.returncode == 0:
                        log.write(f"[green]✓ {out or '(done)'}[/green]")
                    else:
                        log.write(f"[red]✗ {out}[/red]")
                        all_ok = False
                except Exception as e:
                    log.write(f"[red]✗ {e}[/red]")
                    all_ok = False
            if all_ok:
                mark_todo_done(t.get("id", ""))
                log.write(f"[green]✓ Done[/green]")
        log.write("\n[bold green]Auto-run complete.[/bold green]")
        self._populate()

    def _mark_done_selected(self):
        t = self._get_selected_todo()
        if t:
            mark_todo_done(t.get("id", ""))
            self.app.notify(f"✓ Marked done: {t.get('title','?')[:50]}")
            self._populate()

    def _show_add_prompt(self):
        self.app.notify("Use /shell python3 agents/todo_agent.py add '<title>' in chat panel.")


# ══════════════════════════════════════════════════════════════════════════════
# ── Camera Panel ──────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class CameraPanel(Widget):
    """Live Jetson camera feed displayed as ASCII art."""

    def compose(self) -> ComposeResult:
        with Vertical(id="panel-camera"):
            with Horizontal():
                yield Static("[bold cyan]◈ CAMERA[/bold cyan]  [dim]Jetson front camera · Auto-refresh 30s[/dim]", id="cam-header")
                yield Static("", id="cam-status")
            yield Static("", id="cam-ascii", markup=False)
            yield Static("", id="cam-info")
            with Horizontal():
                yield Button("📸 Capture Now", id="btn-cam-snap", variant="primary")
                yield Button("💾 Save Snapshot", id="btn-cam-save")
                yield Button("📊 Camera Info", id="btn-cam-info")
                yield Button("🔄 Restart Service", id="btn-cam-restart")

    def on_mount(self):
        self._fetch_and_display()
        self.set_interval(30, self._fetch_and_display)

    @work(thread=True)
    def _fetch_and_display(self):
        status_w = self.query_one("#cam-status", Static)
        ascii_w  = self.query_one("#cam-ascii",  Static)
        info_w   = self.query_one("#cam-info",   Static)

        status_w.update("[yellow]fetching...[/yellow]")
        data, err = fetch_camera_snapshot()

        if err:
            status_w.update(f"[red]✗ {err}[/red]")
            ascii_w.update("[dim]Camera unavailable[/dim]")
            self.app._cam_ok = False
            return

        ts = datetime.now().strftime("%H:%M:%S")
        status_w.update(f"[green]✓ {len(data)//1024}KB · {ts}[/green]")
        self.app._cam_ok = True

        # Convert to ASCII
        art = jpeg_to_ascii(data, width=80, height=32)
        ascii_w.update(art)
        info_w.update(f"[dim]Jetson {JETSON_IP}:{CAM_PORT}  JPEG {len(data)} bytes  {ts}[/dim]")

        # Save latest snapshot
        snap_dir = WORKDIR / "snapshots"
        snap_dir.mkdir(exist_ok=True)
        snap_path = snap_dir / "jetson_latest.jpg"
        snap_path.write_bytes(data)

    @work(thread=True)
    def _save_snapshot(self):
        data, err = fetch_camera_snapshot()
        if err:
            self.app.notify(f"Camera error: {err}", severity="error")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = WORKDIR / "snapshots" / f"jetson_{ts}.jpg"
        path.mkdir = path.parent.mkdir
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        self.app.notify(f"Snapshot saved: snapshots/jetson_{ts}.jpg ({len(data)//1024}KB)")

    @work(thread=True)
    def _get_info(self):
        import urllib.request
        try:
            with urllib.request.urlopen(f"http://{JETSON_IP}:{CAM_PORT}/info", timeout=5) as r:
                info = json.loads(r.read())
                self.app.notify(f"Camera info:\n{json.dumps(info, indent=2)[:400]}")
        except Exception as e:
            self.app.notify(f"Info fetch failed: {e}", severity="warning")

    @work(thread=True)
    def _restart_service(self):
        result = subprocess.run(
            ["ssh", "-i", "/home/avalii/.ssh/id_rsa", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=no",
             f"avalii@{JETSON_IP}",
             "sudo systemctl restart alii-camera && sleep 3 && curl -s http://localhost:8765/health"],
            capture_output=True, text=True, timeout=20
        )
        if "ok" in result.stdout:
            self.app.notify("✓ Camera service restarted on Jetson")
            self._fetch_and_display()
        else:
            self.app.notify(f"Restart result: {result.stdout[:100]}", severity="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cam-snap":
            self._fetch_and_display()
        elif event.button.id == "btn-cam-save":
            self._save_snapshot()
        elif event.button.id == "btn-cam-info":
            self._get_info()
        elif event.button.id == "btn-cam-restart":
            self._restart_service()


# ══════════════════════════════════════════════════════════════════════════════
# ── Chat Panel ────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

# Tool detection patterns
_TOOL_CAMERA  = re.compile(r'\b(camera|snapshot|photo|picture|feed|see|view|look|watching)\b', re.I)
_TOOL_TODO    = re.compile(r'\b(todo|task|remind|pending|what.*need|what.*do|to.do)\b', re.I)
_TOOL_STATUS  = re.compile(r'\b(status|cluster|nodes|temp|temperature|service|health)\b', re.I)
_TOOL_SHELL   = re.compile(r'\b(run|execute|restart|start|stop|install|pull|git|systemctl|docker|pip)\b', re.I)
_TOOL_MEMORY  = re.compile(r'\b(remember|memory|history|what.*said|recall|forget)\b', re.I)


class ChatPanel(Widget):
    """
    Intelligent streaming chat panel.
    Detects intent → routes to Ollama/LiteLLM, tools, or Claude (/escalate).
    All memory stored in SQLite + Qdrant for persistent context.
    """

    DEFAULT_CSS = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="panel-chat"):
            yield RichLog(id="chat-log", wrap=True, highlight=False, markup=True)
            yield Static("", id="chat-model-indicator")
            with Horizontal(id="chat-input-bar"):
                yield Static("[bold cyan]alii ›[/bold cyan]", id="chat-prompt")
                yield Input(
                    placeholder="Ask anything... tool-aware routing. /shell /todos /camera /memory /escalate",
                    id="chat-input"
                )

    def on_mount(self):
        self.query_one("#chat-log", RichLog).write(ALII_BANNER)
        self.query_one("#chat-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value.strip()
        if not prompt:
            return
        event.input.value = ""
        self._handle_input(prompt)

    def _handle_input(self, prompt: str):
        log = self.query_one("#chat-log", RichLog)
        log.write(f"\n[bold cyan]You ›[/bold cyan] {prompt}")

        p = prompt.lower().strip()

        # Slash commands — direct
        if p == "/clear":
            log.clear()
            log.write(ALII_BANNER)
            return
        if p == "/status":
            self._show_status()
            return
        if p == "/memory":
            self._show_memory()
            return
        if p == "/agents":
            self._show_agents_list()
            return
        if p == "/todos":
            self._show_todos_summary()
            return
        if p == "/camera":
            self._show_camera_snap()
            return
        if p.startswith("/shell "):
            self._run_shell(prompt[7:].strip())
            return
        if p == "/help":
            self.app.show_panel("panel-help")
            return

        # Tool-aware routing — detect intent before hitting LLM
        if _TOOL_CAMERA.search(prompt) and not _TOOL_SHELL.search(prompt):
            log.write("[dim]  → tool: camera snapshot[/dim]")
            self._show_camera_snap()
            # Also answer via LLM
            self._stream_response(prompt)
            return

        if _TOOL_TODO.search(prompt) and len(prompt) < 100:
            self._show_todos_summary()
            return

        if _TOOL_STATUS.search(prompt) and len(prompt) < 80:
            self._show_status()
            return

        if _TOOL_MEMORY.search(prompt) and len(prompt) < 60:
            self._show_memory()
            return

        # Route to LLM
        self._stream_response(prompt)

    @work(exclusive=False)
    async def _stream_response(self, prompt: str):
        log  = self.query_one("#chat-log",             RichLog)
        ind  = self.query_one("#chat-model-indicator", Static)
        backend = get_backend()
        model, reason = classify_prompt(prompt)

        log.write(f"[dim]  → [cyan]{model}[/cyan] ({reason})[/dim]")
        ind.update(f"[dim]  model: {model} | {reason}[/dim]")
        log.write("[bold green]Alii ›[/bold green] ", end=False)

        try:
            full = []
            async for chunk in backend.stream(prompt):
                log.write(chunk, end=False, markup=False)
                full.append(chunk)
            log.write("")
            # Persist to SQLite memory
            self._save_to_memory(prompt, "".join(full), model)
        except Exception as e:
            log.write(f"\n[red]Error: {e}[/red]")
        finally:
            ind.update("")

    @work(thread=True)
    def _run_shell(self, cmd: str):
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[dim]$ {cmd}[/dim]")
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=60, cwd=str(WORKDIR)
            )
            out = result.stdout.strip()
            err = result.stderr.strip()
            if out:
                log.write(f"[green]{out}[/green]")
            if err:
                log.write(f"[yellow]{err}[/yellow]")
            if not out and not err:
                log.write("[dim](no output)[/dim]")
        except subprocess.TimeoutExpired:
            log.write("[red]Command timed out (60s)[/red]")
        except Exception as e:
            log.write(f"[red]Error: {e}[/red]")

    @work(thread=True)
    def _show_camera_snap(self):
        log = self.query_one("#chat-log", RichLog)
        log.write("\n[bold cyan]── Jetson Camera ──[/bold cyan]")
        data, err = fetch_camera_snapshot()
        if err:
            log.write(f"[red]Camera error: {err}[/red]")
            log.write(f"[dim]Service: http://{JETSON_IP}:{CAM_PORT}/snapshot[/dim]")
            return
        art = jpeg_to_ascii(data, width=72, height=22)
        ts = datetime.now().strftime("%H:%M:%S")
        log.write(f"[dim]{art}[/dim]")
        log.write(f"[dim]📷 {len(data)//1024}KB JPEG · {ts} · Panel [4] for full view[/dim]")

    def _show_status(self):
        log = self.query_one("#chat-log", RichLog)
        s = getattr(self.app, "_cluster_state", None)
        if not s:
            log.write("[dim]No cluster state yet. Wait for next poll.[/dim]")
            return
        log.write("\n[bold cyan]── System Status ──[/bold cyan]")
        log.write(f"[green]Precision:[/green] {s.precision.temp_c}°C  load {s.precision.load_1m}  "
                  f"RAM {s.precision.ram_used_gb}/{s.precision.ram_total_gb}GB")
        for name, node in s.nodes.items():
            status = f"[green]ONLINE[/green] {node.temp_c}°C L:{node.load_1m}" if node.online else "[red]OFFLINE[/red]"
            log.write(f"  {name.upper()}: {status}")
        log.write(f"Services: {s.services_up}/{s.services_total} up | Todos: {s.todo_count} pending")
        log.write(f"Ollama: {', '.join(s.ollama_models) or 'none'}")

    def _show_memory(self):
        log = self.query_one("#chat-log", RichLog)
        try:
            import sqlite3
            db = WORKDIR / "memory" / "alii_core.db"
            if db.exists():
                conn = sqlite3.connect(str(db))
                rows = conn.execute(
                    "SELECT role, substr(content,1,120), backend FROM episodic ORDER BY id DESC LIMIT 10"
                ).fetchall()
                conn.close()
                log.write("\n[bold cyan]── Recent Memory (last 10) ──[/bold cyan]")
                for role, content, backend in rows:
                    color = "cyan" if role == "user" else "green"
                    log.write(f"[{color}]{role}[/{color}] [{backend}]: {content}...")
            else:
                log.write("[dim]Memory DB not found — chat history not yet persisted[/dim]")
        except Exception as e:
            log.write(f"[red]Memory error: {e}[/red]")

    def _show_todos_summary(self):
        log = self.query_one("#chat-log", RichLog)
        todos = load_todos()
        pending = sorted(
            [t for t in todos if t.get("status", "pending") == "pending"],
            key=todo_priority_rank
        )
        log.write(f"\n[bold cyan]── Todos ({len(pending)} pending) ──[/bold cyan]")
        for t in pending[:15]:
            color = PRIORITY_COLORS.get(t.get("priority", "low"), "white")
            auto  = "[green]AUTO[/green]" if t.get("can_alii_execute") else "[dim]Pierre[/dim]"
            log.write(f"  [{color}]{t.get('priority','?').upper()[:4]}[/{color}] {auto}  {t.get('title','?')}")
        if len(pending) > 15:
            log.write(f"  [dim]... and {len(pending)-15} more. Press [0] for full view.[/dim]")

    def _show_agents_list(self):
        log = self.query_one("#chat-log", RichLog)
        agents = sorted(AGENTS_DIR.glob("*.py"))
        log.write("\n[bold cyan]── Available Agents ──[/bold cyan]")
        for a in agents:
            if not a.name.startswith("_"):
                log.write(f"  [cyan]{a.stem}[/cyan]")

    def _save_to_memory(self, user_msg: str, alii_msg: str, model: str):
        """Persist conversation to SQLite episodic memory."""
        try:
            import sqlite3
            db_path = WORKDIR / "memory" / "alii_core.db"
            db_path.parent.mkdir(exist_ok=True)
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodic (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT, role TEXT, content TEXT, backend TEXT
                )
            """)
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("INSERT INTO episodic (ts, role, content, backend) VALUES (?,?,?,?)",
                         (now, "user", user_msg, model))
            conn.execute("INSERT INTO episodic (ts, role, content, backend) VALUES (?,?,?,?)",
                         (now, "assistant", alii_msg, model))
            conn.commit()
            conn.close()
        except Exception:
            pass  # Memory failure is non-fatal


# ══════════════════════════════════════════════════════════════════════════════
# ── Agents Panel ──────────────────────────────────────════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

class AgentsPanel(Widget):
    """Shows all agents with status and control buttons."""

    def compose(self) -> ComposeResult:
        with Vertical(id="panel-agents"):
            yield Static("[bold cyan]◈ AGENTS[/bold cyan]  [dim]All Alii agents and their status[/dim]", id="agents-header")
            table = DataTable(id="agents-table")
            table.add_columns("Agent", "Status", "Size", "Description")
            yield table
            with Horizontal():
                yield Button("↻ Refresh", id="btn-agents-refresh", variant="primary")
                yield Button("▶ Run Overhaul Tasks", id="btn-run-overhaul")
                yield Button("📋 View Todos → [0]", id="btn-view-todos")

    def on_mount(self):
        self.set_timer(0.3, self._populate_agents)

    def _populate_agents(self):
        table = self.query_one("#agents-table", DataTable)
        table.clear()

        import socket
        service_ports = {
            "alfred": 7000, "litellm_proxy": 4000, "alii_core": 8000,
            "alii_ui": 8001, "visionclaw_bridge": 7030,
        }
        agents = sorted(AGENTS_DIR.glob("*.py"))
        descriptions = {
            "todo_agent":       "Task queue & manual action tracking",
            "account_agent":    "Platform account management (10 platforms)",
            "social_agent":     "Brand presence & content publishing",
            "ntfy_status":      "Cluster health + todo digest notifications",
            "ntfy_command_listener": "Two-way ntfy command bridge",
            "security_agent":   "Network intrusion detection",
            "money_agent":      "Revenue tracking & crypto monitoring",
            "business_agent":   "Business strategy & planning",
            "law_agent":        "Legal compliance & IP protection",
            "hardware_agent":   "Thermal management & fan control",
            "camera_agent":     "RTSP camera monitoring",
            "jetson_camera_agent": "Jetson edge camera (8765)",
            "imessage_bridge":  "macOS iMessage integration",
            "mac_controller":   "Remote macOS control via HTTP",
            "revenue_tracker":  "Multi-stream revenue monitoring",
            "email_agent":      "Email automation",
            "crypto_agent":     "Cryptocurrency portfolio",
            "media_agent":      "Media content management",
            "pr_agent":         "Pre-commit hook — blocks sensitive data",
            "visionclaw_bridge":"Ray-Ban vision → OpenClaw",
            "iphone_presence":  "iPhone location tracking",
            "macbook_presence": "MacBook presence detection",
        }

        for agent_path in agents:
            if agent_path.name.startswith("_"):
                continue
            name = agent_path.stem
            size = f"{agent_path.stat().st_size // 1024}KB"
            desc = descriptions.get(name, "—")
            try:
                result = subprocess.run(["pgrep", "-f", agent_path.name], capture_output=True, text=True)
                running = result.returncode == 0
            except Exception:
                running = False
            if name in service_ports:
                try:
                    with socket.create_connection(("127.0.0.1", service_ports[name]), timeout=0.5):
                        running = True
                except Exception:
                    pass
            status = "[green]● running[/green]" if running else "[dim]○ idle[/dim]"
            table.add_row(name, Text.from_markup(status), size, desc)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-agents-refresh":
            self._populate_agents()
        elif event.button.id == "btn-run-overhaul":
            self._run_overhaul()
        elif event.button.id == "btn-view-todos":
            self.app.show_panel("panel-todos")

    @work(thread=True)
    def _run_overhaul(self):
        script = WORKDIR / "scripts" / "alii_overhaul_tasks.py"
        if script.exists():
            subprocess.Popen([sys.executable, str(script)], cwd=str(WORKDIR))
            self.app.notify("Overhaul tasks started. Check ntfy for results.")
        else:
            self.app.notify("scripts/alii_overhaul_tasks.py not found", severity="error")


# ══════════════════════════════════════════════════════════════════════════════
# ── Cluster Panel ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class ClusterPanel(Widget):
    """Live cluster node stats table."""

    def compose(self) -> ComposeResult:
        with Vertical(id="panel-cluster"):
            yield Static("[bold cyan]◈ CLUSTER[/bold cyan]  [dim]All nodes — refreshes every 30s[/dim]", id="cluster-header")
            table = DataTable(id="cluster-table")
            table.add_columns("Node", "IP", "Status", "Temp", "Load", "RAM", "Key Services")
            yield table
            yield Static("", id="cluster-models")
            with Horizontal():
                yield Button("↻ Force Refresh", id="btn-cluster-refresh", variant="primary")
                yield Button("🔍 Run Diagnostics", id="btn-cluster-diag")
                yield Button("📦 Inventory", id="btn-cluster-inv")

    def on_mount(self):
        self.set_timer(0.3, self._update_from_state)
        self.set_interval(30, self._update_from_state)

    def _update_from_state(self):
        s = getattr(self.app, "_cluster_state", None)
        if not s:
            return
        self._render_cluster(s)

    def _render_cluster(self, s: ClusterState):
        table = self.query_one("#cluster-table", DataTable)
        table.clear()
        p = s.precision
        p_color  = p.temp_color
        p_status = Text.from_markup(f"[{p_color}]● ONLINE[/{p_color}]")
        p_temp   = Text.from_markup(f"[{p_color}]{p.temp_c}°C[/{p_color}]")
        p_load   = Text.from_markup(f"{'[yellow]' if p.load_pct > 70 else ''}{p.load_1m}{'[/yellow]' if p.load_pct > 70 else ''}")
        p_ram    = f"{p.ram_used_gb}/{p.ram_total_gb}GB"
        up_svcs  = [k for k, v in s.services.items() if v and k not in ("jetson-ollama",)][:4]
        p_svcs   = ", ".join(up_svcs) or "—"
        table.add_row("PRECISION (head)", "100.75.36.73", p_status, p_temp, p_load, p_ram, p_svcs)
        for name, node in s.nodes.items():
            if node.online:
                color  = node.temp_color
                status = Text.from_markup(f"[{color}]● ONLINE[/{color}]")
                temp   = Text.from_markup(f"[{color}]{node.temp_c}°C[/{color}]")
                load   = str(node.load_1m)
                ram    = f"{node.ram_used_mb}/{node.ram_total_mb}MB"
                svcs   = "cam:8765 tinyllama" if name == "jetson" else "ray-worker"
            else:
                status = Text.from_markup("[red]● OFFLINE[/red]")
                temp   = Text.from_markup("[dim]—[/dim]")
                load   = "—"; ram = "—"; svcs = "—"
            table.add_row(name.upper(), node.ip, status, temp, load, ram, svcs)

        models_str = "  ".join(f"[green]{m}[/green]" for m in s.ollama_models) if s.ollama_models else "[dim]none loaded[/dim]"
        self.query_one("#cluster-models", Static).update(
            f"\n[dim]Ollama:[/dim] {models_str}  [dim]│[/dim]  "
            f"[dim]Ray:[/dim] [cyan]{s.ray_nodes}[/cyan]  [dim]│[/dim]  "
            f"[dim]Svcs:[/dim] [{'green' if s.services_up == s.services_total else 'yellow'}]{s.services_up}/{s.services_total}[/{'green' if s.services_up == s.services_total else 'yellow'}]"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cluster-refresh":
            self.app.force_cluster_refresh()
        elif event.button.id == "btn-cluster-diag":
            self._run_diag()
        elif event.button.id == "btn-cluster-inv":
            self._show_inventory()

    @work(thread=True)
    def _run_diag(self):
        self.app.notify("Running cluster diagnostics...")
        result = subprocess.run(
            [sys.executable, str(WORKDIR / "cluster_scan.py")],
            capture_output=True, text=True, timeout=60, cwd=str(WORKDIR)
        )
        self.app.notify(f"Diagnostics:\n{(result.stdout + result.stderr)[:500]}")

    def _show_inventory(self):
        try:
            inv = json.loads((DATA_DIR / "system_inventory.json").read_text())
            self.app.notify(f"Inventory:\n{json.dumps(inv, indent=2)[:600]}")
        except Exception as e:
            self.app.notify(f"Inventory error: {e}", severity="warning")


# ══════════════════════════════════════════════════════════════════════════════
# ── Social Panel ──────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class SocialPanel(Widget):
    """MixPost integration + social agent status."""

    def compose(self) -> ComposeResult:
        with Vertical(id="panel-social"):
            yield Static("[bold cyan]◈ SOCIAL[/bold cyan]  [dim]MixPost · Content Engine · Account Manager[/dim]", id="social-header")
            yield Static(
                f"\n[bold]MixPost Admin:[/bold]  [link={MIXPOST_URL}][cyan]{MIXPOST_URL}[/cyan][/link]\n"
                f"[dim]Access from any Tailscale device (MacBook, iPhone, etc.)[/dim]\n",
                id="mixpost-url"
            )
            table = DataTable(id="social-table")
            table.add_columns("Platform", "Status", "Posts Scheduled", "Last Activity")
            yield table
            with Horizontal():
                yield Button("🌐 Open MixPost", id="btn-open-mixpost", variant="primary")
                yield Button("↻ Refresh", id="btn-social-refresh")
                yield Button("📊 Account Status", id="btn-acct-status")

    def on_mount(self):
        self.set_timer(0.5, self._populate_social)

    def _populate_social(self):
        table = self.query_one("#social-table", DataTable)
        table.clear()
        platforms = ["Twitter/X", "LinkedIn", "Reddit", "GitHub", "Ko-fi",
                     "Gumroad", "ProductHunt", "Dev.to", "MixPost"]
        try:
            reg_file = DATA_DIR / "accounts_registry.json"
            if reg_file.exists():
                registry = json.loads(reg_file.read_text())
                for p, info in registry.items():
                    status = "[green]active[/green]" if info.get("active") else "[dim]inactive[/dim]"
                    table.add_row(p, Text.from_markup(status), str(info.get("scheduled_posts", 0)), info.get("last_activity", "—")[:20])
                return
        except Exception:
            pass
        for p in platforms:
            table.add_row(p, Text.from_markup("[dim]—[/dim]"), "—", "—")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-open-mixpost":
            subprocess.Popen(["xdg-open", MIXPOST_URL])
            self.app.notify(f"Opening MixPost: {MIXPOST_URL}")
        elif event.button.id == "btn-social-refresh":
            self._populate_social()
        elif event.button.id == "btn-acct-status":
            self._show_account_status()

    def _show_account_status(self):
        try:
            log_file = LOGS_DIR / "accounts_status.log"
            if log_file.exists():
                self.app.notify("\n".join(log_file.read_text().splitlines()[-10:]))
            else:
                self.app.notify("No account status log found.")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="warning")


# ══════════════════════════════════════════════════════════════════════════════
# ── Systems Panel ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class SystemsPanel(Widget):
    """System information via tabbed panels."""

    def compose(self) -> ComposeResult:
        with Vertical(id="panel-systems"):
            with TabbedContent():
                with TabPane("💾 Disk", id="tab-disk"):
                    yield RichLog(id="log-disk", wrap=False, markup=True)
                    yield Button("↻ Refresh", id="btn-disk-refresh")
                with TabPane("🐳 Docker", id="tab-docker"):
                    yield RichLog(id="log-docker", wrap=False, markup=True)
                    yield Button("↻ Refresh", id="btn-docker-refresh")
                with TabPane("🤖 Ollama", id="tab-ollama"):
                    yield RichLog(id="log-ollama", wrap=False, markup=True)
                    yield Button("↻ Refresh", id="btn-ollama-refresh")
                with TabPane("⚡ Ray", id="tab-ray"):
                    yield RichLog(id="log-ray", wrap=False, markup=True)
                    yield Button("↻ Refresh", id="btn-ray-refresh")
                with TabPane("📋 Logs", id="tab-logs"):
                    yield RichLog(id="log-recent", wrap=True, markup=True)
                    yield Button("↻ Refresh", id="btn-logs-refresh")

    def on_mount(self):
        self.set_timer(0.5, self._load_all)

    def _load_all(self):
        self._load_disk()
        self._load_docker()
        self._load_ollama()
        self._load_ray()
        self._load_logs()

    @work(thread=True)
    def _load_disk(self):
        out = subprocess.run(["df", "-h"], capture_output=True, text=True, timeout=5).stdout
        log = self.query_one("#log-disk", RichLog)
        log.clear()
        log.write("[bold cyan]Disk Usage[/bold cyan]\n")
        for line in out.splitlines():
            if "Use%" in line or any(m in line for m in ["/mnt/", "/dev/", "tmpfs"]):
                log.write(line)
        lvm = subprocess.run(["sudo", "-n", "lvs", "--noheadings", "-o", "lv_name,vg_name,lv_size"],
                              capture_output=True, text=True, timeout=5).stdout
        if lvm.strip():
            log.write("\n[bold cyan]LVM Volumes[/bold cyan]")
            for l in lvm.strip().splitlines():
                log.write(l.strip())

    @work(thread=True)
    def _load_docker(self):
        out = subprocess.run(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"],
                              capture_output=True, text=True, timeout=10).stdout
        log = self.query_one("#log-docker", RichLog)
        log.clear()
        log.write("[bold cyan]Docker Containers[/bold cyan]\n")
        for line in out.splitlines():
            color = "green" if "Up" in line and "Names" not in line else ("cyan" if "Names" in line else "dim")
            log.write(f"[{color}]{line}[/{color}]")

    @work(thread=True)
    def _load_ollama(self):
        import urllib.request
        log = self.query_one("#log-ollama", RichLog)
        log.clear()
        log.write("[bold cyan]Ollama Models[/bold cyan]\n")
        try:
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
                data = json.loads(r.read())
                for m in data.get("models", []):
                    name   = m.get("name", "?")
                    size   = f"{m.get('size', 0) // (1024**3):.1f}GB"
                    digest = m.get("digest", "")[:12]
                    log.write(f"[green]{name:<40}[/green]  {size}  [dim]{digest}[/dim]")
        except Exception as e:
            log.write(f"[red]Ollama unreachable: {e}[/red]")
        try:
            with urllib.request.urlopen("http://localhost:11434/api/ps", timeout=5) as r:
                data = json.loads(r.read())
                running = data.get("models", [])
                if running:
                    log.write("\n[bold cyan]Currently Loaded in Memory[/bold cyan]")
                    for m in running:
                        log.write(f"  [cyan]{m.get('name','?')}[/cyan]  expires: {m.get('expires_at','?')[:19]}")
        except Exception:
            pass

    @work(thread=True)
    def _load_ray(self):
        log = self.query_one("#log-ray", RichLog)
        log.clear()
        ray_bin = Path("/home/avalii/.venv/ray/bin/ray")
        if not ray_bin.exists():
            log.write("[dim]Ray binary not found at ~/.venv/ray/bin/ray[/dim]")
            return
        out = subprocess.run([str(ray_bin), "status"], capture_output=True, text=True, timeout=15).stdout
        log.write("[bold cyan]Ray Cluster Status[/bold cyan]\n")
        log.write(out or "[dim](no output)[/dim]")

    @work(thread=True)
    def _load_logs(self):
        log = self.query_one("#log-recent", RichLog)
        log.clear()
        log.write("[bold cyan]Recent Log Activity[/bold cyan]\n")
        for log_name in ["alfred.log", "ntfy_status.log", "litellm.log", "todo_agent.log", "jetson_camera.log"]:
            path = LOGS_DIR / log_name
            if path.exists():
                lines = path.read_text().splitlines()[-8:]
                log.write(f"\n[cyan]── {log_name} ──[/cyan]")
                for l in lines:
                    log.write(f"[dim]{l}[/dim]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_map = {
            "btn-disk-refresh":   self._load_disk,
            "btn-docker-refresh": self._load_docker,
            "btn-ollama-refresh": self._load_ollama,
            "btn-ray-refresh":    self._load_ray,
            "btn-logs-refresh":   self._load_logs,
        }
        handler = btn_map.get(event.button.id)
        if handler:
            handler()


# ══════════════════════════════════════════════════════════════════════════════
# ── Config Panel ──────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class ConfigPanel(Widget):
    """Edit key .env settings and view configuration."""

    def compose(self) -> ComposeResult:
        with Vertical(id="panel-config"):
            yield Static("[bold cyan]◈ CONFIGURATION[/bold cyan]  [dim]Edit .env settings (saves immediately on button press)[/dim]", id="config-header")
            yield Static("[dim]─────────────────────────────────────[/dim]")
            yield Static("\n[bold]LiteLLM API Key[/bold]")
            yield Input(placeholder="LITELLM_MASTER_KEY value...", id="cfg-litellm-key", password=True)
            yield Static("\n[bold]Anthropic API Key[/bold] [dim](for /escalate only)[/dim]")
            yield Input(placeholder="ANTHROPIC_API_KEY value...", id="cfg-anthropic-key", password=True)
            yield Static("\n[bold]Groq API Key[/bold] [dim](free fast inference — llama-3.3-70b)[/dim]")
            yield Input(placeholder="GROQ_API_KEY value...", id="cfg-groq-key", password=True)
            yield Static("\n[bold]ntfy Topic[/bold]")
            yield Input(placeholder="alii-precision", id="cfg-ntfy-topic")
            yield Static("\n[bold]Default Model Tier[/bold] [dim](fast/smart/code/heavy)[/dim]")
            yield Input(placeholder="smart", id="cfg-default-model")
            yield Static("")
            with Horizontal():
                yield Button("💾 Save Config", id="btn-cfg-save", variant="primary")
                yield Button("📋 Show Current .env", id="btn-cfg-show")
                yield Button("🔄 Restart LiteLLM", id="btn-cfg-restart-litellm")
                yield Button("🔄 Restart ntfy", id="btn-cfg-restart-ntfy")
            yield Static("", id="cfg-status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cfg-save":
            self._save_config()
        elif event.button.id == "btn-cfg-show":
            self._show_env()
        elif event.button.id == "btn-cfg-restart-litellm":
            self._restart_service("alii-router")
        elif event.button.id == "btn-cfg-restart-ntfy":
            self._restart_service("alii-ntfy-status")

    def _save_config(self):
        updates = {}
        for field_id, env_key in [
            ("cfg-ntfy-topic",    "NTFY_TOPIC"),
            ("cfg-default-model", "DEFAULT_MODEL_TIER"),
        ]:
            val = self.query_one(f"#{field_id}", Input).value.strip()
            if val:
                updates[env_key] = val
        for field_id, env_key in [
            ("cfg-litellm-key",   "LITELLM_MASTER_KEY"),
            ("cfg-anthropic-key", "ANTHROPIC_API_KEY"),
            ("cfg-groq-key",      "GROQ_API_KEY"),
        ]:
            val = self.query_one(f"#{field_id}", Input).value.strip()
            if val:
                updates[env_key] = val
        if not updates:
            self.query_one("#cfg-status", Static).update("[dim]No changes to save.[/dim]")
            return
        self._apply_env_updates(updates)
        self.query_one("#cfg-status", Static).update(f"[green]✓ Saved: {', '.join(updates.keys())}[/green]")
        self.app.notify(f"Config saved: {', '.join(updates.keys())}")

    @work(thread=True)
    def _apply_env_updates(self, updates: dict):
        if not ENV_FILE.exists():
            return
        content = ENV_FILE.read_text()
        for key, val in updates.items():
            pattern = re.compile(rf'^{re.escape(key)}=.*$', re.MULTILINE)
            if pattern.search(content):
                content = pattern.sub(f"{key}={val}", content)
            else:
                content += f"\n{key}={val}\n"
        ENV_FILE.write_text(content)

    def _show_env(self):
        try:
            lines = ENV_FILE.read_text().splitlines()
            safe_lines = []
            for l in lines:
                if "=" in l:
                    k, _, v = l.partition("=")
                    if any(w in k.upper() for w in ["KEY", "SECRET", "PASSWORD", "TOKEN", "PRIVATE"]):
                        safe_lines.append(f"{k}=[dim]**redacted**[/dim]")
                    else:
                        safe_lines.append(l)
                else:
                    safe_lines.append(l)
            self.app.notify("\n".join(safe_lines[:30]))
        except Exception as e:
            self.app.notify(f"Error reading .env: {e}", severity="warning")

    @work(thread=True)
    def _restart_service(self, service: str):
        result = subprocess.run(
            ["sudo", "-n", "systemctl", "restart", service],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            self.app.notify(f"✓ {service} restarted")
        else:
            self.app.notify(f"Failed to restart {service}: {result.stderr[:100]}", severity="error")


# ══════════════════════════════════════════════════════════════════════════════
# ── Help Panel ────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class HelpPanel(Widget):
    """Built-in instruction manual."""

    def compose(self) -> ComposeResult:
        with Vertical(id="panel-help"):
            yield RichLog(id="help-log", wrap=True, markup=True)

    def on_mount(self):
        log = self.query_one("#help-log", RichLog)
        manual_path = WORKDIR / "docs" / "ALII_MANUAL.md"
        if manual_path.exists():
            content = manual_path.read_text()
            for line in content.splitlines():
                if line.startswith("# "):
                    log.write(f"\n[bold cyan]{line[2:]}[/bold cyan]")
                elif line.startswith("## "):
                    log.write(f"\n[bold]{line[3:]}[/bold]")
                elif line.startswith("### "):
                    log.write(f"\n[cyan]{line[4:]}[/cyan]")
                elif line.startswith("- ") or line.startswith("* "):
                    log.write(f"  [dim]•[/dim] {line[2:]}")
                elif line.startswith("```"):
                    pass
                else:
                    log.write(line)
        else:
            log.write("[bold cyan]◈ ALII MANUAL[/bold cyan]\n")
            log.write("Panels: [0]=Todos [1]=Chat [2]=Agents [3]=Cluster [4]=Camera [5]=Social [6]=Systems [7]=Config [8]=Help")
            log.write("\nChat commands: /shell /status /todos /camera /memory /agents /clear /escalate")
            log.write("Keyboard: 0-8 panels | R=refresh | Q=quit")


# ══════════════════════════════════════════════════════════════════════════════
# ── Main App ──────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class AliiApp(App):
    """Alii Unified Terminal Hub v3.0"""

    CSS_PATH = str(WORKDIR / "alii_tui.tcss")
    TITLE    = "Alii — Sovereign AI v3.0"
    BINDINGS = [
        ("0", "show_todos",   "Todos"),
        ("1", "show_chat",    "Chat"),
        ("2", "show_agents",  "Agents"),
        ("3", "show_cluster", "Cluster"),
        ("4", "show_camera",  "Camera"),
        ("5", "show_social",  "Social"),
        ("6", "show_systems", "Systems"),
        ("7", "show_config",  "Config"),
        ("8", "show_help",    "Help"),
        ("q", "quit",         "Quit"),
        ("r", "refresh",      "Refresh"),
        ("?", "show_help",    "Help"),
    ]

    _cluster_state: Optional[ClusterState] = None
    _current_panel: str = "panel-todos"
    _poller: Optional[ClusterPoller] = None
    _cam_ok: bool = False

    def compose(self) -> ComposeResult:
        yield AliiHeader()
        with Horizontal(id="main-layout"):
            yield AliiMenu()
            with ContentSwitcher(id="content-area", initial="panel-todos"):
                yield TodosPanel(id="panel-todos")
                yield ChatPanel(id="panel-chat")
                yield AgentsPanel(id="panel-agents")
                yield ClusterPanel(id="panel-cluster")
                yield CameraPanel(id="panel-camera")
                yield SocialPanel(id="panel-social")
                yield SystemsPanel(id="panel-systems")
                yield ConfigPanel(id="panel-config")
                yield HelpPanel(id="panel-help")
        yield Static("", id="status-bar")

    async def on_mount(self):
        self._poller = ClusterPoller(interval=30.0)
        await self._poller.start()
        self.set_interval(10, self._update_header)
        self._set_status("Alii v3.0 — Cluster scan in progress... Press 0 for Todos, 1 for Chat, 4 for Camera")

    async def _update_header(self):
        if self._poller:
            state = await self._poller.get_state()
            self._cluster_state = state
            self.query_one(AliiHeader).update_state(state)
            if self._current_panel == "panel-cluster":
                self.query_one(ClusterPanel)._render_cluster(state)
        self._set_status(
            f"Last refresh: {datetime.now().strftime('%H:%M:%S')}  |  "
            f"0=Todos 1=Chat 2=Agents 3=Cluster 4=Camera 5=Social 6=Sys 7=Config 8=Help  |  R=refresh Q=quit"
        )

    def force_cluster_refresh(self):
        self._set_status("Forcing cluster refresh...")
        asyncio.create_task(self._do_force_refresh())

    async def _do_force_refresh(self):
        if self._poller:
            state = await self._poller.force_refresh()
            self._cluster_state = state
            self.query_one(AliiHeader).update_state(state)
            if self._current_panel == "panel-cluster":
                self.query_one(ClusterPanel)._render_cluster(state)
        self._set_status("Cluster refreshed.")

    def _set_status(self, msg: str):
        try:
            self.query_one("#status-bar", Static).update(f"[dim]{msg}[/dim]")
        except Exception:
            pass

    def show_panel(self, panel_id: str):
        self._current_panel = panel_id
        self.query_one(ContentSwitcher).current = panel_id
        menu_lv = self.query_one(AliiMenu).query_one(ListView)
        for i, (_, pid) in enumerate(MENU_ITEMS):
            if pid == panel_id:
                menu_lv.index = i
                break

    # ── Key actions ────────────────────────────────────────────────────────────
    def action_show_todos(self):   self.show_panel("panel-todos")
    def action_show_chat(self):    self.show_panel("panel-chat")
    def action_show_agents(self):  self.show_panel("panel-agents")
    def action_show_cluster(self): self.show_panel("panel-cluster")
    def action_show_camera(self):  self.show_panel("panel-camera")
    def action_show_social(self):  self.show_panel("panel-social")
    def action_show_systems(self): self.show_panel("panel-systems")
    def action_show_config(self):  self.show_panel("panel-config")
    def action_show_help(self):    self.show_panel("panel-help")
    def action_refresh(self):      self.force_cluster_refresh()

    def on_alii_menu_selected(self, event: AliiMenu.Selected) -> None:
        self.show_panel(event.panel_id)

    async def on_unmount(self):
        if self._poller:
            await self._poller.stop()


# ══════════════════════════════════════════════════════════════════════════════
# ── Entry point ───────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def main():
    app = AliiApp()
    app.run()

if __name__ == "__main__":
    main()
