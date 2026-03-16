from __future__ import annotations

from ace_lite import orchestrator_runtime_support as support
from ace_lite.orchestrator_runtime_support_shared import (
    apply_contract_error_to_payload,
    get_stage_state,
    run_stage_sequence,
)


def test_runtime_support_keeps_shared_helper_aliases() -> None:
    assert support._run_stage_sequence is run_stage_sequence
    assert support._get_stage_state is get_stage_state
    assert support._apply_contract_error_to_payload is apply_contract_error_to_payload


def test_runtime_support_compat_rerun_stage_resolver_preserves_post_validation_shortcut() -> None:
    assert support._resolve_agent_loop_rerun_stages(
        action_type="request_validation_retry"
    ) == ["validation"]
