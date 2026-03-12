from __future__ import annotations

import hashlib
from typing import Any

from ace_lite.chunking.skeleton import summarize_chunk_contract
from ace_lite.explainability import attach_selection_why
from ace_lite.index_stage.result_payload_sections import (
    build_candidate_ranking_payload,
    build_result_metadata,
)
from ace_lite.retrieval_shared import build_selection_observability
from ace_lite.scip.subgraph import build_subgraph_payload


def _build_context_budget(
    *,
    top_k_files: int,
    min_candidate_score: int,
    candidate_relative_threshold: float,
    chunk_top_k: int,
    chunk_per_file_limit: int,
    chunk_token_budget: int,
    chunk_budget_used: int,
    chunk_count: int,
    chunk_disclosure: str,
) -> dict[str, Any]:
    return {
        "top_k_files": int(top_k_files),
        "min_candidate_score": int(min_candidate_score),
        "candidate_relative_threshold": float(candidate_relative_threshold),
        "chunk_top_k": int(chunk_top_k),
        "chunk_per_file_limit": int(chunk_per_file_limit),
        "chunk_token_budget": int(chunk_token_budget),
        "chunk_budget_used": int(chunk_budget_used),
        "chunk_count": int(chunk_count),
        "chunk_disclosure": str(chunk_disclosure),
    }


def _compute_selection_fingerprint(
    *,
    candidate_files: list[dict[str, Any]],
    candidate_chunks: list[dict[str, Any]],
    chunk_contract: dict[str, Any],
    subgraph_payload: dict[str, Any],
    context_budget: dict[str, Any],
    candidate_ranker: str,
    retrieval_policy: str,
    policy_version: str,
    embedding_enabled: bool,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
) -> str:
    parts: list[str] = []
    parts.append(f"ranker:{candidate_ranker!s}")
    parts.append(f"policy:{retrieval_policy!s}")
    parts.append(f"policy_version:{policy_version!s}")
    parts.append(f"embedding:{1 if embedding_enabled else 0}")
    if embedding_enabled:
        parts.append(f"embedding_provider:{embedding_provider!s}")
        parts.append(f"embedding_model:{embedding_model!s}")
        parts.append(f"embedding_dim:{int(embedding_dimension)}")

    for key in sorted(context_budget):
        parts.append(f"budget:{key}={context_budget[key]}")

    for item in candidate_files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        module = str(item.get("module") or "").strip()
        if path:
            parts.append(f"file:{path}|{module}")

    for item in candidate_chunks:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        qualified = str(item.get("qualified_name") or "").strip()
        kind = str(item.get("kind") or "").strip()
        lineno = int(item.get("lineno") or 0)
        if path and (qualified or lineno > 0):
            parts.append(f"chunk:{path}|{lineno}|{qualified}|{kind}")

    parts.append(
        "chunk_contract:"
        f"{str(chunk_contract.get('schema_version') or '')}"
        f"|{str(chunk_contract.get('requested_disclosure') or '')}"
        f"|{','.join(str(item) for item in chunk_contract.get('observed_disclosures', []))}"
        f"|fallbacks={int(chunk_contract.get('fallback_count', 0) or 0)}"
        f"|skeletons={int(chunk_contract.get('skeleton_chunk_count', 0) or 0)}"
    )
    parts.append(
        "subgraph_payload:"
        f"{str(subgraph_payload.get('payload_version') or '')}"
        f"|{str(subgraph_payload.get('taxonomy_version') or '')}"
        f"|enabled={int(bool(subgraph_payload.get('enabled', False)))}"
        f"|seeds={','.join(str(item) for item in subgraph_payload.get('seed_paths', []))}"
        f"|edges={','.join(f'{key}:{value}' for key, value in sorted((subgraph_payload.get('edge_counts') or {}).items()))}"
    )

    source = "\n".join(parts).encode("utf-8", errors="ignore")
    return hashlib.sha256(source).hexdigest()[:16]


def _build_targets(
    *,
    memory_paths: list[str],
    candidates: list[dict[str, Any]],
    top_k_files: int,
) -> list[str]:
    targets: list[str] = []
    for path in memory_paths:
        if isinstance(path, str) and path not in targets:
            targets.append(path)

    for row in candidates[: max(1, int(top_k_files))]:
        if not isinstance(row, dict):
            continue
        candidate_path = row.get("path")
        if not isinstance(candidate_path, str):
            continue
        if candidate_path not in targets:
            targets.append(candidate_path)
    return targets


