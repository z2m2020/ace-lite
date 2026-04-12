"""Tests for CLI enhancements module."""

from __future__ import annotations

import pytest

from ace_lite.cli_app.cli_enhancements import (
    PARAM_RANGES,
    ErrorMessage,
    HelpExamples,
    OutputFormatter,
    ParameterValidationError,
    validate_all_retrieval_params,
    validate_budget_tokens,
    validate_chunk_per_file_limit,
    validate_chunk_token_budget,
    validate_chunk_top_k,
    validate_float_param,
    validate_int_param,
    validate_min_candidate_score,
    validate_timeout_seconds,
    validate_top_k_files,
)


class TestParameterValidationError:
    """Tests for ParameterValidationError."""

    def test_format_message(self):
        """Test error message formatting."""
        error = ParameterValidationError(
            param_name="top-k",
            message="Value 200 is out of range",
            valid_range="1 to 100",
        )
        assert "top-k" in str(error)
        assert "200" in str(error)
        assert "1 to 100" in str(error)

    def test_format_message_without_range(self):
        """Test error message without valid range."""
        error = ParameterValidationError(
            param_name="timeout",
            message="Expected number",
        )
        assert "timeout" in str(error)
        assert "Expected number" in str(error)


class TestParamRanges:
    """Tests for PARAM_RANGES constants."""

    def test_top_k_files_range(self):
        """Test top_k_files range values."""
        assert PARAM_RANGES.TOP_K_FILES == (1, 100)

    def test_timeout_range(self):
        """Test timeout_seconds range values."""
        assert PARAM_RANGES.TIMEOUT_SECONDS == (1, 300)

    def test_budget_tokens_range(self):
        """Test budget_tokens range values."""
        assert PARAM_RANGES.BUDGET_TOKENS == (100, 50000)


class TestValidateIntParam:
    """Tests for validate_int_param function."""

    def test_valid_value(self):
        """Test valid integer value passes validation."""
        result = validate_int_param("top-k", 50, 1, 100)
        assert result == 50

    def test_boundary_min(self):
        """Test minimum boundary value."""
        result = validate_int_param("top-k", 1, 1, 100)
        assert result == 1

    def test_boundary_max(self):
        """Test maximum boundary value."""
        result = validate_int_param("top-k", 100, 1, 100)
        assert result == 100

    def test_invalid_below_min(self):
        """Test value below minimum raises error."""
        with pytest.raises(ParameterValidationError):
            validate_int_param("top-k", 0, 1, 100)

    def test_invalid_above_max(self):
        """Test value above maximum raises error."""
        with pytest.raises(ParameterValidationError):
            validate_int_param("top-k", 101, 1, 100)

    def test_boolean_rejected(self):
        """Test boolean values are rejected."""
        with pytest.raises(ParameterValidationError):
            validate_int_param("flag", True, 0, 1)

    def test_float_rejected(self):
        """Test float values are rejected."""
        with pytest.raises(ParameterValidationError):
            validate_int_param("value", 3.14, 0, 10)

    def test_string_rejected(self):
        """Test string values are rejected."""
        with pytest.raises(ParameterValidationError):
            validate_int_param("value", "50", 0, 100)


class TestValidateFloatParam:
    """Tests for validate_float_param function."""

    def test_valid_int_value(self):
        """Test integer value is accepted as float."""
        result = validate_float_param("timeout", 5, 0.0, 10.0)
        assert result == 5.0

    def test_valid_float_value(self):
        """Test float value passes validation."""
        result = validate_float_param("timeout", 3.5, 0.0, 10.0)
        assert result == 3.5

    def test_invalid_below_min(self):
        """Test value below minimum raises error."""
        with pytest.raises(ParameterValidationError):
            validate_float_param("timeout", -0.1, 0.0, 10.0)

    def test_invalid_above_max(self):
        """Test value above maximum raises error."""
        with pytest.raises(ParameterValidationError):
            validate_float_param("timeout", 10.1, 0.0, 10.0)

    def test_boolean_rejected(self):
        """Test boolean values are rejected."""
        with pytest.raises(ParameterValidationError):
            validate_float_param("value", False, 0.0, 1.0)


class TestValidateTopKFiles:
    """Tests for validate_top_k_files helper."""

    def test_valid_value(self):
        """Test valid top_k_files value."""
        assert validate_top_k_files(50) == 50

    def test_invalid_value(self):
        """Test invalid top_k_files value."""
        with pytest.raises(ParameterValidationError):
            validate_top_k_files(0)

    def test_invalid_value_too_high(self):
        """Test top_k_files value too high."""
        with pytest.raises(ParameterValidationError):
            validate_top_k_files(101)


class TestValidateTimeoutSeconds:
    """Tests for validate_timeout_seconds helper."""

    def test_valid_value(self):
        """Test valid timeout value."""
        assert validate_timeout_seconds(15.0) == 15.0

    def test_invalid_value(self):
        """Test invalid timeout value."""
        with pytest.raises(ParameterValidationError):
            validate_timeout_seconds(0)


