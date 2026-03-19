from __future__ import annotations

import copy
import random
from itertools import pairwise

from ace_lite.chunking.skeleton import CHUNK_SKELETON_SCHEMA_VERSION
from ace_lite.pipeline.stages.source_plan import run_source_plan
from ace_lite.pipeline.types import StageContext
from ace_lite.source_plan import pack_source_plan_chunks, rank_source_plan_chunks


def _random_chunks(*, seed: int, count: int) -> list[dict[str, object]]:
    rng = random.Random(seed)
    rows: list[dict[str, object]] = []
    for _ in range(count):
        start = rng.randint(1, 300)
        end = start + rng.randint(0, 25)
        rows.append(
            {
                "path": f"src/mod_{rng.randint(0, 6)}.py",
                "qualified_name": f"func_{rng.randint(0, 20)}",
                "kind": "function",
                "lineno": start,
                "end_lineno": end,
                "score": round(rng.random() * 8.0, 6),
            }
        )
    return rows


def test_rank_source_plan_chunks_is_order_invariant_across_generated_inputs() -> None:
    for seed in range(1, 35):
        candidate_chunks = _random_chunks(seed=seed, count=22)
        suspicious_chunks = _random_chunks(seed=1000 + seed, count=12)

        baseline = rank_source_plan_chunks(
            suspicious_chunks=copy.deepcopy(suspicious_chunks),
            candidate_chunks=copy.deepcopy(candidate_chunks),
            test_signal_weight=1.3,
        )
        reversed_result = rank_source_plan_chunks(
            suspicious_chunks=list(reversed(copy.deepcopy(suspicious_chunks))),
            candidate_chunks=list(reversed(copy.deepcopy(candidate_chunks))),
            test_signal_weight=1.3,
        )
        sorted_result = rank_source_plan_chunks(
            suspicious_chunks=sorted(
                copy.deepcopy(suspicious_chunks),
                key=lambda item: (
                    str(item.get("path")),
                    int(item.get("lineno", 0)),
                    str(item.get("qualified_name")),
                ),
            ),
            candidate_chunks=sorted(
                copy.deepcopy(candidate_chunks),
                key=lambda item: (
                    str(item.get("path")),
                    int(item.get("lineno", 0)),
                    str(item.get("qualified_name")),
                ),
            ),
            test_signal_weight=1.3,
        )

        assert baseline == reversed_result == sorted_result

        for left, right in pairwise(baseline):
            left_key = (
                -float(left.get("score", 0.0) or 0.0),
                str(left.get("path") or ""),
                int(left.get("lineno") or 0),
                str(left.get("qualified_name") or ""),
            )
            right_key = (
                -float(right.get("score", 0.0) or 0.0),
                str(right.get("path") or ""),
                int(right.get("lineno") or 0),
                str(right.get("qualified_name") or ""),
            )
            assert left_key <= right_key


def test_run_source_plan_is_deterministic_for_same_context() -> None:
    candidate_chunks = _random_chunks(seed=777, count=14)
    suspicious_chunks = _random_chunks(seed=888, count=6)
    pipeline_order = ["memory", "index", "repomap", "augment", "skills", "source_plan"]

    ctx = StageContext(query="fix failing source plan selection", repo="demo", root=".")
    ctx.state = {
        "memory": {
            "hits_preview": [
                {"preview": "focus on source_plan.py and chunk ranking"},
                {"preview": "prefer deterministic ordering"},
            ]
        },
        "index": {
            "candidate_files": [
                {"path": "src/ace_lite/pipeline/stages/source_plan.py"},
                {"path": "src/ace_lite/source_plan/chunk_ranking.py"},
            ],
            "candidate_chunks": copy.deepcopy(candidate_chunks),
            "chunk_metrics": {"chunk_budget_used": 140.0},
        },
        "repomap": {
            "focused_files": [
                "src/ace_lite/pipeline/stages/source_plan.py",
                "src/ace_lite/source_plan/chunk_ranking.py",
            ]
        },
        "augment": {
            "diagnostics": [],
            "xref": {"count": 0, "results": []},
            "tests": {
                "failures": ["tests/unit/test_source_plan_properties.py::test_case"],
                "suspicious_chunks": copy.deepcopy(suspicious_chunks),
                "suggested_tests": ["pytest -q tests/unit/test_source_plan_properties.py"],
            },
        },
        "skills": {"selected": [{"name": "cross-agent-refactor-safeguards"}]},
        "__policy": {"name": "bugfix_test", "version": "v1", "test_signal_weight": 1.5},
    }

    first = run_source_plan(
        ctx=ctx,
        pipeline_order=pipeline_order,
        chunk_top_k=12,
        chunk_per_file_limit=3,
        chunk_token_budget=1200,
        chunk_disclosure="refs",
        policy_version="v1",
    )
    second = run_source_plan(
        ctx=ctx,
        pipeline_order=pipeline_order,
        chunk_top_k=12,
        chunk_per_file_limit=3,
        chunk_token_budget=1200,
        chunk_disclosure="refs",
        policy_version="v1",
    )

    assert first == second
    assert first["policy_name"] == "bugfix_test"
    assert first["policy_version"] == "v1"
    assert len(first["candidate_chunks"]) <= 12
    assert len(first["chunk_steps"]) == len(first["candidate_chunks"])