def build_index_stage_result(
    *,
    repo: str,
    root: str,
    terms: list[str],
    targets: list[str],
    index_hash: str,
    index_data: dict[str, Any],
    cache_info: dict[str, Any],
    requested_ranker: str,
    selected_ranker: str,
    ranker_fallbacks: list[str],
    corpus_size: int,
    min_score_used: int,
    fusion_mode: str,
    hybrid_re2_rrf_k: int,
    top_k_files: int,
    candidate_relative_threshold: float,
    chunk_top_k: int,
    chunk_per_file_limit: int,
    chunk_token_budget: int,
    chunk_disclosure: str,
    candidates: list[dict[str, Any]],
    candidate_chunks: list[dict[str, Any]],
    chunk_metrics: dict[str, Any],
    exact_search_payload: dict[str, Any],
    docs_payload: dict[str, Any],
    worktree_prior: dict[str, Any],
    parallel_payload: dict[str, Any],
    prior_payload: dict[str, Any],
    graph_lookup_payload: dict[str, Any],
    cochange_payload: dict[str, Any],
    scip_payload: dict[str, Any],
    embeddings_payload: dict[str, Any],
    feedback_payload: dict[str, Any],
    multi_channel_fusion_payload: dict[str, Any],
    second_pass_payload: dict[str, Any],
    refine_pass_payload: dict[str, Any],
    chunk_semantic_rerank_payload: dict[str, Any],
    topological_shield_payload: dict[str, Any],
    chunk_guard_payload: dict[str, Any],
    adaptive_router_payload: dict[str, Any],
    policy_name: str,
    policy_version: str,
    timings_ms: dict[str, Any],
) -> dict[str, Any]:
    module_hint = candidates[0].get("module", "") if candidates else ""
    selection_observability = build_selection_observability(
        requested_ranker=requested_ranker,
        selected_ranker=selected_ranker,
        fallback_reasons=ranker_fallbacks,
        min_score_used=min_score_used,
        corpus_size=corpus_size,
        terms_count=len(terms),
        fusion_mode=fusion_mode,
        rrf_k=int(hybrid_re2_rrf_k),
    )
    selected_fusion_mode = str(selection_observability["fusion_mode"])
    chunk_semantic_pool_effective = int(
        chunk_semantic_rerank_payload.get("rerank_pool_effective", 0) or 0
    )
    chunk_semantic_reranked_count = int(
        chunk_semantic_rerank_payload.get("reranked_count", 0) or 0
    )
    chunk_semantic_rerank_ratio = (
        float(chunk_semantic_reranked_count) / float(chunk_semantic_pool_effective)
        if chunk_semantic_pool_effective > 0
        else 0.0
    )

    candidate_ranking = build_candidate_ranking_payload(
        selection_observability=selection_observability,
        embeddings_payload=embeddings_payload,
        exact_search_payload=exact_search_payload,
        docs_payload=docs_payload,
        prior_payload=prior_payload,
        multi_channel_fusion_payload=multi_channel_fusion_payload,
        worktree_prior=worktree_prior,
        graph_lookup_payload=graph_lookup_payload,
        chunk_semantic_rerank_payload=chunk_semantic_rerank_payload,
        chunk_semantic_pool_effective=chunk_semantic_pool_effective,
        chunk_semantic_reranked_count=chunk_semantic_reranked_count,
        chunk_semantic_rerank_ratio=chunk_semantic_rerank_ratio,
        topological_shield_payload=topological_shield_payload,
        feedback_payload=feedback_payload,
        chunk_guard_payload=chunk_guard_payload,
        adaptive_router_payload=adaptive_router_payload,
        second_pass_payload=second_pass_payload,
        refine_pass_payload=refine_pass_payload,
    )

    limited_candidate_files = candidates[: max(1, int(top_k_files))]
    candidate_chunks_with_why = attach_selection_why(
        candidate_chunks,
        default_reason="ranked_chunk_candidate",
    )
    chunk_contract = summarize_chunk_contract(
        candidate_chunks=candidate_chunks_with_why,
        requested_disclosure=chunk_disclosure,
    )
    subgraph_payload = build_subgraph_payload(
        candidate_files=limited_candidate_files,
        candidate_chunks=candidate_chunks_with_why,
        graph_lookup_payload=graph_lookup_payload,
    )
    context_budget = _build_context_budget(
        top_k_files=top_k_files,
        min_candidate_score=min_score_used,
        candidate_relative_threshold=candidate_relative_threshold,
        chunk_top_k=chunk_top_k,
        chunk_per_file_limit=chunk_per_file_limit,
        chunk_token_budget=chunk_token_budget,
        chunk_budget_used=int(chunk_metrics.get("chunk_budget_used", 0) or 0),
        chunk_count=int(chunk_metrics.get("candidate_chunk_count", 0) or 0),
        chunk_disclosure=chunk_disclosure,
    )
    selection_fingerprint = _compute_selection_fingerprint(
        candidate_files=limited_candidate_files,
        candidate_chunks=candidate_chunks_with_why,
        chunk_contract=chunk_contract,
        subgraph_payload=subgraph_payload,
        context_budget=context_budget,
        candidate_ranker=str(selected_ranker),
        retrieval_policy=str(policy_name),
        policy_version=str(policy_version),
        embedding_enabled=bool(embeddings_payload.get("enabled", False)),
        embedding_provider=str(embeddings_payload.get("runtime_provider", "")),
        embedding_model=str(embeddings_payload.get("runtime_model", "")),
        embedding_dimension=int(embeddings_payload.get("runtime_dimension", 0) or 0),
    )
    limited_candidate_files_with_why = attach_selection_why(
        limited_candidate_files,
        default_reason="ranked_file_candidate",
    )

    metadata = build_result_metadata(
        selection_observability=selection_observability,
        multi_channel_fusion_payload=multi_channel_fusion_payload,
        adaptive_router_payload=adaptive_router_payload,
        policy_name=policy_name,
        policy_version=policy_version,
        cochange_payload=cochange_payload,
        chunk_metrics=chunk_metrics,
        chunk_semantic_rerank_payload=chunk_semantic_rerank_payload,
        chunk_semantic_pool_effective=chunk_semantic_pool_effective,
        chunk_semantic_rerank_ratio=chunk_semantic_rerank_ratio,
        topological_shield_payload=topological_shield_payload,
        chunk_guard_payload=chunk_guard_payload,
        docs_payload=docs_payload,
        prior_payload=prior_payload,
        worktree_prior=worktree_prior,
        graph_lookup_payload=graph_lookup_payload,
        embeddings_payload=embeddings_payload,
        feedback_payload=feedback_payload,
        refine_pass_payload=refine_pass_payload,
        second_pass_payload=second_pass_payload,
        selection_fingerprint=selection_fingerprint,
        timings_ms=timings_ms,
    )
    metadata["chunk_contract_schema_version"] = str(
        chunk_contract.get("schema_version") or ""
    )
    metadata["chunk_contract_requested_disclosure"] = str(
        chunk_contract.get("requested_disclosure") or ""
    )
    metadata["chunk_contract_observed_disclosures"] = list(
        chunk_contract.get("observed_disclosures", [])
    )
    metadata["chunk_contract_fallback_count"] = int(
        chunk_contract.get("fallback_count", 0) or 0
    )
    metadata["chunk_contract_skeleton_chunk_count"] = int(
        chunk_contract.get("skeleton_chunk_count", 0) or 0
    )
    metadata["subgraph_payload_version"] = str(
        subgraph_payload.get("payload_version") or ""
    )
    metadata["subgraph_taxonomy_version"] = str(
        subgraph_payload.get("taxonomy_version") or ""
    )
    metadata["subgraph_enabled"] = bool(subgraph_payload.get("enabled", False))
    metadata["subgraph_seed_path_count"] = len(
        subgraph_payload.get("seed_paths", [])
    )

    return {
        "repo": repo,
        "root": root,
        "terms": terms,
        "targets": targets,
        "module_hint": module_hint,
        "index_hash": index_hash,
        "file_count": int(index_data.get("file_count") or 0),
        "indexed_at": index_data.get("indexed_at"),
        "languages_covered": list(index_data.get("languages_covered", [])),
        "parser": index_data.get("parser", {}),
        "cache": cache_info,
        "candidate_ranker": selected_ranker,
        "candidate_ranking": candidate_ranking,
        "candidate_files": limited_candidate_files_with_why,
        "candidate_chunks": candidate_chunks_with_why,
        "chunk_contract": chunk_contract,
        "subgraph_payload": subgraph_payload,
        "chunk_metrics": chunk_metrics,
        "context_budget": context_budget,
        "chunk_semantic_rerank": chunk_semantic_rerank_payload,
        "topological_shield": topological_shield_payload,
        "chunk_guard": chunk_guard_payload,
        "docs": docs_payload,
        "worktree_prior": worktree_prior,
        "parallel": parallel_payload,
        "prior_applied": prior_payload,
        "graph_lookup": graph_lookup_payload,
        "cochange": cochange_payload,
        "scip": scip_payload,
        "embeddings": embeddings_payload,
        "feedback": feedback_payload,
        "multi_channel_fusion": multi_channel_fusion_payload,
        "adaptive_router": adaptive_router_payload,
        "policy_name": str(policy_name),
        "policy_version": str(policy_version),
        "metadata": metadata,
    }


