"""Tests for scripts/quick_to_plan_utility_summary.py (ALH1-0201.T2)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Load the script as a module using importlib (same pattern as test_gap_report_script.py)
_script_path = Path(__file__).resolve().parents[2] / "scripts" / "quick_to_plan_utility_summary.py"
_spec = importlib.util.spec_from_file_location("quick_to_plan_utility_summary", _script_path)
if _spec is None or _spec.loader is None:
    raise AssertionError(f"failed to load quick_to_plan_utility_summary.py from {_script_path}")
_module = importlib.util.module_from_spec(_spec)
sys.modules["quick_to_plan_utility_summary"] = _module
_spec.loader.exec_module(_module)

SCHEMA_VERSION = _module.SCHEMA_VERSION
build_quick_to_plan_utility_summary = _module.build_quick_to_plan_utility_summary
build_summary_from_dir = _module.build_summary_from_dir
render_summary_markdown = _module.render_summary_markdown


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class TestBuildQuickToPlanUtilitySummary:
    """Unit tests for per-case utility computation."""

    def test_full_plan_higher_task_success_positive_ratio(self, tmp_path: Path) -> None:
        """When full plan improves task success, utility_ratio is positive."""
        quick = {"elapsed_ms": 1000.0, "metrics": {"task_success_hit": 0.5}}
        full = {"elapsed_ms": 5000.0, "metrics": {"task_success_hit": 0.8}}

        result = build_quick_to_plan_utility_summary(
            quick_results=quick,
            full_results=full,
            case_id="pq-1",
        )

        assert result["case_id"] == "pq-1"
        assert result["quick_plan"]["task_success"] == 0.5
        assert result["full_plan"]["task_success"] == 0.8
        assert result["incremental_utility"] == pytest.approx(0.3)
        assert result["incremental_cost_ms"] == pytest.approx(4000.0)
        assert result["utility_ratio"] == pytest.approx(0.3 / 4000.0)
        assert result["warnings"] == []

    def test_full_plan_equal_task_success_zero_ratio(self, tmp_path: Path) -> None:
        """When task success is equal, utility_ratio is zero."""
        quick = {"elapsed_ms": 1000.0, "metrics": {"task_success_hit": 0.6}}
        full = {"elapsed_ms": 5000.0, "metrics": {"task_success_hit": 0.6}}

        result = build_quick_to_plan_utility_summary(
            quick_results=quick,
            full_results=full,
            case_id="pq-2",
        )

        assert result["incremental_utility"] == pytest.approx(0.0)
        assert result["utility_ratio"] == pytest.approx(0.0)

    def test_full_plan_worse_task_success_negative_ratio(self, tmp_path: Path) -> None:
        """When full plan degrades task success, utility_ratio is negative."""
        quick = {"elapsed_ms": 1000.0, "metrics": {"task_success_hit": 0.8}}
        full = {"elapsed_ms": 5000.0, "metrics": {"task_success_hit": 0.5}}

        result = build_quick_to_plan_utility_summary(
            quick_results=quick,
            full_results=full,
            case_id="pq-3",
        )

        assert result["incremental_utility"] == pytest.approx(-0.3)
        assert result["utility_ratio"] < 0

    def test_missing_task_success_unknown(self, tmp_path: Path) -> None:
        """When task_success is absent, incremental_utility is None (not crash)."""
        quick = {"elapsed_ms": 1000.0, "metrics": {}}
        full = {"elapsed_ms": 5000.0, "metrics": {"task_success_hit": 0.9}}

        result = build_quick_to_plan_utility_summary(
            quick_results=quick,
            full_results=full,
            case_id="pq-4",
        )

        assert result["quick_plan"]["task_success"] is None
        assert result["incremental_utility"] is None
        assert result["utility_ratio"] is None
        assert any("unknown" in w for w in result["warnings"])

    def test_missing_elapsed_ms_unknown_cost(self, tmp_path: Path) -> None:
        """When elapsed_ms is absent, incremental_cost_ms is None."""
        quick = {"metrics": {"task_success_hit": 0.5}}
        full = {"metrics": {"task_success_hit": 0.8}}

        result = build_quick_to_plan_utility_summary(
            quick_results=quick,
            full_results=full,
            case_id="pq-5",
        )

        assert result["incremental_cost_ms"] is None
        assert result["utility_ratio"] is None
        assert any("elapsed_ms unknown" in w for w in result["warnings"])

    def test_zero_incremental_cost_prevents_division_by_zero(self, tmp_path: Path) -> None:
        """When incremental_cost_ms is zero, utility_ratio is None (not inf)."""
        quick = {"elapsed_ms": 1000.0, "metrics": {"task_success_hit": 0.5}}
        full = {"elapsed_ms": 1000.0, "metrics": {"task_success_hit": 0.8}}

        result = build_quick_to_plan_utility_summary(
            quick_results=quick,
            full_results=full,
            case_id="pq-6",
        )

        assert result["incremental_cost_ms"] == pytest.approx(0.0)
        assert result["utility_ratio"] is None

    def test_fallback_to_utility_hit(self, tmp_path: Path) -> None:
        """Falls back to utility_hit when task_success_hit is absent."""
        quick = {"elapsed_ms": 1000.0, "metrics": {"utility_hit": 0.4}}
        full = {"elapsed_ms": 3000.0, "metrics": {"utility_hit": 0.7}}

        result = build_quick_to_plan_utility_summary(
            quick_results=quick,
            full_results=full,
            case_id="pq-7",
        )

        assert result["quick_plan"]["task_success"] == 0.4
        assert result["full_plan"]["task_success"] == 0.7
        assert result["incremental_utility"] == pytest.approx(0.3)

    def test_schema_version_present(self, tmp_path: Path) -> None:
        """Output always carries schema_version."""
        quick = {"elapsed_ms": 1000.0, "metrics": {"task_success_hit": 0.5}}
        full = {"elapsed_ms": 5000.0, "metrics": {"task_success_hit": 0.8}}

        result = build_quick_to_plan_utility_summary(
            quick_results=quick,
            full_results=full,
            case_id="pq-8",
        )

        assert result["schema_version"] == SCHEMA_VERSION


class TestBuildSummaryFromDir:
    """Integration tests for directory-level summary building."""

    def test_top_level_quick_full_pair(self, tmp_path: Path) -> None:
        """Works when quick/ and full/ are directly under paired_eval_dir."""
        quick_dir = tmp_path / "run1"
        quick_dir.mkdir()
        _write_json(
            quick_dir / "quick" / "results.json",
            {"elapsed_ms": 1000.0, "metrics": {"task_success_hit": 0.5}},
        )
        _write_json(
            quick_dir / "full" / "results.json",
            {"elapsed_ms": 5000.0, "metrics": {"task_success_hit": 0.8}},
        )

        summary, warnings = build_summary_from_dir(quick_dir)

        assert summary["pair_count"] == 1
        assert summary["pairs"][0]["case_id"] == "run1"
        assert summary["pairs"][0]["incremental_utility"] == pytest.approx(0.3)
        assert summary["warnings"] == []

    def test_missing_quick_results_skips_with_warning(self, tmp_path: Path) -> None:
        """When quick results are absent, pair is skipped and warning is emitted."""
        pair_dir = tmp_path / "pq-1"
        pair_dir.mkdir()
        _write_json(
            pair_dir / "full" / "results.json",
            {"elapsed_ms": 5000.0, "metrics": {"task_success_hit": 0.8}},
        )

        summary, warnings = build_summary_from_dir(pair_dir)

        assert summary["pair_count"] == 0
        assert any("missing quick or full" in w for w in warnings)

    def test_mean_utility_ratio_aggregated(self, tmp_path: Path) -> None:
        """mean_utility_ratio is computed from all valid pairs."""
        run_dir = tmp_path / "run2"
        run_dir.mkdir()
        _write_json(
            run_dir / "quick" / "results.json",
            {"elapsed_ms": 1000.0, "metrics": {"task_success_hit": 0.5}},
        )
        _write_json(
            run_dir / "full" / "results.json",
            {"elapsed_ms": 5000.0, "metrics": {"task_success_hit": 0.8}},
        )

        summary, _ = build_summary_from_dir(run_dir)

        assert summary["aggregate"]["pairs_with_ratio"] == 1
        assert summary["aggregate"]["pairs_unknown"] == 0
        assert summary["aggregate"]["mean_utility_ratio"] is not None


class TestRenderMarkdown:
    """Tests for the markdown renderer."""

    def test_renders_header_and_table(self, tmp_path: Path) -> None:
        """Markdown output contains header, table, and note."""
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": "2026-04-12T00:00:00+00:00",
            "paired_eval_dir": "/tmp/paired-eval",
            "pair_count": 1,
            "pairs": [
                {
                    "case_id": "pq-1",
                    "quick_plan": {"task_success": 0.5, "elapsed_ms": 1000.0},
                    "full_plan": {"task_success": 0.8, "elapsed_ms": 5000.0},
                    "incremental_utility": 0.3,
                    "incremental_cost_ms": 4000.0,
                    "utility_ratio": 0.3 / 4000.0,
                    "warnings": [],
                }
            ],
            "aggregate": {
                "mean_utility_ratio": 0.3 / 4000.0,
                "mean_incremental_utility": 0.3,
                "pairs_with_ratio": 1,
                "pairs_unknown": 0,
            },
            "warnings": [],
        }

        md = render_summary_markdown(summary)

        assert "# Quick-to-Plan Incremental Utility Summary" in md
        assert "| case_id | quick_task_success |" in md
        assert "| pq-1 |" in md
        assert "report-only artifact" in md