def test_run_source_plan_emits_selected_ltm_constraints() -> None:
    ctx = StageContext(query="reuse checkout fallback policy", repo="demo", root=".")
    ctx.state = {
        "memory": {
            "hits_preview": [
                {
                    "handle": "fact-1",
                    "preview": "[fact:repo_policy] runtime.validation.git fallback_policy reuse_checkout_or_skip",
                },
                {
                    "handle": "note-1",
                    "preview": "Prefer deterministic ordering in chunk ranking.",
                },
            ],
            "ltm": {
                "selected_count": 1,
                "selected": [
                    {
                        "handle": "fact-1",
                        "memory_kind": "fact",
                        "fact_type": "repo_policy",
                        "as_of": "2026-03-19T09:44:00+08:00",
                        "derived_from_observation_id": "obs-1",
                    }
                ],
                "attribution": [
                    {
                        "handle": "fact-1",
                        "memory_kind": "fact",
                        "graph_neighborhood": {"triple_count": 1},
                    }
                ],
            },
        },
        "index": {
            "candidate_files": [{"path": "src/ace_lite/validation/sandbox.py"}],
            "candidate_chunks": [],
            "chunk_metrics": {"chunk_budget_used": 0.0},
        },
        "repomap": {"focused_files": ["src/ace_lite/validation/sandbox.py"]},
        "augment": {
            "diagnostics": [],
            "xref": {"count": 0, "results": []},
            "tests": {"suspicious_chunks": [], "suggested_tests": []},
        },
        "skills": {"selected": []},
        "__policy": {"name": "general", "version": "v1", "test_signal_weight": 1.0},
    }

    result = run_source_plan(
        ctx=ctx,
        pipeline_order=["memory", "index", "repomap", "augment", "skills", "source_plan"],
        chunk_top_k=4,
        chunk_per_file_limit=2,
        chunk_token_budget=256,
        chunk_disclosure="refs",
        policy_version="v1",
    )

    assert result["constraints"][0].startswith("[fact:repo_policy]")
    assert result["ltm_constraint_summary"] == {
        "selected_count": 1,
        "constraint_count": 1,
        "graph_neighbor_count": 1,
        "handles": ["fact-1"],
    }
    assert result["ltm_constraints"] == [
        {
            "handle": "fact-1",
            "constraint": "[fact:repo_policy] runtime.validation.git fallback_policy reuse_checkout_or_skip",
            "memory_kind": "fact",
            "fact_type": "repo_policy",
            "as_of": "2026-03-19T09:44:00+08:00",
            "derived_from_observation_id": "obs-1",
            "graph_neighbor_count": 1,
        }
    ]


