"""
Tests for the AliiMemory class defined in alii_core.py.
"""
import os
import sys
import threading
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alii_core import AliiMemory


@pytest.fixture
def mem(tmp_path):
    """Provide a fresh AliiMemory backed by a temp SQLite file."""
    db_path = tmp_path / "memory" / "test.db"
    return AliiMemory(path=db_path)


class TestAliiMemory:

    def test_save_and_retrieve_turn(self, mem):
        """save_turn stores a row; get_context returns it."""
        mem.save_turn("user", "hello world", "litellm")
        ctx = mem.get_context(10)
        assert len(ctx) == 1
        role, content = ctx[0]
        assert role == "user"
        assert content == "hello world"

    def test_context_limit(self, mem):
        """get_context(n) returns at most n rows even when more exist."""
        for i in range(20):
            mem.save_turn("user", f"turn {i}", "test")
        ctx = mem.get_context(5)
        assert len(ctx) == 5
        # The returned rows should be the 5 most recent, in chronological order
        assert ctx[0][1] == "turn 15"
        assert ctx[-1][1] == "turn 19"

    def test_save_and_get_facts(self, mem):
        """save_fact / get_facts round-trip through the semantic table."""
        mem.save_fact("owner", "Pierre")
        mem.save_fact("location", "Akron")
        facts = mem.get_facts(10)
        keys = [k for k, _ in facts]
        assert "owner" in keys
        assert "location" in keys

    def test_save_fact_upsert(self, mem):
        """Saving the same key twice replaces the value (INSERT OR REPLACE)."""
        mem.save_fact("version", "1.0")
        mem.save_fact("version", "2.0")
        facts = mem.get_facts(10)
        version_vals = [v for k, v in facts if k == "version"]
        assert version_vals == ["2.0"]

    def test_count(self, mem):
        """count() reflects the number of episodic turns stored."""
        assert mem.count() == 0
        mem.save_turn("user", "a", "")
        mem.save_turn("assistant", "b", "")
        assert mem.count() == 2

    def test_thread_safety(self, mem):
        """Multiple threads writing concurrently should not corrupt the database."""
        errors = []

        def writer(thread_id):
            try:
                for i in range(50):
                    mem.save_turn("user", f"thread-{thread_id}-msg-{i}", "test")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        assert mem.count() == 200  # 4 threads x 50 messages

    def test_content_truncation(self, mem):
        """Content longer than 4000 chars is truncated on save."""
        long_content = "x" * 5000
        mem.save_turn("user", long_content, "test")
        ctx = mem.get_context(1)
        assert len(ctx) == 1
        assert len(ctx[0][1]) == 4000
