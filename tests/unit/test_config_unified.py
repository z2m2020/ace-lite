"""Unit tests for config_unified module.

Tests verify the unified configuration system (QO-2103/QO-2104).
"""

from __future__ import annotations

import os
import pytest

from ace_lite.config_unified import (
    ConfigKeys,
    DefaultConfig,
    ConfigLoader,
    UnifiedConfig,
    get_global_config,
    set_global_config,
    reset_global_config,
    LegacyConfigAdapter,
)


class TestConfigKeys:
    """Tests for configuration key constants."""

    def test_keys_defined(self):
        """Test that all configuration keys are defined."""
        assert ConfigKeys.TOP_K == "top_k"
        assert ConfigKeys.BUDGET_TOKENS == "budget_tokens"
        assert ConfigKeys.RANKING_PROFILE == "ranking_profile"
        assert ConfigKeys.LANGUAGE == "language"
        assert ConfigKeys.ROOT_PATH == "root_path"
        assert ConfigKeys.LOG_LEVEL == "log_level"


class TestDefaultConfig:
    """Tests for default configuration values."""

    def test_default_values(self):
        """Test default configuration values."""
        defaults = DefaultConfig()

        assert defaults.TOP_K == 8
        assert defaults.BUDGET_TOKENS == 800
        assert defaults.RANKING_PROFILE == "heuristic"
        assert defaults.LANGUAGE is None
        assert defaults.EMBEDDING_ENABLED is True
        assert defaults.USE_ORJSON is False

    def test_frozen(self):
        """Test that DefaultConfig is frozen."""
        defaults = DefaultConfig()
        with pytest.raises(AttributeError):
            defaults.TOP_K = 10  # type: ignore


class TestConfigLoader:
    """Tests for ConfigLoader."""

    def test_load_defaults(self):
        """Test loading with defaults only."""
        loader = ConfigLoader(defaults={"key": "value"})
        config = loader.load()

        assert config["key"] == "value"

    def test_load_with_project_config(self):
        """Test loading with project configuration."""
        loader = ConfigLoader(
            defaults={"key": "default"},
            project_config={"key": "project"},
        )
        config = loader.load()

        # Project config overrides defaults
        assert config["key"] == "project"

    def test_load_with_runtime_config(self):
        """Test loading with runtime configuration."""
        loader = ConfigLoader(
            defaults={"key": "default"},
            runtime_config={"key": "runtime"},
        )
        config = loader.load()

        # Runtime config overrides defaults
        assert config["key"] == "runtime"

    def test_load_with_env_vars(self, monkeypatch):
        """Test loading with environment variables."""
        monkeypatch.setenv("ACE_LITE_TOP_K", "20")
        monkeypatch.setenv("ACE_LITE_MY_CUSTOM_KEY", "custom_value")

        loader = ConfigLoader(defaults={"top_k": 8})
        config = loader.load()

        # Environment variables override defaults
        assert config["top_k"] == 20
        assert config["my_custom_key"] == "custom_value"

    def test_env_var_parsing_boolean(self, monkeypatch):
        """Test parsing boolean environment variables."""
        monkeypatch.setenv("ACE_LITE_FLAG_TRUE", "true")
        monkeypatch.setenv("ACE_LITE_FLAG_FALSE", "false")

        loader = ConfigLoader()
        config = loader.load()

        assert config["flag_true"] is True
        assert config["flag_false"] is False

    def test_env_var_parsing_integer(self, monkeypatch):
        """Test parsing integer environment variables."""
        monkeypatch.setenv("ACE_LITE_COUNT", "42")

        loader = ConfigLoader()
        config = loader.load()

        assert config["count"] == 42

    def test_priority_order(self, monkeypatch):
        """Test that priority order is correct."""
        monkeypatch.setenv("ACE_LITE_KEY", "env")
        monkeypatch.setenv("ACE_LITE_OTHER", "env")

        loader = ConfigLoader(
            defaults={"key": "default", "other": "default"},
            project_config={"key": "project", "other": "project"},
            runtime_config={"key": "runtime"},
        )
        config = loader.load()

        # Priority: env > runtime > project > defaults
        assert config["key"] == "env"
        assert config["other"] == "env"


