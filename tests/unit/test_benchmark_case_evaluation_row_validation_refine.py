from __future__ import annotations

from typing import Any, cast

from tests.unit.test_benchmark_case_evaluation_row import _base_row_kwargs

from ace_lite.benchmark.case_evaluation_row import build_case_evaluation_row


def test_build_case_evaluation_row_tracks_validation_findings_refine_fields() -> None:
    kwargs = _base_row_kwargs()
    kwargs["agent_loop_last_action_reason"] = "source_plan_validation_findings"
    kwargs["agent_loop_validation_findings_refine_applied"] = True
    kwargs["agent_loop_validation_findings_refine_focus_path_count"] = 2

    row = build_case_evaluation_row(**cast(Any, kwargs))

    assert row["agent_loop_last_action_reason"] == "source_plan_validation_findings"
    assert row["agent_loop_validation_findings_refine_applied"] == 1.0
    assert row["agent_loop_validation_findings_refine_focus_path_count"] == 2.0
    assert row["agent_loop_control_plane"]["validation_findings_refine_applied"] is True
    assert row["agent_loop_control_plane"]["validation_findings_refine_focus_path_count"] == 2
