from __future__ import annotations

from itertools import permutations

from ace_lite.prompt_rendering.renderer import (
    PROMPT_RENDERER_BOUNDARY_VERSION,
    build_prompt_rendering_boundary,
    render_prompt,
)
from ace_lite.chunking.skeleton import CHUNK_SKELETON_SCHEMA_VERSION
from ace_lite.pipeline.stages.source_plan import run_source_plan
from ace_lite.pipeline.types import StageContext
from ace_lite.prompt_rendering.segments import (
    SEGMENT_HASH_ALGORITHM,
    SEGMENT_ORDERING,
    PromptSegment,
    canonicalize_segments,
)
from ace_lite.source_plan.steps import build_source_plan_steps
from ace_lite.validation.result import build_validation_result_v1


def _sample_segments() -> list[dict[str, object]]:
    return [
        {
            "segment_id": "candidate-beta",
            "kind": "candidate_chunk",
            "heading": "Candidate Beta",
            "body": "Inspect beta chunk.",
            "priority": 5,
            "path": "src/beta.py",
            "qualified_name": "beta.run",
            "lineno": 30,
            "metadata": {"role": "neighbor_context"},
        },
        {
            "segment_id": "candidate-alpha",
            "kind": "candidate_chunk",
            "heading": "Candidate Alpha",
            "body": "Inspect alpha chunk.",
            "priority": 5,
            "path": "src/alpha.py",
            "qualified_name": "alpha.run",
            "lineno": 10,
            "metadata": {"role": "direct"},
        },
        {
            "segment_id": "constraints",
            "kind": "constraints",
            "heading": "Constraints",
            "body": "Preserve public contract.",
            "priority": 9,
            "metadata": {"strict": True},
        },
    ]


def test_canonicalize_segments_is_order_invariant() -> None:
    expected_signature: list[tuple[str, str, int]] | None = None

    for order in permutations(_sample_segments()):
        ordered = canonicalize_segments(order)
        signature = [
            (segment.segment_id, segment.path, segment.priority) for segment in ordered
        ]
        if expected_signature is None:
            expected_signature = signature
            continue
        assert signature == expected_signature

    assert expected_signature == [
        ("constraints", "", 9),
        ("candidate-alpha", "src/alpha.py", 5),
        ("candidate-beta", "src/beta.py", 5),
    ]


def test_prompt_segment_hash_is_metadata_order_invariant() -> None:
    left = PromptSegment(
        segment_id="chunk",
        kind="candidate_chunk",
        heading="Candidate",
        body="Inspect the chunk.",
        priority=4,
        path="src/app.py",
        qualified_name="run",
        lineno=11,
        metadata={"b": [2, 1], "a": {"y": 2, "x": 1}},
    )
    right = PromptSegment(
        segment_id="chunk",
        kind="candidate_chunk",
        heading="Candidate",
        body="Inspect the chunk.",
        priority=4,
        path="src/app.py",
        qualified_name="run",
        lineno=11,
        metadata={"a": {"x": 1, "y": 2}, "b": [2, 1]},
    )

    assert left.segment_hash == right.segment_hash


def test_render_prompt_uses_canonical_order_and_stable_manifest() -> None:
    baseline = render_prompt(_sample_segments())
    reversed_render = render_prompt(reversed(_sample_segments()))

    assert baseline.text == reversed_render.text
    assert baseline.prompt_hash == reversed_render.prompt_hash
    assert [segment.segment_id for segment in baseline.segments] == [
        "constraints",
        "candidate-alpha",
        "candidate-beta",
    ]
    assert baseline.manifest == {
        "boundary_version": PROMPT_RENDERER_BOUNDARY_VERSION,
        "ordering": SEGMENT_ORDERING,
        "hash_algorithm": SEGMENT_HASH_ALGORITHM,
        "segment_count": 3,
        "segment_hashes": [segment.segment_hash for segment in baseline.segments],
        "prompt_hash": baseline.prompt_hash,
    }


def test_build_source_plan_steps_exposes_prompt_rendering_boundary_metadata() -> None:
    validation_result = build_validation_result_v1(
        replay_key="validation-run-001",
        selected_tests=["pytest -q tests/unit/test_prompt_rendering_boundary.py"],
        executed_tests=["pytest -q tests/unit/test_prompt_rendering_boundary.py"],
        probes=[
            {
                "name": "compile",
                "status": "failed",
                "selected": True,
                "executed": True,
                "issues": [
                    {
                        "code": "probe.compile.failed",
                        "message": "compile probe failed",
                        "path": "src/alpha.py",
                    }
                ],
            }
        ],
        status="failed",
    ).as_dict()
    steps = build_source_plan_steps(
        index_stage={"targets": [], "languages_covered": []},
        repomap_stage={"seed_count": 1, "neighbor_count": 0},
        augment_stage={"vcs_history": {}, "vcs_worktree": {}},
        skills_stage={"selected": []},
        focused_files=["src/alpha.py"],
        prioritized_chunks=[
            {
                "path": "src/alpha.py",
                "qualified_name": "alpha.run",
                "kind": "function",
                "lineno": 10,
                "end_lineno": 20,
                "score": 1.0,
            }
        ],
        candidate_chunk_count=1,
        suspicious_chunk_count=0,
        diagnostics=[],
        xref={"count": 0},
        tests={"failures": []},
        validation_tests=["pytest -q tests/unit/test_prompt_rendering_boundary.py"],
        subgraph_payload={
            "payload_version": "subgraph_payload_v1",
            "taxonomy_version": "subgraph_edge_taxonomy_v1",
            "enabled": False,
            "reason": "disabled",
            "seed_paths": [],
            "edge_counts": {},
        },
        validation_result=validation_result,
    )

    source_plan_step = next(
        item for item in steps if item.get("stage") == "source_plan"
    )
    assert source_plan_step["prompt_rendering_boundary"] == {
        **build_prompt_rendering_boundary(),
    }
    assert source_plan_step["subgraph_payload"]["payload_version"] == "subgraph_payload_v1"
    validate_step = next(item for item in steps if item.get("stage") == "validate")
    assert validate_step["validation_feedback_summary"] == {
        "status": "failed",
        "issue_count": 1,
        "probe_status": "failed",
        "probe_issue_count": 1,
        "probe_executed_count": 1,
        "selected_test_count": 1,
        "executed_test_count": 1,
    }


