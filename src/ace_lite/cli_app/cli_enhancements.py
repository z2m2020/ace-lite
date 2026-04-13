"""CLI Enhancements for ACE-Lite

This module provides unified CLI enhancements including:
1. Parameter validation with range checking
2. Unified error message templates
3. Help examples
4. Output formatting options

PRD-91 CLI Quality Improvements
"""

from __future__ import annotations

from typing import Any

# =============================================================================
# Parameter Range Validators
# =============================================================================


class ParameterValidationError(Exception):
    """Raised when parameter validation fails."""

    def __init__(self, param_name: str, message: str, valid_range: str | None = None):
        self.param_name = param_name
        self.message = message
        self.valid_range = valid_range
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        msg = f"Invalid value for --{self.param_name}: {self.message}"
        if self.valid_range:
            msg += f"\nValid range: {self.valid_range}"
        return msg


class PARAM_RANGES:
    """Valid ranges for CLI parameters."""

    # Retrieval parameters
    TOP_K_FILES = (1, 100)
    MIN_CANDIDATE_SCORE = (0, 100)
    BUDGET_TOKENS = (100, 50000)
    TIMEOUT_SECONDS = (1, 300)
    TOP_K = (1, 1000)
    MEMORY_LIMIT = (1, 100)

    # Chunking parameters
    CHUNK_TOP_K = (1, 1000)
    CHUNK_PER_FILE_LIMIT = (1, 100)
    CHUNK_TOKEN_BUDGET = (100, 10000)
    CHUNK_SNIPPET_MAX_LINES = (1, 100)
    CHUNK_SNIPPET_MAX_CHARS = (100, 10000)

    # Cochange parameters
    COCHANGE_LOOKBACK_COMMITS = (1, 10000)
    COCHANGE_TOP_NEIGHBORS = (1, 100)
    COCHANGE_HALF_LIFE_DAYS = (0.1, 365.0)

    # Other parameters
    CACHE_TTL_SECONDS = (0, 86400 * 30)  # Up to 30 days
    MEMORY_CACHE_MAX_ENTRIES = (1, 10000)


def validate_int_param(
    name: str,
    value: int,
    min_val: int,
    max_val: int,
) -> int:
    """Validate an integer parameter is within range.

    Args:
        name: Parameter name (for error messages)
        value: Value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)

    Returns:
        The validated value

    Raises:
        ParameterValidationError: If value is out of range
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise ParameterValidationError(
            name,
            f"Expected integer, got {type(value).__name__}",
        )
    if value < min_val or value > max_val:
        raise ParameterValidationError(
            name,
            f"Value {value} is out of range",
            valid_range=f"{min_val} to {max_val}",
        )
    return value


def validate_float_param(
    name: str,
    value: float,
    min_val: float,
    max_val: float,
) -> float:
    """Validate a float parameter is within range.

    Args:
        name: Parameter name (for error messages)
        value: Value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)

    Returns:
        The validated value

    Raises:
        ParameterValidationError: If value is out of range
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ParameterValidationError(
            name,
            f"Expected number, got {type(value).__name__}",
        )
    if value < min_val or value > max_val:
        raise ParameterValidationError(
            name,
            f"Value {value} is out of range",
            valid_range=f"{min_val} to {max_val}",
        )
    return float(value)


def validate_top_k_files(value: int) -> int:
    """Validate top_k_files parameter."""
    return validate_int_param("top-k-files", value, *PARAM_RANGES.TOP_K_FILES)


def validate_min_candidate_score(value: int) -> int:
    """Validate min_candidate_score parameter."""
    return validate_int_param("min-candidate-score", value, *PARAM_RANGES.MIN_CANDIDATE_SCORE)


def validate_timeout_seconds(value: float) -> float:
    """Validate timeout_seconds parameter."""
    return validate_float_param("timeout-seconds", value, *PARAM_RANGES.TIMEOUT_SECONDS)


def validate_budget_tokens(value: int) -> int:
    """Validate budget_tokens parameter."""
    return validate_int_param("budget-tokens", value, *PARAM_RANGES.BUDGET_TOKENS)


def validate_chunk_top_k(value: int) -> int:
    """Validate chunk_top_k parameter."""
    return validate_int_param("chunk-top-k", value, *PARAM_RANGES.CHUNK_TOP_K)


def validate_chunk_per_file_limit(value: int) -> int:
    """Validate chunk_per_file_limit parameter."""
    return validate_int_param("chunk-per-file-limit", value, *PARAM_RANGES.CHUNK_PER_FILE_LIMIT)


def validate_chunk_token_budget(value: int) -> int:
    """Validate chunk_token_budget parameter."""
    return validate_int_param("chunk-token-budget", value, *PARAM_RANGES.CHUNK_TOKEN_BUDGET)


