"""
Tests for security_agent.py scan functions.
All file and subprocess I/O is confined to temp directories.
"""
import os
import sys
import stat
import pytest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from security_agent import scan_secrets, scan_permissions, scan_ports


class TestScanSecrets:

    def test_scan_secrets_finds_hardcoded_key(self, tmp_path):
        """A file containing a hardcoded api_key should be flagged."""
        target = tmp_path / "bad_script.py"
        target.write_text("api_key = 'sk-abc12345678901234567890123456789'\n")
        findings = scan_secrets(paths=[str(tmp_path)])
        labels = [f["label"] for f in findings]
        assert any("api_key" in lbl.lower() or "API key" in lbl for lbl in labels), \
            f"Expected a hardcoded key finding, got: {findings}"

    def test_scan_secrets_ignores_env_refs(self, tmp_path):
        """Lines using os.environ should not be flagged."""
        target = tmp_path / "safe_script.py"
        target.write_text("api_key = os.environ.get('API_KEY', '')\n")
        findings = scan_secrets(paths=[str(tmp_path)])
        assert findings == []

    def test_scan_secrets_ignores_comments(self, tmp_path):
        """Lines starting with # should not trigger findings."""
        target = tmp_path / "commented.py"
        target.write_text("# api_key = 'sk-abc12345678901234567890123456789'\n")
        findings = scan_secrets(paths=[str(tmp_path)])
        assert findings == []

    def test_scan_secrets_skips_non_source_files(self, tmp_path):
        """Files with extensions not in SECRET_SCAN_EXTENSIONS are ignored."""
        target = tmp_path / "notes.txt"
        target.write_text("api_key = 'sk-abc12345678901234567890123456789'\n")
        findings = scan_secrets(paths=[str(tmp_path)])
        assert findings == [], "Should not scan .txt files"

    def test_scan_secrets_empty_dir(self, tmp_path):
        """An empty directory produces no findings."""
        findings = scan_secrets(paths=[str(tmp_path)])
        assert findings == []


class TestScanPermissions:

    def test_scan_permissions_empty_dir(self, tmp_path):
        """An empty directory returns no permission findings."""
        with patch("security_agent.SCAN_ROOT", str(tmp_path)):
            findings = scan_permissions()
        assert findings == []

    def test_scan_permissions_world_readable(self, tmp_path):
        """A world-readable .key file should be flagged."""
        key_file = tmp_path / "server.key"
        key_file.write_text("fake private key content")
        key_file.chmod(0o644)  # world-readable
        with patch("security_agent.SCAN_ROOT", str(tmp_path)):
            findings = scan_permissions()
        flagged_files = [f["file"] for f in findings]
        assert str(key_file) in flagged_files

    def test_scan_permissions_restricted_file_ok(self, tmp_path):
        """A properly restricted .key file should NOT be flagged."""
        key_file = tmp_path / "server.key"
        key_file.write_text("fake private key content")
        key_file.chmod(0o600)  # owner-only
        with patch("security_agent.SCAN_ROOT", str(tmp_path)):
            findings = scan_permissions()
        assert findings == []


class TestScanPorts:

    def test_scan_ports_format(self):
        """scan_ports output entries have the expected keys."""
        mock_result = MagicMock()
        mock_result.stdout = "LISTEN  0  128  0.0.0.0:99999  *:*\n"
        mock_result.returncode = 0

        state = {"known_ports": [], "last_run": None}

        with patch("security_agent.subprocess.run", return_value=mock_result):
            findings = scan_ports(state)

        for f in findings:
            assert "type" in f
            assert "port" in f
            assert "message" in f
            assert f["type"] == "new_port"

    def test_scan_ports_approved_not_flagged(self):
        """Ports in APPROVED_PORTS should not appear as findings."""
        mock_result = MagicMock()
        # Port 22 is in APPROVED_PORTS
        mock_result.stdout = "LISTEN  0  128  0.0.0.0:22  *:*\n"
        mock_result.returncode = 0

        state = {"known_ports": [], "last_run": None}

        with patch("security_agent.subprocess.run", return_value=mock_result):
            findings = scan_ports(state)

        flagged_ports = [f["port"] for f in findings]
        assert 22 not in flagged_ports