class TestValidateAllRetrievalParams:
    """Tests for validate_all_retrieval_params function."""

    def test_all_valid(self):
        """Test all valid parameters."""
        result = validate_all_retrieval_params(
            top_k_files=50,
            min_candidate_score=2,
            timeout_seconds=15.0,
            budget_tokens=5000,
        )
        assert result["top_k_files"] == 50
        assert result["min_candidate_score"] == 2
        assert result["timeout_seconds"] == 15.0
        assert result["budget_tokens"] == 5000

    def test_partial_valid(self):
        """Test partial valid parameters."""
        result = validate_all_retrieval_params(top_k_files=50)
        assert result["top_k_files"] == 50
        assert "min_candidate_score" not in result

    def test_none_values(self):
        """Test all None values returns empty dict."""
        result = validate_all_retrieval_params()
        assert result == {}

    def test_mixed_valid_invalid(self):
        """Test mixed valid and invalid parameters."""
        with pytest.raises(ParameterValidationError) as exc_info:
            validate_all_retrieval_params(
                top_k_files=50,
                timeout_seconds=0,  # Invalid
            )
        assert "timeout-seconds" in str(exc_info.value)


class TestErrorMessage:
    """Tests for ErrorMessage class."""

    def test_missing_required(self):
        """Test missing required parameter message."""
        msg = ErrorMessage.missing_required("query", "Provide a query string")
        assert "--query" in msg
        assert "query string" in msg

    def test_invalid_value(self):
        """Test invalid value message."""
        msg = ErrorMessage.invalid_value("top-k", "Value out of range", "1 to 100")
        assert "--top-k" in msg
        assert "out of range" in msg
        assert "1 to 100" in msg

    def test_invalid_choice(self):
        """Test invalid choice message."""
        msg = ErrorMessage.invalid_choice("preset", "invalid", ["balanced", "precision"])
        assert "--preset" in msg
        assert "invalid" in msg
        assert "balanced" in msg

    def test_file_not_found(self):
        """Test file not found message."""
        msg = ErrorMessage.file_not_found("/path/to/file.txt", "Check the path")
        assert "file.txt" in msg
        assert "Check the path" in msg

    def test_directory_not_found(self):
        """Test directory not found message."""
        msg = ErrorMessage.directory_not_found("/path/to/dir", "Create the directory")
        assert "dir" in msg
        assert "Create the directory" in msg

    def test_command_failed(self):
        """Test command failed message."""
        msg = ErrorMessage.command_failed("git status", "Permission denied")
        assert "git status" in msg
        assert "Permission denied" in msg


class TestHelpExamples:
    """Tests for HelpExamples class."""

    def test_get_plan_examples(self):
        """Test getting plan examples."""
        examples = HelpExamples.get_examples("plan")
        assert "ace-lite plan" in examples

    def test_get_doctor_examples(self):
        """Test getting doctor examples."""
        examples = HelpExamples.get_examples("doctor")
        assert "ace-lite doctor" in examples

    def test_get_unknown_command_examples(self):
        """Test getting examples for unknown command returns base examples."""
        examples = HelpExamples.get_examples("unknown")
        assert examples == HelpExamples.BASE_EXAMPLES

    def test_plan_examples_content(self):
        """Test plan examples content."""
        examples = HelpExamples.PLAN_EXAMPLES
        assert "--query" in examples
        assert "--top-k-files" in examples

    def test_doctor_examples_content(self):
        """Test doctor examples content."""
        examples = HelpExamples.DOCTOR_EXAMPLES
        assert "--fast" in examples
        assert "--root" in examples


class TestOutputFormatter:
    """Tests for OutputFormatter class."""

    def test_format_json(self):
        """Test JSON formatting."""
        data = {"key": "value", "number": 42}
        result = OutputFormatter.format_json(data)
        assert '"key"' in result
        assert '"value"' in result

    def test_format_table_empty(self):
        """Test table formatting with empty data."""
        result = OutputFormatter.format_table([])
        assert result == "(empty)"

    def test_format_table_with_data(self):
        """Test table formatting with data."""
        data = [
            {"name": "test", "status": "ok"},
            {"name": "demo", "status": "fail"},
        ]
        result = OutputFormatter.format_table(data)
        assert "name" in result
        assert "status" in result

    def test_format_table_with_columns(self):
        """Test table formatting with specific columns."""
        data = [{"name": "test", "status": "ok", "extra": "x"}]
        result = OutputFormatter.format_table(data, columns=["name", "status"])
        assert "name" in result
        assert "status" in result
        assert "extra" not in result

    def test_format_key_value_nested(self):
        """Test key-value formatting with nested dicts."""
        data = {"outer": {"inner": "value"}}
        result = OutputFormatter.format_key_value(data)
        assert "outer:" in result
        assert "inner:" in result

    def test_format_doctor_table(self):
        """Test doctor table formatting."""
        payload = {
            "ok": True,
            "degraded_reason_codes": [],
            "cache": {"ok": True},
            "git": {"ok": True},
            "version_sync": {"ok": True},
            "integration": {"ok": True},
        }
        result = OutputFormatter.format_doctor_table(payload)
        assert "OK" in result

    def test_format_doctor_table_degraded(self):
        """Test doctor table formatting with degraded status."""
        payload = {
            "ok": False,
            "degraded_reason_codes": ["git_unavailable"],
            "cache": {"ok": True},
            "git": {"ok": False, "reason": "git_unavailable", "recommendations": ["Install git"]},
            "version_sync": {"ok": True},
            "integration": {"ok": True},
        }
        result = OutputFormatter.format_doctor_table(payload)
        assert "DEGRADED" in result
        assert "git_unavailable" in result