def validate_all_retrieval_params(
    *,
    top_k_files: int | None = None,
    min_candidate_score: int | None = None,
    timeout_seconds: float | None = None,
    budget_tokens: int | None = None,
) -> dict[str, Any]:
    """Validate all retrieval-related parameters at once.

    Returns a dict of validated values.
    """
    validated: dict[str, Any] = {}
    errors: list[str] = []

    if top_k_files is not None:
        try:
            validated["top_k_files"] = validate_top_k_files(top_k_files)
        except ParameterValidationError as e:
            errors.append(str(e))

    if min_candidate_score is not None:
        try:
            validated["min_candidate_score"] = validate_min_candidate_score(min_candidate_score)
        except ParameterValidationError as e:
            errors.append(str(e))

    if timeout_seconds is not None:
        try:
            validated["timeout_seconds"] = validate_timeout_seconds(timeout_seconds)
        except ParameterValidationError as e:
            errors.append(str(e))

    if budget_tokens is not None:
        try:
            validated["budget_tokens"] = validate_budget_tokens(budget_tokens)
        except ParameterValidationError as e:
            errors.append(str(e))

    if errors:
        error_msg = "Parameter validation failed:\n  - " + "\n  - ".join(errors)
        error_msg += "\n\nHint: Run 'ace-lite <command> --help' to see valid parameter ranges."
        raise ParameterValidationError("multiple", error_msg)

    return validated


# =============================================================================
# Unified Error Message Templates
# =============================================================================


class ErrorMessage:
    """Unified error message templates for CLI."""

    @staticmethod
    def missing_required(param: str, hint: str | None = None) -> str:
        """Generate error for missing required parameter."""
        msg = f"Missing required option: --{param}"
        if hint:
            msg += f"\n\nHint: {hint}"
        return msg

    @staticmethod
    def invalid_value(param: str, reason: str, valid_range: str | None = None) -> str:
        """Generate error for invalid parameter value."""
        msg = f"Invalid value for --{param}: {reason}"
        if valid_range:
            msg += f"\nValid range: {valid_range}"
        msg += "\n\nHint: See 'ace-lite <command> --help' for valid values"
        return msg

    @staticmethod
    def invalid_choice(param: str, value: str, choices: list[str]) -> str:
        """Generate error for invalid choice."""
        choices_str = ", ".join(f"'{c}'" for c in choices)
        msg = f"Invalid value '{value}' for --{param}"
        msg += f"\nValid choices: {choices_str}"
        msg += "\n\nHint: Use one of the valid choices listed above"
        return msg

    @staticmethod
    def file_not_found(path: str, hint: str | None = None) -> str:
        """Generate error for file not found."""
        msg = f"File not found: {path}"
        if hint:
            msg += f"\n\nHint: {hint}"
        return msg

    @staticmethod
    def directory_not_found(path: str, hint: str | None = None) -> str:
        """Generate error for directory not found."""
        msg = f"Directory not found: {path}"
        if hint:
            msg += f"\n\nHint: {hint}"
        return msg

    @staticmethod
    def command_failed(command: str, reason: str, hint: str | None = None) -> str:
        """Generate error for failed command."""
        msg = f"Command failed: {command}"
        msg += f"\nReason: {reason}"
        if hint:
            msg += f"\n\nHint: {hint}"
        return msg


# =============================================================================
# Help Examples
# =============================================================================


class HelpExamples:
    """Help example templates for CLI commands."""

    # Base examples that apply to all commands
    BASE_EXAMPLES = """
Examples:
  ace-lite --help                    Show this help message
  ace-lite <command> --help         Show help for specific command

See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/CONFIGURATION.md      Configuration guide
"""

    PLAN_EXAMPLES = """
Examples:
  # Basic usage
  ace-lite plan --query="implement login" --repo=myapp --root=.

  # With custom settings
  ace-lite plan --query="fix auth bug" --top-k-files=12 --timeout-seconds=30

  # Using runtime profile
  ace-lite plan --query="refactor" --runtime-profile=refactor --repo=myapp --root=.

  # Export to file
  ace-lite plan --query="..." --output-json=plan.json --repo=myapp --root=.

  # Quick mode (skip memory/skill stages)
  ace-lite plan --quick --query="quick check" --repo=myapp --root=.

See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/RETRIEVAL_PROFILES.md Retrieval profile guide
"""

    REPO_MAP_EXAMPLES = """
Examples:
  # Build RepoMap with defaults
  ace-lite repomap build --root=.

  # Specify languages
  ace-lite repomap build --root=. --languages=python,typescript

  # Custom output paths
  ace-lite repomap build --root=. --output-json=custom_map.json

See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/REPOMAP.md           RepoMap guide
"""

    INDEX_EXAMPLES = """
Examples:
  # Build index with defaults
  ace-lite index --root=.

  # Incremental index (default)
  ace-lite index --root=. --incremental

  # Full rebuild
  ace-lite index --root=. --no-incremental

See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/INDEXING.md           Indexing guide
"""

    DOCTOR_EXAMPLES = """
Examples:
  # Run full diagnostics
  ace-lite doctor --root=.

  # Fast diagnostics (skip heavy checks)
  ace-lite doctor --fast --root=.

  # With custom config
  ace-lite doctor --root=. --config-file=.ace-lite.yml

  # Check specific repo
  ace-lite doctor --root=/path/to/repo

See also:
  docs/guides/GETTING_STARTED.md    Quick start guide
  docs/guides/DIAGNOSTICS.md        Diagnostics guide
"""

    @classmethod
    def get_examples(cls, command: str) -> str:
        """Get examples for a specific command."""
        examples_map = {
            "plan": cls.PLAN_EXAMPLES,
            "repomap": cls.REPO_MAP_EXAMPLES,
            "index": cls.INDEX_EXAMPLES,
            "doctor": cls.DOCTOR_EXAMPLES,
        }
        return examples_map.get(command, cls.BASE_EXAMPLES)


