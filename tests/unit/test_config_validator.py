from __future__ import annotations

from ace_lite.config_validator import validate_orchestrator_config


def test_validate_orchestrator_config_returns_clean_for_defaults() -> None:
    assert validate_orchestrator_config({}) == []


def test_validate_orchestrator_config_flags_inactive_plugin_remote_settings() -> None:
    warnings = validate_orchestrator_config(
        {
                "plugins": {
                    "enabled": False,
                    "remote_slot_allowlist": ["observability.mcp_plugins"],
                    "remote_slot_policy_mode": "warn",
                }
            }
        )

    assert {item["code"] for item in warnings} == {
        "CFG-PLUGINS-001",
        "CFG-PLUGINS-002",
    }


def test_validate_orchestrator_config_flags_inactive_trace_export_settings() -> None:
    warnings = validate_orchestrator_config(
        {
            "trace": {
                "export_enabled": False,
                "otlp_enabled": True,
                "otlp_endpoint": "http://collector:4318/v1/traces",
            }
        }
    )

    assert {item["code"] for item in warnings} == {
        "CFG-TRACE-001",
        "CFG-TRACE-002",
    }


def test_validate_orchestrator_config_flags_inactive_memory_profile_overrides() -> None:
    warnings = validate_orchestrator_config(
        {
            "memory": {
                "profile": {
                    "enabled": False,
                    "top_n": 9,
                    "token_budget": 320,
                }
            }
        }
    )

    assert len(warnings) == 1
    assert warnings[0]["code"] == "CFG-MEMORY-001"
    assert "top_n" in warnings[0]["message"]
    assert "token_budget" in warnings[0]["message"]


def test_validate_orchestrator_config_flags_long_term_write_without_enable() -> None:
    warnings = validate_orchestrator_config(
        {
            "memory": {
                "long_term": {
                    "enabled": False,
                    "write_enabled": True,
                }
            }
        }
    )

    assert len(warnings) == 1
    assert warnings[0]["code"] == "CFG-MEMORY-002"
