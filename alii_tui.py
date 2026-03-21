#!/usr/bin/env python3
"""
alii_tui.py — Unified Alii Terminal Hub

The single entry point for all things Alii.
Type "alii" from Precision or MacBook to launch.

Panels:
  [1] Chat / AI  — streaming chat to LiteLLM/Ollama (Ollama-first, zero Claude tokens)
  [2] Agents     — all agent status, start/stop/restart
  [3] Cluster    — live node stats for all 4 nodes
  [4] Social     — MixPost queue + social agent status
  [5] Systems    — disk, docker, ollama models, ray, logs
  [6] Config     — edit .env settings, model tiers
  [7] Help       — full instruction manual

Author: Alii / Pierre Cabell
"""

from __future__ import annotations
import asyncio, json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Ensure venv is active ──────────────────────────────────────────────────────
WORKDIR = Path("/home/avalii/moltbot")
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
MIXPOST_URL = "http://100.75.36.73:9101"

PANEL_IDS = ["panel-chat", "panel-agents", "panel-cluster",
             "panel-social", "panel-systems", "panel-config", "panel-help"]

MENU_ITEMS = [
    ("[1] Chat / AI",     "panel-chat"),
    ("[2] Agents",        "panel-agents"),
    ("[3] Cluster",       "panel-cluster"),
    ("[4] Social",        "panel-social"),
    ("[5] Systems",       "panel-systems"),
    ("[6] Config",        "panel-config"),
    ("[7] Help / Manual", "panel-help"),
]