# =============================================================================
# Output Formatters
# =============================================================================


class OutputFormatter:
    """Format output in different styles."""

    @staticmethod
    def format_json(data: dict[str, Any]) -> str:
        """Format data as JSON."""
        import json

        return json.dumps(data, ensure_ascii=False, indent=2)

    @staticmethod
    def format_table(data: list[dict[str, Any]], columns: list[str] | None = None) -> str:
        """Format data as ASCII table.

        Args:
            data: List of dicts to format
            columns: Optional list of columns to include

        Returns:
            ASCII table string
        """
        if not data:
            return "(empty)"

        # Determine columns
        if columns is None:
            columns = list(data[0].keys())

        # Filter data to only include specified columns
        filtered = [{k: row.get(k, "") for k in columns} for row in data]

        # Calculate column widths
        widths = {col: len(col) for col in columns}
        for row in filtered:
            for col in columns:
                val = str(row.get(col, ""))
                widths[col] = max(widths[col], len(val))

        # Build header
        header = " | ".join(col.ljust(widths[col]) for col in columns)
        separator = "-|-".join("-" * widths[col] for col in columns)

        # Build rows
        rows = []
        for row in filtered:
            rows.append(" | ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns))

        return "\n".join([header, separator, *rows])

    @staticmethod
    def format_key_value(data: dict[str, Any], indent: int = 0) -> str:
        """Format data as key-value pairs.

        Args:
            data: Dict to format
            indent: Indentation level

        Returns:
            Key-value formatted string
        """
        prefix = "  " * indent
        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(OutputFormatter.format_key_value(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}: [{len(value)} items]")
            else:
                lines.append(f"{prefix}{key}: {value}")
        return "\n".join(lines)

    @staticmethod
    def format_doctor_table(payload: dict[str, Any]) -> str:
        """Format doctor output as human-readable table.

        Args:
            payload: Doctor payload dict

        Returns:
            Formatted table string
        """
        lines = []

        # Overall status
        ok = payload.get("ok", False)
        status = "OK" if ok else "DEGRADED"
        lines.append(f"Overall Status: {status}")
        lines.append("")

        # Degraded reasons
        degraded = payload.get("degraded_reason_codes", [])
        if degraded:
            lines.append("Degraded Reasons:")
            for reason in degraded:
                lines.append(f"  - {reason}")
            lines.append("")

        # Individual checks
        lines.append("Component Checks:")
        lines.append("-" * 50)

        checks = [
            ("cache", payload.get("cache", {})),
            ("git", payload.get("git", {})),
            ("version_sync", payload.get("version_sync", {})),
            ("integration", payload.get("integration", {})),
        ]

        for name, check_data in checks:
            if not isinstance(check_data, dict):
                continue
            check_ok = check_data.get("ok", False)
            check_status = "OK" if check_ok else "FAIL"
            lines.append(f"  {name:20} {check_status}")

            # Add reason if not ok
            if not check_ok:
                reason = check_data.get("reason", "Unknown error")
                lines.append(f"    Reason: {reason}")

                # Add recommendations
                recs = check_data.get("recommendations", [])
                if recs:
                    for rec in recs[:2]:  # Show max 2 recommendations
                        lines.append(f"    Hint: {rec}")

        return "\n".join(lines)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "PARAM_RANGES",
    "ErrorMessage",
    "HelpExamples",
    "OutputFormatter",
    "ParameterValidationError",
    "validate_all_retrieval_params",
    "validate_budget_tokens",
    "validate_chunk_per_file_limit",
    "validate_chunk_token_budget",
    "validate_chunk_top_k",
    "validate_float_param",
    "validate_int_param",
    "validate_min_candidate_score",
    "validate_timeout_seconds",
    "validate_top_k_files",
]
