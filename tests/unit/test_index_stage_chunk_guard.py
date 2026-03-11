from __future__ import annotations

from ace_lite.index_stage.chunk_guard import apply_chunk_guard


def test_apply_chunk_guard_off_preserves_chunk_identity_and_order() -> None:
    chunks = [
        {"path": "src/a.py", "signature": "def a() -> int"},
        {"path": "src/b.py", "signature": "def b() -> int"},
    ]

    result = apply_chunk_guard(
        candidate_chunks=chunks,
        enabled=False,
        mode="off",
        lambda_penalty=0.8,
        min_pool=4,
        max_pool=32,
        min_marginal_utility=0.0,
        compatibility_min_overlap=0.3,
    )

    assert result.candidate_chunks == chunks
    assert result.chunk_guard_payload["enabled"] is False
    assert result.chunk_guard_payload["mode"] == "off"
    assert result.chunk_guard_payload["reason"] == "disabled"


def test_apply_chunk_guard_report_only_counts_signatures_without_filtering() -> None:
    chunks = [
        {
            "path": "src/a.py",
            "qualified_name": "pkg.service_v1",
            "lineno": 1,
            "end_lineno": 3,
            "signature": "def service_v1(token: str) -> bool",
            "score": 1.0,
        },
        {
            "path": "src/b.py",
            "qualified_name": "pkg.service_v2",
            "lineno": 1,
            "end_lineno": 3,
            "signature": "def service_v2(token: str, *, strict: bool = False) -> bool",
            "score": 0.2,
        },
        {
            "path": "src/c.py",
            "qualified_name": "pkg.helper",
            "lineno": 1,
            "end_lineno": 3,
            "signature": "",
            "score": 0.1,
        },
    ]
    sidecar = {
        "src/a.py|1|3|pkg.service_v1": {
            "available": True,
            "compatibility_domain": "service",
            "shape_hash": "shape-a",
            "entity_vocab": ("service", "token", "auth"),
        },
        "src/b.py|1|3|pkg.service_v2": {
            "available": True,
            "compatibility_domain": "service",
            "shape_hash": "shape-b",
            "entity_vocab": ("service", "token", "auth"),
        },
    }

    result = apply_chunk_guard(
        candidate_chunks=chunks,
        robust_signature_sidecar=sidecar,
        enabled=True,
        mode="report_only",
        lambda_penalty=1.0,
        min_pool=1,
        max_pool=32,
        min_marginal_utility=0.0,
        compatibility_min_overlap=0.3,
    )

    assert result.candidate_chunks == chunks
    assert result.chunk_guard_payload["enabled"] is True
    assert result.chunk_guard_payload["report_only"] is True
    assert result.chunk_guard_payload["signed_chunk_count"] == 2
    assert result.chunk_guard_payload["filtered_count"] == 1
    assert result.chunk_guard_payload["retained_count"] == 2
    assert result.chunk_guard_payload["pairwise_conflict_count"] == 1
    assert result.chunk_guard_payload["max_conflict_penalty"] > 0.0
    assert result.chunk_guard_payload["retained_refs"] == ["pkg.service_v1", "pkg.helper"]
    assert result.chunk_guard_payload["filtered_refs"] == ["pkg.service_v2"]


