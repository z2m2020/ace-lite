"""Case-level benchmark evaluation helpers."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any

from ace_lite.benchmark.case_evaluation_details import (
    build_decision_trace as _build_decision_trace_impl,
    build_evidence_insufficiency as _build_evidence_insufficiency_impl,
    classify_chunk_stage_miss as _classify_chunk_stage_miss_impl,
)
from ace_lite.benchmark.case_evaluation_expectations import (
    evaluate_chunk_guard_expectation as _evaluate_chunk_guard_expectation_impl,
    evaluate_task_success as _evaluate_task_success_impl,
)
from ace_lite.benchmark.case_evaluation_payloads import (
    coerce_chunk_refs as _coerce_chunk_refs_impl,
    count_unique_paths as _count_unique_paths_impl,
    compute_chunks_per_file_mean as _compute_chunks_per_file_mean_impl,
    extract_stage_latency_ms as _extract_stage_latency_ms_impl,
    extract_stage_observability as _extract_stage_observability_impl,
    normalize_source_plan_evidence_summary as _normalize_source_plan_evidence_summary_impl,
    safe_ratio as _safe_ratio_impl,
)


def _tokenize(text: str) -> set[str]:
    tokens = [item.strip().lower() for item in text.replace("/", " ").replace(".", " ").split()]
    return {token for token in tokens if token}


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        normalized = str(item or "").strip()
        if normalized:
            output.append(normalized)
    return output


def _normalize_benchmark_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/")


def _resolve_candidate_path_filters(case: dict[str, Any]) -> dict[str, list[str]]:
    filters = case.get("filters", {}) if isinstance(case.get("filters"), dict) else {}
    include_paths = [
        _normalize_benchmark_path(item)
        for item in _coerce_string_list(filters.get("include_paths"))
    ]
    include_globs = [
        _normalize_benchmark_path(item)
        for item in _coerce_string_list(filters.get("include_globs"))
    ]
    exclude_paths = [
        _normalize_benchmark_path(item)
        for item in _coerce_string_list(filters.get("exclude_paths"))
    ]
    exclude_globs = [
        _normalize_benchmark_path(item)
        for item in _coerce_string_list(filters.get("exclude_globs"))
    ]
    return {
        "include_paths": [item for item in include_paths if item],
        "include_globs": [item for item in include_globs if item],
        "exclude_paths": [item for item in exclude_paths if item],
        "exclude_globs": [item for item in exclude_globs if item],
    }


def _candidate_path_matches_filters(
    path: Any,
    *,
    include_paths: list[str],
    include_globs: list[str],
    exclude_paths: list[str],
    exclude_globs: list[str],
) -> bool:
    normalized_path = _normalize_benchmark_path(path)
    if not normalized_path:
        return False
    include_requested = bool(include_paths or include_globs)
    if include_requested:
        included = normalized_path in include_paths or any(
            fnmatchcase(normalized_path, pattern) for pattern in include_globs
        )
        if not included:
            return False
    if normalized_path in exclude_paths:
        return False
    if any(fnmatchcase(normalized_path, pattern) for pattern in exclude_globs):
        return False
    return True


def _filter_candidate_path_items(
    items: Any,
    *,
    include_paths: list[str],
    include_globs: list[str],
    exclude_paths: list[str],
    exclude_globs: list[str],
) -> list[Any]:
    if not isinstance(items, list):
        return []
    output: list[Any] = []
    for item in items:
        if not isinstance(item, dict):
            output.append(item)
            continue
        if not _candidate_path_matches_filters(
            item.get("path"),
            include_paths=include_paths,
            include_globs=include_globs,
            exclude_paths=exclude_paths,
            exclude_globs=exclude_globs,
        ):
            continue
        output.append(item)
    return output


def _extract_stage_latency_ms(*, plan_payload: dict[str, Any], stage: str) -> float:
    return _extract_stage_latency_ms_impl(plan_payload=plan_payload, stage=stage)


def _extract_stage_observability(plan_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return _extract_stage_observability_impl(plan_payload)


def _coerce_chunk_refs(value: Any) -> list[dict[str, Any]]:
    return _coerce_chunk_refs_impl(value)


def _compute_chunks_per_file_mean(candidate_chunks: list[dict[str, Any]]) -> float:
    return _compute_chunks_per_file_mean_impl(candidate_chunks)


def _count_unique_paths(items: list[dict[str, Any]]) -> int:
    return _count_unique_paths_impl(items)


def _safe_ratio(numerator: Any, denominator: Any) -> float:
    return _safe_ratio_impl(numerator, denominator)


def _classify_chunk_stage_miss(
    *,
    case: dict[str, Any],
    candidate_files: list[Any],
    raw_candidate_chunks: list[dict[str, Any]],
    source_plan_candidate_chunks: list[dict[str, Any]],
    source_plan_has_candidate_chunks: bool,
) -> dict[str, Any]:
    return _classify_chunk_stage_miss_impl(
        case=case,
        candidate_files=candidate_files,
        raw_candidate_chunks=raw_candidate_chunks,
        source_plan_candidate_chunks=source_plan_candidate_chunks,
        source_plan_has_candidate_chunks=source_plan_has_candidate_chunks,
    )


def _normalize_source_plan_evidence_summary(value: Any) -> dict[str, float]:
    return _normalize_source_plan_evidence_summary_impl(value)


def _build_evidence_insufficiency(
    *,
    task_success_mode: str,
    task_success_hit: float,
    task_success_failed_checks: list[str],
    candidate_file_count: int,
    candidate_chunk_count: int,
    chunk_hit_at_k: float,
    recall_hit: float,
    noise_rate: float,
    validation_test_count: int,
    docs_enabled: bool,
    docs_hit: float,
    dependency_recall: float,
    neighbor_paths: list[str],
    skills_budget_exhausted: bool,
    slo_downgrade_signals: list[str],
) -> dict[str, Any]:
    return _build_evidence_insufficiency_impl(
        task_success_mode=task_success_mode,
        task_success_hit=task_success_hit,
        task_success_failed_checks=task_success_failed_checks,
        candidate_file_count=candidate_file_count,
        candidate_chunk_count=candidate_chunk_count,
        chunk_hit_at_k=chunk_hit_at_k,
        recall_hit=recall_hit,
        noise_rate=noise_rate,
        validation_test_count=validation_test_count,
        docs_enabled=docs_enabled,
        docs_hit=docs_hit,
        dependency_recall=dependency_recall,
        neighbor_paths=neighbor_paths,
        skills_budget_exhausted=skills_budget_exhausted,
        slo_downgrade_signals=slo_downgrade_signals,
    )


def _build_decision_trace(
    *,
    memory_gate_skipped: bool,
    memory_gate_skip_reason: str,
    memory_fallback_reason: str,
    memory_namespace_fallback: str,
    candidate_ranker_fallbacks: list[str],
    exact_search_payload: dict[str, Any],
    second_pass_payload: dict[str, Any],
    refine_pass_payload: dict[str, Any],
    docs_backend_fallback_reason: str,
    parallel_docs_timed_out: bool,
    parallel_worktree_timed_out: bool,
    embedding_adaptive_budget_applied: bool,
    embedding_time_budget_exceeded: bool,
    embedding_fallback: bool,
    chunk_semantic_time_budget_exceeded: bool,
    chunk_semantic_fallback: bool,
    chunk_semantic_reason: str,
    xref_budget_exhausted: bool,
    skills_budget_exhausted: bool,
) -> list[dict[str, Any]]:
    return _build_decision_trace_impl(
        memory_gate_skipped=memory_gate_skipped,
        memory_gate_skip_reason=memory_gate_skip_reason,
        memory_fallback_reason=memory_fallback_reason,
        memory_namespace_fallback=memory_namespace_fallback,
        candidate_ranker_fallbacks=candidate_ranker_fallbacks,
        exact_search_payload=exact_search_payload,
        second_pass_payload=second_pass_payload,
        refine_pass_payload=refine_pass_payload,
        docs_backend_fallback_reason=docs_backend_fallback_reason,
        parallel_docs_timed_out=parallel_docs_timed_out,
        parallel_worktree_timed_out=parallel_worktree_timed_out,
        embedding_adaptive_budget_applied=embedding_adaptive_budget_applied,
        embedding_time_budget_exceeded=embedding_time_budget_exceeded,
        embedding_fallback=embedding_fallback,
        chunk_semantic_time_budget_exceeded=chunk_semantic_time_budget_exceeded,
        chunk_semantic_fallback=chunk_semantic_fallback,
        chunk_semantic_reason=chunk_semantic_reason,
        xref_budget_exhausted=xref_budget_exhausted,
        skills_budget_exhausted=skills_budget_exhausted,
    )


def _evaluate_task_success(
    *,
    case: dict[str, Any],
    expected: list[str],
    recall_hit: float,
    validation_tests: list[Any],
) -> dict[str, Any]:
    return _evaluate_task_success_impl(
        case=case,
        expected=expected,
        recall_hit=recall_hit,
        validation_tests=validation_tests,
    )


def _evaluate_chunk_guard_expectation(
    *,
    case: dict[str, Any],
    chunk_guard_payload: dict[str, Any],
) -> dict[str, Any]:
    return _evaluate_chunk_guard_expectation_impl(
        case=case,
        chunk_guard_payload=chunk_guard_payload,
    )


def evaluate_case_result(
    *,
    case: dict[str, Any],
    plan_payload: dict[str, Any],
    latency_ms: float,
    include_case_details: bool = True,
) -> dict[str, Any]:
    comparison_lane = str(case.get("comparison_lane") or "").strip()
    expected_keys = case.get("expected_keys", [])
    if isinstance(expected_keys, str):
        expected = [item.strip() for item in expected_keys.split(";") if item.strip()]
    else:
        expected = [str(item).strip() for item in expected_keys if str(item).strip()]

    top_k = int(case.get("top_k", 8))
    observability = (
        plan_payload.get("observability", {})
        if isinstance(plan_payload.get("observability"), dict)
        else {}
    )

    index_payload = plan_payload.get("index", {}) if isinstance(plan_payload.get("index"), dict) else {}
    index_metadata = (
        index_payload.get("metadata", {})
        if isinstance(index_payload.get("metadata"), dict)
        else {}
    )
    index_benchmark_filters = (
        index_payload.get("benchmark_filters", {})
        if isinstance(index_payload.get("benchmark_filters"), dict)
        else {}
    )
    candidate_path_filters = (
        {
            "include_paths": _coerce_string_list(
                index_benchmark_filters.get("include_paths")
            ),
            "include_globs": _coerce_string_list(
                index_benchmark_filters.get("include_globs")
            ),
            "exclude_paths": _coerce_string_list(
                index_benchmark_filters.get("exclude_paths")
            ),
            "exclude_globs": _coerce_string_list(
                index_benchmark_filters.get("exclude_globs")
            ),
        }
        if bool(index_benchmark_filters.get("requested", False))
        else _resolve_candidate_path_filters(case)
    )
    included_candidate_paths = candidate_path_filters["include_paths"]
    included_candidate_globs = candidate_path_filters["include_globs"]
    excluded_candidate_paths = candidate_path_filters["exclude_paths"]
    excluded_candidate_globs = candidate_path_filters["exclude_globs"]
    filters_applied_upstream = bool(index_benchmark_filters.get("requested", False))
    candidate_files = (
        index_payload.get("candidate_files", [])
        if filters_applied_upstream
        else _filter_candidate_path_items(
            index_payload.get("candidate_files", []),
            include_paths=included_candidate_paths,
            include_globs=included_candidate_globs,
            exclude_paths=excluded_candidate_paths,
            exclude_globs=excluded_candidate_globs,
        )
    )
    raw_candidate_chunks = (
        _coerce_chunk_refs(index_payload.get("candidate_chunks", []))
        if filters_applied_upstream
        else _filter_candidate_path_items(
            _coerce_chunk_refs(index_payload.get("candidate_chunks", [])),
            include_paths=included_candidate_paths,
            include_globs=included_candidate_globs,
            exclude_paths=excluded_candidate_paths,
            exclude_globs=excluded_candidate_globs,
        )
    )
    chunk_metrics = index_payload.get("chunk_metrics", {}) if isinstance(index_payload.get("chunk_metrics"), dict) else {}
    embeddings_payload = (
        index_payload.get("embeddings", {})
        if isinstance(index_payload.get("embeddings"), dict)
        else {}
    )
    docs_payload = (
        index_payload.get("docs", {})
        if isinstance(index_payload.get("docs"), dict)
        else {}
    )
    chunk_semantic_payload = (
        index_payload.get("chunk_semantic_rerank", {})
        if isinstance(index_payload.get("chunk_semantic_rerank"), dict)
        else {}
    )
    topological_shield_payload = (
        index_payload.get("topological_shield", {})
        if isinstance(index_payload.get("topological_shield"), dict)
        else {}
    )
    chunk_guard_payload = (
        index_payload.get("chunk_guard", {})
        if isinstance(index_payload.get("chunk_guard"), dict)
        else {}
    )
    chunk_contract_payload = (
        index_payload.get("chunk_contract", {})
        if isinstance(index_payload.get("chunk_contract"), dict)
        else {}
    )
    parallel_payload = (
        index_payload.get("parallel", {})
        if isinstance(index_payload.get("parallel"), dict)
        else {}
    )
    parallel_docs_payload = (
        parallel_payload.get("docs", {})
        if isinstance(parallel_payload.get("docs"), dict)
        else {}
    )
    parallel_worktree_payload = (
        parallel_payload.get("worktree", {})
        if isinstance(parallel_payload.get("worktree"), dict)
        else {}
    )
    candidate_ranking_payload = (
        index_payload.get("candidate_ranking", {})
        if isinstance(index_payload.get("candidate_ranking"), dict)
        else {}
    )
    adaptive_router_payload = (
        index_payload.get("adaptive_router", {})
        if isinstance(index_payload.get("adaptive_router"), dict)
        else {}
    )
    exact_search_payload = (
        candidate_ranking_payload.get("exact_search", {})
        if isinstance(candidate_ranking_payload.get("exact_search"), dict)
        else {}
    )
    second_pass_payload = (
        candidate_ranking_payload.get("second_pass", {})
        if isinstance(candidate_ranking_payload.get("second_pass"), dict)
        else {}
    )
    refine_pass_payload = (
        candidate_ranking_payload.get("refine_pass", {})
        if isinstance(candidate_ranking_payload.get("refine_pass"), dict)
        else {}
    )
    candidate_ranker_fallbacks = candidate_ranking_payload.get("fallbacks", [])
    if not isinstance(candidate_ranker_fallbacks, list):
        candidate_ranker_fallbacks = []
    augment_payload = (
        plan_payload.get("augment", {})
        if isinstance(plan_payload.get("augment"), dict)
        else {}
    )
    xref_payload = (
        augment_payload.get("xref", {})
        if isinstance(augment_payload.get("xref"), dict)
        else {}
    )
    stage_observability = _extract_stage_observability(plan_payload)
    index_stage = stage_observability.get("index", {})
    index_tags = index_stage.get("tags", {}) if isinstance(index_stage.get("tags"), dict) else {}
    augment_stage = stage_observability.get("augment", {})
    augment_tags = (
        augment_stage.get("tags", {})
        if isinstance(augment_stage.get("tags"), dict)
        else {}
    )
    source_plan_stage = stage_observability.get("source_plan", {})
    source_plan_tags = (
        source_plan_stage.get("tags", {})
        if isinstance(source_plan_stage.get("tags"), dict)
        else {}
    )
    source_plan_payload = (
        plan_payload.get("source_plan", {})
        if isinstance(plan_payload.get("source_plan"), dict)
        else {}
    )
    source_plan_packing_payload = (
        source_plan_payload.get("packing", {})
        if isinstance(source_plan_payload.get("packing"), dict)
        else {}
    )
    source_plan_subgraph_payload = (
        source_plan_payload.get("subgraph_payload", {})
        if isinstance(source_plan_payload.get("subgraph_payload"), dict)
        else {}
    )
    source_plan_evidence_summary = _normalize_source_plan_evidence_summary(
        source_plan_payload.get("evidence_summary", {})
    )
    skills_payload = (
        plan_payload.get("skills", {})
        if isinstance(plan_payload.get("skills"), dict)
        else {}
    )
    source_plan_has_candidate_chunks = isinstance(
        source_plan_payload.get("candidate_chunks"),
        list,
    )
    source_plan_candidate_chunks = (
        _coerce_chunk_refs(source_plan_payload.get("candidate_chunks", []))
        if filters_applied_upstream
        else _filter_candidate_path_items(
            _coerce_chunk_refs(source_plan_payload.get("candidate_chunks", [])),
            include_paths=included_candidate_paths,
            include_globs=included_candidate_globs,
            exclude_paths=excluded_candidate_paths,
            exclude_globs=excluded_candidate_globs,
        )
    )
    candidate_chunks = (
        source_plan_candidate_chunks
        if source_plan_has_candidate_chunks
        else raw_candidate_chunks
    )
    chunk_stage_miss = _classify_chunk_stage_miss(
        case=case,
        candidate_files=candidate_files if isinstance(candidate_files, list) else [],
        raw_candidate_chunks=raw_candidate_chunks,
        source_plan_candidate_chunks=source_plan_candidate_chunks,
        source_plan_has_candidate_chunks=source_plan_has_candidate_chunks,
    )
    repomap_payload = (
        plan_payload.get("repomap", {})
        if isinstance(plan_payload.get("repomap"), dict)
        else {}
    )
    index_subgraph_payload = (
        index_payload.get("subgraph_payload", {})
        if isinstance(index_payload.get("subgraph_payload"), dict)
        else {}
    )
    subgraph_payload = (
        source_plan_subgraph_payload
        if source_plan_subgraph_payload
        else index_subgraph_payload
    )

    top_candidates = candidate_files[:top_k] if isinstance(candidate_files, list) else []
    top_chunks = candidate_chunks[: max(1, top_k * 3)] if isinstance(candidate_chunks, list) else []

    candidate_text = " ".join(
        str(item.get("path", "")) + " " + str(item.get("module", ""))
        for item in top_candidates
        if isinstance(item, dict)
    )
    candidate_tokens = _tokenize(candidate_text)

    expected_token_sets = [_tokenize(key) for key in expected]
    expected_hits = [
        key
        for key, token_set in zip(expected, expected_token_sets, strict=True)
        if token_set and candidate_tokens.intersection(token_set)
    ]
    recall_hit = 1.0 if expected and expected_hits else 0.0

    relevant_candidates = 0
    first_hit_rank: int | None = None
    relevant_candidate_paths: list[str] = []
    noise_candidate_paths: list[str] = []
    candidate_matches: list[dict[str, Any]] = []
    for idx, item in enumerate(top_candidates):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "")
        text = f"{path} {item.get('module', '')}"
        token_set = _tokenize(text)
        matched = [
            key
            for key, expected_tokens in zip(expected, expected_token_sets, strict=True)
            if expected_tokens and token_set.intersection(expected_tokens)
        ]
        if matched:
            relevant_candidates += 1
            relevant_candidate_paths.append(path)
            if first_hit_rank is None:
                first_hit_rank = idx + 1
        else:
            noise_candidate_paths.append(path)
        candidate_matches.append({"path": path, "matched_expected_keys": matched})

    denominator = max(1, min(top_k, len(top_candidates)) if top_candidates else top_k)
    precision = relevant_candidates / denominator
    utility = recall_hit
    noise = max(0.0, 1.0 - precision)
    hit_at_1 = 1.0 if first_hit_rank == 1 else 0.0
    reciprocal_rank = (1.0 / float(first_hit_rank)) if first_hit_rank else 0.0

    chunk_text = " ".join(
        f"{item.get('path', '')} {item.get('qualified_name', '')} {item.get('signature', '')}"
        for item in top_chunks
        if isinstance(item, dict)
    )
    chunk_tokens = _tokenize(chunk_text)
    chunk_hits = [key for key in expected if any(tok in chunk_tokens for tok in _tokenize(key))]
    chunk_hit_at_k = 1.0 if expected and chunk_hits else 0.0
    raw_candidate_chunk_count = len(raw_candidate_chunks)
    chunk_contract_fallback_count = max(
        0,
        int(chunk_contract_payload.get("fallback_count", 0) or 0),
    )
    chunk_contract_skeleton_chunk_count = max(
        0,
        int(chunk_contract_payload.get("skeleton_chunk_count", 0) or 0),
    )
    chunk_contract_fallback_ratio = _safe_ratio(
        chunk_contract_fallback_count,
        raw_candidate_chunk_count,
    )
    chunk_contract_skeleton_ratio = _safe_ratio(
        chunk_contract_skeleton_chunk_count,
        raw_candidate_chunk_count,
    )
    unsupported_language_fallback_count = sum(
        1
        for item in raw_candidate_chunks
        if str(item.get("disclosure_fallback_reason") or "").strip()
        == "unsupported_language"
    )
    unsupported_language_fallback_ratio = _safe_ratio(
        unsupported_language_fallback_count,
        raw_candidate_chunk_count,
    )
    subgraph_edge_counts = (
        subgraph_payload.get("edge_counts", {})
        if isinstance(subgraph_payload.get("edge_counts"), dict)
        else {}
    )
    subgraph_seed_paths = (
        subgraph_payload.get("seed_paths", [])
        if isinstance(subgraph_payload.get("seed_paths"), list)
        else []
    )
    subgraph_seed_path_count = len(
        [item for item in subgraph_seed_paths if str(item).strip()]
    )
    subgraph_edge_type_count = len(
        [key for key, value in subgraph_edge_counts.items() if str(key).strip() and int(value or 0) > 0]
    )
    subgraph_edge_total_count = sum(
        max(0, int(value or 0)) for value in subgraph_edge_counts.values()
    )
    subgraph_payload_enabled = bool(subgraph_payload.get("enabled", False))

    dependency = repomap_payload.get("dependency_recall", {})
    dependency_recall = float(dependency.get("hit_rate", 0.0)) if isinstance(dependency, dict) else 0.0
    neighbor_paths = repomap_payload.get("neighbor_paths", [])
    if not isinstance(neighbor_paths, list):
        neighbor_paths = []
    repomap_latency_ms = _extract_stage_latency_ms(plan_payload=plan_payload, stage="repomap")
    memory_latency_ms = _extract_stage_latency_ms(plan_payload=plan_payload, stage="memory")
    index_latency_ms = _extract_stage_latency_ms(plan_payload=plan_payload, stage="index")
    augment_latency_ms = _extract_stage_latency_ms(plan_payload=plan_payload, stage="augment")
    skills_latency_ms = _extract_stage_latency_ms(plan_payload=plan_payload, stage="skills")
    source_plan_latency_ms = _extract_stage_latency_ms(
        plan_payload=plan_payload,
        stage="source_plan",
    )

    memory_payload = (
        plan_payload.get("memory", {})
        if isinstance(plan_payload.get("memory"), dict)
        else {}
    )
    memory_gate_payload = (
        memory_payload.get("gate", {})
        if isinstance(memory_payload.get("gate"), dict)
        else {}
    )
    memory_namespace_payload = (
        memory_payload.get("namespace", {})
        if isinstance(memory_payload.get("namespace"), dict)
        else {}
    )
    profile_payload = (
        memory_payload.get("profile", {})
        if isinstance(memory_payload.get("profile"), dict)
        else {}
    )
    capture_payload = (
        memory_payload.get("capture", {})
        if isinstance(memory_payload.get("capture"), dict)
        else {}
    )
    notes_payload = (
        memory_payload.get("notes", {})
        if isinstance(memory_payload.get("notes"), dict)
        else {}
    )
    validation_tests = source_plan_payload.get("validation_tests", [])
    if not isinstance(validation_tests, list):
        validation_tests = []
    memory_count = max(0, int(memory_payload.get("count", 0) or 0))
    notes_selected_count = max(0, int(notes_payload.get("selected_count", 0) or 0))
    notes_hit_ratio = (
        float(notes_selected_count) / float(memory_count)
        if memory_count > 0
        else 0.0
    )
    profile_selected_count = max(0, int(profile_payload.get("selected_count", 0) or 0))
    capture_triggered = bool(capture_payload.get("triggered", False))
    embedding_enabled = bool(embeddings_payload.get("enabled", False))
    embedding_fallback = bool(embeddings_payload.get("fallback", False))
    embedding_cache_hit = bool(embeddings_payload.get("cache_hit", False))
    embedding_rerank_pool = max(0, int(embeddings_payload.get("rerank_pool", 0) or 0))
    embedding_reranked_count = max(
        0, int(embeddings_payload.get("reranked_count", 0) or 0)
    )
    embedding_rerank_ratio = (
        float(embedding_reranked_count) / float(embedding_rerank_pool)
        if embedding_rerank_pool > 0
        else 0.0
    )
    embedding_similarity_mean = float(
        embeddings_payload.get("similarity_mean", 0.0) or 0.0
    )
    embedding_similarity_max = float(
        embeddings_payload.get("similarity_max", 0.0) or 0.0
    )
    docs_backend_fallback_reason = str(
        docs_payload.get("backend_fallback_reason", "") or ""
    ).strip()
    memory_fallback_reason = str(memory_payload.get("fallback_reason", "") or "").strip()
    memory_gate_skip_reason = str(
        memory_gate_payload.get("skip_reason", "") or ""
    ).strip()
    memory_namespace_fallback = str(
        memory_namespace_payload.get("fallback", "") or ""
    ).strip()
    chunk_semantic_reason = str(chunk_semantic_payload.get("reason", "") or "").strip()
    parallel_time_budget_ms = float(
        parallel_payload.get("time_budget_ms", index_tags.get("parallel_time_budget_ms", 0.0))
        or 0.0
    )
    embedding_time_budget_ms = float(
        embeddings_payload.get(
            "time_budget_ms", index_tags.get("embedding_time_budget_ms", 0.0)
        )
        or 0.0
    )
    chunk_semantic_time_budget_ms = float(
        chunk_semantic_payload.get(
            "time_budget_ms",
            index_tags.get("chunk_semantic_time_budget_ms", 0.0),
        )
        or 0.0
    )
    xref_time_budget_ms = float(
        xref_payload.get("time_budget_ms", augment_tags.get("xref_time_budget_ms", 0.0))
        or 0.0
    )
    parallel_docs_timed_out = bool(
        parallel_docs_payload.get(
            "timed_out", index_tags.get("parallel_docs_timed_out", False)
        )
    )
    parallel_worktree_timed_out = bool(
        parallel_worktree_payload.get(
            "timed_out", index_tags.get("parallel_worktree_timed_out", False)
        )
    )
    embedding_time_budget_exceeded = bool(
        embeddings_payload.get(
            "time_budget_exceeded",
            index_tags.get("embedding_time_budget_exceeded", False),
        )
    )
    embedding_adaptive_budget_applied = bool(
        embeddings_payload.get(
            "adaptive_budget_applied",
            index_tags.get("embedding_adaptive_budget_applied", False),
        )
    )
    chunk_semantic_time_budget_exceeded = bool(
        chunk_semantic_payload.get(
            "time_budget_exceeded",
            index_tags.get("chunk_semantic_time_budget_exceeded", False),
        )
    )
    chunk_semantic_fallback = bool(
        chunk_semantic_payload.get(
            "fallback", index_tags.get("chunk_semantic_fallback", False)
        )
    )
    chunk_guard_candidate_pool = max(
        0,
        int(
            chunk_guard_payload.get(
                "candidate_pool", index_tags.get("chunk_guard_candidate_pool", 0)
            )
            or 0
        ),
    )
    chunk_guard_filtered_count = max(
        0,
        int(
            chunk_guard_payload.get(
                "filtered_count", index_tags.get("chunk_guard_filtered_count", 0)
            )
            or 0
        ),
    )
    chunk_guard_retained_count = max(
        0,
        int(
            chunk_guard_payload.get(
                "retained_count", index_tags.get("chunk_guard_retained_count", 0)
            )
            or 0
        ),
    )
    chunk_guard_signed_chunk_count = max(
        0,
        int(
            chunk_guard_payload.get(
                "signed_chunk_count",
                index_tags.get("chunk_guard_signed_chunk_count", 0),
            )
            or 0
        ),
    )
    chunk_guard_pairwise_conflict_count = max(
        0,
        int(
            chunk_guard_payload.get(
                "pairwise_conflict_count",
                index_tags.get("chunk_guard_pairwise_conflict_count", 0),
            )
            or 0
        ),
    )
    chunk_guard_max_conflict_penalty = float(
        chunk_guard_payload.get(
            "max_conflict_penalty",
            index_tags.get("chunk_guard_max_conflict_penalty", 0.0),
        )
        or 0.0
    )
    chunk_guard_mode = str(
        chunk_guard_payload.get("mode", index_tags.get("chunk_guard_mode", "")) or ""
    ).strip()
    chunk_guard_reason = str(
        chunk_guard_payload.get("reason", index_tags.get("chunk_guard_reason", ""))
        or ""
    ).strip()
    chunk_guard_enabled = bool(
        chunk_guard_payload.get(
            "enabled", index_tags.get("chunk_guard_enabled", False)
        )
    )
    chunk_guard_report_only = bool(
        chunk_guard_payload.get(
            "report_only", index_tags.get("chunk_guard_report_only", False)
        )
    )
    chunk_guard_fallback = bool(
        chunk_guard_payload.get(
            "fallback", index_tags.get("chunk_guard_fallback", False)
        )
    )
    chunk_guard_filter_ratio = (
        float(chunk_guard_filtered_count) / float(chunk_guard_candidate_pool)
        if chunk_guard_candidate_pool > 0
        else 0.0
    )
    xref_budget_exhausted = bool(
        xref_payload.get(
            "budget_exhausted", augment_tags.get("xref_budget_exhausted", False)
        )
    )
    chunk_budget_used = float(
        source_plan_payload.get(
            "chunk_budget_used",
            chunk_metrics.get("chunk_budget_used", 0.0),
        )
        or 0.0
    )
    chunks_per_file_mean = (
        _compute_chunks_per_file_mean(candidate_chunks)
        if source_plan_has_candidate_chunks
        else float(chunk_metrics.get("chunks_per_file_mean", 0.0) or 0.0)
    )
    robust_signature_count = max(
        0,
        int(
            chunk_metrics.get(
                "robust_signature_count",
                index_tags.get("robust_signature_count", 0),
            )
            or 0
        ),
    )
    robust_signature_coverage_ratio = float(
        chunk_metrics.get(
            "robust_signature_coverage_ratio",
            index_tags.get("robust_signature_coverage_ratio", 0.0),
        )
        or 0.0
    )
    graph_prior_chunk_count = max(
        0,
        int(
            chunk_metrics.get(
                "graph_prior_chunk_count",
                index_tags.get("graph_prior_chunk_count", 0),
            )
            or 0
        ),
    )
    graph_prior_coverage_ratio = float(
        chunk_metrics.get(
            "graph_prior_coverage_ratio",
            index_tags.get("graph_prior_coverage_ratio", 0.0),
        )
        or 0.0
    )
    graph_prior_total = float(
        chunk_metrics.get(
            "graph_prior_total",
            index_tags.get("graph_prior_total", 0.0),
        )
        or 0.0
    )
    graph_seeded_chunk_count = max(
        0,
        int(
            chunk_metrics.get(
                "graph_seeded_chunk_count",
                index_tags.get("graph_seeded_chunk_count", 0),
            )
            or 0
        ),
    )
    graph_transfer_count = max(
        0,
        int(
            chunk_metrics.get(
                "graph_transfer_count",
                index_tags.get("graph_transfer_count", 0),
            )
            or 0
        ),
    )
    graph_hub_suppressed_chunk_count = max(
        0,
        int(
            chunk_metrics.get(
                "graph_hub_suppressed_chunk_count",
                index_tags.get("graph_hub_suppressed_chunk_count", 0),
            )
            or 0
        ),
    )
    graph_hub_penalty_total = float(
        chunk_metrics.get(
            "graph_hub_penalty_total",
            index_tags.get("graph_hub_penalty_total", 0.0),
        )
        or 0.0
    )
    graph_closure_enabled = bool(
        chunk_metrics.get(
            "graph_closure_enabled",
            index_tags.get("graph_closure_enabled", 0.0),
        )
    )
    graph_closure_boosted_chunk_count = max(
        0,
        int(
            chunk_metrics.get(
                "graph_closure_boosted_chunk_count",
                index_tags.get("graph_closure_boosted_chunk_count", 0),
            )
            or 0
        ),
    )
    graph_closure_coverage_ratio = float(
        chunk_metrics.get(
            "graph_closure_coverage_ratio",
            index_tags.get("graph_closure_coverage_ratio", 0.0),
        )
        or 0.0
    )
    graph_closure_anchor_count = max(
        0,
        int(
            chunk_metrics.get(
                "graph_closure_anchor_count",
                index_tags.get("graph_closure_anchor_count", 0),
            )
            or 0
        ),
    )
    graph_closure_support_edge_count = max(
        0,
        int(
            chunk_metrics.get(
                "graph_closure_support_edge_count",
                index_tags.get("graph_closure_support_edge_count", 0),
            )
            or 0
        ),
    )
    graph_closure_total = float(
        chunk_metrics.get(
            "graph_closure_total",
            index_tags.get("graph_closure_total", 0.0),
        )
        or 0.0
    )
    topological_shield_enabled = bool(
        topological_shield_payload.get(
            "enabled", chunk_metrics.get("topological_shield_enabled", 0.0)
        )
    )
    topological_shield_report_only = bool(
        topological_shield_payload.get(
            "report_only",
            chunk_metrics.get("topological_shield_report_only", 0.0),
        )
    )
    topological_shield_attenuated_chunk_count = max(
        0,
        int(
            topological_shield_payload.get(
                "attenuated_chunk_count",
                chunk_metrics.get("topological_shield_attenuated_chunk_count", 0.0),
            )
            or 0
        ),
    )
    topological_shield_coverage_ratio = float(
        topological_shield_payload.get(
            "coverage_ratio",
            chunk_metrics.get("topological_shield_coverage_ratio", 0.0),
        )
        or 0.0
    )
    topological_shield_attenuation_total = float(
        topological_shield_payload.get(
            "attenuation_total",
            chunk_metrics.get("topological_shield_attenuation_total", 0.0),
        )
        or 0.0
    )
    selected_skills = skills_payload.get("selected", [])
    if not isinstance(selected_skills, list):
        selected_skills = []
    skipped_for_budget = skills_payload.get("skipped_for_budget", [])
    if not isinstance(skipped_for_budget, list):
        skipped_for_budget = []
    skills_selected_count = float(
        len([item for item in selected_skills if isinstance(item, dict)])
    )
    skills_skipped_for_budget_count = float(
        len([item for item in skipped_for_budget if isinstance(item, dict)])
    )
    skills_token_budget = float(skills_payload.get("token_budget", 0.0) or 0.0)
    skills_token_budget_used = float(
        skills_payload.get(
            "token_budget_used",
            skills_payload.get("selected_token_estimate_total", 0.0),
        )
        or 0.0
    )
    skills_budget_exhausted = bool(skills_payload.get("budget_exhausted", False))
    skills_route_latency_ms = float(skills_payload.get("route_latency_ms", 0.0) or 0.0)
    skills_hydration_latency_ms = float(
        skills_payload.get("hydration_latency_ms", 0.0) or 0.0
    )
    skills_metadata_only_routing = bool(
        skills_payload.get("metadata_only_routing", False)
    )
    skills_precomputed_route = (
        str(skills_payload.get("routing_source") or "").strip().lower() == "precomputed"
    )
    plan_replay_cache_payload = (
        observability.get("plan_replay_cache", {})
        if isinstance(observability.get("plan_replay_cache"), dict)
        else {}
    )
    plan_replay_cache_enabled = bool(plan_replay_cache_payload.get("enabled", False))
    plan_replay_cache_hit = bool(plan_replay_cache_payload.get("hit", False))
    plan_replay_cache_stale_hit_safe = bool(
        plan_replay_cache_payload.get(
            "stale_hit_safe",
            plan_replay_cache_payload.get("safe_hit", False),
        )
    )
    source_plan_graph_closure_preference_enabled = bool(
        source_plan_packing_payload.get(
            "graph_closure_preference_enabled",
            source_plan_tags.get("packing_graph_closure_preference_enabled", False),
        )
    )
    source_plan_graph_closure_bonus_candidate_count = max(
        0,
        int(
            source_plan_packing_payload.get(
                "graph_closure_bonus_candidate_count",
                source_plan_tags.get(
                    "packing_graph_closure_bonus_candidate_count", 0
                ),
            )
            or 0
        ),
    )
    source_plan_graph_closure_preferred_count = max(
        0,
        int(
            source_plan_packing_payload.get(
                "graph_closure_preferred_count",
                source_plan_tags.get("packing_graph_closure_preferred_count", 0),
            )
            or 0
        ),
    )
    source_plan_focused_file_promoted_count = max(
        0,
        int(
            source_plan_packing_payload.get(
                "focused_file_promoted_count",
                source_plan_tags.get("packing_focused_file_promoted_count", 0),
            )
            or 0
        ),
    )
    source_plan_packed_path_count = max(
        0,
        int(
            source_plan_packing_payload.get(
                "packed_path_count",
                source_plan_tags.get("packing_packed_path_count", 0),
            )
            or 0
        ),
    )
    source_plan_packing_reason = str(
        source_plan_packing_payload.get(
            "reason",
            source_plan_tags.get("packing_reason", ""),
        )
        or ""
    )
    candidate_file_path_count = _count_unique_paths(
        [item for item in candidate_files if isinstance(item, dict)]
    )
    effective_packed_path_count = (
        source_plan_packed_path_count
        if source_plan_packed_path_count > 0
        else (
            _count_unique_paths(candidate_chunks)
            if source_plan_has_candidate_chunks
            else candidate_file_path_count
        )
    )
    source_plan_chunk_retention_ratio = _safe_ratio(
        len(candidate_chunks),
        len(raw_candidate_chunks),
    )
    source_plan_packed_path_ratio = _safe_ratio(
        effective_packed_path_count,
        candidate_file_path_count,
    )
    skills_token_budget_utilization_ratio = _safe_ratio(
        skills_token_budget_used,
        skills_token_budget,
    )
    graph_transfer_per_seed_ratio = _safe_ratio(
        graph_transfer_count,
        graph_seeded_chunk_count,
    )
    chunk_guard_pairwise_conflict_density = _safe_ratio(
        chunk_guard_pairwise_conflict_count,
        chunk_guard_candidate_pool,
    )
    topological_shield_attenuation_per_chunk = _safe_ratio(
        topological_shield_attenuation_total,
        topological_shield_attenuated_chunk_count,
    )
    router_enabled = bool(
        adaptive_router_payload.get(
            "enabled",
            index_metadata.get("router_enabled", index_tags.get("router_enabled", False)),
        )
    )
    router_mode = str(
        adaptive_router_payload.get(
            "mode",
            index_metadata.get("router_mode", index_tags.get("router_mode", "")),
        )
        or ""
    )
    router_arm_set = str(
        adaptive_router_payload.get(
            "arm_set",
            index_metadata.get("router_arm_set", index_tags.get("router_arm_set", "")),
        )
        or ""
    )
    router_arm_id = str(
        adaptive_router_payload.get(
            "arm_id",
            index_metadata.get("router_arm_id", index_tags.get("router_arm_id", "")),
        )
        or ""
    )
    router_confidence = float(
        adaptive_router_payload.get(
            "confidence",
            index_metadata.get(
                "router_confidence",
                index_tags.get("router_confidence", 0.0),
            ),
        )
        or 0.0
    )
    router_shadow_arm_id = str(
        adaptive_router_payload.get(
            "shadow_arm_id",
            index_metadata.get(
                "router_shadow_arm_id",
                index_tags.get("router_shadow_arm_id", ""),
            ),
        )
        or ""
    )
    router_shadow_confidence = float(
        adaptive_router_payload.get(
            "shadow_confidence",
            index_metadata.get(
                "router_shadow_confidence",
                index_tags.get("router_shadow_confidence", 0.0),
            ),
        )
        or 0.0
    )
    router_online_bandit_payload = (
        adaptive_router_payload.get("online_bandit", {})
        if isinstance(adaptive_router_payload.get("online_bandit"), dict)
        else {}
    )
    router_online_bandit_requested = bool(
        router_online_bandit_payload.get(
            "requested",
            index_metadata.get(
                "router_online_bandit_requested",
                index_tags.get("router_online_bandit_requested", False),
            ),
        )
    )
    router_experiment_enabled = bool(
        router_online_bandit_payload.get(
            "experiment_enabled",
            index_metadata.get(
                "router_experiment_enabled",
                index_tags.get("router_experiment_enabled", False),
            ),
        )
    )
    router_online_bandit_active = bool(
        router_online_bandit_payload.get(
            "active",
            index_metadata.get(
                "router_online_bandit_active",
                index_tags.get("router_online_bandit_active", False),
            ),
        )
    )
    router_is_exploration = bool(
        router_online_bandit_payload.get(
            "is_exploration",
            index_metadata.get(
                "router_is_exploration",
                index_tags.get("router_is_exploration", False),
            ),
        )
    )
    router_exploration_probability = float(
        router_online_bandit_payload.get(
            "exploration_probability",
            index_metadata.get(
                "router_exploration_probability",
                index_tags.get("router_exploration_probability", 0.0),
            ),
        )
        or 0.0
    )
    router_fallback_applied = bool(
        router_online_bandit_payload.get(
            "fallback_applied",
            index_metadata.get(
                "router_fallback_applied",
                index_tags.get("router_fallback_applied", False),
            ),
        )
    )
    router_fallback_reason = str(
        router_online_bandit_payload.get(
            "fallback_reason",
            index_metadata.get(
                "router_fallback_reason",
                index_tags.get("router_fallback_reason", ""),
            ),
        )
        or ""
    )
    router_online_bandit_reason = str(
        router_online_bandit_payload.get(
            "reason",
            index_metadata.get(
                "router_online_bandit_reason",
                index_tags.get("router_online_bandit_reason", ""),
            ),
        )
        or ""
    )

    policy_profile = str(index_payload.get("policy_name") or "").strip()
    docs_enabled_flag = bool(
        index_metadata.get("docs_enabled", docs_payload.get("enabled", False))
    )
    docs_section_count = int(
        index_metadata.get("docs_section_count", docs_payload.get("section_count", 0)) or 0
    )
    docs_injected_count = int(index_metadata.get("docs_injected_count", 0) or 0)
    docs_hit = 1.0 if docs_enabled_flag and docs_section_count > 0 else 0.0
    hint_inject = 1.0 if docs_injected_count > 0 else 0.0
    task_success = _evaluate_task_success(
        case=case,
        expected=expected,
        recall_hit=recall_hit,
        validation_tests=validation_tests,
    )
    task_success_config = dict(task_success["config"])
    task_success_failed_checks = list(task_success["failed_checks"])
    task_success_hit = float(task_success["hit"])
    slo_downgrade_signals = [
        name
        for name, active in (
            ("parallel_docs_timeout", parallel_docs_timed_out),
            ("parallel_worktree_timeout", parallel_worktree_timed_out),
            ("embedding_time_budget_exceeded", embedding_time_budget_exceeded),
            ("embedding_adaptive_budget_applied", embedding_adaptive_budget_applied),
            ("embedding_fallback", embedding_fallback),
            (
                "chunk_semantic_time_budget_exceeded",
                chunk_semantic_time_budget_exceeded,
            ),
            ("chunk_semantic_fallback", chunk_semantic_fallback),
            ("xref_budget_exhausted", xref_budget_exhausted),
        )
        if active
    ]
    evidence_insufficiency = _build_evidence_insufficiency(
        task_success_mode=str(task_success_config["mode"]),
        task_success_hit=task_success_hit,
        task_success_failed_checks=task_success_failed_checks,
        candidate_file_count=len(top_candidates),
        candidate_chunk_count=len(candidate_chunks),
        chunk_hit_at_k=chunk_hit_at_k,
        recall_hit=recall_hit,
        noise_rate=noise,
        validation_test_count=len(validation_tests),
        docs_enabled=docs_enabled_flag,
        docs_hit=docs_hit,
        dependency_recall=dependency_recall,
        neighbor_paths=[str(item).strip() for item in neighbor_paths if str(item).strip()],
        skills_budget_exhausted=skills_budget_exhausted,
        slo_downgrade_signals=slo_downgrade_signals,
    )
    decision_trace = _build_decision_trace(
        memory_gate_skipped=bool(memory_gate_payload.get("skipped", False)),
        memory_gate_skip_reason=memory_gate_skip_reason,
        memory_fallback_reason=memory_fallback_reason,
        memory_namespace_fallback=memory_namespace_fallback,
        candidate_ranker_fallbacks=[
            str(item).strip()
            for item in candidate_ranker_fallbacks
            if str(item).strip()
        ],
        exact_search_payload=exact_search_payload,
        second_pass_payload=second_pass_payload,
        refine_pass_payload=refine_pass_payload,
        docs_backend_fallback_reason=docs_backend_fallback_reason,
        parallel_docs_timed_out=parallel_docs_timed_out,
        parallel_worktree_timed_out=parallel_worktree_timed_out,
        embedding_adaptive_budget_applied=embedding_adaptive_budget_applied,
        embedding_time_budget_exceeded=embedding_time_budget_exceeded,
        embedding_fallback=embedding_fallback,
        chunk_semantic_time_budget_exceeded=chunk_semantic_time_budget_exceeded,
        chunk_semantic_fallback=chunk_semantic_fallback,
        chunk_semantic_reason=chunk_semantic_reason,
        xref_budget_exhausted=xref_budget_exhausted,
        skills_budget_exhausted=skills_budget_exhausted,
    )
    chunk_guard_expectation = _evaluate_chunk_guard_expectation(
        case=case,
        chunk_guard_payload=chunk_guard_payload,
    )

    payload = {
        "case_id": case.get("case_id", "unknown"),
        "query": case.get("query", ""),
        "expected_keys": expected,
        "top_k": top_k,
        "recall_hit": recall_hit,
        "precision_at_k": precision,
        "first_hit_rank": first_hit_rank,
        "hit_at_1": hit_at_1,
        "reciprocal_rank": reciprocal_rank,
        "utility_hit": utility,
        "task_success_hit": task_success_hit,
        "task_success_mode": str(task_success_config["mode"]),
        "task_success_failed_checks": task_success_failed_checks,
        "task_success_requirements": {
            "require_recall_hit": bool(task_success_config["require_recall_hit"]),
            "min_validation_tests": int(task_success_config["min_validation_tests"]),
        },
        "noise_rate": noise,
        "dependency_recall": dependency_recall,
        "memory_latency_ms": memory_latency_ms,
        "index_latency_ms": index_latency_ms,
        "repomap_latency_ms": repomap_latency_ms,
        "augment_latency_ms": augment_latency_ms,
        "skills_latency_ms": skills_latency_ms,
        "source_plan_latency_ms": source_plan_latency_ms,
        "latency_ms": latency_ms,
        "chunk_hit_at_k": chunk_hit_at_k,
        "chunks_per_file_mean": chunks_per_file_mean,
        "chunk_budget_used": chunk_budget_used,
        "chunk_contract_fallback_count": float(chunk_contract_fallback_count),
        "chunk_contract_skeleton_chunk_count": float(
            chunk_contract_skeleton_chunk_count
        ),
        "chunk_contract_fallback_ratio": chunk_contract_fallback_ratio,
        "chunk_contract_skeleton_ratio": chunk_contract_skeleton_ratio,
        "unsupported_language_fallback_count": float(
            unsupported_language_fallback_count
        ),
        "unsupported_language_fallback_ratio": (
            unsupported_language_fallback_ratio
        ),
        "subgraph_payload_enabled": 1.0 if subgraph_payload_enabled else 0.0,
        "subgraph_seed_path_count": float(subgraph_seed_path_count),
        "subgraph_edge_type_count": float(subgraph_edge_type_count),
        "subgraph_edge_total_count": float(subgraph_edge_total_count),
        "robust_signature_count": float(robust_signature_count),
        "robust_signature_coverage_ratio": robust_signature_coverage_ratio,
        "graph_prior_chunk_count": float(graph_prior_chunk_count),
        "graph_prior_coverage_ratio": float(graph_prior_coverage_ratio),
        "graph_prior_total": float(graph_prior_total),
        "graph_seeded_chunk_count": float(graph_seeded_chunk_count),
        "graph_transfer_count": float(graph_transfer_count),
        "graph_hub_suppressed_chunk_count": float(graph_hub_suppressed_chunk_count),
        "graph_hub_penalty_total": float(graph_hub_penalty_total),
        "graph_closure_enabled": 1.0 if graph_closure_enabled else 0.0,
        "graph_closure_boosted_chunk_count": float(
            graph_closure_boosted_chunk_count
        ),
        "graph_closure_coverage_ratio": float(graph_closure_coverage_ratio),
        "graph_closure_anchor_count": float(graph_closure_anchor_count),
        "graph_closure_support_edge_count": float(
            graph_closure_support_edge_count
        ),
        "graph_closure_total": float(graph_closure_total),
        "topological_shield_enabled": 1.0 if topological_shield_enabled else 0.0,
        "topological_shield_report_only": (
            1.0 if topological_shield_report_only else 0.0
        ),
        "topological_shield_attenuated_chunk_count": float(
            topological_shield_attenuated_chunk_count
        ),
        "topological_shield_coverage_ratio": float(
            topological_shield_coverage_ratio
        ),
        "topological_shield_attenuation_total": float(
            topological_shield_attenuation_total
        ),
        "topological_shield_attenuation_per_chunk": (
            topological_shield_attenuation_per_chunk
        ),
        "skills_selected_count": skills_selected_count,
        "skills_token_budget": skills_token_budget,
        "skills_token_budget_used": skills_token_budget_used,
        "skills_token_budget_utilization_ratio": (
            skills_token_budget_utilization_ratio
        ),
        "skills_budget_exhausted": 1.0 if skills_budget_exhausted else 0.0,
        "skills_skipped_for_budget_count": skills_skipped_for_budget_count,
        "skills_route_latency_ms": skills_route_latency_ms,
        "skills_hydration_latency_ms": skills_hydration_latency_ms,
        "skills_metadata_only_routing": (
            1.0 if skills_metadata_only_routing else 0.0
        ),
        "skills_precomputed_route": 1.0 if skills_precomputed_route else 0.0,
        "plan_replay_cache_enabled": 1.0 if plan_replay_cache_enabled else 0.0,
        "plan_replay_cache_hit": 1.0 if plan_replay_cache_hit else 0.0,
        "plan_replay_cache_stale_hit_safe": (
            1.0 if plan_replay_cache_stale_hit_safe else 0.0
        ),
        "chunk_stage_miss_applicable": 1.0 if chunk_stage_miss["applicable"] else 0.0,
        "chunk_stage_miss_classified": 1.0 if chunk_stage_miss["label"] else 0.0,
        "chunk_stage_miss": str(chunk_stage_miss["label"]),
        "validation_test_count": len(validation_tests),
        "source_plan_direct_evidence_ratio": float(
            source_plan_evidence_summary.get("direct_ratio", 0.0) or 0.0
        ),
        "source_plan_neighbor_context_ratio": float(
            source_plan_evidence_summary.get("neighbor_context_ratio", 0.0) or 0.0
        ),
        "source_plan_hint_only_ratio": float(
            source_plan_evidence_summary.get("hint_only_ratio", 0.0) or 0.0
        ),
        "source_plan_graph_closure_preference_enabled": (
            1.0 if source_plan_graph_closure_preference_enabled else 0.0
        ),
        "source_plan_graph_closure_bonus_candidate_count": float(
            source_plan_graph_closure_bonus_candidate_count
        ),
        "source_plan_graph_closure_preferred_count": float(
            source_plan_graph_closure_preferred_count
        ),
        "source_plan_focused_file_promoted_count": float(
            source_plan_focused_file_promoted_count
        ),
        "source_plan_packed_path_count": float(source_plan_packed_path_count),
        "source_plan_chunk_retention_ratio": source_plan_chunk_retention_ratio,
        "source_plan_packed_path_ratio": source_plan_packed_path_ratio,
        "notes_hit_ratio": notes_hit_ratio,
        "profile_selected_count": float(profile_selected_count),
        "capture_triggered": 1.0 if capture_triggered else 0.0,
        "policy_profile": policy_profile,
        "graph_transfer_per_seed_ratio": graph_transfer_per_seed_ratio,
        "router_enabled": 1.0 if router_enabled else 0.0,
        "router_mode": router_mode,
        "router_arm_set": router_arm_set,
        "router_arm_id": router_arm_id,
        "router_confidence": router_confidence,
        "router_shadow_arm_id": router_shadow_arm_id,
        "router_shadow_confidence": router_shadow_confidence,
        "router_online_bandit_requested": 1.0
        if router_online_bandit_requested
        else 0.0,
        "router_experiment_enabled": 1.0 if router_experiment_enabled else 0.0,
        "router_online_bandit_active": 1.0 if router_online_bandit_active else 0.0,
        "router_is_exploration": 1.0 if router_is_exploration else 0.0,
        "router_exploration_probability": router_exploration_probability,
        "router_fallback_applied": 1.0 if router_fallback_applied else 0.0,
        "router_fallback_reason": router_fallback_reason,
        "router_online_bandit_reason": router_online_bandit_reason,
        "docs_enabled": 1.0 if docs_enabled_flag else 0.0,
        "docs_hit": docs_hit,
        "hint_inject": hint_inject,
        "embedding_enabled": 1.0 if embedding_enabled else 0.0,
        "embedding_similarity_mean": embedding_similarity_mean,
        "embedding_similarity_max": embedding_similarity_max,
        "embedding_rerank_ratio": embedding_rerank_ratio,
        "embedding_cache_hit": 1.0 if embedding_cache_hit else 0.0,
        "embedding_fallback": 1.0 if embedding_fallback else 0.0,
        "parallel_time_budget_ms": parallel_time_budget_ms,
        "embedding_time_budget_ms": embedding_time_budget_ms,
        "chunk_semantic_time_budget_ms": chunk_semantic_time_budget_ms,
        "xref_time_budget_ms": xref_time_budget_ms,
        "parallel_docs_timed_out": 1.0 if parallel_docs_timed_out else 0.0,
        "parallel_worktree_timed_out": 1.0 if parallel_worktree_timed_out else 0.0,
        "embedding_time_budget_exceeded": (
            1.0 if embedding_time_budget_exceeded else 0.0
        ),
        "embedding_adaptive_budget_applied": (
            1.0 if embedding_adaptive_budget_applied else 0.0
        ),
        "chunk_semantic_time_budget_exceeded": (
            1.0 if chunk_semantic_time_budget_exceeded else 0.0
        ),
        "chunk_semantic_fallback": 1.0 if chunk_semantic_fallback else 0.0,
        "chunk_guard_enabled": 1.0 if chunk_guard_enabled else 0.0,
        "chunk_guard_mode": chunk_guard_mode,
        "chunk_guard_reason": chunk_guard_reason,
        "chunk_guard_report_only": 1.0 if chunk_guard_report_only else 0.0,
        "chunk_guard_filtered_count": float(chunk_guard_filtered_count),
        "chunk_guard_filter_ratio": float(chunk_guard_filter_ratio),
        "chunk_guard_pairwise_conflict_count": float(
            chunk_guard_pairwise_conflict_count
        ),
        "chunk_guard_pairwise_conflict_density": (
            chunk_guard_pairwise_conflict_density
        ),
        "chunk_guard_fallback": 1.0 if chunk_guard_fallback else 0.0,
        "chunk_guard_expectation_applicable": (
            1.0 if chunk_guard_expectation["applicable"] else 0.0
        ),
        "chunk_guard_stale_majority_case": (
            1.0 if chunk_guard_expectation["scenario"] == "stale_majority" else 0.0
        ),
        "chunk_guard_expected_retained_hit": (
            1.0 if chunk_guard_expectation["expected_retained_hit"] else 0.0
        ),
        "chunk_guard_expected_filtered_hit_count": float(
            chunk_guard_expectation["expected_filtered_hit_count"]
        ),
        "chunk_guard_expected_filtered_hit_rate": float(
            chunk_guard_expectation["expected_filtered_hit_rate"]
        ),
        "chunk_guard_report_only_improved": (
            1.0 if chunk_guard_expectation["report_only_improved"] else 0.0
        ),
        "xref_budget_exhausted": 1.0 if xref_budget_exhausted else 0.0,
        "slo_downgrade_triggered": 1.0 if slo_downgrade_signals else 0.0,
        "decision_trace_count": len(decision_trace),
        "decision_trace": decision_trace,
        **evidence_insufficiency,
    }
    if comparison_lane:
        payload["comparison_lane"] = comparison_lane
    if include_case_details:
        payload["candidate_paths"] = [
            item.get("path") for item in top_candidates if isinstance(item, dict)
        ]
        if (
            included_candidate_paths
            or included_candidate_globs
            or excluded_candidate_paths
            or excluded_candidate_globs
        ):
            payload["candidate_path_filters"] = {
                "include_paths": included_candidate_paths,
                "include_globs": included_candidate_globs,
                "exclude_paths": excluded_candidate_paths,
                "exclude_globs": excluded_candidate_globs,
            }
        payload["relevant_candidate_paths"] = relevant_candidate_paths
        payload["noise_candidate_paths"] = noise_candidate_paths
        payload["candidate_matches"] = candidate_matches
        payload["candidate_chunk_refs"] = [
            item.get("qualified_name") for item in top_chunks if isinstance(item, dict)
        ]
        payload["expected_hits"] = expected_hits
        payload["chunk_hits"] = chunk_hits
        payload["validation_tests"] = [
            str(item).strip()
            for item in validation_tests
            if str(item).strip()
        ][:20]
        payload["source_plan_evidence_summary"] = source_plan_evidence_summary
        payload["stage_latency_ms"] = {
            "memory": round(memory_latency_ms, 3),
            "index": round(index_latency_ms, 3),
            "repomap": round(repomap_latency_ms, 3),
            "augment": round(augment_latency_ms, 3),
            "skills": round(skills_latency_ms, 3),
            "source_plan": round(source_plan_latency_ms, 3),
        }
        payload["chunk_contract"] = {
            "fallback_count": chunk_contract_fallback_count,
            "skeleton_chunk_count": chunk_contract_skeleton_chunk_count,
            "fallback_ratio": round(chunk_contract_fallback_ratio, 6),
            "skeleton_ratio": round(chunk_contract_skeleton_ratio, 6),
            "unsupported_language_fallback_count": (
                unsupported_language_fallback_count
            ),
            "unsupported_language_fallback_ratio": round(
                unsupported_language_fallback_ratio,
                6,
            ),
        }
        payload["subgraph_payload"] = {
            "enabled": subgraph_payload_enabled,
            "reason": str(subgraph_payload.get("reason") or ""),
            "seed_path_count": subgraph_seed_path_count,
            "edge_type_count": subgraph_edge_type_count,
            "edge_total_count": subgraph_edge_total_count,
            "seed_paths": [
                str(item).strip() for item in subgraph_seed_paths if str(item).strip()
            ],
            "edge_counts": {
                str(key): max(0, int(value or 0))
                for key, value in subgraph_edge_counts.items()
                if str(key).strip()
            },
        }
        payload["skills_budget"] = {
            "selected_count": int(skills_selected_count),
            "token_budget": round(skills_token_budget, 3),
            "token_budget_used": round(skills_token_budget_used, 3),
            "utilization_ratio": round(skills_token_budget_utilization_ratio, 6),
            "budget_exhausted": bool(skills_budget_exhausted),
            "skipped_for_budget_count": int(skills_skipped_for_budget_count),
        }
        payload["skills_routing"] = {
            "source": str(skills_payload.get("routing_source") or ""),
            "mode": str(skills_payload.get("routing_mode") or ""),
            "metadata_only_routing": bool(skills_metadata_only_routing),
            "route_latency_ms": round(skills_route_latency_ms, 3),
            "hydration_latency_ms": round(skills_hydration_latency_ms, 3),
            "selected_manifest_token_estimate_total": round(
                float(
                    skills_payload.get("selected_manifest_token_estimate_total", 0.0)
                    or 0.0
                ),
                3,
            ),
            "hydrated_skill_count": int(skills_payload.get("hydrated_skill_count", 0) or 0),
            "hydrated_sections_count": int(
                skills_payload.get("hydrated_sections_count", 0) or 0
            ),
        }
        payload["plan_replay_cache"] = {
            "enabled": plan_replay_cache_enabled,
            "hit": plan_replay_cache_hit,
            "stale_hit_safe": plan_replay_cache_stale_hit_safe,
            "stage": str(plan_replay_cache_payload.get("stage", "")),
            "reason": str(plan_replay_cache_payload.get("reason", "")),
            "stored": bool(plan_replay_cache_payload.get("stored", False)),
        }
        if chunk_stage_miss["applicable"]:
            payload["chunk_stage_miss_details"] = {
                "oracle_file_path": str(chunk_stage_miss["oracle_file_path"]),
                "oracle_chunk_ref": dict(chunk_stage_miss["oracle_chunk_ref"]),
                "file_present": bool(chunk_stage_miss["file_present"]),
                "raw_chunk_present": bool(chunk_stage_miss["raw_chunk_present"]),
                "source_plan_chunk_present": bool(
                    chunk_stage_miss["source_plan_chunk_present"]
                ),
            }
        payload["slo_downgrade_signals"] = slo_downgrade_signals
        payload["slo_budget_limits_ms"] = {
            "parallel_time_budget_ms": round(parallel_time_budget_ms, 3),
            "embedding_time_budget_ms": round(embedding_time_budget_ms, 3),
            "chunk_semantic_time_budget_ms": round(
                chunk_semantic_time_budget_ms, 3
            ),
            "xref_time_budget_ms": round(xref_time_budget_ms, 3),
        }
        payload["chunk_guard"] = {
            "mode": chunk_guard_mode,
            "reason": chunk_guard_reason,
            "candidate_pool": chunk_guard_candidate_pool,
            "signed_chunk_count": chunk_guard_signed_chunk_count,
            "filtered_count": chunk_guard_filtered_count,
            "retained_count": chunk_guard_retained_count,
            "pairwise_conflict_count": chunk_guard_pairwise_conflict_count,
            "pairwise_conflict_density": round(
                chunk_guard_pairwise_conflict_density, 6
            ),
            "max_conflict_penalty": round(chunk_guard_max_conflict_penalty, 6),
            "retained_refs": list(chunk_guard_payload.get("retained_refs", []))
            if isinstance(chunk_guard_payload.get("retained_refs"), list)
            else [],
            "filtered_refs": list(chunk_guard_payload.get("filtered_refs", []))
            if isinstance(chunk_guard_payload.get("filtered_refs"), list)
            else [],
            "report_only": chunk_guard_report_only,
            "fallback": chunk_guard_fallback,
        }
        if chunk_guard_expectation["applicable"]:
            payload["chunk_guard_expectation"] = {
                "scenario": str(chunk_guard_expectation["scenario"]),
                "expected_retained_refs": list(
                    chunk_guard_expectation["expected_retained_refs"]
                ),
                "expected_filtered_refs": list(
                    chunk_guard_expectation["expected_filtered_refs"]
                ),
                "retained_hits": list(chunk_guard_expectation["retained_hits"]),
                "filtered_hits": list(chunk_guard_expectation["filtered_hits"]),
                "expected_retained_hit": bool(
                    chunk_guard_expectation["expected_retained_hit"]
                ),
                "expected_filtered_hit_count": int(
                    chunk_guard_expectation["expected_filtered_hit_count"]
                ),
                "expected_filtered_hit_rate": round(
                    float(chunk_guard_expectation["expected_filtered_hit_rate"]), 6
                ),
                "report_only_improved": bool(
                    chunk_guard_expectation["report_only_improved"]
                ),
            }
        payload["robust_signature"] = {
            "count": robust_signature_count,
            "coverage_ratio": round(robust_signature_coverage_ratio, 6),
        }
        payload["graph_prior"] = {
            "chunk_count": graph_prior_chunk_count,
            "coverage_ratio": round(graph_prior_coverage_ratio, 6),
            "total": round(graph_prior_total, 6),
            "seeded_chunk_count": graph_seeded_chunk_count,
            "transfer_count": graph_transfer_count,
            "transfer_per_seed_ratio": round(graph_transfer_per_seed_ratio, 6),
            "hub_suppressed_chunk_count": graph_hub_suppressed_chunk_count,
            "hub_penalty_total": round(graph_hub_penalty_total, 6),
        }
        payload["topological_shield"] = {
            "enabled": topological_shield_enabled,
            "report_only": topological_shield_report_only,
            "attenuated_chunk_count": topological_shield_attenuated_chunk_count,
            "coverage_ratio": round(topological_shield_coverage_ratio, 6),
            "attenuation_total": round(topological_shield_attenuation_total, 6),
            "attenuation_per_chunk": round(
                topological_shield_attenuation_per_chunk, 6
            ),
        }
        payload["graph_closure"] = {
            "enabled": graph_closure_enabled,
            "boosted_chunk_count": graph_closure_boosted_chunk_count,
            "coverage_ratio": round(graph_closure_coverage_ratio, 6),
            "anchor_count": graph_closure_anchor_count,
            "support_edge_count": graph_closure_support_edge_count,
            "total": round(graph_closure_total, 6),
        }
        payload["source_plan_packing"] = {
            "graph_closure_preference_enabled": (
                source_plan_graph_closure_preference_enabled
            ),
            "graph_closure_bonus_candidate_count": (
                source_plan_graph_closure_bonus_candidate_count
            ),
            "graph_closure_preferred_count": (
                source_plan_graph_closure_preferred_count
            ),
            "focused_file_promoted_count": source_plan_focused_file_promoted_count,
            "packed_path_count": source_plan_packed_path_count,
            "packed_path_ratio": round(source_plan_packed_path_ratio, 6),
            "chunk_retention_ratio": round(source_plan_chunk_retention_ratio, 6),
            "reason": source_plan_packing_reason,
        }
        payload["year2_normalized_kpis"] = {
            "skills_token_budget_utilization_ratio": round(
                skills_token_budget_utilization_ratio, 6
            ),
            "source_plan_chunk_retention_ratio": round(
                source_plan_chunk_retention_ratio, 6
            ),
            "source_plan_packed_path_ratio": round(
                source_plan_packed_path_ratio, 6
            ),
            "graph_transfer_per_seed_ratio": round(
                graph_transfer_per_seed_ratio, 6
            ),
            "chunk_guard_pairwise_conflict_density": round(
                chunk_guard_pairwise_conflict_density, 6
            ),
            "topological_shield_attenuation_per_chunk": round(
                topological_shield_attenuation_per_chunk, 6
            ),
        }
    return payload


__all__ = ["evaluate_case_result"]
