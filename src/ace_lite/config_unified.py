"""Unified Configuration Module for ACE-Lite

This module provides a single source of truth for configuration
management, eliminating the dual-track configuration system.

PRD-91 QO-2103/QO-2104: Config Single Source of Truth

Key improvements:
1. Unified configuration access interface
2. Type-safe configuration getters
3. Validation and default values
4. Environment variable support
5. Backward compatibility with existing configs
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# =============================================================================
# Configuration Sources (Priority Order)
# =============================================================================
#
# 1. Environment Variables (highest priority)
# 2. Runtime Configuration (passed at runtime)
# 3. Project Configuration (.aceignore, pyproject.toml)
# 4. Global Configuration (~/.ace-lite/config.toml)
# 5. Default Values (lowest priority)
# =============================================================================


# =============================================================================
# Configuration Keys
# =============================================================================


class ConfigKeys:
    """Standard configuration key names."""

    # General
    SCHEMA_VERSION = "schema_version"
    LOG_LEVEL = "log_level"
    VERBOSE = "verbose"

    # Paths
    ROOT_PATH = "root_path"
    CACHE_PATH = "cache_path"
    SKILLS_DIR = "skills_dir"
    MEMORY_DB_PATH = "memory_db_path"

    # Retrieval
    TOP_K = "top_k"
    BUDGET_TOKENS = "budget_tokens"
    RANKING_PROFILE = "ranking_profile"
    SIGNAL_WEIGHTS = "signal_weights"

    # Language
    LANGUAGE = "language"

    # Stage Control
    SKIP_STAGES = "skip_stages"
    FORCE_STAGES = "force_stages"

    # Experimental
    USE_ORJSON = "use_orjson"
    USE_MULTIPROCESSING = "use_multiprocessing"

    # Feature Flags
    EMBEDDING_ENABLED = "embedding_enabled"
    COCHANGE_ENABLED = "cochange_enabled"
    REPOMAP_ENABLED = "repomap_enabled"

    # MCP
    MCP_PLUGINS = "mcp_plugins"
    MCP_SERVER_URL = "mcp_server_url"


# =============================================================================
# Default Values
# =============================================================================


@dataclass(frozen=True)
class DefaultConfig:
    """Default configuration values."""

    # Retrieval defaults
    TOP_K: int = 8
    BUDGET_TOKENS: int = 800
    RANKING_PROFILE: str = "heuristic"
    LANGUAGE: str | None = None

    # Feature defaults
    EMBEDDING_ENABLED: bool = True
    COCHANGE_ENABLED: bool = False
    REPOMAP_ENABLED: bool = True

    # Performance defaults
    USE_ORJSON: bool = False
    USE_MULTIPROCESSING: bool = False

    # Logging defaults
    LOG_LEVEL: str = "INFO"
    VERBOSE: bool = False

    # Cache defaults
    CACHE_MAX_ENTRIES: int = 96
    CACHE_TTL_SECONDS: int = 3600

    # Memory defaults
    MEMORY_NAMESPACE: str = "default"
    MEMORY_DB_ENABLED: bool = True

    # Stage defaults
    PIPELINE_ORDER: tuple[str, ...] = (
        "prep",
        "index",
        "repomap",
        "retrieval",
        "rerank",
        "report",
    )


# =============================================================================
# Configuration Loader
# =============================================================================


@dataclass
class ConfigLoader:
    """Configuration loader with priority-based resolution.

    Loads configuration from multiple sources and resolves
    conflicts based on priority order.
    """

    # Base defaults
    defaults: dict[str, Any] = field(default_factory=dict)

    # Project config (from .aceignore, pyproject.toml)
    project_config: dict[str, Any] = field(default_factory=dict)

    # Runtime config (passed programmatically)
    runtime_config: dict[str, Any] = field(default_factory=dict)

    # Environment variables
    env_prefix: str = "ACE_LITE_"

    def load(self) -> dict[str, Any]:
        """Load configuration from all sources.

        Returns:
            Merged configuration dict
        """
        config: dict[str, Any] = {}

        # 1. Start with defaults
        config.update(self.defaults)

        # 2. Apply project config
        config.update(self.project_config)

        # 3. Apply runtime config
        config.update(self.runtime_config)

        # 4. Apply environment variables (highest priority)
        config.update(self._load_env_vars())

        return config

    def _load_env_vars(self) -> dict[str, Any]:
        """Load configuration from environment variables."""
        env_config: dict[str, Any] = {}

        for key, value in os.environ.items():
            if not key.startswith(self.env_prefix):
                continue

            # Convert ACE_LITE_TOP_K -> top_k
            config_key = key[len(self.env_prefix) :].lower()

            # Parse value type
            parsed_value = self._parse_env_value(value)
            env_config[config_key] = parsed_value

        return env_config

    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value to appropriate type."""
        # Boolean
        if value.lower() in ("true", "1", "yes", "on"):
            return True
        if value.lower() in ("false", "0", "no", "off"):
            return False

        # Integer
        try:
            return int(value)
        except ValueError:
            pass

        # Float
        try:
            return float(value)
        except ValueError:
            pass

        # String (default)
        return value


