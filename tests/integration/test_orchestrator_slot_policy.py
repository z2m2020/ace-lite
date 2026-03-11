from __future__ import annotations

from ace_lite.orchestrator import AceOrchestrator
from ace_lite.pipeline.plugin_runtime import (
    DEFAULT_REMOTE_SLOT_ALLOWLIST,
    apply_slot_contributions,
    build_plugin_policy_summary,
    summarize_slot_policy_events,
)


def test_apply_slot_contributions_blocks_unallowlisted_remote_slot() -> None:
    output: dict[str, object] = {}
    contributions = [
        {
            "plugin": "remote-plugin",
            "slot": "source_plan.writeback_template.decision",
            "value": "remote-overwrite",
            "mode": "set",
            "source": "mcp_remote",
        }
    ]

    summary = apply_slot_contributions(
        stage_name="source_plan",
        output=output,
        contributions=contributions,
        remote_slot_allowlist=DEFAULT_REMOTE_SLOT_ALLOWLIST,
        remote_slot_policy_mode="strict",
    )

    assert output == {}
    assert summary["applied"] == []
    assert len(summary["conflicts"]) == 1
    assert summary["conflicts"][0]["reason"] == "slot_not_allowed_for_source"


def test_apply_slot_contributions_allows_remote_observability_slot() -> None:
    output: dict[str, object] = {}
    contributions = [
        {
            "plugin": "remote-plugin",
            "slot": "observability.mcp_plugins",
            "value": {"name": "remote-plugin"},
            "mode": "append",
            "source": "mcp_remote",
        }
    ]

    summary = apply_slot_contributions(
        stage_name="augment",
        output=output,
        contributions=contributions,
        remote_slot_allowlist=DEFAULT_REMOTE_SLOT_ALLOWLIST,
        remote_slot_policy_mode="strict",
    )

    assert summary["conflicts"] == []
    assert len(summary["applied"]) == 1
    assert summary["applied"][0]["source"] == "mcp_remote"
    assert output == {"observability": {"mcp_plugins": [{"name": "remote-plugin"}]}}


def test_apply_slot_contributions_allows_stage_prefixed_remote_observability_slot() -> (
    None
):
    output: dict[str, object] = {}
    contributions = [
        {
            "plugin": "remote-plugin",
            "slot": "augment.observability.mcp_plugins",
            "value": {"name": "remote-plugin"},
            "mode": "append",
            "source": "mcp_remote",
        }
    ]

    summary = apply_slot_contributions(
        stage_name="augment",
        output=output,
        contributions=contributions,
        remote_slot_allowlist=DEFAULT_REMOTE_SLOT_ALLOWLIST,
        remote_slot_policy_mode="strict",
    )

    assert summary["conflicts"] == []
    assert len(summary["applied"]) == 1
    assert output == {"observability": {"mcp_plugins": [{"name": "remote-plugin"}]}}


def test_apply_slot_contributions_keeps_local_plugin_behavior_unchanged() -> None:
    output: dict[str, object] = {}
    contributions = [
        {
            "plugin": "local-plugin",
            "slot": "source_plan.writeback_template.decision",
            "value": "keep-existing-behavior",
            "mode": "set",
        }
    ]

    summary = apply_slot_contributions(
        stage_name="source_plan",
        output=output,
        contributions=contributions,
        remote_slot_allowlist=DEFAULT_REMOTE_SLOT_ALLOWLIST,
        remote_slot_policy_mode="strict",
    )

    assert summary["conflicts"] == []
    assert len(summary["applied"]) == 1
    assert output == {"writeback_template": {"decision": "keep-existing-behavior"}}


def test_apply_slot_contributions_warn_mode_records_conflict_but_applies() -> None:
    output: dict[str, object] = {}
    contributions = [
        {
            "plugin": "remote-plugin",
            "slot": "source_plan.writeback_template.decision",
            "value": "warn-mode-allowed",
            "mode": "set",
            "source": "mcp_remote",
        }
    ]

    summary = apply_slot_contributions(
        stage_name="source_plan",
        output=output,
        contributions=contributions,
        remote_slot_allowlist=DEFAULT_REMOTE_SLOT_ALLOWLIST,
        remote_slot_policy_mode="warn",
    )

    assert len(summary["conflicts"]) == 1
    assert summary["conflicts"][0]["reason"] == "slot_not_allowed_for_source_warn"
    assert len(summary["applied"]) == 1
    assert output == {"writeback_template": {"decision": "warn-mode-allowed"}}


def test_apply_slot_contributions_off_mode_skips_remote_slot_filtering() -> None:
    output: dict[str, object] = {}
    contributions = [
        {
            "plugin": "remote-plugin",
            "slot": "source_plan.writeback_template.decision",
            "value": "off-mode-allowed",
            "mode": "set",
            "source": "mcp_remote",
        }
    ]

    summary = apply_slot_contributions(
        stage_name="source_plan",
        output=output,
        contributions=contributions,
        remote_slot_allowlist=DEFAULT_REMOTE_SLOT_ALLOWLIST,
        remote_slot_policy_mode="off",
    )

    assert summary["conflicts"] == []
    assert len(summary["applied"]) == 1
    assert output == {"writeback_template": {"decision": "off-mode-allowed"}}


def test_summarize_slot_policy_events_counts_block_warn_and_remote() -> None:
    summary = summarize_slot_policy_events(
        slot_summary={
            "applied": [
                {"source": "mcp_remote"},
                {"source": ""},
            ],
            "conflicts": [
                {"reason": "slot_not_allowed_for_source"},
                {"reason": "slot_not_allowed_for_source_warn"},
                {"reason": "slot_not_list"},
            ],
        }
    )

    assert summary == {
        "applied": 2,
        "conflicts": 3,
        "blocked": 1,
        "warn": 1,
        "remote_applied": 1,
    }


def test_build_plugin_policy_summary_aggregates_and_preserves_stage_order() -> None:
    summary = build_plugin_policy_summary(
        stage_summary={
            "source_plan": {
                "applied": 2,
                "conflicts": 1,
                "blocked": 1,
                "warn": 0,
                "remote_applied": 1,
            },
            "augment": {
                "applied": 1,
                "conflicts": 1,
                "blocked": 0,
                "warn": 1,
                "remote_applied": 1,
            },
        },
        pipeline_order=AceOrchestrator.PIPELINE_ORDER,
        remote_slot_allowlist=DEFAULT_REMOTE_SLOT_ALLOWLIST,
        remote_slot_policy_mode="strict",
    )

    assert summary["mode"] == "strict"
    assert summary["allowlist"] == ["observability.mcp_plugins"]
    assert summary["totals"] == {
        "applied": 3,
        "conflicts": 2,
        "blocked": 1,
        "warn": 1,
        "remote_applied": 2,
    }
    assert summary["by_stage"] == [
        {
            "stage": "augment",
            "applied": 1,
            "conflicts": 1,
            "blocked": 0,
            "warn": 1,
            "remote_applied": 1,
        },
        {
            "stage": "source_plan",
            "applied": 2,
            "conflicts": 1,
            "blocked": 1,
            "warn": 0,
            "remote_applied": 1,
        },
    ]
