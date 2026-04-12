"""Tests for scripts/phase2_overlay_builder.py (ALH1-0205.T2)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


def _load_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "phase2_overlay_builder.py"
    spec = importlib.util.spec_from_file_location("phase2_overlay_builder_script", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load phase2_overlay_builder.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# _artifact_summary
# ---------------------------------------------------------------------------


class TestArtifactSummary:
    def _summary(self, artifact: dict | None) -> dict:
        module = _load_module()
        return module._artifact_summary(artifact)

    def test_available_artifact(self) -> None:
        artifact = {"schema_version": "v1", "generated_at": "2026-04-12T00:00:00Z"}
        result = self._summary(artifact)
        assert result["available"] is True
        assert result["schema_version"] == "v1"
        assert result["generated_at"] == "2026-04-12T00:00:00Z"

    def test_missing_artifact(self) -> None:
        result = self._summary(None)
        assert result["available"] is False


# ---------------------------------------------------------------------------
# _build_review
# ---------------------------------------------------------------------------


class TestBuildReview:
    def _review(self, utility=None, outcome=None, smoke=None, drift=None) -> dict:
        module = _load_module()
        return module._build_review(utility, outcome, smoke, drift)

    def test_no_artifacts(self) -> None:
        review = self._review()
        assert review["all_operational_health_green"] is False
        assert review["ready_for_phase3"] is False

    def test_smoke_healthy_no_drift(self) -> None:
        smoke = {"healthy": True}
        drift = {"has_install_drift": False, "has_stale_process": False}
        review = self._review(smoke=smoke, drift=drift)
        assert review["all_operational_health_green"] is True

    def test_smoke_unhealthy(self) -> None:
        smoke = {"healthy": False}
        drift = {"has_install_drift": False, "has_stale_process": False}
        review = self._review(smoke=smoke, drift=drift)
        assert review["all_operational_health_green"] is False

    def test_ready_for_phase3_with_ratio_and_rate(self) -> None:
        utility = {"ratio": 1.2}
        outcome = {"run_count": 10, "aggregate": {"upgrade_recommended_count": 8}}
        review = self._review(utility=utility, outcome=outcome)
        assert review["ready_for_phase3"] is True
        assert review["signals"]["quick_to_plan_ratio"] == 1.2
        assert review["signals"]["upgrade_recommended_rate"] == 0.8

    def test_not_ready_without_ratio(self) -> None:
        outcome = {"run_count": 10, "aggregate": {"upgrade_recommended_count": 8}}
        review = self._review(outcome=outcome)
        assert review["ready_for_phase3"] is False

    def test_not_ready_without_rate(self) -> None:
        utility = {"ratio": 1.2}
        review = self._review(utility=utility)
        assert review["ready_for_phase3"] is False


# ---------------------------------------------------------------------------
# build_overlay
# ---------------------------------------------------------------------------


class TestBuildOverlay:
    def _overlay(self, tmp_path: Path) -> dict:
        module = _load_module()

        # Artifact dirs must be at tmp_path/checkpoints/../  (two levels above output-dir)
        # output_dir = tmp_path / "checkpoints" / "phase2" / "latest"
        # output_dir.parent.parent = tmp_path / "checkpoints"
        # so artifacts must be at: tmp_path / "checkpoints" / "observability" / ...
        # But we want them at tmp_path / "observability" / ...
        # So we use tmp_path as the root and set output_dir to tmp_path/checkpoints/phase2/latest
        # This means build_overlay's parent.parent resolves to tmp_path/checkpoints
        # Let's instead put artifacts under tmp_path/checkpoints/../  which is tmp_path
        # OR: set output_dir = tmp_path / "checkpoints" / "phase2" / "latest"
        # then artifacts need to be at: tmp_path / "checkpoints" / "observability" / ...
        # But we want them at: tmp_path / "observability" / ...
        # Solution: set output_dir to tmp_path so parent.parent = tmp_path
        output_dir = tmp_path / "checkpoints" / "phase2" / "latest"

        # build_overlay does: output_dir.parent.parent / "observability" / ...
        # If output_dir = tmp_path/checkpoints/phase2/latest
        # Then: parent = tmp_path/checkpoints/phase2, parent.parent = tmp_path/checkpoints
        # So artifacts at: tmp_path/checkpoints/observability/...
        obs_dir = tmp_path / "checkpoints" / "observability" / "quick_to_plan" / "latest"
        pq_dir = tmp_path / "checkpoints" / "plan-quick-outcomes" / "latest"
        smoke_dir = tmp_path / "checkpoints" / "smoke" / "latest"
        doctor_dir = tmp_path / "checkpoints" / "doctor" / "latest"

        _write_json(
            obs_dir / "quick_to_plan_utility_summary.json",
            {"schema_version": "quick_to_plan_utility_summary_v1", "ratio": 1.25},
        )
        _write_json(
            pq_dir / "plan_quick_outcome_summary.json",
            {
                "schema_version": "plan_quick_outcome_summary_v1",
                "run_count": 5,
                "aggregate": {"upgrade_recommended_count": 4},
            },
        )
        _write_json(
            smoke_dir / "smoke_summary.json",
            {"schema_version": "smoke_summary_v1", "healthy": True},
        )
        _write_json(
            doctor_dir / "version_drift_report.json",
            {
                "schema_version": "version_drift_report_v1",
                "has_install_drift": False,
                "has_stale_process": False,
            },
        )

        module.build_overlay(output_dir)

        overlay_path = output_dir / "phase2_quickfirst_overlay.json"
        assert overlay_path.exists()
        return json.loads(overlay_path.read_text(encoding="utf-8"))

    def test_overlay_schema_version(self, tmp_path: Path) -> None:
        overlay = self._overlay(tmp_path)
        assert overlay["schema_version"] == "phase2_quickfirst_overlay_v1"

    def test_overlay_has_generated_at(self, tmp_path: Path) -> None:
        overlay = self._overlay(tmp_path)
        assert "generated_at" in overlay
        assert "phase" in overlay
        assert overlay["phase"] == "phase2"

    def test_overlay_artifact_availability(self, tmp_path: Path) -> None:
        overlay = self._overlay(tmp_path)
        artifacts = overlay["artifacts"]
        assert artifacts["quick_to_plan_utility_summary"]["available"] is True
        assert artifacts["plan_quick_outcome_summary"]["available"] is True
        assert artifacts["smoke_summary"]["available"] is True
        assert artifacts["version_drift_report"]["available"] is True

    def test_overlay_review_signals(self, tmp_path: Path) -> None:
        overlay = self._overlay(tmp_path)
        signals = overlay["review"]["signals"]
        assert signals["quick_to_plan_ratio"] == 1.25
        assert signals["upgrade_recommended_rate"] == 0.8
        assert signals["smoke_healthy"] is True

    def test_overlay_markdown_written(self, tmp_path: Path) -> None:
        module = _load_module()
        output_dir = tmp_path / "checkpoints" / "phase2" / "latest"
        module.build_overlay(output_dir)
        md_path = output_dir / "phase2_quickfirst_overlay.md"
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "Phase 2 QuickFirst Review Overlay" in content
        assert "quick_to_plan_ratio" in content
