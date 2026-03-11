from __future__ import annotations

from ace_lite.benchmark.diff import build_diff_markdown, diff_benchmark_results


def test_diff_benchmark_results_builds_delta() -> None:
    a = {"metrics": {"recall_at_k": 0.5, "latency_p95_ms": 100.0}}
    b = {"metrics": {"recall_at_k": 0.75, "latency_p95_ms": 120.0}}
    diff = diff_benchmark_results(a=a, b=b)
    assert diff.delta["recall_at_k"] == 0.25
    assert diff.delta["latency_p95_ms"] == 20.0


def test_build_diff_markdown_contains_sections() -> None:
    a = {"metrics": {"recall_at_k": 0.5}}
    b = {"metrics": {"recall_at_k": 0.6}}
    diff = diff_benchmark_results(a=a, b=b)
    md = build_diff_markdown(diff)
    assert "# ACE-Lite Benchmark Diff" in md
    assert "## Delta (B - A)" in md
