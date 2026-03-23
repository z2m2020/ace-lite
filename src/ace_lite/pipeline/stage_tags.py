from __future__ import annotations

from typing import Any


def build_stage_tags(*, stage_name: str, output: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(output, dict):
        return {}

    policy_name = str(output.get("policy_name", ""))
    policy_version = str(output.get("policy_version", ""))

    if stage_name == "memory":
        cache = output.get("cache", {}) if isinstance(output.get("cache"), dict) else {}
        timeline = (
            output.get("timeline", {}) if isinstance(output.get("timeline"), dict) else {}
        )
        disclosure = (
            output.get("disclosure", {})
            if isinstance(output.get("disclosure"), dict)
            else {}
        )
        cost = output.get("cost", {}) if isinstance(output.get("cost"), dict) else {}
        namespace = (
            output.get("namespace", {})
            if isinstance(output.get("namespace"), dict)
            else {}
        )
        profile = (
            output.get("profile", {})
            if isinstance(output.get("profile"), dict)
            else {}
        )
        capture = (
            output.get("capture", {})
            if isinstance(output.get("capture"), dict)
            else {}
        )
        notes = output.get("notes", {}) if isinstance(output.get("notes"), dict) else {}
        temporal = (
            output.get("temporal", {})
            if isinstance(output.get("temporal"), dict)
            else {}
        )
        recency = (
            temporal.get("recency_boost", {})
            if isinstance(temporal.get("recency_boost"), dict)
            else {}
        )
        return {
            "channel_used": str(output.get("channel_used", "")),
            "strategy": str(output.get("strategy", "")),
            "fallback": bool(output.get("fallback_reason")),
            "hit_count": int(output.get("count", 0) or 0),
            "disclosure_mode": str(disclosure.get("mode", "")),
            "preview_tokens": int(cost.get("preview_est_tokens_total", 0) or 0),
            "tokenizer_model": str(cost.get("tokenizer_model", "")),
            "tokenizer_backend": str(cost.get("tokenizer_backend", "")),
            "cache_hit_count": int(cache.get("hit_count", 0) or 0),
            "timeline_groups": len(timeline.get("groups", []))
            if isinstance(timeline.get("groups", []), list)
            else 0,
            "memory_namespace_mode": str(namespace.get("mode", "")),
            "memory_namespace_source": str(namespace.get("source", "")),
            "memory_container_tag_set": bool(
                str(namespace.get("container_tag_effective", "")).strip()
            ),
            "memory_namespace_fallback": bool(str(namespace.get("fallback", "")).strip()),
            "memory_profile_enabled": bool(profile.get("enabled", False)),
            "memory_profile_selected": int(profile.get("selected_count", 0) or 0),
            "capture_enabled": bool(capture.get("enabled", False)),
            "capture_triggered": bool(capture.get("triggered", False)),
            "captured_items": int(capture.get("captured_items", 0) or 0),
            "capture_notes_pruned_expired": int(
                capture.get("notes_pruned_expired_count", 0) or 0
            ),
            "notes_enabled": bool(notes.get("enabled", False)),
            "notes_selected_count": int(notes.get("selected_count", 0) or 0),
            "notes_matched_count": int(notes.get("matched_count", 0) or 0),
            "notes_expired_count": int(notes.get("expired_count", 0) or 0),
            "temporal_requested": bool(temporal.get("requested", False)),
            "temporal_enabled": bool(temporal.get("enabled", False)),
            "temporal_reason": str(temporal.get("reason", "")),
            "temporal_filtered_out": int(temporal.get("filtered_out_count", 0) or 0),
            "temporal_unknown_timestamp_count": int(
                temporal.get("unknown_timestamp_count", 0) or 0
            ),
            "recency_boost_enabled": bool(recency.get("enabled", False)),
            "recency_boost_effective": bool(recency.get("enabled_effective", False)),
            "recency_boost_applied_count": int(recency.get("applied_count", 0) or 0),
            "policy_name": policy_name,
            "policy_version": policy_version,
        }

    if stage_name == "index":
        cache = output.get("cache", {}) if isinstance(output.get("cache"), dict) else {}
        candidates = output.get("candidate_files", [])
        chunks = output.get("candidate_chunks", [])
        router = (
            output.get("adaptive_router", {})
            if isinstance(output.get("adaptive_router"), dict)
            else {}
        )
        router_online_bandit = (
            router.get("online_bandit", {})
            if isinstance(router.get("online_bandit"), dict)
            else {}
        )
        chunk_metrics = (
            output.get("chunk_metrics", {})
            if isinstance(output.get("chunk_metrics"), dict)
            else {}
        )
        chunk_semantic = (
            output.get("chunk_semantic_rerank", {})
            if isinstance(output.get("chunk_semantic_rerank"), dict)
            else {}
        )
        chunk_guard = (
            output.get("chunk_guard", {})
            if isinstance(output.get("chunk_guard"), dict)
            else {}
        )
        cochange = (
            output.get("cochange", {}) if isinstance(output.get("cochange"), dict) else {}
        )
        ranking = (
            output.get("candidate_ranking", {})
            if isinstance(output.get("candidate_ranking"), dict)
            else {}
        )
        embeddings = (
            output.get("embeddings", {})
            if isinstance(output.get("embeddings"), dict)
            else {}
        )
        docs = output.get("docs", {}) if isinstance(output.get("docs"), dict) else {}
        worktree_prior = (
            output.get("worktree_prior", {})
            if isinstance(output.get("worktree_prior"), dict)
            else {}
        )
        prior = (
            output.get("prior_applied", {})
            if isinstance(output.get("prior_applied"), dict)
            else {}
        )
        graph_lookup = (
            output.get("graph_lookup", {})
            if isinstance(output.get("graph_lookup"), dict)
            else {}
        )
        graph_lookup_weights = (
            graph_lookup.get("weights", {})
            if isinstance(graph_lookup.get("weights"), dict)
            else {}
        )
        parallel = (
            output.get("parallel", {})
            if isinstance(output.get("parallel"), dict)
            else {}
        )
        parallel_docs = (
            parallel.get("docs", {}) if isinstance(parallel.get("docs"), dict) else {}
        )
        parallel_worktree = (
            parallel.get("worktree", {})
            if isinstance(parallel.get("worktree"), dict)
            else {}
        )
        multi_channel_fusion = (
            output.get("multi_channel_fusion", {})
            if isinstance(output.get("multi_channel_fusion"), dict)
            else {}
        )
        multi_channel_channels = (
            multi_channel_fusion.get("channels", {})
            if isinstance(multi_channel_fusion.get("channels"), dict)
            else {}
        )
        multi_channel_granularity = (
            multi_channel_channels.get("granularity", {})
            if isinstance(multi_channel_channels.get("granularity"), dict)
            else {}
        )
        multi_channel_fused = (
            multi_channel_fusion.get("fused", {})
            if isinstance(multi_channel_fusion.get("fused"), dict)
            else {}
        )
        chunk_semantic_reranked_count = int(
            chunk_semantic.get("reranked_count", 0) or 0
        )
        chunk_semantic_pool_effective = int(
            chunk_semantic.get("rerank_pool_effective", 0) or 0
        )
        chunk_semantic_ratio = (
            float(chunk_semantic_reranked_count) / float(chunk_semantic_pool_effective)
            if chunk_semantic_pool_effective > 0
            else 0.0
        )
        multi_channel_granularity_count = max(
            0, int(multi_channel_granularity.get("count", 0) or 0)
        )
        multi_channel_rrf_pool_size = max(
            0, int(multi_channel_fused.get("pool_size", 0) or 0)
        )
        multi_channel_granularity_pool_ratio = (
            float(multi_channel_granularity_count) / float(multi_channel_rrf_pool_size)
            if multi_channel_rrf_pool_size > 0
            else 0.0
        )
        return {
            "cache_mode": str(cache.get("mode", "")),
            "cache_hit": bool(cache.get("cache_hit", False)),
            "candidate_count": len(candidates) if isinstance(candidates, list) else 0,
            "candidate_chunk_count": len(chunks) if isinstance(chunks, list) else 0,
            "chunks_per_file_mean": float(
                chunk_metrics.get("chunks_per_file_mean", 0.0) or 0.0
            ),
            "chunk_budget_used": float(chunk_metrics.get("chunk_budget_used", 0.0) or 0.0),
            "chunk_dedup_ratio": float(chunk_metrics.get("dedup_ratio", 0.0) or 0.0),
            "chunk_unique_files": int(
                chunk_metrics.get("unique_files_in_chunks", 0) or 0
            ),
            "chunk_unique_symbol_families": int(
                chunk_metrics.get("unique_symbol_families_in_chunks", 0) or 0
            ),
            "robust_signature_count": int(
                chunk_metrics.get("robust_signature_count", 0) or 0
            ),
            "robust_signature_coverage_ratio": float(
                chunk_metrics.get("robust_signature_coverage_ratio", 0.0) or 0.0
            ),
            "graph_prior_chunk_count": int(
                chunk_metrics.get("graph_prior_chunk_count", 0) or 0
            ),
            "graph_prior_coverage_ratio": float(
                chunk_metrics.get("graph_prior_coverage_ratio", 0.0) or 0.0
            ),
            "graph_prior_total": float(
                chunk_metrics.get("graph_prior_total", 0.0) or 0.0
            ),
            "graph_seeded_chunk_count": int(
                chunk_metrics.get("graph_seeded_chunk_count", 0) or 0
            ),
            "graph_transfer_count": int(
                chunk_metrics.get("graph_transfer_count", 0) or 0
            ),
            "graph_hub_suppressed_chunk_count": int(
                chunk_metrics.get("graph_hub_suppressed_chunk_count", 0) or 0
            ),
            "graph_hub_penalty_total": float(
                chunk_metrics.get("graph_hub_penalty_total", 0.0) or 0.0
            ),
            "graph_closure_enabled": bool(
                chunk_metrics.get("graph_closure_enabled", 0.0) or 0.0
            ),
            "graph_closure_boosted_chunk_count": int(
                chunk_metrics.get("graph_closure_boosted_chunk_count", 0) or 0
            ),
            "graph_closure_coverage_ratio": float(
                chunk_metrics.get("graph_closure_coverage_ratio", 0.0) or 0.0
            ),
            "graph_closure_anchor_count": int(
                chunk_metrics.get("graph_closure_anchor_count", 0) or 0
            ),
            "graph_closure_support_edge_count": int(
                chunk_metrics.get("graph_closure_support_edge_count", 0) or 0
            ),
            "graph_closure_total": float(
                chunk_metrics.get("graph_closure_total", 0.0) or 0.0
            ),
            "chunk_diversity_enabled": bool(
                chunk_metrics.get("diversity_enabled", 0.0) or 0.0
            ),
            "cochange_enabled": bool(cochange.get("enabled", False)),
            "cochange_neighbors_added": int(cochange.get("neighbors_added", 0) or 0),
            "docs_enabled": bool(docs.get("enabled", False)),
            "docs_section_count": int(docs.get("section_count", 0) or 0),
            "docs_hint_path_count": int(prior.get("docs_hint_paths", 0) or 0),
            "docs_injected_count": int(
                prior.get("docs_injected_candidate_count", 0) or 0
            ),
            "worktree_enabled": bool(worktree_prior.get("enabled", False)),
            "worktree_changed_count": int(worktree_prior.get("changed_count", 0) or 0),
            "worktree_seed_count": len(worktree_prior.get("seed_paths", []))
            if isinstance(worktree_prior.get("seed_paths"), list)
            else 0,
            "prior_boosted_count": int(prior.get("boosted_candidate_count", 0) or 0),
            "prior_added_count": int(prior.get("added_candidate_count", 0) or 0),
            "graph_lookup_enabled": bool(graph_lookup.get("enabled", False)),
            "graph_lookup_reason": str(graph_lookup.get("reason", "")),
            "graph_lookup_guarded": bool(graph_lookup.get("guarded", False)),
            "graph_lookup_boosted_count": int(graph_lookup.get("boosted_count", 0) or 0),
            "graph_lookup_weight_scip": float(graph_lookup_weights.get("scip", 0.0) or 0.0),
            "graph_lookup_weight_xref": float(graph_lookup_weights.get("xref", 0.0) or 0.0),
            "graph_lookup_weight_query_xref": float(
                graph_lookup_weights.get("query_xref", 0.0) or 0.0
            ),
            "graph_lookup_weight_symbol": float(
                graph_lookup_weights.get("symbol", 0.0) or 0.0
            ),
            "graph_lookup_weight_import": float(
                graph_lookup_weights.get("import", 0.0) or 0.0
            ),
            "graph_lookup_weight_coverage": float(
                graph_lookup_weights.get("coverage", 0.0) or 0.0
            ),
            "graph_lookup_candidate_count": int(graph_lookup.get("candidate_count", 0) or 0),
            "graph_lookup_pool_size": int(graph_lookup.get("pool_size", 0) or 0),
            "graph_lookup_query_terms_count": int(
                graph_lookup.get("query_terms_count", 0) or 0
            ),
            "graph_lookup_normalization": str(graph_lookup.get("normalization", "")),
            "graph_lookup_guard_max_candidates": int(
                graph_lookup.get("guard_max_candidates", 0) or 0
            ),
            "graph_lookup_guard_min_query_terms": int(
                graph_lookup.get("guard_min_query_terms", 0) or 0
            ),
            "graph_lookup_guard_max_query_terms": int(
                graph_lookup.get("guard_max_query_terms", 0) or 0
            ),
            "graph_lookup_query_hit_paths": int(
                graph_lookup.get("query_hit_paths", 0) or 0
            ),
            "graph_lookup_scip_signal_paths": int(
                graph_lookup.get("scip_signal_paths", 0) or 0
            ),
            "graph_lookup_xref_signal_paths": int(
                graph_lookup.get("xref_signal_paths", 0) or 0
            ),
            "graph_lookup_symbol_hit_paths": int(
                graph_lookup.get("symbol_hit_paths", 0) or 0
            ),
            "graph_lookup_import_hit_paths": int(
                graph_lookup.get("import_hit_paths", 0) or 0
            ),
            "graph_lookup_coverage_hit_paths": int(
                graph_lookup.get("coverage_hit_paths", 0) or 0
            ),
            "graph_lookup_max_inbound": float(graph_lookup.get("max_inbound", 0.0) or 0.0),
            "graph_lookup_max_xref_count": float(
                graph_lookup.get("max_xref_count", 0.0) or 0.0
            ),
            "graph_lookup_max_query_hits": float(
                graph_lookup.get("max_query_hits", 0.0) or 0.0
            ),
            "graph_lookup_max_symbol_hits": float(
                graph_lookup.get("max_symbol_hits", 0.0) or 0.0
            ),
            "graph_lookup_max_import_hits": float(
                graph_lookup.get("max_import_hits", 0.0) or 0.0
            ),
            "graph_lookup_max_query_coverage": float(
                graph_lookup.get("max_query_coverage", 0.0) or 0.0
            ),
            "embedding_enabled": bool(embeddings.get("enabled", False)),
            "embedding_reranked_count": int(embeddings.get("reranked_count", 0) or 0),
            "embedding_fallback": bool(embeddings.get("fallback", False)),
            "embedding_time_budget_exceeded": bool(
                embeddings.get("time_budget_exceeded", False)
            ),
            "embedding_similarity_mean": float(embeddings.get("similarity_mean", 0.0) or 0.0),
            "chunk_semantic_rerank_enabled": bool(chunk_semantic.get("enabled", False)),
            "chunk_semantic_rerank_reason": str(chunk_semantic.get("reason", "")),
            "chunk_semantic_rerank_reranked_count": chunk_semantic_reranked_count,
            "chunk_semantic_rerank_pool_effective": chunk_semantic_pool_effective,
            "chunk_semantic_rerank_ratio": float(round(chunk_semantic_ratio, 6)),
            "chunk_semantic_time_budget_ms": int(
                chunk_semantic.get("time_budget_ms", 0) or 0
            ),
            "chunk_semantic_time_budget_exceeded": bool(
                chunk_semantic.get("time_budget_exceeded", False)
            ),
            "chunk_semantic_fallback": bool(chunk_semantic.get("fallback", False)),
            "chunk_semantic_similarity_mean": float(
                chunk_semantic.get("similarity_mean", 0.0) or 0.0
            ),
            "chunk_semantic_similarity_max": float(
                chunk_semantic.get("similarity_max", 0.0) or 0.0
            ),
            "chunk_guard_enabled": bool(chunk_guard.get("enabled", False)),
            "chunk_guard_mode": str(chunk_guard.get("mode", "")),
            "chunk_guard_reason": str(chunk_guard.get("reason", "")),
            "chunk_guard_candidate_pool": int(
                chunk_guard.get("candidate_pool", 0) or 0
            ),
            "chunk_guard_signed_chunk_count": int(
                chunk_guard.get("signed_chunk_count", 0) or 0
            ),
            "chunk_guard_filtered_count": int(
                chunk_guard.get("filtered_count", 0) or 0
            ),
            "chunk_guard_retained_count": int(
                chunk_guard.get("retained_count", 0) or 0
            ),
            "chunk_guard_pairwise_conflict_count": int(
                chunk_guard.get("pairwise_conflict_count", 0) or 0
            ),
            "chunk_guard_max_conflict_penalty": float(
                chunk_guard.get("max_conflict_penalty", 0.0) or 0.0
            ),
            "chunk_guard_report_only": bool(chunk_guard.get("report_only", False)),
            "chunk_guard_fallback": bool(chunk_guard.get("fallback", False)),
            "language_count": len(output.get("languages_covered", []))
            if isinstance(output.get("languages_covered"), list)
            else 0,
            "candidate_ranker": str(
                ranking.get("selected", output.get("candidate_ranker", "heuristic"))
            ),
            "candidate_ranker_fallback": bool(ranking.get("fallbacks")),
            "multi_channel_rrf_enabled": bool(
                multi_channel_fusion.get("enabled", False)
            ),
            "multi_channel_rrf_applied": bool(
                multi_channel_fusion.get("applied", False)
            ),
            "multi_channel_rrf_granularity_count": multi_channel_granularity_count,
            "multi_channel_rrf_pool_size": multi_channel_rrf_pool_size,
            "multi_channel_rrf_granularity_pool_ratio": float(
                round(multi_channel_granularity_pool_ratio, 6)
            ),
            "parallel_enabled": bool(parallel.get("enabled", False)),
            "parallel_time_budget_ms": int(parallel.get("time_budget_ms", 0) or 0),
            "parallel_docs_timed_out": bool(parallel_docs.get("timed_out", False)),
            "parallel_worktree_timed_out": bool(
                parallel_worktree.get("timed_out", False)
            ),
            "router_enabled": bool(router.get("enabled", False)),
            "router_mode": str(router.get("mode", "")),
            "router_arm_set": str(router.get("arm_set", "")),
            "router_arm_id": str(router.get("arm_id", "")),
            "router_source": str(router.get("source", "")),
            "router_confidence": float(router.get("confidence", 0.0) or 0.0),
            "router_shadow_arm_id": str(router.get("shadow_arm_id", "")),
            "router_shadow_source": str(router.get("shadow_source", "")),
            "router_shadow_confidence": float(router.get("shadow_confidence", 0.0) or 0.0),
            "router_online_bandit_requested": bool(
                router_online_bandit.get("requested", False)
            ),
            "router_experiment_enabled": bool(
                router_online_bandit.get("experiment_enabled", False)
            ),
            "router_online_bandit_eligible": bool(
                router_online_bandit.get("eligible", False)
            ),
            "router_online_bandit_active": bool(
                router_online_bandit.get("active", False)
            ),
            "router_is_exploration": bool(
                router_online_bandit.get("is_exploration", False)
            ),
            "router_exploration_probability": float(
                router_online_bandit.get("exploration_probability", 0.0) or 0.0
            ),
            "router_fallback_applied": bool(
                router_online_bandit.get("fallback_applied", False)
            ),
            "router_fallback_reason": str(
                router_online_bandit.get("fallback_reason", "")
            ),
            "router_online_bandit_reason": str(
                router_online_bandit.get("reason", "")
            ),
            "policy_name": policy_name,
            "policy_version": policy_version,
        }

    if stage_name == "repomap":
        dependency = (
            output.get("dependency_recall", {})
            if isinstance(output.get("dependency_recall"), dict)
            else {}
        )
        tag_summary = (
            output.get("tag_summary", {})
            if isinstance(output.get("tag_summary"), dict)
            else {}
        )
        return {
            "enabled": bool(output.get("enabled", True)),
            "seed_count": int(output.get("seed_count", 0) or 0),
            "neighbor_count": int(output.get("neighbor_count", 0) or 0),
            "worktree_seed_count": int(output.get("worktree_seed_count", 0) or 0),
            "subgraph_seed_count": int(output.get("subgraph_seed_count", 0) or 0),
            "seed_candidates_count": int(output.get("seed_candidates_count", 0) or 0),
            "neighbor_limit": int(output.get("neighbor_limit", 0) or 0),
            "neighbor_depth": int(output.get("neighbor_depth", 1) or 1),
            "budget_tokens": int(output.get("budget_tokens", 0) or 0),
            "ranking_profile": str(
                output.get(
                    "ranking_profile_effective",
                    output.get("ranking_profile", "graph"),
                )
            ),
            "repomap_enabled_effective": bool(
                output.get("repomap_enabled_effective", output.get("enabled", True))
            ),
            "cache_hit": bool(
                (
                    output.get("cache", {}) if isinstance(output.get("cache"), dict) else {}
                ).get("hit", False)
            ),
            "cache_store_written": bool(
                (
                    output.get("cache", {}) if isinstance(output.get("cache"), dict) else {}
                ).get("store_written", False)
            ),
            "dependency_recall": float(dependency.get("hit_rate", 0.0) or 0.0),
            "tag_total": int(tag_summary.get("total_tags", 0) or 0),
            "policy_name": policy_name,
            "policy_version": policy_version,
        }

    if stage_name == "augment":
        xref = output.get("xref", {}) if isinstance(output.get("xref"), dict) else {}
        xref_errors = (
            xref.get("errors", []) if isinstance(xref.get("errors"), list) else []
        )
        vcs_history = (
            output.get("vcs_history", {})
            if isinstance(output.get("vcs_history"), dict)
            else {}
        )
        vcs_worktree = (
            output.get("vcs_worktree", {})
            if isinstance(output.get("vcs_worktree"), dict)
            else {}
        )
        tests = output.get("tests", {}) if isinstance(output.get("tests"), dict) else {}
        failures = tests.get("failures", []) if isinstance(tests.get("failures"), list) else []
        suspicious = (
            tests.get("suspicious_chunks", [])
            if isinstance(tests.get("suspicious_chunks"), list)
            else []
        )
        return {
            "enabled": bool(output.get("enabled", False)),
            "diagnostic_count": int(output.get("count", 0) or 0),
            "error_count": len(output.get("errors", []))
            if isinstance(output.get("errors"), list)
            else 0,
            "xref_count": int(xref.get("count", 0) or 0),
            "xref_error_count": len(xref_errors),
            "xref_budget_exhausted": bool(xref.get("budget_exhausted", False)),
            "test_failure_count": len(failures),
            "suspicious_chunk_count": len(suspicious),
            "sbfl_metric": str(tests.get("sbfl_metric", "")) if isinstance(tests, dict) else "",
            "vcs_history_enabled": bool(vcs_history.get("enabled", False)),
            "vcs_commit_count": int(vcs_history.get("commit_count", 0) or 0),
            "vcs_history_error": bool(str(vcs_history.get("error") or "").strip()),
            "vcs_worktree_enabled": bool(vcs_worktree.get("enabled", False)),
            "vcs_worktree_changed_count": int(vcs_worktree.get("changed_count", 0) or 0),
            "vcs_worktree_truncated": bool(vcs_worktree.get("truncated", False)),
            "vcs_worktree_error": bool(str(vcs_worktree.get("error") or "").strip()),
            "policy_name": policy_name,
            "policy_version": policy_version,
        }

    if stage_name == "skills":
        selected = output.get("selected", [])
        return {
            "selected_count": len(selected) if isinstance(selected, list) else 0,
            "available_count": int(output.get("available_count", 0) or 0),
            "token_budget": int(output.get("token_budget", 0) or 0),
            "token_budget_used": int(output.get("token_budget_used", 0) or 0),
            "budget_exhausted": bool(output.get("budget_exhausted", False)),
            "skipped_for_budget_count": len(output.get("skipped_for_budget", []))
            if isinstance(output.get("skipped_for_budget"), list)
            else 0,
            "policy_name": policy_name,
            "policy_version": policy_version,
        }

    if stage_name == "source_plan":
        diagnostics = output.get("diagnostics", [])
        constraints = output.get("constraints", [])
        chunks = output.get("candidate_chunks", [])
        chunk_steps = output.get("chunk_steps", [])
        packing = output.get("packing", {}) if isinstance(output.get("packing"), dict) else {}
        evidence_summary = (
            output.get("evidence_summary", {})
            if isinstance(output.get("evidence_summary"), dict)
            else {}
        )
        return {
            "diagnostic_count": len(diagnostics) if isinstance(diagnostics, list) else 0,
            "constraint_count": len(constraints) if isinstance(constraints, list) else 0,
            "step_count": len(output.get("steps", []))
            if isinstance(output.get("steps"), list)
            else 0,
            "candidate_chunk_count": len(chunks) if isinstance(chunks, list) else 0,
            "chunk_step_count": len(chunk_steps) if isinstance(chunk_steps, list) else 0,
            "validation_test_count": len(output.get("validation_tests", []))
            if isinstance(output.get("validation_tests"), list)
            else 0,
            "evidence_direct_count": int(
                evidence_summary.get("direct_count", 0.0) or 0.0
            ),
            "evidence_neighbor_context_count": int(
                evidence_summary.get("neighbor_context_count", 0.0) or 0.0
            ),
            "evidence_hint_only_count": int(
                evidence_summary.get("hint_only_count", 0.0) or 0.0
            ),
            "evidence_direct_ratio": float(
                evidence_summary.get("direct_ratio", 0.0) or 0.0
            ),
            "evidence_neighbor_context_ratio": float(
                evidence_summary.get("neighbor_context_ratio", 0.0) or 0.0
            ),
            "evidence_hint_only_ratio": float(
                evidence_summary.get("hint_only_ratio", 0.0) or 0.0
            ),
            "chunk_budget_used": float(output.get("chunk_budget_used", 0.0) or 0.0),
            "packing_graph_closure_preference_enabled": bool(
                packing.get("graph_closure_preference_enabled", False)
            ),
            "packing_graph_closure_bonus_candidate_count": int(
                packing.get("graph_closure_bonus_candidate_count", 0) or 0
            ),
            "packing_graph_closure_preferred_count": int(
                packing.get("graph_closure_preferred_count", 0) or 0
            ),
            "packing_granularity_preferred_count": int(
                packing.get("granularity_preferred_count", 0) or 0
            ),
            "packing_focused_file_promoted_count": int(
                packing.get("focused_file_promoted_count", 0) or 0
            ),
            "packing_packed_path_count": int(
                packing.get("packed_path_count", 0) or 0
            ),
            "packing_reason": str(packing.get("reason", "")),
            "policy_name": policy_name,
            "policy_version": policy_version,
        }

    if stage_name == "validation":
        sandbox = output.get("sandbox", {}) if isinstance(output.get("sandbox"), dict) else {}
        apply_result = (
            sandbox.get("apply_result", {})
            if isinstance(sandbox.get("apply_result"), dict)
            else {}
        )
        result = output.get("result", {}) if isinstance(output.get("result"), dict) else {}
        summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
        probes = (
            output.get("probes", {})
            if isinstance(output.get("probes"), dict)
            else (
                result.get("probes", {})
                if isinstance(result.get("probes"), dict)
                else {}
            )
        )
        xref = output.get("xref", {}) if isinstance(output.get("xref"), dict) else {}
        return {
            "enabled": bool(output.get("enabled", False)),
            "reason": str(output.get("reason", "")),
            "patch_artifact_present": bool(output.get("patch_artifact_present", False)),
            "patch_applied": bool(sandbox.get("patch_applied", False)),
            "cleanup_ok": bool(sandbox.get("cleanup_ok", False)),
            "sandbox_apply_reason": str(apply_result.get("reason", "")),
            "sandbox_apply_timed_out": bool(apply_result.get("timed_out", False)),
            "diagnostic_count": int(output.get("diagnostic_count", 0) or 0),
            "xref_enabled": bool(output.get("xref_enabled", False)),
            "xref_count": int(xref.get("count", 0) or 0),
            "validation_status": str(summary.get("status", "")),
            "validation_issue_count": int(summary.get("issue_count", 0) or 0),
            "validation_probe_enabled": bool(probes.get("enabled", False)),
            "validation_probe_available_count": len(probes.get("available", []))
            if isinstance(probes.get("available"), list)
            else 0,
            "validation_probe_count": len(probes.get("results", []))
            if isinstance(probes.get("results"), list)
            else 0,
            "validation_probe_selected_count": int(
                probes.get("selected_count", 0) or 0
            ),
            "validation_probe_executed_count": int(
                probes.get("executed_count", 0) or 0
            ),
            "validation_probe_issue_count": int(probes.get("issue_count", 0) or 0),
            "validation_probe_status": str(probes.get("status", "")),
            "policy_name": policy_name,
            "policy_version": policy_version,
        }

    return {}


__all__ = ["build_stage_tags"]