def test_run_source_plan_preserves_mixed_chunk_disclosure_contracts() -> None:
    ctx = StageContext(query="trace mixed disclosure flow", repo="demo", root=".")
    ctx.state = {
        "memory": {},
        "index": {
            "candidate_files": [
                {"path": "src/auth.py"},
                {"path": "docs/guide.md"},
            ],
            "candidate_chunks": [
                {
                    "path": "src/auth.py",
                    "qualified_name": "validate_token",
                    "kind": "function",
                    "lineno": 10,
                    "end_lineno": 20,
                    "score": 10.0,
                    "disclosure": "skeleton_light",
                    "skeleton": {
                        "schema_version": CHUNK_SKELETON_SCHEMA_VERSION,
                        "mode": "skeleton_light",
                        "language": "python",
                        "module": "src.auth",
                        "symbol": {
                            "name": "validate_token",
                            "qualified_name": "validate_token",
                            "kind": "function",
                        },
                        "span": {
                            "start_line": 10,
                            "end_line": 20,
                            "line_count": 11,
                        },
                        "anchors": {
                            "path": "src/auth.py",
                            "signature": "def validate_token(raw: str) -> bool:",
                            "robust_signature_available": True,
                        },
                    },
                },
                {
                    "path": "docs/guide.md",
                    "qualified_name": "guide",
                    "kind": "heading",
                    "lineno": 1,
                    "end_lineno": 4,
                    "score": 8.0,
                    "disclosure": "refs",
                    "disclosure_requested": "skeleton_light",
                    "disclosure_fallback_reason": "unsupported_language",
                },
            ],
            "chunk_metrics": {"chunk_budget_used": 64.0},
        },
        "repomap": {"focused_files": ["src/auth.py", "docs/guide.md"]},
        "augment": {
            "diagnostics": [],
            "xref": {"count": 0, "results": []},
            "tests": {"suspicious_chunks": [], "suggested_tests": []},
        },
        "skills": {"selected": []},
        "__policy": {"name": "general", "version": "v1", "test_signal_weight": 1.0},
    }

    result = run_source_plan(
        ctx=ctx,
        pipeline_order=["memory", "index", "repomap", "augment", "skills", "source_plan"],
        chunk_top_k=4,
        chunk_per_file_limit=2,
        chunk_token_budget=256,
        chunk_disclosure="skeleton_light",
        policy_version="v1",
    )

    assert [item["disclosure"] for item in result["candidate_chunks"]] == [
        "skeleton_light",
        "refs",
    ]
    assert result["candidate_chunks"][0]["skeleton"]["mode"] == "skeleton_light"
    assert result["candidate_chunks"][1]["disclosure_requested"] == "skeleton_light"
    assert (
        result["candidate_chunks"][1]["disclosure_fallback_reason"]
        == "unsupported_language"
    )
    assert "skeleton" not in result["candidate_chunks"][1]
    assert result["chunk_contract"] == {
        "schema_version": CHUNK_SKELETON_SCHEMA_VERSION,
        "requested_disclosure": "skeleton_light",
        "observed_disclosures": ["skeleton_light", "refs"],
        "fallback_count": 1,
        "chunk_count": 2,
        "skeleton_chunk_count": 1,
        "skeleton_modes": ["skeleton_light"],
        "skeleton_schema_versions": [CHUNK_SKELETON_SCHEMA_VERSION],
    }
    assert [
        item["chunk_ref"]["skeleton_available"] for item in result["chunk_steps"]
    ] == [True, False]


