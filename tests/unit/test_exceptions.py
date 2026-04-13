"""Unit tests for exceptions module.

Tests verify the exception handling utilities (QO-1104).
"""

from __future__ import annotations

import pytest

from ace_lite.exceptions import (
    ACELiteError,
    CacheError,
    ConfigError,
    ErrorPayload,
    ExceptionContext,
    ExceptionHandlerConfig,
    ExceptionRiskLevel,
    ParseError,
    PathError,
    assess_exception_risk,
    handle_exception,
    safe_execute,
    safe_execute_with_result,
    safe_float_parse,
    safe_int_parse,
    safe_json_parse,
)


class TestExceptionRiskLevel:
    """Tests for exception risk level enumeration."""

    def test_risk_levels_defined(self):
        """Test that all risk levels are defined."""
        assert ExceptionRiskLevel.CRITICAL is not None
        assert ExceptionRiskLevel.WARNING is not None
        assert ExceptionRiskLevel.INFO is not None

    def test_risk_levels_are_enum(self):
        """Test that risk levels are enum members."""
        assert isinstance(ExceptionRiskLevel.CRITICAL, ExceptionRiskLevel)


class TestAssessExceptionRisk:
    """Tests for exception risk assessment."""

    def test_critical_exceptions(self):
        """Test critical exception classification."""
        critical_exceptions = [
            PermissionError("Permission denied"),
            OSError("OS error"),
            MemoryError(),
        ]
        for exc in critical_exceptions:
            assert assess_exception_risk(exc) == ExceptionRiskLevel.CRITICAL

    def test_warning_exceptions(self):
        """Test warning exception classification."""
        warning_exceptions = [
            ValueError("Invalid value"),
            KeyError("Missing key"),
            IndexError("Index out of range"),
            TypeError("Expected str, got int"),
            AttributeError("Object has no attribute"),
        ]
        for exc in warning_exceptions:
            assert assess_exception_risk(exc) == ExceptionRiskLevel.WARNING

    def test_info_exceptions(self):
        """Test info exception classification."""
        exc = RuntimeError("General error")
        assert assess_exception_risk(exc) == ExceptionRiskLevel.INFO

    def test_custom_exceptions(self):
        """Test custom ACE-Lite exceptions."""
        custom_exceptions = [
            ACELiteError("Custom error"),
            CacheError("Cache error"),
            ParseError("Parse error"),
            ConfigError("Config error"),
            PathError("Path error"),
        ]
        for exc in custom_exceptions:
            # Custom exceptions default to INFO level
            assert assess_exception_risk(exc) == ExceptionRiskLevel.INFO


class TestErrorPayload:
    """Tests for ErrorPayload dataclass."""

    def test_creation(self):
        """Test basic creation."""
        payload = ErrorPayload(
            error_type="ValueError",
            message="Invalid value",
            risk_level="WARNING",
            recoverable=True,
            details={"key": "value"},
        )

        assert payload.error_type == "ValueError"
        assert payload.message == "Invalid value"
        assert payload.risk_level == "WARNING"
        assert payload.recoverable is True
        assert payload.details == {"key": "value"}

    def test_to_dict(self):
        """Test conversion to dictionary."""
        payload = ErrorPayload(
            error_type="ValueError",
            message="Invalid value",
            risk_level="WARNING",
            recoverable=True,
        )

        result = payload.to_dict()

        assert isinstance(result, dict)
        assert result["error_type"] == "ValueError"
        assert result["recoverable"] is True

    def test_default_details(self):
        """Test default empty details."""
        payload = ErrorPayload(
            error_type="ValueError",
            message="Invalid value",
            risk_level="WARNING",
            recoverable=True,
        )

        assert payload.details == {}