def test_apply_chunk_guard_enforce_filters_deterministic_subset() -> None:
    chunks = [
        {
            "path": "src/a.py",
            "qualified_name": "pkg.service_v1",
            "lineno": 1,
            "end_lineno": 3,
            "signature": "def service_v1(token: str) -> bool",
            "score": 1.0,
        },
        {
            "path": "src/b.py",
            "qualified_name": "pkg.service_v2",
            "lineno": 1,
            "end_lineno": 3,
            "signature": "def service_v2(token: str, *, strict: bool = False) -> bool",
            "score": 0.2,
        },
        {
            "path": "src/c.py",
            "qualified_name": "pkg.helper",
            "lineno": 1,
            "end_lineno": 3,
            "signature": "",
            "score": 0.1,
        },
    ]
    sidecar = {
        "src/a.py|1|3|pkg.service_v1": {
            "available": True,
            "compatibility_domain": "service",
            "shape_hash": "shape-a",
            "entity_vocab": ("service", "token", "auth"),
        },
        "src/b.py|1|3|pkg.service_v2": {
            "available": True,
            "compatibility_domain": "service",
            "shape_hash": "shape-b",
            "entity_vocab": ("service", "token", "auth"),
        },
    }

    result = apply_chunk_guard(
        candidate_chunks=chunks,
        robust_signature_sidecar=sidecar,
        enabled=True,
        mode="enforce",
        lambda_penalty=1.0,
        min_pool=1,
        max_pool=32,
        min_marginal_utility=0.0,
        compatibility_min_overlap=0.3,
    )

    assert result.candidate_chunks == [chunks[0], chunks[2]]
    assert result.chunk_guard_payload["enabled"] is True
    assert result.chunk_guard_payload["fallback"] is False
    assert result.chunk_guard_payload["reason"] == "enforce_applied"
    assert result.chunk_guard_payload["filtered_count"] == 1
    assert result.chunk_guard_payload["retained_count"] == 2
    assert result.chunk_guard_payload["filtered_refs"] == ["pkg.service_v2"]
    assert result.chunk_guard_payload["retained_refs"] == ["pkg.service_v1", "pkg.helper"]


def test_apply_chunk_guard_enforce_is_deterministic_across_input_permutations() -> None:
    chunks = [
        {
            "path": "src/a.py",
            "qualified_name": "pkg.service_v1",
            "lineno": 1,
            "end_lineno": 3,
            "signature": "def service_v1(token: str) -> bool",
            "score": 1.0,
        },
        {
            "path": "src/b.py",
            "qualified_name": "pkg.service_v2",
            "lineno": 1,
            "end_lineno": 3,
            "signature": "def service_v2(token: str, *, strict: bool = False) -> bool",
            "score": 0.2,
        },
        {
            "path": "src/c.py",
            "qualified_name": "pkg.helper",
            "lineno": 1,
            "end_lineno": 3,
            "signature": "",
            "score": 0.1,
        },
    ]
    sidecar = {
        "src/a.py|1|3|pkg.service_v1": {
            "available": True,
            "compatibility_domain": "service",
            "shape_hash": "shape-a",
            "entity_vocab": ("service", "token", "auth"),
        },
        "src/b.py|1|3|pkg.service_v2": {
            "available": True,
            "compatibility_domain": "service",
            "shape_hash": "shape-b",
            "entity_vocab": ("service", "token", "auth"),
        },
    }

    baseline = apply_chunk_guard(
        candidate_chunks=chunks,
        robust_signature_sidecar=sidecar,
        enabled=True,
        mode="enforce",
        lambda_penalty=1.0,
        min_pool=1,
        max_pool=32,
        min_marginal_utility=0.0,
        compatibility_min_overlap=0.3,
    )
    permuted = apply_chunk_guard(
        candidate_chunks=[chunks[2], chunks[1], chunks[0]],
        robust_signature_sidecar=sidecar,
        enabled=True,
        mode="enforce",
        lambda_penalty=1.0,
        min_pool=1,
        max_pool=32,
        min_marginal_utility=0.0,
        compatibility_min_overlap=0.3,
    )

    assert [item["qualified_name"] for item in baseline.candidate_chunks] == [
        "pkg.service_v1",
        "pkg.helper",
    ]
    assert [item["qualified_name"] for item in permuted.candidate_chunks] == [
        "pkg.service_v1",
        "pkg.helper",
    ]
    assert baseline.chunk_guard_payload["filtered_refs"] == ["pkg.service_v2"]
    assert permuted.chunk_guard_payload["filtered_refs"] == ["pkg.service_v2"]


def test_apply_chunk_guard_enforce_fails_open_without_signatures() -> None:
    chunks = [{"path": "src/a.py", "qualified_name": "pkg.a", "signature": ""}]

    result = apply_chunk_guard(
        candidate_chunks=chunks,
        enabled=True,
        mode="enforce",
        lambda_penalty=0.8,
        min_pool=1,
        max_pool=32,
        min_marginal_utility=0.0,
        compatibility_min_overlap=0.3,
    )

    assert result.candidate_chunks == chunks
    assert result.chunk_guard_payload["enabled"] is True
    assert result.chunk_guard_payload["fallback"] is True
    assert result.chunk_guard_payload["reason"] == "no_signatures"
