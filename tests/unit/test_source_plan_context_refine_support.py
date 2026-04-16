from __future__ import annotations

from ace_lite.source_plan.context_refine_support import resolve_source_plan_candidate_review


def test_resolve_source_plan_candidate_review_prefers_context_refine_stage_payload() -> None:
    review = resolve_source_plan_candidate_review(
        context_refine_state={"candidate_review": {"status": "watch", "source": "context_refine"}},
        focused_files=["src/a.py"],
        candidate_chunks=[{"path": "src/a.py"}],
        evidence_summary={
            "direct_ratio": 1.0,
            "hint_only_ratio": 0.0,
            "neighbor_context_ratio": 0.0,
        },
        failure_signal_summary={"has_failure": False, "issue_count": 0, "probe_issue_count": 0},
        validation_tests=["pytest -q tests/unit/test_a.py"],
    )

    assert review == {"status": "watch", "source": "context_refine"}


def test_resolve_source_plan_candidate_review_builds_report_only_fallback() -> None:
    review = resolve_source_plan_candidate_review(
        context_refine_state={},
        focused_files=["src/a.py"],
        candidate_chunks=[{"path": "src/a.py"}],
        evidence_summary={
            "direct_ratio": 0.2,
            "hint_only_ratio": 0.6,
            "neighbor_context_ratio": 0.1,
        },
        failure_signal_summary={"has_failure": True, "issue_count": 1, "probe_issue_count": 0},
        validation_tests=[],
    )

    assert review["schema_version"] == "candidate_review_v1"
    assert review["status"] == "watch"
    assert "hint_heavy_shortlist" in review["watch_items"]