class TestExceptionHandlerConfig:
    """Tests for ExceptionHandlerConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = ExceptionHandlerConfig()

        assert config.log_threshold == ExceptionRiskLevel.INFO
        assert config.reraise_threshold == ExceptionRiskLevel.CRITICAL
        assert config.include_traceback is False
        assert config.default_value is None

    def test_custom_config(self):
        """Test custom configuration."""
        config = ExceptionHandlerConfig(
            log_threshold=ExceptionRiskLevel.WARNING,
            reraise_threshold=ExceptionRiskLevel.WARNING,
            include_traceback=True,
            default_value="fallback",
        )

        assert config.log_threshold == ExceptionRiskLevel.WARNING
        assert config.reraise_threshold == ExceptionRiskLevel.WARNING
        assert config.include_traceback is True
        assert config.default_value == "fallback"


class TestHandleException:
    """Tests for handle_exception function."""

    def test_handles_info_exception(self):
        """Test handling info-level exception."""
        exc = RuntimeError("Test error")
        config = ExceptionHandlerConfig(default_value="fallback")

        result = handle_exception(
            exc,
            context={"operation": "test"},
            config=config,
            operation_name="test_op",
        )

        assert result == "fallback"

    def test_reraises_critical_exception(self):
        """Test that critical exceptions are re-raised."""
        config = ExceptionHandlerConfig(default_value="fallback")

        # Wrap in a function that should re-raise
        def should_reraise():
            exc = PermissionError("Permission denied")
            handle_exception(
                exc,
                context={"operation": "test"},
                config=config,
            )

        with pytest.raises(PermissionError):
            should_reraise()

    def test_warning_exception_not_reraised(self):
        """Test that warning exceptions are not re-raised by default."""
        exc = ValueError("Invalid value")
        config = ExceptionHandlerConfig(default_value="fallback")

        result = handle_exception(
            exc,
            context={"operation": "test"},
            config=config,
        )

        assert result == "fallback"


class TestSafeExecuteDecorator:
    """Tests for safe_execute decorator."""

    def test_successful_execution(self):
        """Test that successful execution works normally."""
        @safe_execute(default="fallback", operation_name="add")
        def add(a: int, b: int) -> int:
            return a + b

        result = add(1, 2)
        assert result == 3

    def test_exception_returns_default(self):
        """Test that exceptions return default value."""
        @safe_execute(default=-1, operation_name="divide")
        def divide(a: int, b: int) -> float:
            return a / b

        result = divide(1, 0)  # ZeroDivisionError
        assert result == -1

    def test_custom_default_value(self):
        """Test custom default value."""
        @safe_execute(default="error", operation_name="parse")
        def parse(text: str) -> int:
            return int(text)

        result = parse("not a number")
        assert result == "error"


class TestSafeExecuteWithResultDecorator:
    """Tests for safe_execute_with_result decorator."""

    def test_successful_execution(self):
        """Test that successful execution returns result and None."""
        @safe_execute_with_result(default="fallback", operation_name="add")
        def add(a: int, b: int) -> int:
            return a + b

        result, error = add(1, 2)
        assert result == 3
        assert error is None

    def test_exception_returns_error_payload(self):
        """Test that exceptions return error payload."""
        @safe_execute_with_result(default="fallback", operation_name="divide")
        def divide(a: int, b: int) -> float:
            return a / b

        result, error = divide(1, 0)
        assert result == "fallback"
        assert error is not None
        assert error.error_type == "ZeroDivisionError"
        assert error.recoverable is True

    def test_error_payload_has_details(self):
        """Test that error payload includes details."""
        @safe_execute_with_result(default=None, operation_name="test")
        def failing_func() -> None:
            raise ValueError("test error")

        _, error = failing_func()
        assert error is not None
        assert "function" in error.details


class TestExceptionContext:
    """Tests for ExceptionContext context manager."""

    def test_no_exception(self):
        """Test that no exception returns context without error."""
        with ExceptionContext(operation_name="test") as ctx:
            result = 42

        assert ctx.error_payload is None

    def test_exception_caught(self):
        """Test that exception is caught and error payload created."""
        with ExceptionContext(operation_name="test") as ctx:
            raise ValueError("test error")

        assert ctx.error_payload is not None
        assert ctx.error_payload.error_type == "ValueError"
        assert ctx.error_payload.message == "test error"

    def test_critical_exception_reraised(self):
        """Test that critical exceptions are re-raised."""
        with pytest.raises(PermissionError):
            with ExceptionContext(operation_name="test"):
                raise PermissionError("permission denied")

    def test_custom_default(self):
        """Test custom default value."""
        with ExceptionContext(operation_name="test", default="fallback") as ctx:
            raise ValueError("test error")

        assert ctx.error_payload is not None


class TestSafeIntParse:
    """Tests for safe_int_parse function."""

    def test_valid_integer(self):
        """Test parsing valid integer."""
        assert safe_int_parse("42") == 42
        assert safe_int_parse(42) == 42

    def test_float_parsed(self):
        """Test parsing float (truncates)."""
        assert safe_int_parse(42.9) == 42

    def test_invalid_value_default(self):
        """Test invalid value returns default."""
        assert safe_int_parse("not a number") == 0
        assert safe_int_parse(None) == 0

    def test_negative_value(self):
        """Test negative value returns default."""
        assert safe_int_parse(-5) == 0

    def test_custom_default(self):
        """Test custom default value."""
        assert safe_int_parse("invalid", default=99) == 99
        assert safe_int_parse(-5, default=99) == 99


class TestSafeFloatParse:
    """Tests for safe_float_parse function."""

    def test_valid_float(self):
        """Test parsing valid float."""
        assert safe_float_parse("3.14") == 3.14
        assert safe_float_parse(3.14) == 3.14

    def test_int_parsed(self):
        """Test parsing int as float."""
        assert safe_float_parse(42) == 42.0

    def test_invalid_value_default(self):
        """Test invalid value returns default."""
        assert safe_float_parse("not a number") == 0.0
        assert safe_float_parse(None) == 0.0

    def test_custom_default(self):
        """Test custom default value."""
        assert safe_float_parse("invalid", default=99.0) == 99.0


class TestSafeJsonParse:
    """Tests for safe_json_parse function."""

    def test_valid_json(self):
        """Test parsing valid JSON."""
        result = safe_json_parse('{"key": "value"}')
        assert result == {"key": "value"}

    def test_invalid_json_default(self):
        """Test invalid JSON returns default."""
        assert safe_json_parse("not json") is None

    def test_custom_default(self):
        """Test custom default value."""
        result = safe_json_parse("not json", default={})
        assert result == {}

    def test_complex_json(self):
        """Test parsing complex JSON."""
        json_str = '{"numbers": [1, 2, 3], "nested": {"key": "value"}}'
        result = safe_json_parse(json_str)
        assert result == {"numbers": [1, 2, 3], "nested": {"key": "value"}}


class TestCustomExceptions:
    """Tests for custom exception classes."""

    def test_custom_exception_creation(self):
        """Test creating custom exceptions."""
        exc = ACELiteError("test", context={"key": "value"})
        assert str(exc) == "test"
        assert exc.context == {"key": "value"}

    def test_cache_error(self):
        """Test CacheError."""
        exc = CacheError("cache failed")
        assert isinstance(exc, ACELiteError)

    def test_parse_error(self):
        """Test ParseError."""
        exc = ParseError("parse failed")
        assert isinstance(exc, ACELiteError)

    def test_config_error(self):
        """Test ConfigError."""
        exc = ConfigError("config invalid")
        assert isinstance(exc, ACELiteError)

    def test_path_error(self):
        """Test PathError."""
        exc = PathError("path not found")
        assert isinstance(exc, ACELiteError)