def test_run_source_plan_does_not_leak_internal_chunk_sidecars() -> None:
    ctx = StageContext(query="trace internal sidecar boundary", repo="demo", root=".")
    ctx.state = {
        "memory": {},
        "index": {
            "candidate_files": [{"path": "src/auth.py"}],
            "candidate_chunks": [
                {
                    "path": "src/auth.py",
                    "qualified_name": "validate_token",
                    "kind": "function",
                    "lineno": 10,
                    "end_lineno": 20,
                    "score": 10.0,
                    "disclosure": "refs",
                    "_retrieval_context": "module=src.auth\nsymbol=validate_token",
                    "_robust_signature_lite": {
                        "available": True,
                        "compatibility_domain": "src/auth.py::function",
                    },
                    "_topological_shield": {"enabled": True, "attenuation": 0.2},
                }
            ],
            "chunk_metrics": {"chunk_budget_used": 32.0},
        },
        "repomap": {"focused_files": ["src/auth.py"]},
        "augment": {
            "diagnostics": [],
            "xref": {"count": 0, "results": []},
            "tests": {"suspicious_chunks": [], "suggested_tests": []},
        },
        "skills": {"selected": []},
        "__policy": {"name": "general", "version": "v1", "test_signal_weight": 1.0},
    }

    result = run_source_plan(
        ctx=ctx,
        pipeline_order=["memory", "index", "repomap", "augment", "skills", "source_plan"],
        chunk_top_k=4,
        chunk_per_file_limit=2,
        chunk_token_budget=256,
        chunk_disclosure="refs",
        policy_version="v1",
    )

    assert len(result["candidate_chunks"]) == 1
    assert "_retrieval_context" not in result["candidate_chunks"][0]
    assert "_robust_signature_lite" not in result["candidate_chunks"][0]
    assert "_topological_shield" not in result["candidate_chunks"][0]
    assert "_retrieval_context" not in result["chunk_steps"][0]["chunk_ref"]
    assert "_robust_signature_lite" not in result["chunk_steps"][0]["chunk_ref"]
    assert "_topological_shield" not in result["chunk_steps"][0]["chunk_ref"]

    source_plan_step = next(
        item for item in result["steps"] if item.get("stage") == "source_plan"
    )
    assert "_retrieval_context" not in source_plan_step["candidate_chunks"][0]
    assert "_robust_signature_lite" not in source_plan_step["candidate_chunks"][0]
    assert "_topological_shield" not in source_plan_step["candidate_chunks"][0]


def test_run_source_plan_promotes_focused_file_coverage() -> None:
    candidate_chunks = [
        {
            "path": "src/a.py",
            "qualified_name": "a.first",
            "kind": "function",
            "lineno": 10,
            "end_lineno": 20,
            "score": 10.0,
        },
        {
            "path": "src/a.py",
            "qualified_name": "a.second",
            "kind": "function",
            "lineno": 30,
            "end_lineno": 40,
            "score": 9.0,
        },
        {
            "path": "src/a.py",
            "qualified_name": "a.third",
            "kind": "function",
            "lineno": 50,
            "end_lineno": 60,
            "score": 8.0,
        },
        {
            "path": "src/b.py",
            "qualified_name": "b.first",
            "kind": "function",
            "lineno": 10,
            "end_lineno": 20,
            "score": 7.0,
        },
        {
            "path": "src/c.py",
            "qualified_name": "c.first",
            "kind": "function",
            "lineno": 10,
            "end_lineno": 20,
            "score": 6.0,
        },
    ]
    ctx = StageContext(query="trace cross-file planner flow", repo="demo", root=".")
    ctx.state = {
        "memory": {},
        "index": {
            "candidate_files": [
                {"path": "src/a.py"},
                {"path": "src/b.py"},
                {"path": "src/c.py"},
            ],
            "candidate_chunks": copy.deepcopy(candidate_chunks),
            "chunk_metrics": {"chunk_budget_used": 88.0},
        },
        "repomap": {
            "focused_files": ["src/a.py", "src/b.py", "src/c.py"],
        },
        "augment": {
            "diagnostics": [],
            "xref": {"count": 0, "results": []},
            "tests": {"suspicious_chunks": [], "suggested_tests": []},
        },
        "skills": {"selected": []},
        "__policy": {"name": "general", "version": "v1", "test_signal_weight": 1.0},
    }

    result = run_source_plan(
        ctx=ctx,
        pipeline_order=["memory", "index", "repomap", "augment", "skills", "source_plan"],
        chunk_top_k=4,
        chunk_per_file_limit=3,
        chunk_token_budget=1200,
        chunk_disclosure="refs",
        policy_version="v1",
    )

    assert [item["path"] for item in result["candidate_chunks"]] == [
        "src/a.py",
        "src/b.py",
        "src/c.py",
        "src/a.py",
    ]
    assert len(result["chunk_steps"]) == 4


