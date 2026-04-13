"""Tests for scripts/plan_quick_outcome_summary.py (ALH1-0202.T2)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "plan_quick_outcome_summary.py"
    spec = importlib.util.spec_from_file_location("plan_quick_outcome_summary_script", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load plan_quick_outcome_summary.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# extract_outcome_record
# ---------------------------------------------------------------------------


class TestExtractOutcomeRecord:
    def _rec(self, payload: dict) -> dict:
        module = _load_module()
        return module.extract_outcome_record(payload)

    def test_plan_quick_success(self) -> None:
        payload = {
            "outcome_label": "plan_quick_success",
            "upgrade_outcome_hint": {
                "expected_incremental_value": "medium",
                "expected_cost_ms_band": "low",
                "upgrade_recommended": True,
            },
        }
        rec = self._rec(payload)
        assert rec["outcome_label"] == "plan_quick_success"
        assert rec["upgrade_recommended"] is True
        assert rec["expected_incremental_value"] == "medium"
        assert rec["expected_cost_ms_band"] == "low"

    def test_plan_quick_timeout_fallback(self) -> None:
        payload = {
            "outcome_label": "plan_quick_timeout_fallback",
            "upgrade_outcome_hint": {
                "expected_incremental_value": "high",
                "expected_cost_ms_band": "medium",
                "upgrade_recommended": True,
            },
        }
        rec = self._rec(payload)
        assert rec["outcome_label"] == "plan_quick_timeout_fallback"
        assert rec["upgrade_recommended"] is True
        assert rec["expected_incremental_value"] == "high"

    def test_plan_quick_error(self) -> None:
        payload = {
            "outcome_label": "plan_quick_error",
            "upgrade_outcome_hint": {
                "expected_incremental_value": "low",
                "expected_cost_ms_band": "high",
                "upgrade_recommended": False,
            },
        }
        rec = self._rec(payload)
        assert rec["outcome_label"] == "plan_quick_error"
        assert rec["upgrade_recommended"] is False

    def test_missing_outcome_label_returns_empty(self) -> None:
        rec = self._rec({})
        assert rec["outcome_label"] == ""

    def test_unknown_outcome_label_normalized_to_empty(self) -> None:
        rec = self._rec({"outcome_label": "not_a_valid_label"})
        assert rec["outcome_label"] == ""

    def test_hint_not_a_dict(self) -> None:
        rec = self._rec(
            {"outcome_label": "plan_quick_success", "upgrade_outcome_hint": "not-a-dict"}
        )
        assert rec["outcome_label"] == "plan_quick_success"
        assert rec["upgrade_recommended"] is None
        assert rec["expected_incremental_value"] is None

    def test_hint_partially_missing_fields(self) -> None:
        rec = self._rec(
            {
                "outcome_label": "plan_quick_success",
                "upgrade_outcome_hint": {"expected_incremental_value": "low"},
            }
        )
        assert rec["upgrade_recommended"] is None
        assert rec["expected_incremental_value"] == "low"
        assert rec["expected_cost_ms_band"] is None


# ---------------------------------------------------------------------------
# build_summary_from_dir
# ---------------------------------------------------------------------------


class TestBuildSummaryFromDir:
    def _summary(self, tmp_path: Path) -> tuple[dict, list[str]]:
        module = _load_module()
        return module.build_summary_from_dir(tmp_path)

    def test_empty_dir_returns_zero_counts(self) -> None:
        summary, _ = self._summary(Path("/nonexistent"))
        assert summary["run_count"] == 0
        assert summary["outcome_counts"] == {}
        assert summary["aggregate"]["upgrade_recommended_count"] == 0
        assert summary["aggregate"]["upgrade_not_recommended_count"] == 0

    def test_single_valid_run(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "runs"
        _write_json(
            run_dir / "run_2026-04-12_10-00-00.json",
            {
                "outcome_label": "plan_quick_success",
                "upgrade_outcome_hint": {
                    "expected_incremental_value": "medium",
                    "expected_cost_ms_band": "low",
                    "upgrade_recommended": True,
                },
            },
        )
        summary, _ = self._summary(run_dir)
        assert summary["run_count"] == 1
        assert summary["outcome_counts"] == {"plan_quick_success": 1}
        assert summary["aggregate"]["upgrade_recommended_count"] == 1
        assert summary["aggregate"]["upgrade_not_recommended_count"] == 0
        assert len(summary["records"]) == 1
        assert summary["records"][0]["source_file"] == "run_2026-04-12_10-00-00.json"

    def test_multiple_runs_aggregated(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "runs"
        _write_json(
            run_dir / "run_2026-04-12_10-00-00.json",
            {
                "outcome_label": "plan_quick_success",
                "upgrade_outcome_hint": {"upgrade_recommended": True},
            },
        )
        _write_json(
            run_dir / "run_2026-04-12_11-00-00.json",
            {
                "outcome_label": "plan_quick_timeout_fallback",
                "upgrade_outcome_hint": {"upgrade_recommended": True},
            },
        )
        _write_json(
            run_dir / "run_2026-04-12_12-00-00.json",
            {
                "outcome_label": "plan_quick_success",
                "upgrade_outcome_hint": {"upgrade_recommended": False},
            },
        )
        summary, _ = self._summary(run_dir)
        assert summary["run_count"] == 3
        assert summary["outcome_counts"]["plan_quick_success"] == 2
        assert summary["outcome_counts"]["plan_quick_timeout_fallback"] == 1
        assert summary["aggregate"]["upgrade_recommended_count"] == 2
        assert summary["aggregate"]["upgrade_not_recommended_count"] == 1

    def test_skips_non_json_files(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "runs"
        _write_json(
            run_dir / "run_2026-04-12_10-00-00.json",
            {
                "outcome_label": "plan_quick_success",
                "upgrade_outcome_hint": {"upgrade_recommended": True},
            },
        )
        (run_dir / "readme.txt").write_text("not a json file")
        summary, _ = self._summary(run_dir)
        assert summary["run_count"] == 1  # only the .json file

    def test_unknown_outcome_label_recorded_as_unknown(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "runs"
        _write_json(run_dir / "run_2026-04-12_10-00-00.json", {"outcome_label": "bogus"})
        summary, warnings = self._summary(run_dir)
        assert summary["run_count"] == 1
        assert summary["outcome_counts"] == {"unknown": 1}
        assert summary["records"][0]["outcome_label"] == "unknown"
        assert any("outcome_label missing/unknown" in w for w in warnings)

    def test_value_breakdown(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "runs"
        _write_json(
            run_dir / "run_2026-04-12_10-00-00.json",
            {
                "outcome_label": "plan_quick_success",
                "upgrade_outcome_hint": {
                    "expected_incremental_value": "high",
                    "upgrade_recommended": True,
                },
            },
        )
        _write_json(
            run_dir / "run_2026-04-12_11-00-00.json",
            {
                "outcome_label": "plan_quick_success",
                "upgrade_outcome_hint": {
                    "expected_incremental_value": "high",
                    "upgrade_recommended": True,
                },
            },
        )
        _write_json(
            run_dir / "run_2026-04-12_12-00-00.json",
            {
                "outcome_label": "plan_quick_success",
                "upgrade_outcome_hint": {
                    "expected_incremental_value": "low",
                    "upgrade_recommended": False,
                },
            },
        )
        summary, _ = self._summary(run_dir)
        assert summary["aggregate"]["value_breakdown"]["high"] == 2
        assert summary["aggregate"]["value_breakdown"]["low"] == 1


# ---------------------------------------------------------------------------
# render_summary_markdown
# ---------------------------------------------------------------------------


class TestRenderSummaryMarkdown:
    def _render(self, summary: dict) -> str:
        module = _load_module()
        return module.render_summary_markdown(summary)

    def test_renders_header(self) -> None:
        summary = {
            "schema_version": "plan_quick_outcome_summary_v1",
            "generated_at": "2026-04-12T10:00:00Z",
            "input_dir": "/some/input",
            "run_count": 5,
            "outcome_counts": {},
            "records": [],
            "aggregate": {
                "upgrade_recommended_count": 3,
                "upgrade_not_recommended_count": 1,
                "unknown_count": 1,
                "value_breakdown": {},
            },
            "warnings": [],
        }
        md = self._render(summary)
        assert "**Total runs**: 5" in md
        assert "**upgrade_recommended=true**:  3" in md
        assert "**upgrade_recommended=false**: 1" in md
        assert "**unknown**:                  1" in md
        assert "**Note**: This is a report-only artifact" in md

    def test_renders_outcome_counts(self) -> None:
        summary = {
            "schema_version": "plan_quick_outcome_summary_v1",
            "generated_at": "2026-04-12T10:00:00Z",
            "input_dir": "/some/input",
            "run_count": 2,
            "outcome_counts": {"plan_quick_success": 1, "plan_quick_timeout_fallback": 1},
            "records": [],
            "aggregate": {
                "upgrade_recommended_count": 2,
                "upgrade_not_recommended_count": 0,
                "unknown_count": 0,
                "value_breakdown": {},
            },
            "warnings": [],
        }
        md = self._render(summary)
        assert "**plan_quick_success**: 1" in md
        assert "**plan_quick_timeout_fallback**: 1" in md

    def test_renders_warnings(self) -> None:
        summary = {
            "schema_version": "plan_quick_outcome_summary_v1",
            "generated_at": "2026-04-12T10:00:00Z",
            "input_dir": "/some/input",
            "run_count": 0,
            "outcome_counts": {},
            "records": [],
            "aggregate": {
                "upgrade_recommended_count": 0,
                "upgrade_not_recommended_count": 0,
                "unknown_count": 0,
                "value_breakdown": {},
            },
            "warnings": ["input-dir not found: /nonexistent", "empty JSON skipped: bad.json"],
        }
        md = self._render(summary)
        assert "## Warnings" in md
        assert "input-dir not found" in md
        assert "empty JSON skipped" in md
