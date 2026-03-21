#!/usr/bin/env python3
"""
alii_tui_chat.py — Async chat backend for the Alii TUI.

Connects to LiteLLM proxy at localhost:4000 with streaming.
Routes to appropriate model tiers based on prompt classification.
"""

from __future__ import annotations
import asyncio, json, re
from typing import AsyncIterator, Optional

LITELLM_URL = "http://localhost:4000"
OLLAMA_URL  = "http://localhost:11434"

# Model tiers (match litellm_config.yaml)
MODEL_FAST       = "fast"           # dolphin-phi:2.7b  — instant
MODEL_SMART      = "smart"          # qwen2.5:7b        — default reasoning
MODEL_SMART_PLUS = "smart-plus"     # mistral-nemo:12b  — deeper reasoning
MODEL_CODE       = "code"           # qwen2.5-coder:7b  — code discussion
MODEL_HEAVY      = "dolphin-llama3" # dolphin-llama3:8b — fallback heavy

# Patterns for routing
_CODE_KW    = re.compile(r'\b(write|create|edit|implement|code|script|deploy|fix|debug|refactor|function|class|import)\b', re.I)
_QUICK_KW   = re.compile(r'^(what|who|when|where|hi|hello|hey|thanks|ok|yes|no|sure)\b', re.I)
_HEAVY_KW   = re.compile(r'\b(analyze|compare|explain|research|summarize|strategy|plan|architecture|design|evaluate)\b', re.I)
_ESCALATE   = re.compile(r'^/(escalate|claude|anthropic)\b', re.I)

SYSTEM_PROMPT = """You are Alii, a sovereign AI built by Pierre Cabell running on recycled hardware in Akron, Ohio.
You ARE the system — Ray cluster, Ollama LLMs, Alfred orchestrator, LiteLLM proxy, agents.
Pierre is your owner: systems thinker, builder, values directness and capability.
When asked to do something: DO IT. Be direct. Be concise. Be capable.
Use tools, execute shell commands, access memory, spawn agents as needed.
Never say "I can't" — find a way. Never hedge excessively. Get things done."""


def classify_prompt(prompt: str) -> tuple[str, str]:
    """Returns (model_name, reason)."""
    p = prompt.strip()

    # Explicit escalation to Claude API
    if _ESCALATE.match(p):
        return "claude-sonnet", "explicit escalation"

    # Short quick questions
    if len(p) < 60 and _QUICK_KW.match(p):
        return MODEL_FAST, "quick query"

    # Code-specific prompts
    if _CODE_KW.search(p):
        return MODEL_CODE, "code task"

    # Long or analytical prompts
    if len(p) > 400 or _HEAVY_KW.search(p):
        return MODEL_SMART_PLUS, "deep analysis"

    # Default: smart reasoning
    return MODEL_SMART, "default"


class ChatBackend:
    """
    Async chat backend. Streams tokens as they arrive from LiteLLM.
    Falls back to direct Ollama if LiteLLM is unavailable.
    """

    def __init__(self):
        self._history: list[dict] = []
        self._litellm_ok: bool = True

    def clear_history(self):
        self._history.clear()

    async def _check_litellm(self) -> bool:
        """Quick TCP check on LiteLLM port."""
        import asyncio
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", 4000), timeout=1.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """
        Stream a response to prompt. Yields text chunks as they arrive.
        Usage:
            async for chunk in backend.stream("hello"):
                print(chunk, end="", flush=True)
        """
        model, reason = classify_prompt(prompt)

        self._history.append({"role": "user", "content": prompt})
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self._history[-20:]

        # Try LiteLLM first
        if await self._check_litellm():
            try:
                async for chunk in self._stream_litellm(model, messages):
                    yield chunk
                return
            except Exception:
                self._litellm_ok = False

        # Fallback to direct Ollama
        ollama_model = {
            MODEL_FAST: "dolphin-phi:2.7b",
            MODEL_SMART: "qwen2.5:7b",
            MODEL_SMART_PLUS: "qwen2.5:7b",
            MODEL_CODE: "qwen2.5-coder:7b",
        }.get(model, "qwen2.5:7b")

        async for chunk in self._stream_ollama(ollama_model, messages):
            yield chunk

    async def _stream_litellm(self, model: str, messages: list) -> AsyncIterator[str]:
        """Stream from LiteLLM OpenAI-compatible endpoint."""
        import aiohttp
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": 2048,
            "temperature": 0.7,
        }
        full_response = []
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{LITELLM_URL}/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120, connect=5),
            ) as resp:
                resp.raise_for_status()
                async for raw_line in resp.content:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            delta = data["choices"][0].get("delta", {})
                            chunk = delta.get("content", "")
                            if chunk:
                                full_response.append(chunk)
                                yield chunk
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        # Add assistant message to history
        if full_response:
            self._history.append({"role": "assistant", "content": "".join(full_response)})

    async def _stream_ollama(self, model: str, messages: list) -> AsyncIterator[str]:
        """Stream directly from Ollama."""
        import aiohttp
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        full_response = []
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120, connect=5),
            ) as resp:
                resp.raise_for_status()
                async for raw_line in resp.content:
                    try:
                        data = json.loads(raw_line.decode("utf-8", errors="replace"))
                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            full_response.append(chunk)
                            yield chunk
                        if data.get("done"):
                            break
                    except (json.JSONDecodeError, KeyError):
                        continue
        if full_response:
            self._history.append({"role": "assistant", "content": "".join(full_response)})

    async def get_model_for_display(self, prompt: str) -> str:
        """Returns human-readable model name for status bar."""
        model, reason = classify_prompt(prompt)
        if not await self._check_litellm():
            return f"ollama/{model} (litellm down)"
        return f"litellm/{model} ({reason})"


# Singleton for reuse across panels
_backend: Optional[ChatBackend] = None

def get_backend() -> ChatBackend:
    global _backend
    if _backend is None:
        _backend = ChatBackend()
    return _backend