def test_pack_source_plan_chunks_promotes_focused_file_coverage() -> None:
    prioritized_chunks = [
        {
            "path": "src/a.py",
            "qualified_name": "a.first",
            "kind": "function",
            "lineno": 10,
            "end_lineno": 20,
            "score": 10.0,
        },
        {
            "path": "src/a.py",
            "qualified_name": "a.second",
            "kind": "function",
            "lineno": 30,
            "end_lineno": 40,
            "score": 9.0,
        },
        {
            "path": "src/a.py",
            "qualified_name": "a.third",
            "kind": "function",
            "lineno": 50,
            "end_lineno": 60,
            "score": 8.0,
        },
        {
            "path": "src/b.py",
            "qualified_name": "b.first",
            "kind": "function",
            "lineno": 10,
            "end_lineno": 20,
            "score": 7.0,
        },
        {
            "path": "src/c.py",
            "qualified_name": "c.first",
            "kind": "function",
            "lineno": 10,
            "end_lineno": 20,
            "score": 6.0,
        },
    ]

    packed = pack_source_plan_chunks(
        prioritized_chunks=copy.deepcopy(prioritized_chunks),
        focused_files=["src/a.py", "src/b.py", "src/c.py"],
        chunk_top_k=4,
    )

    assert [item["path"] for item in packed] == [
        "src/a.py",
        "src/b.py",
        "src/c.py",
        "src/a.py",
    ]


def test_pack_source_plan_chunks_prefers_graph_closure_bonus_after_anchor_selection() -> None:
    prioritized_chunks = [
        {
            "path": "src/a.py",
            "qualified_name": "a.anchor",
            "kind": "function",
            "lineno": 10,
            "end_lineno": 20,
            "score": 10.0,
        },
        {
            "path": "src/b.py",
            "qualified_name": "b.first",
            "kind": "function",
            "lineno": 10,
            "end_lineno": 20,
            "score": 9.0,
        },
        {
            "path": "src/a.py",
            "qualified_name": "a.neighbor",
            "kind": "function",
            "lineno": 30,
            "end_lineno": 40,
            "score": 8.0,
            "score_breakdown": {"graph_closure_bonus": 0.12},
        },
        {
            "path": "src/c.py",
            "qualified_name": "c.first",
            "kind": "function",
            "lineno": 10,
            "end_lineno": 20,
            "score": 7.0,
        },
    ]

    packed = pack_source_plan_chunks(
        prioritized_chunks=copy.deepcopy(prioritized_chunks),
        focused_files=["src/a.py", "src/b.py", "src/c.py"],
        chunk_top_k=4,
    )

    assert [item["qualified_name"] for item in packed] == [
        "a.anchor",
        "a.neighbor",
        "b.first",
        "c.first",
    ]


def test_pack_source_plan_chunks_can_disable_graph_closure_preference() -> None:
    packed, metadata = pack_source_plan_chunks(
        prioritized_chunks=[
            {
                "path": "src/a.py",
                "qualified_name": "a.anchor",
                "kind": "function",
                "lineno": 10,
                "end_lineno": 20,
                "score": 10.0,
            },
            {
                "path": "src/b.py",
                "qualified_name": "b.first",
                "kind": "function",
                "lineno": 10,
                "end_lineno": 20,
                "score": 9.0,
            },
            {
                "path": "src/a.py",
                "qualified_name": "a.neighbor",
                "kind": "function",
                "lineno": 30,
                "end_lineno": 40,
                "score": 8.0,
                "score_breakdown": {"graph_closure_bonus": 0.12},
            },
            {
                "path": "src/c.py",
                "qualified_name": "c.first",
                "kind": "function",
                "lineno": 10,
                "end_lineno": 20,
                "score": 7.0,
            },
        ],
        focused_files=["src/a.py", "src/b.py", "src/c.py"],
        chunk_top_k=4,
        graph_closure_preference_enabled=False,
        return_metadata=True,
    )

    assert [item["qualified_name"] for item in packed] == [
        "a.anchor",
        "b.first",
        "c.first",
        "a.neighbor",
    ]
    assert metadata == {
        "graph_closure_preference_enabled": False,
        "graph_closure_bonus_candidate_count": 1,
        "graph_closure_preferred_count": 0,
        "focused_file_promoted_count": 3,
        "packed_path_count": 3,
        "reason": "disabled_by_policy",
    }


