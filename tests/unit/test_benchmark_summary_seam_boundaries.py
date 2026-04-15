from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_repo_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_benchmark_summaries_uses_summary_memory_seam() -> None:
    summaries_text = _read_repo_text("src/ace_lite/benchmark/summaries.py")

    expected_tokens = (
        "from ace_lite.benchmark.summary_memory import (",
        "build_chunk_cache_contract_summary as _build_chunk_cache_contract_summary_impl",
        "build_ltm_explainability_summary as _build_ltm_explainability_summary_impl",
        "return _build_ltm_explainability_summary_impl(case_results)",
        "return _build_chunk_cache_contract_summary_impl(case_results)",
    )
    for token in expected_tokens:
        assert token in summaries_text

    forbidden_local_impl_tokens = (
        'feedback_signal_names = ("helpful", "stale", "harmful")',
        'payload_raw = item.get("ltm_explainability")',
        "present_case_count = 0",
        "fingerprint_present_case_count = 0",
        "metadata_aligned_case_count = 0",
    )
    for token in forbidden_local_impl_tokens:
        assert token not in summaries_text
