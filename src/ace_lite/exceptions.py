"""Exception Handling Utilities for ACE-Lite

This module provides structured exception handling utilities for
categorizing and handling exceptions by risk level.

PRD-91 QO-1104: High-Risk Exception Classification

Risk Level Definitions:
- Critical: Filesystem corruption, memory leaks, data integrity
- Warning: Potential data loss, performance degradation
- Info: Logging only, does not affect main flow

Design Principles:
1. Prefer specific exception types over broad catches
2. Use context managers for resource cleanup
3. Structured error payloads for diagnostics
4. Fail-open for non-critical operations
"""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)


# =============================================================================
# Risk Levels
# =============================================================================


class ExceptionRiskLevel(Enum):
    """Risk levels for exception handling.

    Supports comparison operators for threshold-based decisions.
    Order: INFO < WARNING < CRITICAL
    """

    # Critical: May cause data corruption, security issues, or crashes
    CRITICAL = 3

    # Warning: May cause data loss or performance issues
    WARNING = 2

    # Info: Logging only, recoverable
    INFO = 1

    def __ge__(self, other: "ExceptionRiskLevel") -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, ExceptionRiskLevel):
            return NotImplemented
        return self.value >= other.value

    def __gt__(self, other: "ExceptionRiskLevel") -> bool:
        """Greater than comparison."""
        if not isinstance(other, ExceptionRiskLevel):
            return NotImplemented
        return self.value > other.value

    def __le__(self, other: "ExceptionRiskLevel") -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, ExceptionRiskLevel):
            return NotImplemented
        return self.value <= other.value

    def __lt__(self, other: "ExceptionRiskLevel") -> bool:
        """Less than comparison."""
        if not isinstance(other, ExceptionRiskLevel):
            return NotImplemented
        return self.value < other.value


# =============================================================================
# Custom Exception Classes
# =============================================================================


class ACELiteError(Exception):
    """Base exception for ACE-Lite errors."""

    def __init__(
        self,
        message: str,
        *,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.context = context or {}


class CacheError(ACELiteError):
    """Cache-related errors."""

    pass


class ParseError(ACELiteError):
    """Parsing/serialization errors."""

    pass


class ConfigError(ACELiteError):
    """Configuration errors."""

    pass


class PathError(ACELiteError):
    """Path/filesystem-related errors."""

    pass


class StageContractError(ACELiteError):
    """Raised when a stage output violates its contract.

    This exception is raised by the pipeline validation system
    when a stage's output does not match the expected schema.
    """

    def __init__(
        self,
        message: str,
        *,
        stage: str = "",
        error_code: str = "",
        reason: str = "",
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message, context=context)
        self.stage = stage
        self.error_code = error_code
        self.reason = reason
        self.message = message


# =============================================================================
# Error Payloads
# =============================================================================


@dataclass
class ErrorPayload:
    """Structured error payload for diagnostics."""

    error_type: str
    message: str
    risk_level: str
    recoverable: bool
    details: dict[str, Any] = field(default_factory=dict)
    traceback_summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "risk_level": self.risk_level,
            "recoverable": self.recoverable,
            "details": self.details,
            "traceback_summary": self.traceback_summary,
        }


# =============================================================================
# Risk Assessment
# =============================================================================


def assess_exception_risk(exc: Exception) -> ExceptionRiskLevel:
    """Assess the risk level of an exception.

    Args:
        exc: The exception to assess

    Returns:
        Risk level based on exception type
    """
    exc_type = type(exc).__name__

    # Critical exceptions - data corruption risk
    critical_exceptions = {
        "PermissionError",
        "OSError",  # May indicate filesystem issues
        "MemoryError",
        "SystemError",
        "RecursionError",
    }

    # Warning exceptions - data loss or performance risk
    warning_exceptions = {
        "IOError",
        "ValueError",
        "KeyError",
        "IndexError",
        "TypeError",
        "AttributeError",
    }

    if exc_type in critical_exceptions:
        return ExceptionRiskLevel.CRITICAL
    elif exc_type in warning_exceptions:
        return ExceptionRiskLevel.WARNING
    else:
        return ExceptionRiskLevel.INFO


# =============================================================================
# Exception Handlers
# =============================================================================


@dataclass
class ExceptionHandlerConfig:
    """Configuration for exception handling."""

    # Risk level threshold for logging
    log_threshold: ExceptionRiskLevel = ExceptionRiskLevel.INFO

    # Risk level threshold for re-raising
    reraise_threshold: ExceptionRiskLevel = ExceptionRiskLevel.CRITICAL

    # Include traceback in logs
    include_traceback: bool = False

    # Default value when exception is caught and not re-raised
    default_value: Any = None


def handle_exception(
    exc: Exception,
    *,
    context: dict[str, Any] | None = None,
    config: ExceptionHandlerConfig | None = None,
    operation_name: str = "operation",
) -> Any:
    """Handle an exception based on risk assessment.

    Args:
        exc: The exception to handle
        context: Additional context for logging
        config: Handler configuration
        operation_name: Name of the operation for logging

    Returns:
        Default value if exception is handled (not re-raised)
    """
    config = config or ExceptionHandlerConfig()
    context = context or {}
    risk_level = assess_exception_risk(exc)

    # Build error payload
    error_payload = ErrorPayload(
        error_type=type(exc).__name__,
        message=str(exc),
        risk_level=risk_level.name,
        recoverable=risk_level != ExceptionRiskLevel.CRITICAL,
        details=context,
    )

    # Include traceback if configured and level warrants it
    if config.include_traceback and risk_level >= config.log_threshold:
        error_payload.traceback_summary = _summarize_traceback()

    # Log based on risk level
    _log_exception(exc, risk_level, operation_name, error_payload)

    # Re-raise if above threshold
    if risk_level >= config.reraise_threshold:
        raise exc  # Explicit re-raise with original exception

    return config.default_value


