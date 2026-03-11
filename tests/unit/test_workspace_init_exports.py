from __future__ import annotations

import ace_lite.workspace as workspace


def test_workspace_init_exports_include_expected_symbols() -> None:
    assert hasattr(workspace, "DEFAULT_SUMMARY_TTL_SECONDS")
    assert hasattr(workspace, "SUMMARY_TEMPERATURE_TIERS")
    assert hasattr(workspace, "load_workspace_benchmark_baseline")
    assert hasattr(workspace, "compare_workspace_benchmark_metrics")
    assert hasattr(workspace, "evaluate_workspace_benchmark_against_baseline")
