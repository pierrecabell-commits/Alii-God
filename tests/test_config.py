"""
Tests for the config.py module.
Uses importlib.reload to pick up environment variable overrides.
"""
import os
import sys
import importlib
import pytest
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _reload_config():
    """Force-reload config so environment changes take effect."""
    import config
    return importlib.reload(config)


class TestWorkdir:

    def test_workdir_default(self):
        """WORKDIR should default to the project root (where config.py lives)."""
        env_backup = os.environ.pop("ALII_WORKDIR", None)
        try:
            cfg = _reload_config()
            assert cfg.WORKDIR == Path(PROJECT_ROOT).resolve()
        finally:
            if env_backup is not None:
                os.environ["ALII_WORKDIR"] = env_backup

    def test_workdir_env_override(self, tmp_path, monkeypatch):
        """Setting ALII_WORKDIR env var should override the default WORKDIR."""
        monkeypatch.setenv("ALII_WORKDIR", str(tmp_path))
        cfg = _reload_config()
        assert cfg.WORKDIR == tmp_path


class TestPaths:

    def test_paths_are_under_workdir(self):
        """All directory/path configs should live under WORKDIR."""
        env_backup = os.environ.pop("ALII_WORKDIR", None)
        try:
            cfg = _reload_config()
            workdir = cfg.WORKDIR
            path_attrs = [cfg.DB_PATH, cfg.PERF_LOG, cfg.LOG_DIR, cfg.DATA_DIR,
                          cfg.MEMORY_DIR, cfg.ACCOUNTS_DIR, cfg.VAULT_FILE]
            for p in path_attrs:
                assert str(p).startswith(str(workdir)), \
                    f"{p} is not under WORKDIR ({workdir})"
        finally:
            if env_backup is not None:
                os.environ["ALII_WORKDIR"] = env_backup


class TestURLDefaults:

    def test_url_defaults(self, monkeypatch):
        """Default URLs should point to localhost on expected ports."""
        # Clear URL env vars so defaults apply
        for var in ("ALFRED_URL", "LITELLM_URL", "OLLAMA_HOST", "QDRANT_URL"):
            monkeypatch.delenv(var, raising=False)
        cfg = _reload_config()
        assert "127.0.0.1:7000" in cfg.ALFRED_URL
        assert "127.0.0.1:4000" in cfg.LITELLM_URL
        assert "127.0.0.1:11434" in cfg.OLLAMA_URL
        assert "6333" in cfg.QDRANT_URL

    def test_url_env_override(self, monkeypatch):
        """Environment variables should override URL defaults."""
        monkeypatch.setenv("ALFRED_URL", "http://custom:9999")
        cfg = _reload_config()
        assert cfg.ALFRED_URL == "http://custom:9999"


class TestEnsureDirs:

    def test_ensure_dirs_creates_directories(self, tmp_path, monkeypatch):
        """ensure_dirs() should create all required sub-directories."""
        monkeypatch.setenv("ALII_WORKDIR", str(tmp_path))
        cfg = _reload_config()
        cfg.ensure_dirs()
        assert cfg.LOG_DIR.is_dir()
        assert cfg.DATA_DIR.is_dir()
        assert cfg.MEMORY_DIR.is_dir()
        assert cfg.ACCOUNTS_DIR.is_dir()
        assert cfg.PERF_LOG.parent.is_dir()
