from __future__ import annotations

from pathlib import Path


def test_full_validation_script_includes_required_gates() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "run_full_validation.ps1"
    assert script_path.exists()
    content = script_path.read_text(encoding="utf-8")
    assert "function Assert-LastExitCode" in content
    assert "run_scenario_validation.py" in content
    assert "run_benchmark_matrix.py" in content
    assert "run_release_freeze_regression.py" in content
    assert "metrics_collector.py" in content
    assert "Assert-LastExitCode -StepName \"trend checks\"" in content
