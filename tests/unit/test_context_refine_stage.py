from __future__ import annotations

from ace_lite.pipeline.stages.context_refine import run_context_refine
from ace_lite.pipeline.types import StageContext


def test_run_context_refine_emits_report_only_review_actions() -> None:
    ctx = StageContext(
        query="inspect source plan shortlist",
        repo="demo",
        root=".",
        state={
            "index": {
                "candidate_files": [
                    {
                        "path": "src/ace_lite/pipeline/stages/source_plan.py",
                        "score": 0.9,
                        "score_breakdown": {"candidate": 1.0},
                    },
                    {
                        "path": "tests/unit/test_source_plan_report_only.py",
                        "score": 0.05,
                        "score_breakdown": {},
                    },
                ],
                "candidate_chunks": [
                    {
                        "path": "src/ace_lite/pipeline/stages/source_plan.py",
                        "qualified_name": "run_source_plan",
                        "score": 0.8,
                        "score_breakdown": {"chunk_symbol_exact": 1.0},
                    },
                    {
                        "path": "tests/unit/test_source_plan_report_only.py",
                        "qualified_name": "test_noise",
                        "score": 0.02,
                        "score_breakdown": {},
                    },
                ],
                "policy_name": "rrf_hybrid",
                "policy_version": "v1",
            },
            "repomap": {
                "focused_files": [
                    "src/ace_lite/pipeline/stages/source_plan.py",
                ]
            },
            "augment": {
                "diagnostics": ["memory_fallback"],
                "tests": {"suspicious_chunks": [{"path": "src/ace_lite/pipeline/stages/source_plan.py"}]},
            },
        },
    )

    payload = run_context_refine(ctx=ctx)

    assert payload["enabled"] is True
    assert payload["reason"] == "report_only"
    assert payload["focused_files"] == ["src/ace_lite/pipeline/stages/source_plan.py"]
    assert payload["decision_counts"]["keep"] >= 1
    assert payload["decision_counts"]["drop"] >= 1
    assert payload["candidate_review"]["schema_version"] == "candidate_review_v2"
    assert payload["candidate_review"]["status"] == "watch"
    assert payload["candidate_review"]["candidate_file_actions"]
    assert payload["candidate_review"]["candidate_chunk_actions"]