class TestUnifiedConfig:
    """Tests for UnifiedConfig."""

    def test_initialization(self):
        """Test basic initialization."""
        config = UnifiedConfig({"key": "value"})
        assert config.get("key") == "value"

    def test_get_with_default(self):
        """Test get with default value."""
        config = UnifiedConfig({})
        assert config.get("missing", "default") == "default"

    def test_set_and_get(self):
        """Test setting and getting values."""
        config = UnifiedConfig({})
        config.set("key", "value")
        assert config.get("key") == "value"

    def test_update(self):
        """Test updating multiple values."""
        config = UnifiedConfig({})
        config.update({"a": 1, "b": 2})
        assert config.get("a") == 1
        assert config.get("b") == 2

    def test_get_int(self):
        """Test getting integer values."""
        config = UnifiedConfig({"count": 42})
        assert config.get_int("count") == 42

    def test_get_int_with_default(self):
        """Test getting integer with default."""
        config = UnifiedConfig({})
        assert config.get_int("missing", 10) == 10

    def test_get_int_from_string(self):
        """Test getting integer from string."""
        config = UnifiedConfig({"count": "42"})
        assert config.get_int("count") == 42

    def test_get_float(self):
        """Test getting float values."""
        config = UnifiedConfig({"rate": 3.14})
        assert config.get_float("rate") == 3.14

    def test_get_bool(self):
        """Test getting boolean values."""
        config = UnifiedConfig({"flag": True})
        assert config.get_bool("flag") is True

    def test_get_bool_from_string(self):
        """Test getting boolean from string."""
        config = UnifiedConfig({"flag": "true"})
        assert config.get_bool("flag") is True

    def test_get_str(self):
        """Test getting string values."""
        config = UnifiedConfig({"name": "test"})
        assert config.get_str("name") == "test"

    def test_get_list(self):
        """Test getting list values."""
        config = UnifiedConfig({"items": [1, 2, 3]})
        assert config.get_list("items") == [1, 2, 3]

    def test_get_list_from_string(self):
        """Test getting list from comma-separated string."""
        config = UnifiedConfig({"items": "a, b, c"})
        assert config.get_list("items") == ["a", "b", "c"]

    def test_get_dict(self):
        """Test getting dict values."""
        config = UnifiedConfig({"nested": {"key": "value"}})
        assert config.get_dict("nested") == {"key": "value"}

    def test_get_path(self):
        """Test getting path values."""
        from pathlib import Path

        config = UnifiedConfig({"path": "/some/path"})
        assert config.get_path("path") == Path("/some/path")

    def test_specific_properties(self):
        """Test specific configuration properties."""
        config = UnifiedConfig({
            "top_k": 10,
            "budget_tokens": 1000,
            "ranking_profile": "hybrid",
            "language": "python",
            "embedding_enabled": False,
        })

        assert config.top_k == 10
        assert config.budget_tokens == 1000
        assert config.ranking_profile == "hybrid"
        assert config.language == "python"
        assert config.embedding_enabled is False

    def test_specific_properties_defaults(self):
        """Test specific configuration properties with defaults."""
        config = UnifiedConfig({})

        assert config.top_k == 8
        assert config.budget_tokens == 800
        assert config.ranking_profile == "heuristic"
        assert config.embedding_enabled is True

    def test_to_dict(self):
        """Test exporting configuration as dict."""
        config = UnifiedConfig({"a": 1, "b": 2})
        result = config.to_dict()

        assert isinstance(result, dict)
        assert result["a"] == 1
        assert result["b"] == 2

    def test_repr(self):
        """Test string representation."""
        config = UnifiedConfig({"a": 1})
        assert "UnifiedConfig" in repr(config)
        assert "1 keys" in repr(config)


class TestGlobalConfig:
    """Tests for global configuration."""

    def setup_method(self):
        """Reset global config before each test."""
        reset_global_config()

    def teardown_method(self):
        """Reset global config after each test."""
        reset_global_config()

    def test_get_global_config_creates_default(self):
        """Test that get_global_config creates default if not set."""
        config = get_global_config()
        assert isinstance(config, UnifiedConfig)

    def test_set_global_config(self):
        """Test setting global configuration."""
        new_config = UnifiedConfig({"custom": "value"})
        set_global_config(new_config)

        retrieved = get_global_config()
        assert retrieved is new_config
        assert retrieved.get("custom") == "value"

    def test_reset_global_config(self):
        """Test resetting global configuration."""
        set_global_config(UnifiedConfig({"key": "value"}))
        reset_global_config()

        # After reset, a new instance should be created
        config = get_global_config()
        assert isinstance(config, UnifiedConfig)


class TestLegacyConfigAdapter:
    """Tests for LegacyConfigAdapter."""

    def test_get(self):
        """Test getting value through adapter."""
        unified = UnifiedConfig({"key": "value"})
        adapter = LegacyConfigAdapter(unified)

        assert adapter.get("key") == "value"

    def test_dict_access(self):
        """Test dict-like access through adapter."""
        unified = UnifiedConfig({"key": "value"})
        adapter = LegacyConfigAdapter(unified)

        assert adapter["key"] == "value"

    def test_dict_assignment(self):
        """Test dict-like assignment through adapter."""
        unified = UnifiedConfig({})
        adapter = LegacyConfigAdapter(unified)

        adapter["key"] = "value"
        assert unified.get("key") == "value"


class TestConfigPriority:
    """Tests for configuration priority resolution."""

    def test_env_overrides_runtime(self, monkeypatch):
        """Test that env vars override runtime config."""
        monkeypatch.setenv("ACE_LITE_TEST_KEY", "from_env")

        loader = ConfigLoader(
            defaults={"test_key": "from_default"},
            runtime_config={"test_key": "from_runtime"},
        )
        config = loader.load()

        assert config["test_key"] == "from_env"

    def test_runtime_overrides_project(self):
        """Test that runtime config overrides project config."""
        loader = ConfigLoader(
            defaults={"key": "default"},
            project_config={"key": "project"},
            runtime_config={"key": "runtime"},
        )
        config = loader.load()

        assert config["key"] == "runtime"

    def test_project_overrides_defaults(self):
        """Test that project config overrides defaults."""
        loader = ConfigLoader(
            defaults={"key": "default"},
            project_config={"key": "project"},
        )
        config = loader.load()

        assert config["key"] == "project"
