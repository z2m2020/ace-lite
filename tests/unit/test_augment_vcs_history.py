from __future__ import annotations

from pathlib import Path

from ace_lite.pipeline.stages.augment import run_diagnostics_augment


def test_run_diagnostics_augment_includes_vcs_history_payload(tmp_path: Path) -> None:
    payload = run_diagnostics_augment(
        root=str(tmp_path),
        query="q",
        index_stage={"candidate_files": [{"path": "src/app.py", "language": "python"}]},
        enabled=False,
        top_n=3,
        broker=None,
        xref_enabled=False,
        xref_top_n=1,
        xref_time_budget_ms=100,
    )

    assert payload["enabled"] is False
    assert "vcs_history" in payload
    assert payload["vcs_history"]["enabled"] is False
    assert payload["vcs_history"]["reason"] == "disabled"
