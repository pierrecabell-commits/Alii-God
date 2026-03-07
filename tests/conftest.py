"""
Shared pytest fixtures for the Alii-God test suite.
"""
import os
import sys
import sqlite3
import pytest

# Ensure the project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def tmp_workdir(tmp_path):
    """Create a temporary working directory with standard Alii sub-directories."""
    for subdir in ("memory", "logs", "data", "accounts"):
        (tmp_path / subdir).mkdir()
    return tmp_path


@pytest.fixture
def mock_env(monkeypatch):
    """Patch os.environ with safe test values so no real services are contacted."""
    env_vars = {
        "ALII_WORKDIR": "/tmp/alii_test",
        "ANTHROPIC_API_KEY": "test-key-not-real",
        "LITELLM_MASTER_KEY": "test-litellm-key",
        "ALFRED_URL": "http://127.0.0.1:19999",
        "LITELLM_URL": "http://127.0.0.1:19998",
        "OLLAMA_HOST": "http://127.0.0.1:19997",
        "MACBOOK_TAILSCALE_IP": "100.0.0.1",
        "MACBOOK_SSH_USER": "testuser",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


@pytest.fixture
def memory_db():
    """Create an in-memory SQLite database with the Alii episodic/semantic/working schema."""
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS episodic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT, content TEXT, backend TEXT,
            ts TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS semantic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE, value TEXT,
            ts TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS working (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT, value TEXT,
            ts TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS ep_ts ON episodic(ts);
    """)
    conn.commit()
    yield conn
    conn.close()