def build_index_stage_output(
    *,
    repo: str,
    root: str,
    terms: list[str],
    memory_paths: list[str],
    index_hash: str,
    index_data: dict[str, Any],
    cache_info: dict[str, Any],
    requested_ranker: str,
    selected_ranker: str,
    ranker_fallbacks: list[str],
    corpus_size: int,
    min_score_used: int,
    fusion_mode: str,
    hybrid_re2_rrf_k: int,
    top_k_files: int,
    candidate_relative_threshold: float,
    chunk_top_k: int,
    chunk_per_file_limit: int,
    chunk_token_budget: int,
    chunk_disclosure: str,
    candidates: list[dict[str, Any]],
    candidate_chunks: list[dict[str, Any]],
    chunk_metrics: dict[str, Any],
    exact_search_payload: dict[str, Any],
    docs_payload: dict[str, Any],
    worktree_prior: dict[str, Any],
    parallel_payload: dict[str, Any],
    prior_payload: dict[str, Any],
    graph_lookup_payload: dict[str, Any],
    cochange_payload: dict[str, Any],
    scip_payload: dict[str, Any],
    embeddings_payload: dict[str, Any],
    feedback_payload: dict[str, Any],
    multi_channel_fusion_payload: dict[str, Any],
    second_pass_payload: dict[str, Any],
    refine_pass_payload: dict[str, Any],
    chunk_semantic_rerank_payload: dict[str, Any],
    topological_shield_payload: dict[str, Any],
    chunk_guard_payload: dict[str, Any],
    adaptive_router_payload: dict[str, Any],
    policy_name: str,
    policy_version: str,
    timings_ms: dict[str, Any],
) -> dict[str, Any]:
    targets = _build_targets(
        memory_paths=memory_paths,
        candidates=candidates,
        top_k_files=top_k_files,
    )
    return build_index_stage_result(
        repo=repo,
        root=root,
        terms=terms,
        targets=targets,
        index_hash=index_hash,
        index_data=index_data,
        cache_info=cache_info,
        requested_ranker=requested_ranker,
        selected_ranker=selected_ranker,
        ranker_fallbacks=ranker_fallbacks,
        corpus_size=corpus_size,
        min_score_used=min_score_used,
        fusion_mode=fusion_mode,
        hybrid_re2_rrf_k=hybrid_re2_rrf_k,
        top_k_files=top_k_files,
        candidate_relative_threshold=candidate_relative_threshold,
        chunk_top_k=chunk_top_k,
        chunk_per_file_limit=chunk_per_file_limit,
        chunk_token_budget=chunk_token_budget,
        chunk_disclosure=chunk_disclosure,
        candidates=candidates,
        candidate_chunks=candidate_chunks,
        chunk_metrics=chunk_metrics,
        exact_search_payload=exact_search_payload,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        parallel_payload=parallel_payload,
        prior_payload=prior_payload,
        graph_lookup_payload=graph_lookup_payload,
        cochange_payload=cochange_payload,
        scip_payload=scip_payload,
        embeddings_payload=embeddings_payload,
        feedback_payload=feedback_payload,
        multi_channel_fusion_payload=multi_channel_fusion_payload,
        second_pass_payload=second_pass_payload,
        refine_pass_payload=refine_pass_payload,
        chunk_semantic_rerank_payload=chunk_semantic_rerank_payload,
        topological_shield_payload=topological_shield_payload,
        chunk_guard_payload=chunk_guard_payload,
        adaptive_router_payload=adaptive_router_payload,
        policy_name=policy_name,
        policy_version=policy_version,
        timings_ms=timings_ms,
    )


__all__ = ["build_index_stage_output", "build_index_stage_result"]
