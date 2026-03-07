"""
Alii-God — Centralized Configuration
=====================================

Single source of truth for every path, URL, port, and tunable constant
used across the Alii agent ecosystem.

**Override any value** by setting the corresponding environment variable
(see inline comments).  A project-local ``.env`` file is loaded
automatically when this module is first imported — existing env vars are
never overwritten.

Usage in other modules::

    from config import cfg

    db   = cfg.DB_PATH
    url  = cfg.LITELLM_URL
    port = cfg.ALFRED_PORT
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import FrozenSet

# ---------------------------------------------------------------------------
# .env loader — runs at import time, no external dependencies
# ---------------------------------------------------------------------------

def _load_dotenv(env_path: Path) -> None:
    """Parse a .env file into ``os.environ`` without overriding existing vars.

    Supports:
    - blank lines and ``#`` comments
    - ``KEY=value`` and ``KEY="value"`` (strips outer quotes)
    - inline comments after unquoted values
    """
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip matched surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)


# ---------------------------------------------------------------------------
# Resolve WORKDIR first — everything else is derived from it
# ---------------------------------------------------------------------------

WORKDIR = Path(
    os.environ.get("ALII_WORKDIR", str(Path(__file__).resolve().parent))
)

# Load .env early so subsequent os.environ.get() calls see its values
_load_dotenv(WORKDIR / ".env")


# ═══════════════════════════════════════════════════════════════════════════
# Configuration namespace
# ═══════════════════════════════════════════════════════════════════════════

class _Config:
    """Read-only namespace that groups every configurable value.

    All attributes are computed once at import time and never mutated.
    """

    # ------------------------------------------------------------------
    # Root directories
    # ------------------------------------------------------------------

    WORKDIR: Path = WORKDIR
    """Project root.  Env: ``ALII_WORKDIR`` (default: directory containing config.py)."""

    LOG_DIR: Path = WORKDIR / "logs"
    """Central log directory."""

    DATA_DIR: Path = WORKDIR / "data"
    """Runtime data / state files."""

    MEMORY_DIR: Path = WORKDIR / "memory"
    """Memory subsystem root."""

    ACCOUNTS_DIR: Path = WORKDIR / "accounts"
    """Accounts / vault storage."""

    # ------------------------------------------------------------------
    # Database & memory paths
    # ------------------------------------------------------------------

    DB_PATH: Path = Path(
        os.environ.get("ALII_DB_PATH", str(WORKDIR / "memory" / "alii_core.db"))
    )
    """SQLite core database.  Env: ``ALII_DB_PATH``."""

    SQLITE_DB: Path = DB_PATH  # alias used by memory_bridge.py

    MEMORIES_JSON: Path = Path(
        os.environ.get(
            "ALII_MEMORIES_JSON", str(WORKDIR / "memory" / "memories.json")
        )
    )
    """Flat-file memory export.  Env: ``ALII_MEMORIES_JSON``."""

    COLLECTION_NAME: str = os.environ.get("ALII_COLLECTION_NAME", "alii_memories")
    """Qdrant collection name.  Env: ``ALII_COLLECTION_NAME``."""

    EMBED_DIM: int = int(os.environ.get("ALII_EMBED_DIM", "768"))
    """Embedding vector dimension.  Env: ``ALII_EMBED_DIM``."""

    # ------------------------------------------------------------------
    # Log / performance paths
    # ------------------------------------------------------------------

    PERF_LOG: Path = Path(
        os.environ.get(
            "ALII_PERF_LOG", str(WORKDIR / "memory" / "logs" / "model_perf.json")
        )
    )
    """Model performance log.  Env: ``ALII_PERF_LOG``."""

    MEMORY_BRIDGE_LOG: Path = Path(
        os.environ.get(
            "ALII_MEMORY_BRIDGE_LOG", str(WORKDIR / "logs" / "memory_bridge.log")
        )
    )
    """Memory bridge log file.  Env: ``ALII_MEMORY_BRIDGE_LOG``."""

    SECURITY_LOG: Path = Path(
        os.environ.get(
            "ALII_SECURITY_LOG", str(WORKDIR / "logs" / "security_agent.log")
        )
    )
    """Security agent log file.  Env: ``ALII_SECURITY_LOG``."""

    CLUSTER_SCAN_LOG: Path = Path(
        os.environ.get(
            "ALII_CLUSTER_SCAN_LOG", str(WORKDIR / "logs" / "cluster_scan.log")
        )
    )
    """Cluster scan log file.  Env: ``ALII_CLUSTER_SCAN_LOG``."""

    REVENUE_LOG: Path = Path(
        os.environ.get(
            "ALII_REVENUE_LOG", str(WORKDIR / "logs" / "revenue_agent.log")
        )
    )
    """Revenue agent log file.  Env: ``ALII_REVENUE_LOG``."""

    INVENTORY_LOG: Path = Path(
        os.environ.get(
            "ALII_INVENTORY_LOG", str(WORKDIR / "logs" / "inventory_agent.log")
        )
    )
    """Inventory agent log file.  Env: ``ALII_INVENTORY_LOG``."""

    TODO_LOG: Path = Path(
        os.environ.get(
            "ALII_TODO_LOG", str(WORKDIR / "logs" / "todo_agent.log")
        )
    )
    """Todo agent log file.  Env: ``ALII_TODO_LOG``."""

    MONEY_REPORT: Path = Path(
        os.environ.get(
            "ALII_MONEY_REPORT", str(WORKDIR / "logs" / "money_report.json")
        )
    )
    """Revenue report file.  Env: ``ALII_MONEY_REPORT``."""

    # ------------------------------------------------------------------
    # State files
    # ------------------------------------------------------------------

    ALFRED_STATE: Path = Path(
        os.environ.get(
            "ALII_ALFRED_STATE", str(WORKDIR / "memory" / "alfred_state.json")
        )
    )
    """Alfred persistent state.  Env: ``ALII_ALFRED_STATE``."""

    MEMORY_BRIDGE_STATE: Path = Path(
        os.environ.get(
            "ALII_MEMORY_BRIDGE_STATE",
            str(WORKDIR / "data" / "memory_bridge_state.json"),
        )
    )
    """Memory bridge state file.  Env: ``ALII_MEMORY_BRIDGE_STATE``."""

    SECURITY_STATE: Path = Path(
        os.environ.get(
            "ALII_SECURITY_STATE", str(WORKDIR / "data" / "security_state.json")
        )
    )
    """Security agent state file.  Env: ``ALII_SECURITY_STATE``."""

    REVENUE_STATE: Path = Path(
        os.environ.get(
            "ALII_REVENUE_STATE", str(WORKDIR / "data" / "revenue_state.json")
        )
    )
    """Revenue agent state file.  Env: ``ALII_REVENUE_STATE``."""

    # ------------------------------------------------------------------
    # Data files
    # ------------------------------------------------------------------

    INVENTORY_FILE: Path = Path(
        os.environ.get(
            "ALII_INVENTORY_FILE",
            str(WORKDIR / "data" / "system_inventory.json"),
        )
    )
    """System inventory snapshot.  Env: ``ALII_INVENTORY_FILE``."""

    TODO_DATA: Path = Path(
        os.environ.get(
            "ALII_TODO_DATA", str(WORKDIR / "data" / "owner_todos.json")
        )
    )
    """Todo list data file.  Env: ``ALII_TODO_DATA``."""

    CLUSTER_CREDENTIALS: Path = Path(
        os.environ.get(
            "ALII_CLUSTER_CREDENTIALS",
            str(WORKDIR / "cluster_credentials.json"),
        )
    )
    """Cluster credentials file.  Env: ``ALII_CLUSTER_CREDENTIALS``."""

    CLUSTER_OUTPUT_DIR: Path = Path(
        os.environ.get("ALII_CLUSTER_OUTPUT_DIR", str(WORKDIR / "data"))
    )
    """Directory for cluster scan output.  Env: ``ALII_CLUSTER_OUTPUT_DIR``."""

    VAULT_FILE: Path = Path(
        os.environ.get(
            "ALII_VAULT_FILE", str(WORKDIR / "accounts" / "vault.json")
        )
    )
    """Encrypted account vault.  Env: ``ALII_VAULT_FILE``."""

    ENV_FILE: Path = WORKDIR / ".env"
    """Project .env file (loaded at import time)."""

    # ------------------------------------------------------------------
    # Service URLs
    # ------------------------------------------------------------------

    ALFRED_URL: str = os.environ.get("ALFRED_URL", "http://127.0.0.1:7000")
    """Alfred orchestrator URL.  Env: ``ALFRED_URL``."""

    LITELLM_URL: str = os.environ.get("LITELLM_URL", "http://127.0.0.1:4000")
    """LiteLLM proxy URL.  Env: ``LITELLM_URL``."""

    OLLAMA_URL: str = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    """Ollama inference server URL.  Env: ``OLLAMA_HOST``."""

    QDRANT_URL: str = os.environ.get("QDRANT_URL", "http://localhost:6333")
    """Qdrant vector database URL.  Env: ``QDRANT_URL``."""

    NTFY_TOPIC: str = os.environ.get("NTFY_TOPIC", "alii-alerts")
    """Ntfy notification topic.  Env: ``NTFY_TOPIC``."""

    NTFY_URL: str = os.environ.get(
        "NTFY_URL",
        f"http://localhost:8080/{os.environ.get('NTFY_TOPIC', 'alii-alerts')}",
    )
    """Ntfy push URL (includes topic).  Env: ``NTFY_URL``."""

    # ------------------------------------------------------------------
    # Service ports
    # ------------------------------------------------------------------

    ALFRED_PORT: int = int(os.environ.get("ALFRED_PORT", "7000"))
    """Alfred HTTP port.  Env: ``ALFRED_PORT``."""

    LITELLM_PORT: int = int(os.environ.get("LITELLM_PORT", "4000"))
    """LiteLLM proxy port.  Env: ``LITELLM_PORT``."""

    OLLAMA_PORT: int = int(os.environ.get("OLLAMA_PORT", "11434"))
    """Ollama server port.  Env: ``OLLAMA_PORT``."""

    QDRANT_PORT: int = int(os.environ.get("QDRANT_PORT", "6333"))
    """Qdrant HTTP port.  Env: ``QDRANT_PORT``."""

    MAC_CONTROLLER_PORT: int = int(os.environ.get("MAC_CONTROLLER_PORT", "7020"))
    """Mac cluster controller port.  Env: ``MAC_CONTROLLER_PORT``."""

    CONTACT_FORM_PORT: int = int(os.environ.get("CONTACT_FORM_PORT", "8888"))
    """Contact form server port.  Env: ``CONTACT_FORM_PORT``."""

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------

    SCAN_ROOT: Path = Path(
        os.environ.get("ALII_SCAN_ROOT", str(Path.home()))
    )
    """Root directory for security scans.  Env: ``ALII_SCAN_ROOT``."""

    APPROVED_PORTS: FrozenSet[int] = frozenset(
        int(p)
        for p in os.environ.get(
            "ALII_APPROVED_PORTS",
            "22,3000,3001,4000,5678,6333,8001,9000,9001,9090,11434,41641",
        ).split(",")
    )
    """Ports considered safe by the security agent.  Env: ``ALII_APPROVED_PORTS`` (comma-separated)."""

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    VERSION: str = "2.1.0"
    """Alii system version."""

    HISTORY_FILE: Path = Path(
        os.environ.get("ALII_HISTORY_FILE", str(Path.home() / ".alii_history"))
    )
    """CLI history file.  Env: ``ALII_HISTORY_FILE``."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def ensure_dirs(self) -> None:
        """Create every expected directory if it does not already exist."""
        for d in (
            self.LOG_DIR,
            self.DATA_DIR,
            self.MEMORY_DIR,
            self.ACCOUNTS_DIR,
            self.PERF_LOG.parent,      # memory/logs
        ):
            d.mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:
        return f"<AliiConfig WORKDIR={self.WORKDIR}>"