def test_rank_source_plan_chunks_preserves_candidate_breakdown_for_packing() -> None:
    ranked = rank_source_plan_chunks(
        suspicious_chunks=[
            {
                "path": "src/a.py",
                "qualified_name": "a.anchor",
                "kind": "function",
                "lineno": 10,
                "end_lineno": 20,
                "score": 1.5,
            }
        ],
        candidate_chunks=[
            {
                "path": "src/a.py",
                "qualified_name": "a.anchor",
                "kind": "function",
                "lineno": 10,
                "end_lineno": 20,
                "score": 10.0,
                "score_breakdown": {
                    "graph_prior": 0.35,
                    "graph_closure_bonus": 0.12,
                },
            }
        ],
        test_signal_weight=2.0,
    )

    assert len(ranked) == 1
    assert ranked[0]["score"] == 13.0
    assert ranked[0]["score_breakdown"] == {
        "graph_prior": 0.35,
        "graph_closure_bonus": 0.12,
        "candidate": 10.0,
        "test_signal": 3.0,
    }


def test_run_source_plan_prefers_packed_multi_file_chunk_order() -> None:
    ctx = StageContext(query="fix chunk sufficiency", repo="demo", root=".")
    ctx.state = {
        "index": {
            "candidate_files": [
                {"path": "src/a.py"},
                {"path": "src/b.py"},
                {"path": "src/c.py"},
            ],
            "candidate_chunks": [
                {
                    "path": "src/a.py",
                    "qualified_name": "a.first",
                    "kind": "function",
                    "lineno": 10,
                    "end_lineno": 20,
                    "score": 10.0,
                },
                {
                    "path": "src/a.py",
                    "qualified_name": "a.second",
                    "kind": "function",
                    "lineno": 30,
                    "end_lineno": 40,
                    "score": 9.0,
                },
                {
                    "path": "src/b.py",
                    "qualified_name": "b.first",
                    "kind": "function",
                    "lineno": 10,
                    "end_lineno": 20,
                    "score": 8.0,
                },
                {
                    "path": "src/c.py",
                    "qualified_name": "c.first",
                    "kind": "function",
                    "lineno": 10,
                    "end_lineno": 20,
                    "score": 7.0,
                },
            ],
            "chunk_metrics": {"chunk_budget_used": 88.0},
        },
        "repomap": {
            "focused_files": ["src/a.py", "src/b.py", "src/c.py"],
        },
        "augment": {
            "diagnostics": [],
            "xref": {"count": 0, "results": []},
            "tests": {},
        },
        "skills": {"selected": []},
        "__policy": {"name": "general", "version": "v1", "test_signal_weight": 1.0},
    }

    result = run_source_plan(
        ctx=ctx,
        pipeline_order=["index", "repomap", "augment", "skills", "source_plan"],
        chunk_top_k=4,
        chunk_per_file_limit=2,
        chunk_token_budget=200,
        chunk_disclosure="refs",
        policy_version="v1",
    )

    assert [item["path"] for item in result["candidate_chunks"]] == [
        "src/a.py",
        "src/b.py",
        "src/c.py",
        "src/a.py",
    ]
    assert [item["chunk_ref"]["path"] for item in result["chunk_steps"]] == [
        "src/a.py",
        "src/b.py",
        "src/c.py",
        "src/a.py",
    ]


