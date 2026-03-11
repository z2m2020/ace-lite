from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ace_lite.index_stage.chunk_selection import apply_chunk_selection


@dataclass(frozen=True, slots=True)
class _FakeStats:
    reranked_count: int = 0
    similarity_mean: float = 0.0
    similarity_max: float = 0.0


def _build_chunks(**kwargs: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return (
        [
            {
                "path": "src/app.py",
                "qualified_name": "app.handler",
                "signature": "def handler() -> None",
                "snippet": "def handler() -> None:\n    pass",
                "robust_signature_summary": {
                    "version": "v1",
                    "available": True,
                    "compatibility_domain": "src/app.py::function",
                    "shape_hash": "shape123",
                    "entity_vocab_count": 4,
                },
                "_robust_signature_lite": {
                    "version": "v1",
                    "available": True,
                    "compatibility_domain": "src/app.py::function",
                    "entity_vocab": ("app", "handler"),
                    "shape_hash": "shape123",
                    "shape_features_count": 3,
                    "entity_vocab_count": 2,
                },
            }
        ],
        {
            "chunk_count": 1,
            "robust_signature_count": 1.0,
            "robust_signature_coverage_ratio": 1.0,
        },
    )


def _build_chunks_with_topological_shield(
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _ = kwargs
    return (
        [
            {
                "path": "src/app.py",
                "qualified_name": "app.handler",
                "signature": "def handler() -> None",
                "snippet": "def handler() -> None:\n    pass",
                "score": 1.0,
                "score_breakdown": {
                    "topological_shield_attenuation": 0.4,
                    "topological_shield_adjacency_evidence_count": 1.0,
                    "topological_shield_shared_parent_evidence_count": 1.0,
                    "topological_shield_graph_attested": 1.0,
                },
                "robust_signature_summary": {
                    "version": "v1",
                    "available": True,
                    "compatibility_domain": "src/app.py::function",
                    "shape_hash": "shape123",
                    "entity_vocab_count": 4,
                },
                "_robust_signature_lite": {
                    "version": "v1",
                    "available": True,
                    "compatibility_domain": "src/app.py::function",
                    "entity_vocab": ("app", "handler"),
                    "shape_hash": "shape123",
                    "shape_features_count": 3,
                    "entity_vocab_count": 2,
                },
            }
        ],
        {
            "chunk_count": 1,
            "robust_signature_count": 1.0,
            "robust_signature_coverage_ratio": 1.0,
            "topological_shield_enabled": 1.0,
            "topological_shield_report_only": 1.0,
            "topological_shield_attenuated_chunk_count": 1.0,
            "topological_shield_coverage_ratio": 1.0,
            "topological_shield_adjacency_evidence_count": 1.0,
            "topological_shield_shared_parent_evidence_count": 1.0,
            "topological_shield_graph_attested_chunk_count": 1.0,
            "topological_shield_attenuation_total": 0.4,
        },
    )


def _build_conflicting_chunks(**kwargs: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _ = kwargs
    return (
        [
            {
                "path": "src/service.py",
                "qualified_name": "pkg.service_v1",
                "kind": "function",
                "lineno": 1,
                "end_lineno": 3,
                "signature": "def service_v1(token: str) -> bool",
                "snippet": "def service_v1(token: str) -> bool:\n    return True",
                "score": 1.0,
                "robust_signature_summary": {
                    "version": "v1",
                    "available": True,
                    "compatibility_domain": "service",
                    "shape_hash": "shape-a",
                    "entity_vocab_count": 3,
                },
                "_robust_signature_lite": {
                    "version": "v1",
                    "available": True,
                    "compatibility_domain": "service",
                    "entity_vocab": ("service", "token", "auth"),
                    "shape_hash": "shape-a",
                    "shape_features_count": 3,
                    "entity_vocab_count": 3,
                },
            },
            {
                "path": "src/service.py",
                "qualified_name": "pkg.service_v2",
                "kind": "function",
                "lineno": 5,
                "end_lineno": 7,
                "signature": "def service_v2(token: str, *, strict: bool = False) -> bool",
                "snippet": "def service_v2(token: str, *, strict: bool = False) -> bool:\n    return False",
                "score": 0.2,
                "robust_signature_summary": {
                    "version": "v1",
                    "available": True,
                    "compatibility_domain": "service",
                    "shape_hash": "shape-b",
                    "entity_vocab_count": 3,
                },
                "_robust_signature_lite": {
                    "version": "v1",
                    "available": True,
                    "compatibility_domain": "service",
                    "entity_vocab": ("service", "token", "auth"),
                    "shape_hash": "shape-b",
                    "shape_features_count": 4,
                    "entity_vocab_count": 3,
                },
            },
            {
                "path": "src/helper.py",
                "qualified_name": "pkg.helper",
                "lineno": 9,
                "end_lineno": 10,
                "signature": "",
                "snippet": "HELPER = True",
                "score": 0.1,
            },
        ],
        {
            "chunk_count": 3,
            "robust_signature_count": 2.0,
            "robust_signature_coverage_ratio": 2.0 / 3.0,
        },
    )


def test_apply_chunk_selection_marks_policy_disabled() -> None:
    timings: list[str] = []

    result = apply_chunk_selection(
        root=".",
        query="explain the handler",
        files_map={"src/app.py": {"path": "src/app.py"}},
        candidates=[{"path": "src/app.py", "score": 1.0}],
        terms=["explain", "handler"],
        top_k_files=4,
        chunk_top_k=8,
        chunk_per_file_limit=2,
        chunk_token_budget=500,
        chunk_guard_enabled=False,
        chunk_guard_mode="off",
        chunk_guard_lambda_penalty=0.8,
        chunk_guard_min_pool=4,
        chunk_guard_max_pool=32,
        chunk_guard_min_marginal_utility=0.0,
        chunk_guard_compatibility_min_overlap=0.3,
        chunk_disclosure="snippet",
        chunk_snippet_max_lines=8,
        chunk_snippet_max_chars=400,
        policy={"chunk_semantic_rerank_enabled": False},
        tokenizer_model="gpt-4o-mini",
        chunk_diversity_enabled=True,
        chunk_diversity_path_penalty=0.1,
        chunk_diversity_symbol_family_penalty=0.1,
        chunk_diversity_kind_penalty=0.1,
        chunk_diversity_locality_penalty=0.1,
        chunk_diversity_locality_window=64,
        chunk_topological_shield_enabled=False,
        chunk_topological_shield_mode="off",
        chunk_topological_shield_max_attenuation=0.6,
        chunk_topological_shield_shared_parent_attenuation=0.2,
        chunk_topological_shield_adjacency_attenuation=0.5,
        index_hash="idx",
        embedding_enabled=True,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        embeddings_payload={
            "runtime_provider": "hash",
            "runtime_model": "hash-v1",
            "runtime_dimension": 16,
        },
        semantic_embedding_provider_impl=None,
        semantic_cross_encoder_provider=None,
        mark_timing=lambda name, started: timings.append(name),
        rerank_rows_embeddings_with_time_budget=lambda **kwargs: ([], _FakeStats()),
        rerank_rows_cross_encoder_with_time_budget=lambda **kwargs: ([], _FakeStats()),
        build_candidate_chunks_fn=_build_chunks,
    )

    assert result.chunk_metrics["chunk_count"] == 1
    assert result.chunk_semantic_rerank_payload["reason"] == "policy_disabled"
    assert result.chunk_guard_payload["reason"] == "disabled"
    assert result.chunk_guard_payload["signed_chunk_count"] == 1
    assert "_robust_signature_lite" not in result.candidate_chunks[0]
    assert result.candidate_chunks[0]["robust_signature_summary"]["available"] is True
    assert timings == ["chunk_build", "chunk_semantic_rerank", "chunk_guard"]


def test_apply_chunk_selection_surfaces_topological_shield_payload() -> None:
    result = apply_chunk_selection(
        root=".",
        query="explain the handler",
        files_map={"src/app.py": {"path": "src/app.py"}},
        candidates=[{"path": "src/app.py", "score": 1.0}],
        terms=["explain", "handler"],
        top_k_files=4,
        chunk_top_k=8,
        chunk_per_file_limit=2,
        chunk_token_budget=500,
        chunk_guard_enabled=False,
        chunk_guard_mode="off",
        chunk_guard_lambda_penalty=0.8,
        chunk_guard_min_pool=4,
        chunk_guard_max_pool=32,
        chunk_guard_min_marginal_utility=0.0,
        chunk_guard_compatibility_min_overlap=0.3,
        chunk_disclosure="snippet",
        chunk_snippet_max_lines=8,
        chunk_snippet_max_chars=400,
        policy={"chunk_semantic_rerank_enabled": False},
        tokenizer_model="gpt-4o-mini",
        chunk_diversity_enabled=True,
        chunk_diversity_path_penalty=0.1,
        chunk_diversity_symbol_family_penalty=0.1,
        chunk_diversity_kind_penalty=0.1,
        chunk_diversity_locality_penalty=0.1,
        chunk_diversity_locality_window=64,
        chunk_topological_shield_enabled=True,
        chunk_topological_shield_mode="report_only",
        chunk_topological_shield_max_attenuation=0.6,
        chunk_topological_shield_shared_parent_attenuation=0.2,
        chunk_topological_shield_adjacency_attenuation=0.5,
        index_hash="idx",
        embedding_enabled=True,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        embeddings_payload={
            "runtime_provider": "hash",
            "runtime_model": "hash-v1",
            "runtime_dimension": 16,
        },
        semantic_embedding_provider_impl=None,
        semantic_cross_encoder_provider=None,
        mark_timing=lambda name, started: None,
        rerank_rows_embeddings_with_time_budget=lambda **kwargs: ([], _FakeStats()),
        rerank_rows_cross_encoder_with_time_budget=lambda **kwargs: ([], _FakeStats()),
        build_candidate_chunks_fn=_build_chunks_with_topological_shield,
    )

    assert result.topological_shield_payload["enabled"] is True
    assert result.topological_shield_payload["report_only"] is True
    assert result.topological_shield_payload["attenuated_chunk_count"] == 1
    assert result.topological_shield_payload["attenuation_total"] == 0.4
    assert result.chunk_guard_payload["mode"] == "off"


def test_apply_chunk_selection_marks_provider_unavailable() -> None:
    result = apply_chunk_selection(
        root=".",
        query="explain the handler",
        files_map={"src/app.py": {"path": "src/app.py"}},
        candidates=[{"path": "src/app.py", "score": 1.0}],
        terms=["explain", "handler"],
        top_k_files=4,
        chunk_top_k=8,
        chunk_per_file_limit=2,
        chunk_token_budget=500,
        chunk_guard_enabled=True,
        chunk_guard_mode="report_only",
        chunk_guard_lambda_penalty=0.8,
        chunk_guard_min_pool=4,
        chunk_guard_max_pool=32,
        chunk_guard_min_marginal_utility=0.0,
        chunk_guard_compatibility_min_overlap=0.3,
        chunk_disclosure="snippet",
        chunk_snippet_max_lines=8,
        chunk_snippet_max_chars=400,
        policy={
            "chunk_semantic_rerank_enabled": True,
            "chunk_semantic_rerank_time_budget_ms": 40,
            "embedding_enabled": True,
        },
        tokenizer_model="gpt-4o-mini",
        chunk_diversity_enabled=True,
        chunk_diversity_path_penalty=0.1,
        chunk_diversity_symbol_family_penalty=0.1,
        chunk_diversity_kind_penalty=0.1,
        chunk_diversity_locality_penalty=0.1,
        chunk_diversity_locality_window=64,
        chunk_topological_shield_enabled=False,
        chunk_topological_shield_mode="off",
        chunk_topological_shield_max_attenuation=0.6,
        chunk_topological_shield_shared_parent_attenuation=0.2,
        chunk_topological_shield_adjacency_attenuation=0.5,
        index_hash="idx",
        embedding_enabled=True,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        embeddings_payload={
            "runtime_provider": "hash",
            "runtime_model": "hash-v1",
            "runtime_dimension": 16,
        },
        semantic_embedding_provider_impl=None,
        semantic_cross_encoder_provider=None,
        mark_timing=lambda name, started: None,
        rerank_rows_embeddings_with_time_budget=lambda **kwargs: ([], _FakeStats()),
        rerank_rows_cross_encoder_with_time_budget=lambda **kwargs: ([], _FakeStats()),
        build_candidate_chunks_fn=_build_chunks,
    )

    assert result.chunk_semantic_rerank_payload["reason"] == "provider_unavailable"
    assert result.chunk_semantic_rerank_payload["fallback"] is False
    assert result.chunk_guard_payload["report_only"] is True


def test_apply_chunk_selection_reranks_rows_with_embeddings() -> None:
    captured: dict[str, Any] = {}

    def _rerank_rows_embeddings(**kwargs: Any) -> tuple[list[dict[str, Any]], _FakeStats]:
        captured["rerank_pool"] = kwargs["rerank_pool"]
        captured["index_path"] = str(kwargs["index_path"])
        return list(reversed(kwargs["rows"])), _FakeStats(
            reranked_count=1,
            similarity_mean=0.5,
            similarity_max=0.9,
        )

    result = apply_chunk_selection(
        root=".",
        query="explain the handler",
        files_map={"src/app.py": {"path": "src/app.py"}},
        candidates=[{"path": "src/app.py", "score": 1.0}],
        terms=["explain", "handler"],
        top_k_files=4,
        chunk_top_k=8,
        chunk_per_file_limit=2,
        chunk_token_budget=500,
        chunk_guard_enabled=True,
        chunk_guard_mode="report_only",
        chunk_guard_lambda_penalty=0.8,
        chunk_guard_min_pool=4,
        chunk_guard_max_pool=32,
        chunk_guard_min_marginal_utility=0.0,
        chunk_guard_compatibility_min_overlap=0.3,
        chunk_disclosure="snippet",
        chunk_snippet_max_lines=8,
        chunk_snippet_max_chars=400,
        policy={
            "chunk_semantic_rerank_enabled": True,
            "chunk_semantic_rerank_time_budget_ms": 40,
            "embedding_enabled": True,
        },
        tokenizer_model="gpt-4o-mini",
        chunk_diversity_enabled=True,
        chunk_diversity_path_penalty=0.1,
        chunk_diversity_symbol_family_penalty=0.1,
        chunk_diversity_kind_penalty=0.1,
        chunk_diversity_locality_penalty=0.1,
        chunk_diversity_locality_window=64,
        chunk_topological_shield_enabled=False,
        chunk_topological_shield_mode="off",
        chunk_topological_shield_max_attenuation=0.6,
        chunk_topological_shield_shared_parent_attenuation=0.2,
        chunk_topological_shield_adjacency_attenuation=0.5,
        index_hash="idx",
        embedding_enabled=True,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        embeddings_payload={
            "runtime_provider": "hash",
            "runtime_model": "hash-v1",
            "runtime_dimension": 16,
        },
        semantic_embedding_provider_impl=object(),
        semantic_cross_encoder_provider=None,
        mark_timing=lambda name, started: None,
        rerank_rows_embeddings_with_time_budget=_rerank_rows_embeddings,
        rerank_rows_cross_encoder_with_time_budget=lambda **kwargs: ([], _FakeStats()),
        build_candidate_chunks_fn=_build_chunks,
    )

    assert captured["rerank_pool"] == 1
    assert captured["index_path"].endswith("context-map\\embeddings\\chunks.index.json")
    assert result.chunk_semantic_rerank_payload["reason"] == "ok"
    assert result.chunk_semantic_rerank_payload["reranked_count"] == 1
    assert result.chunk_guard_payload["retained_count"] == 1


def test_apply_chunk_selection_enforce_filters_conflicting_chunks() -> None:
    result = apply_chunk_selection(
        root=".",
        query="explain the handler",
        files_map={
            "src/service.py": {"path": "src/service.py"},
            "src/helper.py": {"path": "src/helper.py"},
        },
        candidates=[
            {"path": "src/service.py", "score": 1.0},
            {"path": "src/service.py", "score": 0.2},
            {"path": "src/helper.py", "score": 0.1},
        ],
        terms=["explain", "handler"],
        top_k_files=4,
        chunk_top_k=8,
        chunk_per_file_limit=2,
        chunk_token_budget=500,
        chunk_guard_enabled=True,
        chunk_guard_mode="enforce",
        chunk_guard_lambda_penalty=1.0,
        chunk_guard_min_pool=1,
        chunk_guard_max_pool=32,
        chunk_guard_min_marginal_utility=0.0,
        chunk_guard_compatibility_min_overlap=0.3,
        chunk_disclosure="snippet",
        chunk_snippet_max_lines=8,
        chunk_snippet_max_chars=400,
        policy={"chunk_semantic_rerank_enabled": False},
        tokenizer_model="gpt-4o-mini",
        chunk_diversity_enabled=True,
        chunk_diversity_path_penalty=0.1,
        chunk_diversity_symbol_family_penalty=0.1,
        chunk_diversity_kind_penalty=0.1,
        chunk_diversity_locality_penalty=0.1,
        chunk_diversity_locality_window=64,
        chunk_topological_shield_enabled=False,
        chunk_topological_shield_mode="off",
        chunk_topological_shield_max_attenuation=0.6,
        chunk_topological_shield_shared_parent_attenuation=0.2,
        chunk_topological_shield_adjacency_attenuation=0.5,
        index_hash="idx",
        embedding_enabled=True,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        embeddings_payload={
            "runtime_provider": "hash",
            "runtime_model": "hash-v1",
            "runtime_dimension": 16,
        },
        semantic_embedding_provider_impl=None,
        semantic_cross_encoder_provider=None,
        mark_timing=lambda name, started: None,
        rerank_rows_embeddings_with_time_budget=lambda **kwargs: ([], _FakeStats()),
        rerank_rows_cross_encoder_with_time_budget=lambda **kwargs: ([], _FakeStats()),
        build_candidate_chunks_fn=_build_conflicting_chunks,
    )

    assert [item["qualified_name"] for item in result.candidate_chunks] == [
        "pkg.service_v1",
        "pkg.helper",
    ]
    assert result.chunk_guard_payload["reason"] == "enforce_applied"
    assert result.chunk_guard_payload["fallback"] is False
    assert result.chunk_guard_payload["filtered_count"] == 1
    assert result.chunk_guard_payload["retained_count"] == 2
    assert "_robust_signature_lite" not in result.candidate_chunks[0]


def test_apply_chunk_selection_marks_timeout_fail_open() -> None:
    def _timeout_rows(**kwargs: Any) -> tuple[list[dict[str, Any]], _FakeStats]:
        raise TimeoutError("chunk_embedding_time_budget_exceeded:40ms")

    result = apply_chunk_selection(
        root=".",
        query="explain the handler",
        files_map={"src/app.py": {"path": "src/app.py"}},
        candidates=[{"path": "src/app.py", "score": 1.0}],
        terms=["explain", "handler"],
        top_k_files=4,
        chunk_top_k=8,
        chunk_per_file_limit=2,
        chunk_token_budget=500,
        chunk_guard_enabled=True,
        chunk_guard_mode="enforce",
        chunk_guard_lambda_penalty=0.8,
        chunk_guard_min_pool=1,
        chunk_guard_max_pool=32,
        chunk_guard_min_marginal_utility=0.0,
        chunk_guard_compatibility_min_overlap=0.3,
        chunk_disclosure="snippet",
        chunk_snippet_max_lines=8,
        chunk_snippet_max_chars=400,
        policy={
            "chunk_semantic_rerank_enabled": True,
            "chunk_semantic_rerank_time_budget_ms": 40,
            "embedding_enabled": True,
        },
        tokenizer_model="gpt-4o-mini",
        chunk_diversity_enabled=True,
        chunk_diversity_path_penalty=0.1,
        chunk_diversity_symbol_family_penalty=0.1,
        chunk_diversity_kind_penalty=0.1,
        chunk_diversity_locality_penalty=0.1,
        chunk_diversity_locality_window=64,
        chunk_topological_shield_enabled=False,
        chunk_topological_shield_mode="off",
        chunk_topological_shield_max_attenuation=0.6,
        chunk_topological_shield_shared_parent_attenuation=0.2,
        chunk_topological_shield_adjacency_attenuation=0.5,
        index_hash="idx",
        embedding_enabled=True,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        embeddings_payload={
            "runtime_provider": "hash",
            "runtime_model": "hash-v1",
            "runtime_dimension": 16,
        },
        semantic_embedding_provider_impl=object(),
        semantic_cross_encoder_provider=None,
        mark_timing=lambda name, started: None,
        rerank_rows_embeddings_with_time_budget=_timeout_rows,
        rerank_rows_cross_encoder_with_time_budget=lambda **kwargs: ([], _FakeStats()),
        build_candidate_chunks_fn=_build_chunks,
    )

    assert result.chunk_semantic_rerank_payload["reason"] == "fail_open"
    assert result.chunk_semantic_rerank_payload["fallback"] is True
    assert result.chunk_semantic_rerank_payload["time_budget_exceeded"] is True
    assert result.chunk_guard_payload["reason"] == "enforce_applied"
    assert result.chunk_guard_payload["fallback"] is False