# ---------------------------------------------------------------------------
# Module-level singleton — import as:  from config import cfg
# ---------------------------------------------------------------------------

cfg = _Config()

# ---------------------------------------------------------------------------
# Backward-compatible top-level exports (for files that already do
# ``from config import WORKDIR, DB_PATH, …``).  These are identical
# to the attributes on ``cfg``.
# ---------------------------------------------------------------------------

WORKDIR             = cfg.WORKDIR
LOG_DIR             = cfg.LOG_DIR
DATA_DIR            = cfg.DATA_DIR
MEMORY_DIR          = cfg.MEMORY_DIR
ACCOUNTS_DIR        = cfg.ACCOUNTS_DIR

DB_PATH             = cfg.DB_PATH
SQLITE_DB           = cfg.SQLITE_DB
MEMORIES_JSON       = cfg.MEMORIES_JSON
COLLECTION_NAME     = cfg.COLLECTION_NAME
EMBED_DIM           = cfg.EMBED_DIM

PERF_LOG            = cfg.PERF_LOG
MEMORY_BRIDGE_LOG   = cfg.MEMORY_BRIDGE_LOG
SECURITY_LOG        = cfg.SECURITY_LOG
CLUSTER_SCAN_LOG    = cfg.CLUSTER_SCAN_LOG
REVENUE_LOG         = cfg.REVENUE_LOG
INVENTORY_LOG       = cfg.INVENTORY_LOG
TODO_LOG            = cfg.TODO_LOG
MONEY_REPORT        = cfg.MONEY_REPORT

