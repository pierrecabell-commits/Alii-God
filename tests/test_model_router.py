"""
Tests for AliiModelRouter in alii_model_router.py.
All HTTP calls are mocked so no real Ollama/LiteLLM traffic is generated.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alii_model_router import AliiModelRouter, MODELS, TASK_ROUTING


@pytest.fixture
def router(tmp_path):
    """Create an AliiModelRouter that writes perf data to a temp file."""
    perf_file = tmp_path / "model_perf.json"
    with patch("alii_model_router.PERF_LOG", perf_file), \
         patch("alii_model_router.requests.Session") as MockSession:
        # Prevent any real HTTP calls
        mock_session = MagicMock()
        MockSession.return_value = mock_session
        r = AliiModelRouter()
        r._session = mock_session
        yield r


class TestClassifyTask:

    def test_classify_code_task_def(self, router):
        """Prompt containing 'def ' is classified as code."""
        assert router.classify_task("def my_function():") == "code"

    def test_classify_code_task_import(self, router):
        """Prompt containing 'import ' is classified as code."""
        assert router.classify_task("import os") == "code"

    def test_classify_analysis(self, router):
        """Prompt with 'analyze' is classified as analysis."""
        assert router.classify_task("analyze this data set") == "analysis"

    def test_classify_quick(self, router):
        """Short prompt with no keywords -> quick_reply."""
        assert router.classify_task("hi there") == "quick_reply"

    def test_classify_planning(self, router):
        """Prompt with 'plan' keyword is classified as planning."""
        assert router.classify_task("plan the deployment steps for rollout") == "planning"


class TestSelectModel:

    def test_select_model_returns_valid(self, router):
        """Selected model must exist in the MODELS dict."""
        for task_type in TASK_ROUTING:
            model = router.select_model(task_type)
            assert model in MODELS, f"select_model({task_type!r}) returned unknown model {model!r}"

    def test_select_model_speed(self, router):
        """prefer_speed=True should pick the fastest candidate."""
        model = router.select_model("code", prefer_speed=True)
        candidates = TASK_ROUTING["code"]
        fastest = max(candidates, key=lambda m: MODELS[m].speed_tps)
        assert model == fastest


class TestPerformanceTracking:

    def test_record_success_updates_perf(self, router):
        """_record_success creates / updates the perf_data entry."""
        model = "dolphin-phi:2.7b"
        router._record_success(model, 25.0)
        assert model in router.perf_data
        assert router.perf_data[model]["samples"] >= 1
        assert router.perf_data[model]["avg_tps"] > 0

    def test_record_success_running_average(self, router):
        """Multiple _record_success calls compute a running average."""
        model = "qwen2.5:7b"
        router._record_success(model, 10.0)
        router._record_success(model, 20.0)
        avg = router.perf_data[model]["avg_tps"]
        assert 14.0 <= avg <= 16.0  # running average of 10 and 20

    def test_record_failure_decreases_rate(self, router):
        """_record_failure should decrease the success_rate."""
        model = "dolphin-phi:2.7b"
        # Seed with a success so rate starts at 1.0
        router._record_success(model, 20.0)
        initial_rate = router.perf_data[model]["success_rate"]
        router._record_failure(model)
        assert router.perf_data[model]["success_rate"] < initial_rate

    def test_record_failure_new_model(self, router):
        """_record_failure on an unknown model creates a default entry."""
        model = "never-seen-before:1b"
        router._record_failure(model)
        assert model in router.perf_data
        assert router.perf_data[model]["success_rate"] <= 0.5


class TestBenchmark:

    def test_benchmark_format(self, router):
        """benchmark() returns a dict keyed by model names from MODELS."""
        # Mock the HTTP response for each model
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "blue", "eval_count": 10}
        mock_response.raise_for_status.return_value = None
        router._session.post.return_value = mock_response

        results = router.benchmark()
        assert isinstance(results, dict)
        for model_name in MODELS:
            assert model_name in results, f"Missing model {model_name!r} in benchmark results"
            assert "status" in results[model_name]

    def test_benchmark_handles_errors(self, router):
        """benchmark() gracefully handles connection errors per model."""
        router._session.post.side_effect = ConnectionError("no server")
        results = router.benchmark()
        for model_name in MODELS:
            assert results[model_name]["status"] == "error"