ALII_BANNER = """[bold cyan]
  ╔═══════════════════════════════════════╗
  ║    ◈  A L I I  —  Sovereign AI  ◈    ║
  ║    Precision Cluster · Akron, OH      ║
  ╚═══════════════════════════════════════╝[/bold cyan]
[dim]  Routing: Ollama-first · Claude: /escalate only[/dim]
[dim]  Type your message below. Commands: /shell /memory /agents /status /clear[/dim]
"""


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
        # Do first refresh asap
        self.set_timer(0.5, self._refresh_header)

    def update_state(self, state: ClusterState):
        self._state = state
        self._render_header()

    def _refresh_header(self):
        # Get state from app poller
        app = self.app
        if hasattr(app, "_cluster_state") and app._cluster_state:
            self._state = app._cluster_state
        self._render_header()

    def _render_header(self):
        s = self._state
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if s is None:
            self.query_one("#header-line1", Static).update(
                f"[bold cyan]◈ ALII[/bold cyan]  [dim]initializing cluster scan...[/dim]  [dim]{now}[/dim]"
            )
            return

        p = s.precision

        # Node status
        def node_badge(name: str) -> str:
            node = s.nodes.get(name)
            if not node:
                return f"[dim]●{name.upper()}?[/dim]"
            if not node.online:
                return f"[red]●{name.upper()}:OFF[/red]"
            color = node.temp_color
            return f"[{color}]●{name.upper()}:{node.temp_c:.0f}°[/{color}]"

        # Precision badge
        p_color = p.temp_color
        prec_badge = (
            f"[bold {p_color}]●PRECISION:{p.temp_c:.0f}°C[/bold {p_color}]"
            f"[dim] L:{p.load_1m} RAM:{p.ram_used_gb}/{p.ram_total_gb}G[/dim]"
        )

        nodes_str = "  ".join(node_badge(n) for n in ["xps", "nuc", "jetson"])

        # Models
        models = s.ollama_models[:4]
        models_str = " ".join(f"[green]{m}✓[/green]" for m in models) if models else "[dim]none[/dim]"

        # Services
        svc_color = "green" if s.services_up == s.services_total else "yellow"
        svc_str = f"[{svc_color}]{s.services_up}/{s.services_total}✓[/{svc_color}]"

        # Todos
        todo_color = "yellow" if s.todo_count > 0 else "dim"
        todo_str = f"[{todo_color}]{s.todo_count} todo{'s' if s.todo_count != 1 else ''}[/{todo_color}]"

        self.query_one("#header-line1", Static).update(
            f"[bold cyan]◈ ALII[/bold cyan]  {prec_badge}  {nodes_str}"
        )
        self.query_one("#header-line2", Static).update(
            f"[dim]Models:[/dim] {models_str}  [dim]│[/dim]  [dim]Claude: /escalate only[/dim]  [dim]│[/dim]  [dim]LiteLLM/Ollama: default[/dim]"
        )
        self.query_one("#header-line3", Static).update(
            f"[dim]Services:[/dim] {svc_str}  [dim]│[/dim]  {todo_str}  [dim]│[/dim]  [dim]{now}[/dim]"
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
        yield Static("  [dim][Q] Quit[/dim]")
        yield Static("  [dim][R] Refresh[/dim]")
        yield Static("  [dim][?] Help[/dim]")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.id:
            panel_id = event.item.id.replace("menu-", "")
            self.post_message(self.Selected(panel_id))


# ══════════════════════════════════════════════════════════════════════════════
# ── Chat Panel ────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class ChatPanel(Widget):
    """Streaming chat panel — routes to LiteLLM/Ollama."""

    DEFAULT_CSS = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="panel-chat"):
            yield RichLog(id="chat-log", wrap=True, highlight=False, markup=True)
            with Horizontal(id="chat-input-bar"):
                yield Static("[bold cyan]alii ›[/bold cyan]", id="chat-prompt")
                yield Input(placeholder="Type a message... (/shell /memory /agents /status /clear /escalate)", id="chat-input")

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

        # Built-in slash commands
        if prompt.lower() == "/clear":
            log.clear()
            log.write(ALII_BANNER)
            return

        if prompt.lower() == "/status":
            self._show_status()
            return

        if prompt.lower() == "/memory":
            self._show_memory()
            return

        if prompt.lower() == "/agents":
            self._show_agents_list()
            return

        if prompt.lower().startswith("/shell "):
            cmd = prompt[7:].strip()
            self._run_shell(cmd)
            return

        if prompt.lower() == "/help":
            self.app.show_panel("panel-help")
            return

        # Route to LLM
        self._stream_response(prompt)

    @work(exclusive=False)
    async def _stream_response(self, prompt: str):
        log = self.query_one("#chat-log", RichLog)
        backend = get_backend()
        model, reason = classify_prompt(prompt)

        log.write(f"[dim]  → routing to [cyan]{model}[/cyan] ({reason})[/dim]")
        log.write("[bold green]Alii ›[/bold green] ", end=False)

        try:
            full = []
            async for chunk in backend.stream(prompt):
                log.write(chunk, end=False, markup=False)
                full.append(chunk)
            log.write("")  # newline after stream ends
        except Exception as e:
            log.write(f"\n[red]Error: {e}[/red]")

    @work(thread=True)
    def _run_shell(self, cmd: str):
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[dim]$ {cmd}[/dim]")
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=30, cwd=str(WORKDIR)
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
            log.write("[red]Command timed out (30s)[/red]")
        except Exception as e:
            log.write(f"[red]Error: {e}[/red]")

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
        log.write(f"Services: {s.services_up}/{s.services_total} up")
        log.write(f"Todos: {s.todo_count} pending")
        log.write(f"Ollama models: {', '.join(s.ollama_models) or 'none'}")

    def _show_memory(self):
        log = self.query_one("#chat-log", RichLog)
        try:
            import sqlite3
            db = WORKDIR / "memory" / "alii_core.db"
            if db.exists():
                conn = sqlite3.connect(str(db))
                rows = conn.execute(
                    "SELECT role, substr(content,1,120), backend FROM episodic ORDER BY id DESC LIMIT 8"
                ).fetchall()
                conn.close()
                log.write("\n[bold cyan]── Recent Memory (last 8) ──[/bold cyan]")
                for role, content, backend in rows:
                    color = "cyan" if role == "user" else "green"
                    log.write(f"[{color}]{role}[/{color}] [{backend}]: {content}...")
            else:
                log.write("[dim]Memory DB not found[/dim]")
        except Exception as e:
            log.write(f"[red]Memory error: {e}[/red]")

    def _show_agents_list(self):
        log = self.query_one("#chat-log", RichLog)
        agents = sorted(AGENTS_DIR.glob("*.py"))
        log.write("\n[bold cyan]── Available Agents ──[/bold cyan]")
        for a in agents:
            if not a.name.startswith("_"):
                log.write(f"  [cyan]{a.stem}[/cyan]")


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
                yield Button("📋 View Todos", id="btn-view-todos")

    def on_mount(self):
        self.set_timer(0.3, self._populate_agents)

    def _populate_agents(self):
        table = self.query_one("#agents-table", DataTable)
        table.clear()

        # Port-based service detection
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
            "ntfy_status":      "Cluster health notifications",
            "ntfy_command_listener": "Two-way ntfy command bridge",
            "security_agent":   "Network intrusion detection",
            "money_agent":      "Revenue tracking & crypto monitoring",
            "business_agent":   "Business strategy & planning",
            "law_agent":        "Legal compliance & IP protection",
            "hardware_agent":   "Thermal management & fan control",
            "camera_agent":     "RTSP camera monitoring",
            "imessage_bridge":  "macOS iMessage integration",
            "mac_controller":   "Remote macOS control via HTTP",
            "revenue_tracker":  "Multi-stream revenue monitoring",
            "email_agent":      "Email automation",
            "crypto_agent":     "Cryptocurrency portfolio",
            "media_agent":      "Media content management",
            "pr_agent":         "Pull request automation",
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

            # Check if there's a running process for this agent
            try:
                result = subprocess.run(
                    ["pgrep", "-f", agent_path.name],
                    capture_output=True, text=True
                )
                running = result.returncode == 0
            except Exception:
                running = False

            # Check service ports
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
            self._show_todos()

    @work(thread=True)
    def _run_overhaul(self):
        script = WORKDIR / "scripts" / "alii_overhaul_tasks.py"
        if script.exists():
            subprocess.Popen(
                [sys.executable, str(script)],
                cwd=str(WORKDIR)
            )
            self.app.notify("Overhaul tasks started. Check ntfy for results.")
        else:
            self.app.notify("scripts/alii_overhaul_tasks.py not found", severity="error")

    def _show_todos(self):
        try:
            data = json.loads((DATA_DIR / "owner_todos.json").read_text())
            todos = data if isinstance(data, list) else data.get("todos", [])
            pending = [t for t in todos if t.get("status", "pending") == "pending"]
            if pending:
                lines = "\n".join(
                    f"[{t.get('priority','?')}] {t.get('title','?')}"
                    for t in pending[:15]
                )
                self.app.notify(f"{len(pending)} pending todos:\n{lines[:300]}")
            else:
                self.app.notify("No pending todos!")
        except Exception as e:
            self.app.notify(f"Could not load todos: {e}", severity="warning")


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
        p_color = p.temp_color
        p_status = Text.from_markup(f"[{p_color}]● ONLINE[/{p_color}]")
        p_temp   = Text.from_markup(f"[{p_color}]{p.temp_c}°C[/{p_color}]")
        p_load   = Text.from_markup(f"{'[yellow]' if p.load_pct > 70 else ''}{p.load_1m}{'[/yellow]' if p.load_pct > 70 else ''}")
        p_ram    = f"{p.ram_used_gb}/{p.ram_total_gb}GB"

        # Key services summary
        up_svcs = [k for k, v in s.services.items() if v and k not in ("jetson-ollama",)][:4]
        p_svcs  = ", ".join(up_svcs) or "—"

        table.add_row("PRECISION (head)", "100.75.36.73", p_status, p_temp, p_load, p_ram, p_svcs)

        for name, node in s.nodes.items():
            if node.online:
                color = node.temp_color
                status = Text.from_markup(f"[{color}]● ONLINE[/{color}]")
                temp   = Text.from_markup(f"[{color}]{node.temp_c}°C[/{color}]")
                load   = str(node.load_1m)
                ram    = f"{node.ram_used_mb}/{node.ram_total_mb}MB"
                svcs   = "tinyllama" if name == "jetson" else "ray-worker"
            else:
                status = Text.from_markup("[red]● OFFLINE[/red]")
                temp   = Text.from_markup("[dim]—[/dim]")
                load   = "—"
                ram    = "—"
                svcs   = "—"
            table.add_row(name.upper(), node.ip, status, temp, load, ram, svcs)

        # Models info
        models_str = "  ".join(f"[green]{m}[/green]" for m in s.ollama_models) if s.ollama_models else "[dim]none loaded[/dim]"
        self.query_one("#cluster-models", Static).update(
            f"\n[dim]Ollama models on Precision:[/dim] {models_str}\n"
            f"[dim]Ray nodes:[/dim] [cyan]{s.ray_nodes}[/cyan]  "
            f"[dim]Services:[/dim] [{'green' if s.services_up == s.services_total else 'yellow'}]{s.services_up}/{s.services_total}[/{'green' if s.services_up == s.services_total else 'yellow'}]"
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
        out = (result.stdout + result.stderr)[:500]
        self.app.notify(f"Diagnostics:\n{out}")

    def _show_inventory(self):
        try:
            inv = json.loads((DATA_DIR / "system_inventory.json").read_text())
            summary = json.dumps(inv, indent=2)[:600]
            self.app.notify(f"Inventory:\n{summary}")
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
                f"[dim]Access this URL from any device on Tailscale (MacBook, iPhone, etc.)[/dim]\n",
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

        # Read accounts registry if available
        platforms = ["Twitter/X", "LinkedIn", "Reddit", "GitHub", "Ko-fi",
                     "Gumroad", "ProductHunt", "Dev.to", "MixPost"]
        try:
            reg_file = DATA_DIR / "accounts_registry.json"
            if reg_file.exists():
                registry = json.loads(reg_file.read_text())
                for p, info in registry.items():
                    status = "[green]active[/green]" if info.get("active") else "[dim]inactive[/dim]"
                    posts  = str(info.get("scheduled_posts", 0))
                    last   = info.get("last_activity", "—")[:20]
                    table.add_row(p, Text.from_markup(status), posts, last)
                return
        except Exception:
            pass

        # Fallback: just list known platforms
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
                lines = log_file.read_text().splitlines()[-10:]
                self.app.notify("\n".join(lines))
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
                    yield Button("↻ Refresh Disk", id="btn-disk-refresh")
                with TabPane("🐳 Docker", id="tab-docker"):
                    yield RichLog(id="log-docker", wrap=False, markup=True)
                    yield Button("↻ Refresh Docker", id="btn-docker-refresh")
                with TabPane("🤖 Ollama", id="tab-ollama"):
                    yield RichLog(id="log-ollama", wrap=False, markup=True)
                    yield Button("↻ Refresh Ollama", id="btn-ollama-refresh")
                with TabPane("⚡ Ray", id="tab-ray"):
                    yield RichLog(id="log-ray", wrap=False, markup=True)
                    yield Button("↻ Refresh Ray", id="btn-ray-refresh")
                with TabPane("📋 Logs", id="tab-logs"):
                    yield RichLog(id="log-recent", wrap=True, markup=True)
                    yield Button("↻ Refresh Logs", id="btn-logs-refresh")

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

        # LVM info
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

        # Running models
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
        log.write("[bold cyan]Recent Log Activity (last 20 lines per key log)[/bold cyan]\n")
        for log_name in ["alfred.log", "ntfy_status.log", "litellm.log", "todo_agent.log"]:
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
            yield Static("\n[bold]ntfy Topic[/bold]")
            yield Input(placeholder="alii-precision", id="cfg-ntfy-topic")
            yield Static("\n[bold]Default Model Tier[/bold] [dim](fast/smart/code/heavy)[/dim]")
            yield Input(placeholder="smart", id="cfg-default-model")
            yield Static("")
            with Horizontal():
                yield Button("💾 Save Config", id="btn-cfg-save", variant="primary")
                yield Button("📋 Show Current .env", id="btn-cfg-show")
                yield Button("🔄 Restart LiteLLM", id="btn-cfg-restart-litellm")
            yield Static("", id="cfg-status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cfg-save":
            self._save_config()
        elif event.button.id == "btn-cfg-show":
            self._show_env()
        elif event.button.id == "btn-cfg-restart-litellm":
            self._restart_service("alii-router")

    def _save_config(self):
        updates = {}
        for field_id, env_key in [
            ("cfg-ntfy-topic",    "NTFY_TOPIC"),
            ("cfg-default-model", "DEFAULT_MODEL_TIER"),
        ]:
            val = self.query_one(f"#{field_id}", Input).value.strip()
            if val:
                updates[env_key] = val

        # API keys — only update if non-empty (avoid clearing existing)
        for field_id, env_key in [
            ("cfg-litellm-key",   "LITELLM_MASTER_KEY"),
            ("cfg-anthropic-key", "ANTHROPIC_API_KEY"),
        ]:
            val = self.query_one(f"#{field_id}", Input).value.strip()
            if val:
                updates[env_key] = val

        if not updates:
            self.query_one("#cfg-status", Static).update("[dim]No changes to save.[/dim]")
            return

        self._apply_env_updates(updates)
        keys = ", ".join(updates.keys())
        self.query_one("#cfg-status", Static).update(f"[green]✓ Saved: {keys}[/green]")
        self.app.notify(f"Config saved: {keys}")

    @work(thread=True)
    def _apply_env_updates(self, updates: dict):
        if not ENV_FILE.exists():
            return
        content = ENV_FILE.read_text()
        for key, val in updates.items():
            import re
            # Replace existing key or append
            pattern = re.compile(rf'^{re.escape(key)}=.*$', re.MULTILINE)
            if pattern.search(content):
                content = pattern.sub(f"{key}={val}", content)
            else:
                content += f"\n{key}={val}\n"
        ENV_FILE.write_text(content)

    def _show_env(self):
        try:
            lines = ENV_FILE.read_text().splitlines()
            # Redact values for keys containing sensitive words
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
            # Simple markdown → rich rendering
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
                    pass  # skip code fences
                else:
                    log.write(line)
        else:
            log.write("[bold cyan]◈ ALII MANUAL[/bold cyan]\n")
            log.write("[dim]Manual file not found at docs/ALII_MANUAL.md[/dim]\n")
            log.write("Quick reference:\n")
            log.write("  [cyan]/shell <cmd>[/cyan]   — run any shell command")
            log.write("  [cyan]/status[/cyan]         — show cluster status")
            log.write("  [cyan]/memory[/cyan]         — show recent conversation memory")
            log.write("  [cyan]/agents[/cyan]         — list all available agents")
            log.write("  [cyan]/clear[/cyan]          — clear chat window")
            log.write("  [cyan]/escalate <msg>[/cyan] — route to Claude API (uses tokens!)")
            log.write("\nKeyboard shortcuts:")
            log.write("  [cyan]1-7[/cyan]  — switch panels")
            log.write("  [cyan]q[/cyan]    — quit")
            log.write("  [cyan]r[/cyan]    — force cluster refresh")


# ══════════════════════════════════════════════════════════════════════════════
# ── Main App ──────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class AliiApp(App):
    """Alii Unified Terminal Hub."""

    CSS_PATH = str(WORKDIR / "alii_tui.tcss")
    TITLE = "Alii — Sovereign AI"
    BINDINGS = [
        ("1", "show_chat",    "Chat"),
        ("2", "show_agents",  "Agents"),
        ("3", "show_cluster", "Cluster"),
        ("4", "show_social",  "Social"),
        ("5", "show_systems", "Systems"),
        ("6", "show_config",  "Config"),
        ("7", "show_help",    "Help"),
        ("q", "quit",         "Quit"),
        ("r", "refresh",      "Refresh"),
        ("?", "show_help",    "Help"),
    ]

    _cluster_state: Optional[ClusterState] = None
    _current_panel: str = "panel-chat"
    _poller: Optional[ClusterPoller] = None

    def compose(self) -> ComposeResult:
        yield AliiHeader()
        with Horizontal(id="main-layout"):
            yield AliiMenu()
            with ContentSwitcher(id="content-area", initial="panel-chat"):
                yield ChatPanel(id="panel-chat")
                yield AgentsPanel(id="panel-agents")
                yield ClusterPanel(id="panel-cluster")
                yield SocialPanel(id="panel-social")
                yield SystemsPanel(id="panel-systems")
                yield ConfigPanel(id="panel-config")
                yield HelpPanel(id="panel-help")
        yield Static("", id="status-bar")

    async def on_mount(self):
        # Start cluster poller
        self._poller = ClusterPoller(interval=30.0)
        await self._poller.start()
        # Schedule periodic header updates
        self.set_interval(10, self._update_header)
        # Show startup message in status bar
        self._set_status("Alii TUI started. Cluster scan in progress...")

    async def _update_header(self):
        if self._poller:
            state = await self._poller.get_state()
            self._cluster_state = state
            header = self.query_one(AliiHeader)
            header.update_state(state)
            # Update cluster panel if visible
            if self._current_panel == "panel-cluster":
                cluster_panel = self.query_one(ClusterPanel)
                cluster_panel._render_cluster(state)
        self._set_status(
            f"Last refresh: {datetime.now().strftime('%H:%M:%S')}  |  "
            f"Press 1-7 to navigate  |  R to refresh  |  Q to quit"
        )

    def force_cluster_refresh(self):
        """Trigger an immediate cluster refresh."""
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
        switcher = self.query_one(ContentSwitcher)
        switcher.current = panel_id
        # Update menu highlight
        menu_lv = self.query_one(AliiMenu).query_one(ListView)
        for i, (_, pid) in enumerate(MENU_ITEMS):
            if pid == panel_id:
                menu_lv.index = i
                break

    # ── Key actions ────────────────────────────────────────────────────────────

    def action_show_chat(self):    self.show_panel("panel-chat")
    def action_show_agents(self):  self.show_panel("panel-agents")
    def action_show_cluster(self): self.show_panel("panel-cluster")
    def action_show_social(self):  self.show_panel("panel-social")
    def action_show_systems(self): self.show_panel("panel-systems")
    def action_show_config(self):  self.show_panel("panel-config")
    def action_show_help(self):    self.show_panel("panel-help")

    def action_refresh(self):
        self.force_cluster_refresh()

    def on_alii_menu_selected(self, event: AliiMenu.Selected) -> None:
        self.show_panel(event.panel_id)

    # ── Cleanup ────────────────────────────────────────────────────────────────

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