ALFRED_STATE        = cfg.ALFRED_STATE
MEMORY_BRIDGE_STATE = cfg.MEMORY_BRIDGE_STATE
SECURITY_STATE      = cfg.SECURITY_STATE
REVENUE_STATE       = cfg.REVENUE_STATE

INVENTORY_FILE      = cfg.INVENTORY_FILE
TODO_DATA           = cfg.TODO_DATA
CLUSTER_CREDENTIALS = cfg.CLUSTER_CREDENTIALS
CLUSTER_OUTPUT_DIR  = cfg.CLUSTER_OUTPUT_DIR
VAULT_FILE          = cfg.VAULT_FILE
ENV_FILE            = cfg.ENV_FILE

ALFRED_URL          = cfg.ALFRED_URL
LITELLM_URL         = cfg.LITELLM_URL
OLLAMA_URL          = cfg.OLLAMA_URL
QDRANT_URL          = cfg.QDRANT_URL
NTFY_TOPIC          = cfg.NTFY_TOPIC
NTFY_URL            = cfg.NTFY_URL

ALFRED_PORT         = cfg.ALFRED_PORT
LITELLM_PORT        = cfg.LITELLM_PORT
OLLAMA_PORT         = cfg.OLLAMA_PORT
QDRANT_PORT         = cfg.QDRANT_PORT
MAC_CONTROLLER_PORT = cfg.MAC_CONTROLLER_PORT
CONTACT_FORM_PORT   = cfg.CONTACT_FORM_PORT

SCAN_ROOT           = cfg.SCAN_ROOT
APPROVED_PORTS      = cfg.APPROVED_PORTS

VERSION             = cfg.VERSION
HISTORY_FILE        = cfg.HISTORY_FILE


def ensure_dirs() -> None:
    """Module-level convenience wrapper."""
    cfg.ensure_dirs()