def _log_exception(
    exc: Exception,
    risk_level: ExceptionRiskLevel,
    operation_name: str,
    payload: ErrorPayload,
) -> None:
    """Log exception based on risk level."""
    log_message = f"Exception in {operation_name}: {exc} (risk={risk_level.name})"

    if risk_level == ExceptionRiskLevel.CRITICAL:
        logger.error(log_message, exc_info=True)
    elif risk_level == ExceptionRiskLevel.WARNING:
        logger.warning(log_message, exc_info=False)
    else:
        logger.debug(log_message, exc_info=False)


def _summarize_traceback() -> str:
    """Get a summary of the current traceback."""
    tb = traceback.format_exc()
    # Limit to first few lines
    lines = tb.split("\n")
    return "\n".join(lines[:5])


# =============================================================================
# Decorators for Exception Handling
# =============================================================================


T = TypeVar("T")


def safe_execute(
    *,
    default: T,
    context: dict[str, Any] | None = None,
    operation_name: str = "function",
    log_errors: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for safe function execution.

    Args:
        default: Default value to return on exception
        context: Additional context for logging
        operation_name: Name of the operation for logging
        log_errors: Whether to log errors

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                if log_errors:
                    ctx = {**(context or {}), "function": func.__name__}
                    handle_exception(
                        exc,
                        context=ctx,
                        config=ExceptionHandlerConfig(
                            default_value=default,
                            log_threshold=ExceptionRiskLevel.INFO,
                            reraise_threshold=ExceptionRiskLevel.CRITICAL,
                        ),
                        operation_name=operation_name,
                    )
                return default

        return wrapper

    return decorator


def safe_execute_with_result(
    *,
    default: Any = None,
    context: dict[str, Any] | None = None,
    operation_name: str = "function",
) -> Callable[[Callable[..., Any]], Callable[..., tuple[Any, ErrorPayload | None]]]:
    """Decorator that returns (result, error_payload) tuple.

    Useful when you need to know if an exception occurred without re-raising.

    Args:
        default: Default value to return on exception
        context: Additional context for logging
        operation_name: Name of the operation for logging

    Returns:
        Decorated function that returns (result, error) tuple
    """

    def decorator(
        func: Callable[..., Any],
    ) -> Callable[..., tuple[Any, ErrorPayload | None]]:
        def wrapper(*args: Any, **kwargs: Any) -> tuple[Any, ErrorPayload | None]:
            try:
                return func(*args, **kwargs), None
            except Exception as exc:
                ctx = {**(context or {}), "function": func.__name__}
                risk_level = assess_exception_risk(exc)
                error_payload = ErrorPayload(
                    error_type=type(exc).__name__,
                    message=str(exc),
                    risk_level=risk_level.name,
                    recoverable=risk_level != ExceptionRiskLevel.CRITICAL,
                    details=ctx,
                    traceback_summary=_summarize_traceback(),
                )
                logger.warning(
                    f"Exception in {operation_name}: {exc}",
                    exc_info=False,
                )
                return default, error_payload

        return wrapper

    return decorator


# =============================================================================
# Context Managers
# =============================================================================


class ExceptionContext:
    """Context manager for exception handling with risk assessment."""

    def __init__(
        self,
        *,
        operation_name: str = "operation",
        default: Any = None,
        reraise_on_critical: bool = True,
    ):
        self.operation_name = operation_name
        self.default = default
        self.reraise_on_critical = reraise_on_critical
        self.error_payload: ErrorPayload | None = None
        self._exc_info: tuple[Any, Any, Any] | None = None

    def __enter__(self) -> "ExceptionContext":
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        if exc_val is None:
            return True  # No exception

        risk_level = assess_exception_risk(exc_val)
        self._exc_info = (exc_type, exc_val, exc_tb)

        self.error_payload = ErrorPayload(
            error_type=type(exc_val).__name__,
            message=str(exc_val),
            risk_level=risk_level.name,
            recoverable=risk_level != ExceptionRiskLevel.CRITICAL,
            details={"operation": self.operation_name},
            traceback_summary=traceback.format_exception(
                exc_type, exc_val, exc_tb
            )[:500] if exc_tb else None,
        )

        _log_exception(exc_val, risk_level, self.operation_name, self.error_payload)

        if risk_level == ExceptionRiskLevel.CRITICAL and self.reraise_on_critical:
            return False  # Re-raise

        return True  # Suppress


# =============================================================================
# Specific Exception Handlers
# =============================================================================


def safe_int_parse(
    value: Any,
    default: int = 0,
    *,
    context: dict[str, Any] | None = None,
) -> int:
    """Safely parse an integer value.

    This is a common operation that warrants its own helper.
    """
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        pass
    return default


def safe_float_parse(
    value: Any,
    default: float = 0.0,
    *,
    context: dict[str, Any] | None = None,
) -> float:
    """Safely parse a float value."""
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    return default


def safe_json_parse(
    text: str,
    default: Any = None,
    *,
    context: dict[str, Any] | None = None,
) -> Any:
    """Safely parse JSON text."""
    import json

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.debug(f"JSON parse error: {exc}")
        return default


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "ExceptionRiskLevel",
    "ACELiteError",
    "CacheError",
    "ParseError",
    "ConfigError",
    "PathError",
    "StageContractError",
    "ErrorPayload",
    "ExceptionHandlerConfig",
    "assess_exception_risk",
    "handle_exception",
    "safe_execute",
    "safe_execute_with_result",
    "ExceptionContext",
    "safe_int_parse",
    "safe_float_parse",
    "safe_json_parse",
]
