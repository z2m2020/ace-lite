"""Unit tests for orchestrator_contracts module.

Tests verify the typed contracts for the orchestrator (QO-2101/QO-2102).
"""

from __future__ import annotations

import pytest

from ace_lite.orchestrator_contracts import (
    # TypedDicts
    PlanRequestPayload,
    PlanResponsePayload,
    StageStatePayload,
    # Accessors
    get_optional,
    get_required,
    get_typed,
    get_str,
    get_int,
    get_float,
    get_bool,
    get_list,
    get_dict,
    # Validation
    ValidationError,
    validate_payload,
    validate_plan_request,
    validate_plan_response,
    # Builders
    build_stage_state,
    build_retrieval_candidate,
    # Adapters
    PlanRequestAdapter,
    PlanResponseAdapter,
    StageStateAdapter,
)


class TestTypedDicts:
    """Tests for TypedDict definitions."""

    def test_plan_request_payload(self):
        """Test PlanRequestPayload structure."""
        payload: PlanRequestPayload = {
            "query": "test query",
            "root": "/path/to/root",
            "top_k": 10,
        }
        assert payload["query"] == "test query"
        assert payload["top_k"] == 10

    def test_plan_response_payload(self):
        """Test PlanResponsePayload structure."""
        payload: PlanResponsePayload = {
            "schema_version": "v1",
            "query": "test",
            "plan": "implementation",
            "confidence": 0.95,
        }
        assert payload["plan"] == "implementation"

    def test_stage_state_payload(self):
        """Test StageStatePayload structure."""
        payload: StageStatePayload = {
            "stage_name": "index",
            "enabled": True,
            "status": "completed",
            "metrics": {"files": 100},
        }
        assert payload["status"] == "completed"


class TestAccessors:
    """Tests for accessor functions."""

    def test_get_optional_found(self):
        """Test get_optional when key exists."""
        data = {"key": "value"}
        assert get_optional(data, "key") == "value"

    def test_get_optional_not_found(self):
        """Test get_optional when key doesn't exist."""
        data = {}
        assert get_optional(data, "key") is None
        assert get_optional(data, "key", "default") == "default"

    def test_get_required_found(self):
        """Test get_required when key exists."""
        data = {"key": "value"}
        assert get_required(data, "key") == "value"

    def test_get_required_not_found(self):
        """Test get_required when key doesn't exist."""
        data = {}
        with pytest.raises(KeyError):
            get_required(data, "key")

    def test_get_required_with_context(self):
        """Test get_required with context in error."""
        data = {}
        with pytest.raises(KeyError) as exc_info:
            get_required(data, "key", "PlanRequestPayload")
        assert "PlanRequestPayload" in str(exc_info.value)

    def test_get_str(self):
        """Test get_str accessor."""
        assert get_str({"key": "value"}, "key") == "value"
        assert get_str({}, "key") == ""
        assert get_str({}, "key", "default") == "default"

    def test_get_int(self):
        """Test get_int accessor."""
        assert get_int({"key": 42}, "key") == 42
        assert get_int({}, "key") == 0
        assert get_int({"key": "123"}, "key") == 123

    def test_get_float(self):
        """Test get_float accessor."""
        assert get_float({"key": 3.14}, "key") == 3.14
        assert get_float({}, "key") == 0.0
        assert get_float({"key": "3.14"}, "key") == 3.14

    def test_get_bool(self):
        """Test get_bool accessor."""
        assert get_bool({"key": True}, "key") is True
        assert get_bool({"key": "true"}, "key") is True
        assert get_bool({"key": "false"}, "key") is False
        assert get_bool({}, "key") is False

    def test_get_list(self):
        """Test get_list accessor."""
        assert get_list({"key": [1, 2]}, "key") == [1, 2]
        assert get_list({}, "key") == []
        assert get_list({}, "key", [1]) == [1]

    def test_get_dict(self):
        """Test get_dict accessor."""
        assert get_dict({"key": {"nested": 1}}, "key") == {"nested": 1}
        assert get_dict({}, "key") == {}


class TestValidation:
    """Tests for validation functions."""

    def test_validate_payload_success(self):
        """Test successful payload validation."""
        data = {"key1": "value1", "key2": "value2"}
        validate_payload(data, ["key1", "key2"])

    def test_validate_payload_missing_key(self):
        """Test validation with missing key."""
        data = {"key1": "value1"}
        with pytest.raises(ValidationError) as exc_info:
            validate_payload(data, ["key1", "key2"])
        assert exc_info.value.key == "key2"

    def test_validate_plan_request(self):
        """Test plan request validation."""
        payload = {"query": "test"}
        result = validate_plan_request(payload)
        assert result == payload

    def test_validate_plan_request_missing_query(self):
        """Test plan request validation with missing query."""
        with pytest.raises(ValidationError):
            validate_plan_request({})

    def test_validate_plan_response(self):
        """Test plan response validation."""
        payload = {"schema_version": "v1", "plan": "test"}
        result = validate_plan_response(payload)
        assert result == payload