# =============================================================================
# Unified Configuration Access
# =============================================================================


class UnifiedConfig:
    """Unified configuration access class.

    Provides type-safe access to configuration values with
    validation and default values.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize with configuration dict.

        Args:
            config: Optional configuration dict
        """
        if config is None:
            loader = ConfigLoader(
                defaults=self._get_default_config(),
            )
            config = loader.load()

        self._config = config

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration values."""
        defaults = DefaultConfig()
        return {
            ConfigKeys.TOP_K: defaults.TOP_K,
            ConfigKeys.BUDGET_TOKENS: defaults.BUDGET_TOKENS,
            ConfigKeys.RANKING_PROFILE: defaults.RANKING_PROFILE,
            ConfigKeys.LANGUAGE: defaults.LANGUAGE,
            ConfigKeys.EMBEDDING_ENABLED: defaults.EMBEDDING_ENABLED,
            ConfigKeys.COCHANGE_ENABLED: defaults.COCHANGE_ENABLED,
            ConfigKeys.REPOMAP_ENABLED: defaults.REPOMAP_ENABLED,
            ConfigKeys.USE_ORJSON: defaults.USE_ORJSON,
            ConfigKeys.USE_MULTIPROCESSING: defaults.USE_MULTIPROCESSING,
            ConfigKeys.LOG_LEVEL: defaults.LOG_LEVEL,
            ConfigKeys.VERBOSE: defaults.VERBOSE,
        }

    # ------------------------------------------------------------------
    # Generic Accessors
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.

        Args:
            key: Configuration key
            value: Value to set
        """
        self._config[key] = value

    def update(self, updates: dict[str, Any]) -> None:
        """Update multiple configuration values.

        Args:
            updates: Dict of key-value pairs to update
        """
        self._config.update(updates)

    # ------------------------------------------------------------------
    # Typed Accessors
    # ------------------------------------------------------------------

    def get_int(self, key: str, default: int = 0) -> int:
        """Get an integer configuration value."""
        value = self._config.get(key, default)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return default
        return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get a float configuration value."""
        value = self._config.get(key, default)
        if isinstance(value, (int, float)):
            return float(value)
        return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean configuration value."""
        value = self._config.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return default

    def get_str(self, key: str, default: str = "") -> str:
        """Get a string configuration value."""
        return str(self._config.get(key, default))

    def get_list(self, key: str, default: list | None = None) -> list:
        """Get a list configuration value."""
        if default is None:
            default = []
        value = self._config.get(key, default)
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [v.strip() for v in value.split(",")]
        return default

    def get_dict(self, key: str, default: dict | None = None) -> dict:
        """Get a dict configuration value."""
        if default is None:
            default = {}
        value = self._config.get(key, default)
        if isinstance(value, dict):
            return value
        return default

    def get_path(self, key: str, default: str = "") -> Path:
        """Get a path configuration value."""
        value = self._config.get(key, default)
        return Path(value) if value else Path(default)

    # ------------------------------------------------------------------
    # Specific Configuration Getters
    # ------------------------------------------------------------------

    @property
    def top_k(self) -> int:
        """Get the top K value for retrieval."""
        return self.get_int(ConfigKeys.TOP_K, DefaultConfig.TOP_K)

    @property
    def budget_tokens(self) -> int:
        """Get the budget tokens value."""
        return self.get_int(ConfigKeys.BUDGET_TOKENS, DefaultConfig.BUDGET_TOKENS)

    @property
    def ranking_profile(self) -> str:
        """Get the ranking profile."""
        return self.get_str(ConfigKeys.RANKING_PROFILE, DefaultConfig.RANKING_PROFILE)

    @property
    def language(self) -> str | None:
        """Get the language filter."""
        value = self.get(ConfigKeys.LANGUAGE, DefaultConfig.LANGUAGE)
        return value if isinstance(value, str) else None

    @property
    def embedding_enabled(self) -> bool:
        """Check if embedding is enabled."""
        return self.get_bool(ConfigKeys.EMBEDDING_ENABLED, DefaultConfig.EMBEDDING_ENABLED)

    @property
    def repomap_enabled(self) -> bool:
        """Check if repomap is enabled."""
        return self.get_bool(ConfigKeys.REPOMAP_ENABLED, DefaultConfig.REPOMAP_ENABLED)

    @property
    def use_orjson(self) -> bool:
        """Check if orjson should be used."""
        return self.get_bool(ConfigKeys.USE_ORJSON, DefaultConfig.USE_ORJSON)

    @property
    def use_multiprocessing(self) -> bool:
        """Check if multiprocessing should be used."""
        return self.get_bool(ConfigKeys.USE_MULTIPROCESSING, DefaultConfig.USE_MULTIPROCESSING)

    @property
    def log_level(self) -> str:
        """Get the log level."""
        return self.get_str(ConfigKeys.LOG_LEVEL, DefaultConfig.LOG_LEVEL)

    @property
    def verbose(self) -> bool:
        """Check if verbose mode is enabled."""
        return self.get_bool(ConfigKeys.VERBOSE, DefaultConfig.VERBOSE)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Export configuration as dict."""
        return dict(self._config)

    def __repr__(self) -> str:
        """String representation."""
        return f"UnifiedConfig({len(self._config)} keys)"


# =============================================================================
# Global Configuration Instance
# =============================================================================

_global_config: UnifiedConfig | None = None


def get_global_config() -> UnifiedConfig:
    """Get the global configuration instance.

    Returns:
        The global UnifiedConfig instance
    """
    global _global_config
    if _global_config is None:
        _global_config = UnifiedConfig()
    return _global_config


def set_global_config(config: UnifiedConfig) -> None:
    """Set the global configuration instance.

    Args:
        config: The UnifiedConfig to set as global
    """
    global _global_config
    _global_config = config


def reset_global_config() -> None:
    """Reset the global configuration instance."""
    global _global_config
    _global_config = None


# =============================================================================
# Backward Compatibility Layer
# =============================================================================


class LegacyConfigAdapter:
    """Adapter for legacy configuration access.

    Provides backward compatibility with existing code
    that uses the old dual-track configuration system.
    """

    def __init__(self, unified: UnifiedConfig):
        self._unified = unified

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value (legacy interface)."""
        return self._unified.get(key, default)

    def __getitem__(self, key: str) -> Any:
        """Get a configuration value using dict-like access."""
        return self._unified.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Set a configuration value using dict-like access."""
        self._unified.set(key, value)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "ConfigKeys",
    "ConfigLoader",
    "DefaultConfig",
    "LegacyConfigAdapter",
    "UnifiedConfig",
    "get_global_config",
    "reset_global_config",
    "set_global_config",
]
