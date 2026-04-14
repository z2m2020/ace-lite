from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from ace_lite.config_models import (
    PluginsConfig,
    RetrievalGroupConfig,
    RuntimeConfig,
    RuntimeCronTaskConfig,
    SharedPlanConfig,
    validate_cli_config,
)
from ace_lite.config_models import (
    TestsCliConfig as RuntimeTestsCliConfig,
)


def test_plugins_config_coerces_boolean_remote_slot_policy_mode() -> None:
    assert PluginsConfig(remote_slot_policy_mode=True).remote_slot_policy_mode == "strict"
    assert PluginsConfig(remote_slot_policy_mode=False).remote_slot_policy_mode == "off"


def test_retrieval_group_config_rejects_negative_exact_search_controls() -> None:
    with pytest.raises(ValidationError, match=re.escape("retrieval.exact_search_* must be >= 0")):
        RetrievalGroupConfig(exact_search_time_budget_ms=-1)

    with pytest.raises(ValidationError, match=re.escape("retrieval.exact_search_* must be >= 0")):
        RetrievalGroupConfig(exact_search_max_paths=-1)


def test_runtime_config_rejects_invalid_hot_reload_thresholds() -> None:
    with pytest.raises(
        ValidationError,
        match=re.escape("runtime.hot_reload.poll_interval_seconds must be > 0"),
    ):
        RuntimeConfig(hot_reload={"poll_interval_seconds": 0})

    with pytest.raises(
        ValidationError,
        match=re.escape("runtime.hot_reload.debounce_ms must be >= 0"),
    ):
        RuntimeConfig(hot_reload={"debounce_ms": -1})


def test_runtime_cron_task_config_validates_name_and_schedule() -> None:
    task = RuntimeCronTaskConfig(name=" nightly-index ", schedule=" 0 3 * * * ")
    assert task.name == "nightly-index"
    assert task.schedule == "0 3 * * *"

    with pytest.raises(
        ValidationError,
        match=re.escape("runtime.scheduler.cron[].name cannot be empty"),
    ):
        RuntimeCronTaskConfig(name=" ", schedule="0 3 * * *")


def test_shared_plan_config_normalizes_runtime_profile() -> None:
    config = SharedPlanConfig(runtime_profile=" BugFix ")
    assert config.runtime_profile == "bugfix"

    assert SharedPlanConfig(runtime_profile="   ").runtime_profile is None


def test_tests_cli_config_preserves_nested_sbfl_json_alias() -> None:
    config = RuntimeTestsCliConfig(sbfl={"json": " artifacts/sbfl.json "})
    dumped = config.model_dump(exclude_none=True, by_alias=True)

    assert dumped["sbfl"]["json"] == " artifacts/sbfl.json "


def test_validate_cli_config_formats_nested_validation_errors() -> None:
    with pytest.raises(ValueError) as exc_info:
        validate_cli_config(
            {
                "runtime": {
                    "hot_reload": {
                        "poll_interval_seconds": 0,
                    }
                }
            }
        )

    message = str(exc_info.value)
    assert message.startswith("Invalid .ace-lite.yml configuration:")
    assert "runtime.hot_reload.poll_interval_seconds" in message
    assert "must be > 0" in message
