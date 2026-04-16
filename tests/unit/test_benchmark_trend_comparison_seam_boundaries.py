from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_validation_rich_scripts_import_shared_support_bundle() -> None:
    comparison_text = _read("scripts/build_validation_rich_comparison_report.py")
    trend_text = _read("scripts/build_validation_rich_trend_report.py")

    for text in (comparison_text, trend_text):
        assert "from ace_lite.benchmark.report_script_support import (" in text
        assert "build_validation_rich_support_bundle" in text
        assert "load_report_json" in text
        assert "resolve_report_path" in text


def test_trend_and_comparison_scripts_keep_shared_generic_helpers_out_of_entrypoints() -> None:
    comparison_text = _read("scripts/build_validation_rich_comparison_report.py")
    validation_trend_text = _read("scripts/build_validation_rich_trend_report.py")
    freeze_text = _read("scripts/build_freeze_trend_report.py")
    latency_text = _read("scripts/build_latency_slo_trend_report.py")

    for text in (comparison_text, validation_trend_text, freeze_text, latency_text):
        assert "def _resolve_path(" not in text
        assert "def _load_json(" not in text
        assert "def _safe_float(" not in text

    for text in (validation_trend_text, freeze_text, latency_text):
        assert "collect_recent_git_diff_paths_with_runner(" in text
        assert "def _collect_suspect_files(" not in text
