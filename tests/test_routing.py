"""
Tests for the classify_prompt routing function in alii_core.py.
"""
import os
import sys
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alii_core import classify_prompt


class TestClassifyPrompt:

    def test_ops_query(self):
        """Short prompts containing ops keywords route to ops/fast."""
        backend, hint = classify_prompt("status")
        assert backend == "ops"
        assert hint == "fast"

    def test_code_implement(self):
        """'implement' triggers the claude_code backend."""
        backend, hint = classify_prompt("implement a login system")
        assert backend == "claude_code"
        assert hint == "code"

    def test_code_simple(self):
        """Generic code keywords without complex action route to litellm/code."""
        backend, hint = classify_prompt("write python code")
        assert backend == "litellm"
        assert hint == "code"

    def test_analysis(self):
        """Analysis keywords route to claude_api/smart."""
        backend, hint = classify_prompt("analyze this architecture")
        assert backend == "claude_api"
        assert hint == "smart"

    def test_quick_reply(self):
        """Short greetings route to litellm/fast."""
        backend, hint = classify_prompt("hello")
        assert backend == "litellm"
        assert hint == "fast"

    def test_long_prompt(self):
        """Prompts longer than 800 chars route to claude_api/smart."""
        long_prompt = "Tell me about " + "something very detailed " * 50  # > 900 chars
        assert len(long_prompt) > 800
        backend, hint = classify_prompt(long_prompt)
        assert backend == "claude_api"
        assert hint == "smart"

    def test_default(self):
        """A medium-length general prompt with no special keywords -> litellm/default."""
        # Must be >= 60 chars (to skip fast), <= 800 chars, and no special keywords
        prompt = "I would like to know more about the general state of things in the world today for my own curiosity"
        assert 60 <= len(prompt) <= 800
        backend, hint = classify_prompt(prompt)
        assert backend == "litellm"
        assert hint == "default"

    def test_ops_long_sentence_not_ops(self):
        """Ops keywords in a longer sentence should NOT route to ops."""
        # classify_prompt requires < 6 words for ops
        backend, hint = classify_prompt("what is the current status of the entire cluster and all services")
        assert backend != "ops"
