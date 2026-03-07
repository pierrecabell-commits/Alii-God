#!/usr/bin/env python3
"""
ALII MODEL ROUTER - Intelligent speed-optimized model switching
Selects fastest appropriate model per task type.
Learns from performance history to continuously improve routing.
"""
import json, time, os
from dataclasses import dataclass
from typing import List
import requests

@dataclass
class ModelProfile:
    name: str
    speed_tps: float
    ctx_window: int
    strengths: List[str]
    ram_gb: float

MODELS = {
    "dolphin-phi:2.7b":             ModelProfile("dolphin-phi:2.7b",             28.0, 4096,  ["fast","code","chat","tools"], 1.6),
    "qwen2.5:7b":                   ModelProfile("qwen2.5:7b",                   12.0, 32768, ["reasoning","analysis","long_ctx"], 4.7),
    "qwen2.5-coder:7b":             ModelProfile("qwen2.5-coder:7b",             12.0, 32768, ["code","debug","refactor"], 4.7),
    "neural-chat:7b":               ModelProfile("neural-chat:7b",                11.0, 8192,  ["conversation","planning"], 4.1),
    "dolphin-llama3:8b":            ModelProfile("dolphin-llama3:8b",             10.0, 8192,  ["general","tools","autonomous"], 4.7),
    "wizard-vicuna-uncensored:13b": ModelProfile("wizard-vicuna-uncensored:13b",   5.5, 4096,  ["complex","creative"], 7.4),
}

TASK_ROUTING = {
    "quick_reply":   ["dolphin-phi:2.7b", "neural-chat:7b"],
    "code":          ["qwen2.5-coder:7b", "dolphin-llama3:8b"],
    "analysis":      ["qwen2.5:7b", "dolphin-llama3:8b"],
    "autonomous":    ["dolphin-llama3:8b", "qwen2.5:7b"],
    "planning":      ["qwen2.5:7b", "neural-chat:7b"],
    "complex":       ["wizard-vicuna-uncensored:13b", "qwen2.5:7b"],
    "memory_search": ["dolphin-phi:2.7b"],
    "default":       ["dolphin-llama3:8b", "qwen2.5:7b"],
}

OLLAMA_OPTIONS = {"num_thread": 16, "num_batch": 1024, "num_ctx": 8192, "num_gpu": 99, "repeat_penalty": 1.1, "use_mmap": True, "use_mlock": True}