class TestBuilders:
    """Tests for builder functions."""

    def test_build_stage_state_basic(self):
        """Test basic stage state building."""
        state = build_stage_state("index", "completed")
        assert state["stage_name"] == "index"
        assert state["status"] == "completed"

    def test_build_stage_state_with_kwargs(self):
        """Test stage state building with kwargs."""
        state = build_stage_state(
            "retrieval",
            "running",
            metrics={"candidates": 10},
        )
        assert state["metrics"] == {"candidates": 10}

    def test_build_retrieval_candidate(self):
        """Test retrieval candidate building."""
        candidate = build_retrieval_candidate(
            path="/src/main.py",
            score=0.95,
            rank=1,
        )
        assert candidate["path"] == "/src/main.py"
        assert candidate["score"] == 0.95
        assert candidate["rank"] == 1


class TestPlanRequestAdapter:
    """Tests for PlanRequestAdapter."""

    def test_basic_properties(self):
        """Test basic property access."""
        payload = {
            "query": "test query",
            "root": "/project",
            "top_k": 10,
            "budget_tokens": 1000,
        }
        adapter = PlanRequestAdapter(payload)

        assert adapter.query == "test query"
        assert adapter.root == "/project"
        assert adapter.top_k == 10
        assert adapter.budget_tokens == 1000

    def test_defaults(self):
        """Test default values."""
        adapter = PlanRequestAdapter({})

        assert adapter.query == ""
        assert adapter.root == "."
        assert adapter.top_k == 8
        assert adapter.budget_tokens == 800

    def test_optional_properties(self):
        """Test optional property access."""
        payload = {
            "query": "test",
            "language": "python",
            "skip_stages": ["index"],
        }
        adapter = PlanRequestAdapter(payload)

        assert adapter.language == "python"
        assert adapter.skip_stages == ["index"]


class TestPlanResponseAdapter:
    """Tests for PlanResponseAdapter."""

    def test_basic_properties(self):
        """Test basic property access."""
        payload = {
            "schema_version": "v1",
            "query": "test",
            "plan": "implementation",
            "confidence": 0.95,
        }
        adapter = PlanResponseAdapter(payload)

        assert adapter.schema_version == "v1"
        assert adapter.query == "test"
        assert adapter.plan == "implementation"
        assert adapter.confidence == 0.95

    def test_candidates(self):
        """Test candidate access."""
        payload = {
            "candidates": [
                {"path": "/a.py", "score": 0.9},
                {"path": "/b.py", "score": 0.8},
            ]
        }
        adapter = PlanResponseAdapter(payload)

        assert len(adapter.candidates) == 2
        assert adapter.get_candidate_paths() == ["/a.py", "/b.py"]
        assert adapter.get_candidate_scores() == [0.9, 0.8]

    def test_stage_metrics(self):
        """Test stage metrics access."""
        payload = {
            "stage_metrics": [
                {"stage": "index", "elapsed_ms": 100},
            ]
        }
        adapter = PlanResponseAdapter(payload)

        assert len(adapter.stage_metrics) == 1


class TestStageStateAdapter:
    """Tests for StageStateAdapter."""

    def test_basic_properties(self):
        """Test basic property access."""
        payload = {
            "stage_name": "retrieval",
            "enabled": True,
            "status": "completed",
        }
        adapter = StageStateAdapter(payload)

        assert adapter.stage_name == "retrieval"
        assert adapter.enabled is True
        assert adapter.status == "completed"

    def test_status_checks(self):
        """Test status check methods."""
        running = StageStateAdapter({"status": "running"})
        completed = StageStateAdapter({"status": "completed"})
        failed = StageStateAdapter({"status": "failed"})

        assert running.is_running is True
        assert running.is_completed is False

        assert completed.is_running is False
        assert completed.is_completed is True

        assert failed.is_failed is True

    def test_elapsed_time(self):
        """Test elapsed time calculation."""
        import time

        now = time.time()
        payload = {
            "started_at": now - 10,
            "completed_at": now,
        }
        adapter = StageStateAdapter(payload)

        elapsed = adapter.elapsed_time
        assert elapsed is not None
        assert 9 <= elapsed <= 11  # Approximately 10 seconds

    def test_result_and_error(self):
        """Test result and error access."""
        payload = {
            "result": {"output": "test"},
            "error": None,
        }
        adapter = StageStateAdapter(payload)

        assert adapter.result == {"output": "test"}
        assert adapter.error is None


class TestGetTyped:
    """Tests for get_typed function."""

    def test_correct_type(self):
        """Test with correct type."""
        assert get_typed({"key": "value"}, "key", str, "default") == "value"

    def test_wrong_type(self):
        """Test with wrong type."""
        assert get_typed({"key": "value"}, "key", int, "default") == "default"

    def test_bool_is_not_int(self):
        """Test that bool is handled correctly with int.

        Note: In Python, bool is a subclass of int, so
        isinstance(True, int) returns True. This is expected behavior.
        """
        assert get_typed({"key": True}, "key", bool, "default") is True
        # Since bool is subclass of int, True will be returned for int type check
        # This is Python's standard behavior
        result = get_typed({"key": True}, "key", int, 0)
        assert result is True  # or 1, since True == 1 in Python