def test_run_source_plan_exposes_top_level_contract_metadata() -> None:
    ctx = StageContext(
        query="validate token behavior",
        repo="demo",
        root="/tmp/demo",
        state={
            "memory": {"hits_preview": []},
            "index": {
                "candidate_files": [{"path": "src/auth.py"}],
                "candidate_chunks": [
                    {
                        "path": "src/auth.py",
                        "qualified_name": "validate_token",
                        "kind": "function",
                        "lineno": 10,
                        "end_lineno": 20,
                        "score": 1.0,
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
                    }
                ],
                "chunk_metrics": {"chunk_budget_used": 32},
            },
            "repomap": {"focused_files": ["src/auth.py"], "seed_count": 1, "neighbor_count": 0},
            "augment": {"tests": {}, "xref": {}, "diagnostics": [], "vcs_history": {}, "vcs_worktree": {}},
            "skills": {"selected": []},
            "__policy": {"name": "general", "version": "v1"},
        },
    )

    payload = run_source_plan(
        ctx=ctx,
        pipeline_order=["memory", "index", "repomap", "augment", "skills", "source_plan"],
        chunk_top_k=8,
        chunk_per_file_limit=2,
        chunk_token_budget=256,
        chunk_disclosure="skeleton_light",
        policy_version="v1",
    )

    assert payload["prompt_rendering_boundary"] == build_prompt_rendering_boundary()
    assert payload["chunk_contract"] == {
        "schema_version": CHUNK_SKELETON_SCHEMA_VERSION,
        "requested_disclosure": "skeleton_light",
        "observed_disclosures": ["skeleton_light"],
        "fallback_count": 0,
        "chunk_count": 1,
        "skeleton_chunk_count": 1,
        "skeleton_modes": ["skeleton_light"],
        "skeleton_schema_versions": [CHUNK_SKELETON_SCHEMA_VERSION],
    }
    assert payload["subgraph_payload"]["payload_version"] == "subgraph_payload_v1"
    assert payload["subgraph_payload"]["taxonomy_version"] == "subgraph_edge_taxonomy_v1"


def test_run_source_plan_keeps_prompt_boundary_isolated_from_internal_sidecars() -> None:
    ctx = StageContext(
        query="trace prompt boundary sidecar isolation",
        repo="demo",
        root="/tmp/demo",
        state={
            "memory": {"hits_preview": []},
            "index": {
                "candidate_files": [{"path": "src/auth.py"}],
                "candidate_chunks": [
                    {
                        "path": "src/auth.py",
                        "qualified_name": "validate_token",
                        "kind": "function",
                        "lineno": 10,
                        "end_lineno": 20,
                        "score": 1.0,
                        "disclosure": "refs",
                        "_retrieval_context": "module=src.auth\nsymbol=validate_token",
                        "_contextual_chunking_sidecar": {
                            "schema_version": "contextual_chunking_sidecar_v1",
                            "symbol_path": "src.auth:validate_token",
                            "module_hint": "src.auth",
                        },
                        "_robust_signature_lite": {
                            "available": True,
                            "compatibility_domain": "src/auth.py::function",
                        },
                        "_topological_shield": {
                            "enabled": True,
                            "attenuation": 0.15,
                        },
                    }
                ],
                "chunk_metrics": {"chunk_budget_used": 24},
            },
            "repomap": {
                "focused_files": ["src/auth.py"],
                "seed_count": 1,
                "neighbor_count": 0,
            },
            "augment": {
                "tests": {},
                "xref": {},
                "diagnostics": [],
                "vcs_history": {},
                "vcs_worktree": {},
            },
            "skills": {"selected": []},
            "__policy": {"name": "general", "version": "v1"},
        },
    )

    payload = run_source_plan(
        ctx=ctx,
        pipeline_order=["memory", "index", "repomap", "augment", "skills", "source_plan"],
        chunk_top_k=8,
        chunk_per_file_limit=2,
        chunk_token_budget=256,
        chunk_disclosure="refs",
        policy_version="v1",
    )

    source_plan_step = next(
        item for item in payload["steps"] if item.get("stage") == "source_plan"
    )

    assert payload["prompt_rendering_boundary"] == build_prompt_rendering_boundary()
    assert source_plan_step["prompt_rendering_boundary"] == build_prompt_rendering_boundary()

    for forbidden_key in (
        "_retrieval_context",
        "_contextual_chunking_sidecar",
        "_robust_signature_lite",
        "_topological_shield",
    ):
        assert forbidden_key not in payload["candidate_chunks"][0]
        assert forbidden_key not in source_plan_step["candidate_chunks"][0]
