from __future__ import annotations

from ace_lite.orchestrator_runtime_support_compat import (
    build_orchestrator_runtime_support_compat,
)
from ace_lite.orchestrator_runtime_support_shared import (
    apply_contract_error_to_payload,
    get_stage_state,
    run_stage_sequence,
)


def test_runtime_support_compat_reexports_shared_patchpoints() -> None:
    compat = build_orchestrator_runtime_support_compat(
        pre_stage_names=("memory", "index"),
        source_plan_stage_names=("source_plan",),
        post_stage_names=("validation",),
    )

    assert compat.run_stage_sequence is run_stage_sequence
    assert compat.get_stage_state is get_stage_state
    assert compat.apply_contract_error_to_payload is apply_contract_error_to_payload


def test_runtime_support_compat_preserves_validation_retry_shortcut() -> None:
    compat = build_orchestrator_runtime_support_compat(
        pre_stage_names=("memory", "index"),
        source_plan_stage_names=("source_plan",),
        post_stage_names=("validation",),
    )

    assert compat.resolve_agent_loop_rerun_stages(
        action_type="request_validation_retry"
    ) == ["validation"]
    assert compat.resolve_agent_loop_rerun_stages(action_type="other") == [
        "index",
        "source_plan",
        "validation",
    ]