def test_run_source_plan_packs_graph_closure_bonus_before_uncovered_focus() -> None:
    ctx = StageContext(query="fix graph-near closure context", repo="demo", root=".")
    ctx.state = {
        "index": {
            "candidate_files": [
                {"path": "src/a.py"},
                {"path": "src/b.py"},
                {"path": "src/c.py"},
            ],
            "candidate_chunks": [
                {
                    "path": "src/a.py",
                    "qualified_name": "a.anchor",
                    "kind": "function",
                    "lineno": 10,
                    "end_lineno": 20,
                    "score": 10.0,
                },
                {
                    "path": "src/b.py",
                    "qualified_name": "b.first",
                    "kind": "function",
                    "lineno": 10,
                    "end_lineno": 20,
                    "score": 9.0,
                },
                {
                    "path": "src/a.py",
                    "qualified_name": "a.neighbor",
                    "kind": "function",
                    "lineno": 30,
                    "end_lineno": 40,
                    "score": 8.0,
                    "score_breakdown": {"graph_closure_bonus": 0.12},
                },
                {
                    "path": "src/c.py",
                    "qualified_name": "c.first",
                    "kind": "function",
                    "lineno": 10,
                    "end_lineno": 20,
                    "score": 7.0,
                },
            ],
            "chunk_metrics": {"chunk_budget_used": 88.0},
        },
        "repomap": {
            "focused_files": ["src/a.py", "src/b.py", "src/c.py"],
        },
        "augment": {
            "diagnostics": [],
            "xref": {"count": 0, "results": []},
            "tests": {},
        },
        "skills": {"selected": []},
        "__policy": {"name": "general", "version": "v1", "test_signal_weight": 1.0},
    }

    result = run_source_plan(
        ctx=ctx,
        pipeline_order=["index", "repomap", "augment", "skills", "source_plan"],
        chunk_top_k=4,
        chunk_per_file_limit=2,
        chunk_token_budget=200,
        chunk_disclosure="refs",
        policy_version="v1",
    )

    assert [item["qualified_name"] for item in result["candidate_chunks"]] == [
        "a.anchor",
        "a.neighbor",
        "b.first",
        "c.first",
    ]
    assert [item["chunk_ref"]["qualified_name"] for item in result["chunk_steps"]] == [
        "a.anchor",
        "a.neighbor",
        "b.first",
        "c.first",
    ]
    assert result["packing"] == {
        "graph_closure_preference_enabled": True,
        "graph_closure_bonus_candidate_count": 1,
        "graph_closure_preferred_count": 1,
        "focused_file_promoted_count": 3,
        "packed_path_count": 3,
        "reason": "ok",
    }


def test_run_source_plan_can_disable_graph_closure_packing_preference() -> None:
    ctx = StageContext(query="fix graph-near closure context", repo="demo", root=".")
    ctx.state = {
        "index": {
            "candidate_files": [
                {"path": "src/a.py"},
                {"path": "src/b.py"},
                {"path": "src/c.py"},
            ],
            "candidate_chunks": [
                {
                    "path": "src/a.py",
                    "qualified_name": "a.anchor",
                    "kind": "function",
                    "lineno": 10,
                    "end_lineno": 20,
                    "score": 10.0,
                },
                {
                    "path": "src/b.py",
                    "qualified_name": "b.first",
                    "kind": "function",
                    "lineno": 10,
                    "end_lineno": 20,
                    "score": 9.0,
                },
                {
                    "path": "src/a.py",
                    "qualified_name": "a.neighbor",
                    "kind": "function",
                    "lineno": 30,
                    "end_lineno": 40,
                    "score": 8.0,
                    "score_breakdown": {"graph_closure_bonus": 0.12},
                },
                {
                    "path": "src/c.py",
                    "qualified_name": "c.first",
                    "kind": "function",
                    "lineno": 10,
                    "end_lineno": 20,
                    "score": 7.0,
                },
            ],
            "chunk_metrics": {"chunk_budget_used": 88.0},
        },
        "repomap": {
            "focused_files": ["src/a.py", "src/b.py", "src/c.py"],
        },
        "augment": {
            "diagnostics": [],
            "xref": {"count": 0, "results": []},
            "tests": {},
        },
        "skills": {"selected": []},
        "__policy": {
            "name": "general",
            "version": "v1",
            "test_signal_weight": 1.0,
            "source_plan_graph_closure_pack_enabled": False,
        },
    }

    result = run_source_plan(
        ctx=ctx,
        pipeline_order=["index", "repomap", "augment", "skills", "source_plan"],
        chunk_top_k=4,
        chunk_per_file_limit=2,
        chunk_token_budget=200,
        chunk_disclosure="refs",
        policy_version="v1",
    )

    assert [item["qualified_name"] for item in result["candidate_chunks"]] == [
        "a.anchor",
        "b.first",
        "c.first",
        "a.neighbor",
    ]
    assert result["packing"] == {
        "graph_closure_preference_enabled": False,
        "graph_closure_bonus_candidate_count": 1,
        "graph_closure_preferred_count": 0,
        "focused_file_promoted_count": 3,
        "packed_path_count": 3,
        "reason": "disabled_by_policy",
    }


