"""Domain exceptions for ace-lite-engine.

This module defines focused exception classes for different failure modes.
These exceptions preserve context and enable better error handling.

Note: Argument validation errors (e.g., invalid parameter values) should
continue to raise ValueError. Domain exceptions are for runtime/semantic failures.
"""

from __future__ import annotations

from typing import Any


class AceLiteException(Exception):
    """Base exception for all ace-lite-engine errors.

    Attributes:
        message: Human-readable error description.
        context: Additional context for debugging (optional).
        stage: Pipeline stage where error occurred (optional).
    """

    def __init__(
        self,
        message: str,
        *,
        context: dict[str, Any] | None = None,
        stage: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.stage = stage

    def __str__(self) -> str:
        parts = [self.message]
        if self.stage:
            parts.append(f"stage={self.stage}")
        if self.context:
            parts.append(f"context={self.context}")
        return " | ".join(parts)


class PipelineError(AceLiteException):
    """Error during pipeline execution.

    Raised when a stage fails to execute or produces invalid output.
    """

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        cause: Exception | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, context=context, stage=stage)
        self.cause = cause

    def __str__(self) -> str:
        base = super().__str__()
        if self.cause:
            base += f" | cause={self.cause.__class__.__name__}: {self.cause}"
        return base


class StageContractError(AceLiteException):
    """Error when a pipeline stage violates its output contract."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        error_code: str,
        reason: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, context=context, stage=stage)
        self.error_code = str(error_code or "").strip() or "stage_contract_error"
        self.reason = str(reason or "").strip() or "unknown"

    def __str__(self) -> str:
        base = super().__str__()
        return f"error_code={self.error_code} | reason={self.reason} | {base}"


class ConfigurationError(AceLiteException):
    """Error in configuration or settings.

    Raised when configuration is invalid, missing required values,
    or has incompatible settings.
    """

    def __init__(
        self,
        message: str,
        *,
        key: str | None = None,
        value: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, context=context)
        self.key = key
        self.value = value

    def __str__(self) -> str:
        base = super().__str__()
        if self.key:
            base = f"key={self.key} | " + base
        return base


class MemoryProviderError(AceLiteException):
    """Error from memory provider operations.

    Raised when memory search or fetch operations fail.
    """

    def __init__(
        self,
        message: str,
        *,
        channel: str | None = None,
        provider: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, context=context, stage="memory")
        self.channel = channel
        self.provider = provider

    def __str__(self) -> str:
        base = super().__str__()
        if self.channel:
            base += f" | channel={self.channel}"
        if self.provider:
            base += f" | provider={self.provider}"
        return base


class RankerError(AceLiteException):
    """Error during candidate ranking.

    Raised when ranking algorithms fail or produce invalid results.
    """

    def __init__(
        self,
        message: str,
        *,
        ranker: str | None = None,
        terms: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, context=context, stage="index")
        self.ranker = ranker
        self.terms = terms or []

    def __str__(self) -> str:
        base = super().__str__()
        if self.ranker:
            base += f" | ranker={self.ranker}"
        return base


class IndexBuildError(AceLiteException):
    """Error during index building or parsing.

    Raised when source code parsing fails or index cannot be built.
    """

    def __init__(
        self,
        message: str,
        *,
        path: str | None = None,
        language: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, context=context, stage="index")
        self.path = path
        self.language = language

    def __str__(self) -> str:
        base = super().__str__()
        if self.path:
            base += f" | path={self.path}"
        if self.language:
            base += f" | language={self.language}"
        return base


class PluginError(AceLiteException):
    """Error during plugin loading or execution.

    Raised when plugins fail to load, have invalid manifests,
    or cause runtime errors.
    """

    def __init__(
        self,
        message: str,
        *,
        plugin_name: str | None = None,
        slot: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, context=context)
        self.plugin_name = plugin_name
        self.slot = slot

    def __str__(self) -> str:
        base = super().__str__()
        if self.plugin_name:
            base += f" | plugin={self.plugin_name}"
        if self.slot:
            base += f" | slot={self.slot}"
        return base


__all__ = [
    "AceLiteException",
    "ConfigurationError",
    "IndexBuildError",
    "MemoryProviderError",
    "PipelineError",
    "PluginError",
    "RankerError",
    "StageContractError",
]