class AliiModelRouter:
    def __init__(self):
        self.base_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.perf_log = "/home/avalii/moltbot/memory/logs/model_perf.json"
        os.makedirs(os.path.dirname(self.perf_log), exist_ok=True)
        self.perf_data = self._load_perf()
        self._last_save = 0.0
        self._session = requests.Session()  # reuse TCP connection across calls

    def _load_perf(self):
        try:
            with open(self.perf_log) as f: return json.load(f)
        except Exception: return {}

    def _save_perf(self):
        try:
            with open(self.perf_log, "w") as f:
                json.dump(self.perf_data, f, indent=2)
        except OSError:
            pass

    def classify_task(self, prompt: str) -> str:
        p = prompt.lower()
        if any(w in p for w in ["def ", "import ", "function", "bug ", "error", " code", "python", "bash", "script", "class ", "syntax"]): return "code"
        if any(w in p for w in ["analyze", "explain", "why ", "compare", "review", "assess", "evaluate"]): return "analysis"
        if any(w in p for w in ["plan", "schedule", "strategy", "roadmap", "steps to", "how to"]): return "planning"
        if any(w in p for w in ["execute", "run ", "task", "autonomous", "build ", "create ", "implement", "deploy"]): return "autonomous"
        if len(prompt) < 80: return "quick_reply"
        if len(prompt) > 800: return "complex"
        return "default"

    def select_model(self, task_type: str, prefer_speed=False) -> str:
        candidates = TASK_ROUTING.get(task_type, TASK_ROUTING["default"])
        if prefer_speed:
            return sorted(candidates, key=lambda m: MODELS.get(m, ModelProfile(m,5,4096,[],5)).speed_tps, reverse=True)[0]
        best, best_score = candidates[0], -1
        for m in candidates:
            hist = self.perf_data.get(m, {})
            avg_tps = hist.get("avg_tps", MODELS.get(m, ModelProfile(m,8,4096,[],5)).speed_tps)
            success_rate = hist.get("success_rate", 1.0)
            score = avg_tps * success_rate
            if score > best_score:
                best_score, best = score, m
        return best

    def _record_success(self, model, tps):
        if model not in self.perf_data:
            self.perf_data[model] = {"samples": 0, "avg_tps": tps, "success_rate": 1.0}
        d = self.perf_data[model]; n = d["samples"]
        d["avg_tps"] = (d["avg_tps"] * n + tps) / (n + 1)
        d["success_rate"] = min(1.0, (d["success_rate"] * n + 1.0) / (n + 1))
        d["samples"] = n + 1; d["last_used"] = time.time()
        self._maybe_save_perf()

    def _record_failure(self, model):
        if model not in self.perf_data:
            self.perf_data[model] = {"samples": 1, "avg_tps": 5, "success_rate": 0.5}
        else:
            d = self.perf_data[model]; n = d["samples"]
            d["success_rate"] = max(0.1, (d["success_rate"] * n) / (n + 1))
            d["samples"] = n + 1
        self._maybe_save_perf()

    def _maybe_save_perf(self):
        """Write perf log at most once per 60 s to avoid per-call disk I/O."""
        now = time.time()
        if now - self._last_save >= 60:
            self._save_perf()
            self._last_save = now

    def generate(self, prompt: str, task_type: str = None, system: str = None) -> str:
        if task_type is None: task_type = self.classify_task(prompt)
        model = self.select_model(task_type)
        start = time.time()
        payload = {"model": model, "prompt": prompt, "stream": False, "options": OLLAMA_OPTIONS.copy()}
        if system: payload["system"] = system
        try:
            resp = self._session.post(f"{self.base_url}/api/generate", json=payload, timeout=120)
            resp.raise_for_status()
            result = resp.json()
            tps = result.get("eval_count", 50) / max(time.time() - start, 0.1)
            self._record_success(model, tps)
            return result.get("response", "")
        except Exception as e:
            self._record_failure(model)
            try:
                resp = self._session.post(f"{self.base_url}/api/generate",
                    json={"model": "dolphin-phi:2.7b", "prompt": prompt, "stream": False,
                          "options": {"num_ctx": 2048, "num_thread": 10}}, timeout=60)
                resp.raise_for_status()
                return resp.json().get("response", f"Error: {e}")
            except Exception:
                return f"[ERROR] {e}"

    def get_fastest_model(self) -> str:
        return self.select_model("quick_reply", prefer_speed=True)

    def benchmark(self):
        results = {}
        test = "Respond in exactly 3 words: The sky is"
        for model in MODELS:
            start = time.time()
            try:
                r = self._session.post(f"{self.base_url}/api/generate",
                    json={"model": model, "prompt": test, "stream": False,
                          "options": {"num_ctx": 512, "num_thread": 10}}, timeout=30)
                elapsed = time.time() - start
                tps = r.json().get("eval_count", 10) / max(elapsed, 0.1)
                results[model] = {"tps": round(tps, 1), "latency_s": round(elapsed, 2), "status": "ok"}
            except Exception as e:
                results[model] = {"status": "error", "error": str(e)}
        return results

    def status(self) -> dict:
        return {"models": {k: {"speed_tps": v.speed_tps, "ram_gb": v.ram_gb, "strengths": v.strengths}
                           for k, v in MODELS.items()},
                "routing_table": TASK_ROUTING, "performance_history": self.perf_data}

if __name__ == "__main__":
    router = AliiModelRouter()
    print("=== ALII MODEL ROUTER ===")
    print(f"Fastest model: {router.get_fastest_model()}")
    tests = ["write a python function", "say hi", "analyze this and explain"]
    for t in tests:
        print(f"  classify({t[:40]!r}) -> {router.classify_task(t)}")
    print("Router operational.")