def test_run_source_plan_emits_machine_readable_grounding_roles() -> None:
    ctx = StageContext(query="triage auth planner grounding", repo="demo", root=".")
    ctx.state = {
        "index": {
            "candidate_files": [
                {"path": "src/direct.py"},
                {"path": "src/primary.py"},
            ],
            "candidate_chunks": [
                {
                    "path": "src/direct.py",
                    "qualified_name": "direct_hit",
                    "kind": "function",
                    "lineno": 10,
                    "end_lineno": 20,
                    "score": 5.0,
                },
                {
                    "path": "src/neighbor.py",
                    "qualified_name": "neighbor_hit",
                    "kind": "function",
                    "lineno": 30,
                    "end_lineno": 40,
                    "score": 3.0,
                },
            ],
            "chunk_metrics": {"chunk_budget_used": 42.0},
        },
        "repomap": {
            "focused_files": ["src/direct.py", "src/neighbor.py", "src/hint.py"],
        },
        "augment": {
            "diagnostics": [],
            "xref": {"count": 0, "results": []},
            "tests": {
                "suspicious_chunks": [
                    {
                        "path": "src/direct.py",
                        "qualified_name": "direct_hit",
                        "kind": "function",
                        "lineno": 10,
                        "end_lineno": 20,
                        "score": 1.0,
                    },
                    {
                        "path": "src/hint.py",
                        "qualified_name": "hint_only",
                        "kind": "function",
                        "lineno": 50,
                        "end_lineno": 60,
                        "score": 2.0,
                    },
                ],
                "suggested_tests": [],
            },
        },
        "skills": {"selected": []},
        "__policy": {"name": "bugfix_test", "version": "v1", "test_signal_weight": 2.0},
    }

    result = run_source_plan(
        ctx=ctx,
        pipeline_order=["index", "repomap", "augment", "skills", "source_plan"],
        chunk_top_k=4,
        chunk_per_file_limit=2,
        chunk_token_budget=200,
        chunk_disclosure="refs",
        policy_version="v1",
    )

    roles_by_name = {
        str(item.get("qualified_name")): item["evidence"]["role"]
        for item in result["candidate_chunks"]
    }
    assert roles_by_name["direct_hit"] == "direct"
    assert roles_by_name["neighbor_hit"] == "neighbor_context"
    assert roles_by_name["hint_only"] == "hint_only"

    direct_chunk = next(
        item for item in result["candidate_chunks"] if item["qualified_name"] == "direct_hit"
    )
    assert direct_chunk["evidence"] == {
        "role": "direct",
        "direct_retrieval": True,
        "neighbor_context": False,
        "hint_only": False,
        "hint_support": True,
        "sources": ["direct_candidate", "test_hint"],
    }

    chunk_step_ref = next(
        item["chunk_ref"]
        for item in result["chunk_steps"]
        if item["chunk_ref"]["qualified_name"] == "hint_only"
    )
    assert chunk_step_ref["evidence"]["role"] == "hint_only"

    source_plan_step = next(
        item for item in result["steps"] if item.get("stage") == "source_plan"
    )
    step_roles = [
        item["evidence"]["role"] for item in source_plan_step["candidate_chunks"][:3]
    ]
    assert step_roles == ["direct", "neighbor_context", "hint_only"]

    assert result["evidence_summary"] == {
        "direct_count": 1.0,
        "neighbor_context_count": 1.0,
        "hint_only_count": 1.0,
        "direct_ratio": 1.0 / 3.0,
        "neighbor_context_ratio": 1.0 / 3.0,
        "hint_only_ratio": 1.0 / 3.0,
    }
