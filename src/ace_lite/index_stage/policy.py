"""Deterministic retrieval policy routing for the pipeline."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ace_lite.pipeline.stages.skills import infer_intent

# Requirement ID patterns: EXPL-01, REQ-01, TASK-01, etc.
_REQ_ID_PATTERN = re.compile(r"\b([A-Z]{2,})-(\d+)\b", re.IGNORECASE)

_DEFAULT_SHADOW_ARM_BY_POLICY: dict[str, str] = {
    "bugfix_test": "bugfix_dense",
    "doc_intent": "doc_intent_hybrid",
    "feature": "feature_graph",
    "refactor": "refactor_graph",
}
_ONLINE_BANDIT_REQUIRED_STREAMS: tuple[tuple[str, str], ...] = (
    ("Y18", "shadow_mode_ready"),
    ("Y19", "observability_ready"),
    ("Y20", "promotion_gate_reviewed"),
    ("Y21", "reward_logging_ready"),
)


def _clamp_confidence(value: Any, *, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _load_shadow_router_model(model_path: str | Path) -> dict[str, Any] | None:
    path = Path(model_path)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _coerce_shadow_arm_entry(
    entry: Any,
    *,
    default_confidence: float,
) -> tuple[str, float] | None:
    if isinstance(entry, str):
        arm_id = entry.strip()
        if arm_id:
            return arm_id, default_confidence
        return None
    if not isinstance(entry, dict):
        return None
    arm_id = str(entry.get("arm_id", "")).strip()
    if not arm_id:
        return None
    confidence = _clamp_confidence(entry.get("confidence"), default=default_confidence)
    return arm_id, confidence


def _resolve_fallback_shadow_arm(
    *,
    executed_policy_name: str,
    candidate_ranker: str,
    embedding_enabled: bool,
) -> str:
    policy_name = str(executed_policy_name or "").strip().lower()
    if policy_name == "general":
        normalized_ranker = str(candidate_ranker or "").strip().lower()
        if not embedding_enabled or normalized_ranker in {"heuristic", "bm25", "bm25_lite"}:
            return "general_heuristic"
        if normalized_ranker == "hybrid_re2":
            return "general_hybrid"
        return "general_rrf"
    return _DEFAULT_SHADOW_ARM_BY_POLICY.get(policy_name, "")


def _text_contains_marker(text: str, marker: str) -> bool:
    normalized_text = str(text or "").lower()
    normalized_marker = str(marker or "").strip().lower()
    if not normalized_text or not normalized_marker:
        return False
    if any("\u4e00" <= char <= "\u9fff" for char in normalized_marker):
        return normalized_marker in normalized_text
    if any(char.isspace() for char in normalized_marker):
        return normalized_marker in normalized_text
    return bool(
        re.search(
            rf"(?<![a-z0-9_]){re.escape(normalized_marker)}(?![a-z0-9_])",
            normalized_text,
        )
    )


def resolve_shadow_router_arm(
    *,
    enabled: bool,
    mode: str,
    model_path: str | Path,
    arm_set: str,
    executed_policy_name: str,
    candidate_ranker: str,
    embedding_enabled: bool,
) -> dict[str, Any]:
    """Resolve a report-only shadow arm for adaptive-router comparisons."""

    if not enabled or str(mode or "").strip().lower() != "shadow":
        return {"arm_id": "", "confidence": 0.0, "source": "disabled"}

    model_payload = _load_shadow_router_model(model_path)
    if isinstance(model_payload, dict):
        configured_arm_set = str(arm_set or "").strip()
        model_arm_set = str(model_payload.get("arm_set", "")).strip()
        if model_arm_set and configured_arm_set and model_arm_set != configured_arm_set:
            model_payload = None

    if isinstance(model_payload, dict):
        default_confidence = _clamp_confidence(
            model_payload.get("default_confidence"),
            default=0.6,
        )
        policy_arms = model_payload.get("policy_arms", {})
        if isinstance(policy_arms, dict):
            shadow_entry = _coerce_shadow_arm_entry(
                policy_arms.get(str(executed_policy_name or "").strip()),
                default_confidence=default_confidence,
            )
            if shadow_entry is not None:
                arm_id, confidence = shadow_entry
                return {"arm_id": arm_id, "confidence": confidence, "source": "model"}

        default_entry = _coerce_shadow_arm_entry(
            model_payload.get("default"),
            default_confidence=default_confidence,
        )
        if default_entry is None and str(model_payload.get("default_arm_id", "")).strip():
            default_entry = (
                str(model_payload.get("default_arm_id", "")).strip(),
                default_confidence,
            )
        if default_entry is not None:
            arm_id, confidence = default_entry
            return {
                "arm_id": arm_id,
                "confidence": confidence,
                "source": "model_default",
            }

    arm_id = _resolve_fallback_shadow_arm(
        executed_policy_name=executed_policy_name,
        candidate_ranker=candidate_ranker,
        embedding_enabled=embedding_enabled,
    )
    return {
        "arm_id": arm_id,
        "confidence": 0.25 if arm_id else 0.0,
        "source": "fallback",
    }


def resolve_online_bandit_gate(
    *,
    enabled: bool,
    experiment_enabled: bool,
    state_path: str | Path,
) -> dict[str, Any]:
    """Resolve explicit online-bandit gating without activating runtime learning."""

    requested = bool(enabled)
    prerequisites = [
        {
            "task_id": task_id,
            "capability": capability,
            "ready": True,
        }
        for task_id, capability in _ONLINE_BANDIT_REQUIRED_STREAMS
    ]
    prerequisites_met = all(bool(item["ready"]) for item in prerequisites)
    experiment_requested = bool(experiment_enabled)
    experiment_active = bool(requested and experiment_requested and prerequisites_met)
    reason = "disabled"
    fallback_applied = False
    fallback_reason = ""
    if requested and not experiment_requested:
        reason = "experiment_mode_required"
        fallback_applied = True
        fallback_reason = "experiment_mode_disabled"
    elif requested:
        reason = "eligible_pending_runtime"
        fallback_applied = True
        fallback_reason = "heuristic_default"
    return {
        "requested": requested,
        "eligible": bool(requested and prerequisites_met),
        "experiment_enabled": experiment_requested,
        "active": False,
        "reason": reason,
        "is_exploration": False,
        "exploration_probability": 0.0,
        "fallback_applied": fallback_applied or experiment_active,
        "fallback_reason": fallback_reason,
        "executed_mode": "heuristic",
        "fallback_mode": "heuristic",
        "state_path": str(state_path).strip(),
        "required_task_ids": [task_id for task_id, _ in _ONLINE_BANDIT_REQUIRED_STREAMS],
        "prerequisites": prerequisites,
    }


def resolve_retrieval_policy(
    *,
    query: str,
    retrieval_policy: str,
    policy_version: str,
    cochange_enabled: bool,
    embedding_enabled: bool,
) -> dict[str, Any]:
    """Resolve retrieval policy profile for the given query."""

    profiles: dict[str, dict[str, float | bool | str]] = {
        "bugfix_test": {
            "cochange_enabled": False,
            "cochange_weight": 0.0,
            "cochange_expand_candidates": False,
            "embedding_enabled": False,
            "chunk_weight": 1.3,
            "docs_enabled": True,
            "docs_weight": 0.30,
            "docs_module_weight": 0.16,
            "docs_symbol_weight": 0.12,
            "worktree_weight": 1.25,
            "worktree_neighbor_weight": 0.70,
            "worktree_expand_candidates": True,
            "worktree_expand_limit": 8,
            "worktree_query_guard_enabled": False,
            "worktree_query_guard_min_overlap": 1,
            "tests_path_penalty": 0.0,
            "rankers_focus_boost": 0.0,
            "repomap_enabled": False,
            "repomap_budget_scale": 0.70,
            "repomap_neighbor_scale": 0.75,
            "repomap_cache_ttl_seconds": 1200,
            "repomap_precompute_ttl_seconds": 3600,
            "repomap_ranking_profile": "graph",
            "test_signal_weight": 1.6,
            "scip_weight": 0.8,
            "graph_lookup_enabled": False,
            "graph_lookup_scip_weight": 0.24,
            "graph_lookup_xref_weight": 0.16,
            "graph_lookup_query_weight": 0.16,
            "graph_lookup_symbol_weight": 0.08,
            "graph_lookup_import_weight": 0.05,
            "graph_lookup_coverage_weight": 0.06,
            "graph_lookup_log_norm": True,
            "graph_lookup_pool": 16,
            "index_parallel_enabled": False,
            "index_parallel_time_budget_ms": 0,
            "chunk_graph_prior_enabled": True,
            "chunk_graph_seed_limit": 6,
            "chunk_graph_neighbor_limit": 3,
            "chunk_graph_max_candidates": 160,
            "chunk_graph_edge_weight": 0.12,
            "chunk_graph_prior_cap": 0.24,
            "chunk_graph_seed_min_lexical": 1.2,
            "chunk_graph_seed_min_file_prior": 2.2,
            "chunk_graph_hub_soft_cap": 2,
            "chunk_graph_hub_penalty_weight": 0.05,
            "chunk_semantic_rerank_enabled": False,
            "chunk_semantic_rerank_pool_cap": 16,
            "chunk_semantic_rerank_time_budget_ms": 0,
            "semantic_rerank_time_budget_ms": 80,
        },
        "doc_intent": {
            "cochange_enabled": False,
            "cochange_weight": 0.0,
            "cochange_expand_candidates": False,
            "embedding_enabled": True,
            "chunk_weight": 1.05,
            "docs_enabled": True,
            "docs_expand_candidates": True,
            "docs_expand_limit": 3,
            "docs_injection_min_overlap": 1,
            "docs_weight": 1.35,
            "docs_module_weight": 0.75,
            "docs_symbol_weight": 0.60,
            "worktree_weight": 0.45,
            "worktree_neighbor_weight": 0.30,
            "worktree_expand_candidates": True,
            "worktree_expand_limit": 6,
            "worktree_query_guard_enabled": True,
            "worktree_query_guard_min_overlap": 1,
            "tests_path_penalty": 7.0,
            "rankers_focus_boost": 0.35,
            "repomap_enabled": True,
            "repomap_budget_scale": 0.75,
            "repomap_neighbor_scale": 0.80,
            "repomap_cache_ttl_seconds": 1800,
            "repomap_precompute_ttl_seconds": 5400,
            "repomap_ranking_profile": "graph_seeded",
            "test_signal_weight": 0.8,
            "scip_weight": 1.0,
            "graph_lookup_enabled": False,
            "graph_lookup_scip_weight": 0.20,
            "graph_lookup_xref_weight": 0.12,
            "graph_lookup_query_weight": 0.15,
            "graph_lookup_symbol_weight": 0.08,
            "graph_lookup_import_weight": 0.05,
            "graph_lookup_coverage_weight": 0.08,
            "graph_lookup_log_norm": True,
            "graph_lookup_pool": 24,
            "index_parallel_enabled": False,
            "index_parallel_time_budget_ms": 0,
            "chunk_graph_prior_enabled": True,
            "chunk_graph_seed_limit": 6,
            "chunk_graph_neighbor_limit": 3,
            "chunk_graph_max_candidates": 160,
            "chunk_graph_edge_weight": 0.10,
            "chunk_graph_prior_cap": 0.22,
            "chunk_graph_seed_min_lexical": 1.2,
            "chunk_graph_seed_min_file_prior": 2.2,
            "chunk_graph_hub_soft_cap": 2,
            "chunk_graph_hub_penalty_weight": 0.05,
            "chunk_semantic_rerank_enabled": True,
            "chunk_semantic_rerank_pool_cap": 12,
            "chunk_semantic_rerank_time_budget_ms": 40,
            "semantic_rerank_time_budget_ms": 120,
        },
        "feature": {
            "cochange_enabled": False,
            "cochange_weight": 1.2,
            "cochange_expand_candidates": False,
            "embedding_enabled": True,
            "chunk_weight": 1.1,
            "docs_enabled": True,
            "docs_weight": 0.55,
            "docs_module_weight": 0.30,
            "docs_symbol_weight": 0.24,
            "worktree_weight": 1.10,
            "worktree_neighbor_weight": 0.62,
            "worktree_expand_candidates": True,
            "worktree_expand_limit": 10,
            "worktree_query_guard_enabled": False,
            "worktree_query_guard_min_overlap": 1,
            "repomap_enabled": True,
            "repomap_budget_scale": 1.05,
            "repomap_neighbor_scale": 1.05,
            "repomap_cache_ttl_seconds": 1800,
            "repomap_precompute_ttl_seconds": 5400,
            "repomap_ranking_profile": "graph_seeded",
            "test_signal_weight": 0.8,
            "scip_weight": 1.0,
            "graph_lookup_enabled": True,
            "graph_lookup_scip_weight": 0.16,
            "graph_lookup_xref_weight": 0.10,
            "graph_lookup_query_weight": 0.10,
            "graph_lookup_symbol_weight": 0.08,
            "graph_lookup_import_weight": 0.06,
            "graph_lookup_coverage_weight": 0.08,
            "graph_lookup_log_norm": True,
            "graph_lookup_pool": 16,
            "graph_lookup_max_candidates": 56,
            "graph_lookup_min_query_terms": 1,
            "graph_lookup_max_query_terms": 12,
            "index_parallel_enabled": False,
            "index_parallel_time_budget_ms": 0,
            "chunk_graph_prior_enabled": True,
            "chunk_graph_seed_limit": 8,
            "chunk_graph_neighbor_limit": 4,
            "chunk_graph_max_candidates": 192,
            "chunk_graph_edge_weight": 0.16,
            "chunk_graph_prior_cap": 0.34,
            "chunk_graph_seed_min_lexical": 1.0,
            "chunk_graph_seed_min_file_prior": 2.0,
            "chunk_graph_hub_soft_cap": 3,
            "chunk_graph_hub_penalty_weight": 0.04,
            "chunk_semantic_rerank_enabled": False,
            "chunk_semantic_rerank_pool_cap": 16,
            "chunk_semantic_rerank_time_budget_ms": 0,
            "semantic_rerank_time_budget_ms": 110,
        },
        "refactor": {
            "cochange_enabled": False,
            "cochange_weight": 1.0,
            "cochange_expand_candidates": False,
            "embedding_enabled": True,
            "chunk_weight": 1.15,
            "docs_enabled": True,
            "docs_weight": 0.45,
            "docs_module_weight": 0.25,
            "docs_symbol_weight": 0.18,
            "worktree_weight": 0.95,
            "worktree_neighbor_weight": 0.50,
            "worktree_expand_candidates": True,
            "worktree_expand_limit": 8,
            "worktree_query_guard_enabled": False,
            "worktree_query_guard_min_overlap": 1,
            "repomap_enabled": True,
            "repomap_budget_scale": 1.00,
            "repomap_neighbor_scale": 1.0,
            "repomap_cache_ttl_seconds": 1800,
            "repomap_precompute_ttl_seconds": 5400,
            "repomap_ranking_profile": "graph_seeded",
            "test_signal_weight": 0.9,
            "scip_weight": 1.35,
            "graph_lookup_enabled": True,
            "graph_lookup_scip_weight": 0.26,
            "graph_lookup_xref_weight": 0.12,
            "graph_lookup_query_weight": 0.10,
            "graph_lookup_symbol_weight": 0.10,
            "graph_lookup_import_weight": 0.07,
            "graph_lookup_coverage_weight": 0.08,
            "graph_lookup_log_norm": True,
            "graph_lookup_pool": 20,
            "index_parallel_enabled": False,
            "index_parallel_time_budget_ms": 0,
            "chunk_graph_prior_enabled": True,
            "chunk_graph_seed_limit": 8,
            "chunk_graph_neighbor_limit": 4,
            "chunk_graph_max_candidates": 192,
            "chunk_graph_edge_weight": 0.18,
            "chunk_graph_prior_cap": 0.40,
            "chunk_graph_seed_min_lexical": 1.0,
            "chunk_graph_seed_min_file_prior": 2.0,
            "chunk_graph_hub_soft_cap": 3,
            "chunk_graph_hub_penalty_weight": 0.04,
            "chunk_semantic_rerank_enabled": False,
            "chunk_semantic_rerank_pool_cap": 16,
            "chunk_semantic_rerank_time_budget_ms": 0,
            "semantic_rerank_time_budget_ms": 100,
        },
        "general": {
            "cochange_enabled": False,
            "cochange_weight": 0.0,
            "cochange_expand_candidates": False,
            "embedding_enabled": True,
            "chunk_weight": 1.0,
            "docs_enabled": False,
            "docs_weight": 0.0,
            "docs_module_weight": 0.0,
            "docs_symbol_weight": 0.0,
            "worktree_weight": 0.85,
            "worktree_neighbor_weight": 0.45,
            "worktree_expand_candidates": True,
            "worktree_expand_limit": 8,
            "worktree_query_guard_enabled": True,
            "worktree_query_guard_min_overlap": 1,
            "tests_path_penalty": 6.0,
            "rankers_focus_boost": 0.35,
            "repomap_enabled": True,
            "repomap_budget_scale": 0.85,
            "repomap_neighbor_scale": 0.85,
            "repomap_cache_ttl_seconds": 1500,
            "repomap_precompute_ttl_seconds": 4800,
            "repomap_ranking_profile": "graph_seeded",
            "test_signal_weight": 1.0,
            "scip_weight": 1.0,
            "graph_lookup_enabled": True,
            "graph_lookup_scip_weight": 0.12,
            "graph_lookup_xref_weight": 0.08,
            "graph_lookup_query_weight": 0.08,
            "graph_lookup_symbol_weight": 0.06,
            "graph_lookup_import_weight": 0.05,
            "graph_lookup_coverage_weight": 0.06,
            "graph_lookup_log_norm": True,
            "graph_lookup_pool": 14,
            "graph_lookup_max_candidates": 48,
            "graph_lookup_min_query_terms": 1,
            "graph_lookup_max_query_terms": 10,
            "index_parallel_enabled": False,
            "index_parallel_time_budget_ms": 0,
            "chunk_graph_prior_enabled": True,
            "chunk_graph_seed_limit": 8,
            "chunk_graph_neighbor_limit": 4,
            "chunk_graph_max_candidates": 192,
            "chunk_graph_edge_weight": 0.14,
            "chunk_graph_prior_cap": 0.30,
            "chunk_graph_seed_min_lexical": 1.0,
            "chunk_graph_seed_min_file_prior": 2.0,
            "chunk_graph_hub_soft_cap": 3,
            "chunk_graph_hub_penalty_weight": 0.04,
            "chunk_semantic_rerank_enabled": False,
            "chunk_semantic_rerank_pool_cap": 16,
            "chunk_semantic_rerank_time_budget_ms": 0,
            "semantic_rerank_time_budget_ms": 90,
        },
    }

    configured = str(retrieval_policy or "auto").strip().lower()
    source = "configured" if configured in profiles else "auto"
    if configured in profiles:
        selected = configured
    else:
        lowered = str(query or "").lower()
        inferred_intent = infer_intent(query)
        is_definition_lookup = any(
            token in lowered for token in ("where", "defined", "implemented", "located")
        ) and any(
            token in lowered
            for token in (
                "class",
                "function",
                "method",
                "symbol",
                "interface",
                "exception",
                "module",
                "variable",
                "constant",
            )
        )
        is_definition_lookup = is_definition_lookup or (
            any(
                token in lowered
                for token in (
                    "在哪",
                    "在哪里",
                    "位置",
                    "位于",
                    "哪个文件",
                    "哪一个文件",
                    "源码",
                    "源代码",
                    "定义",
                    "实现",
                )
            )
            and any(
                token in lowered
                for token in (
                    "类",
                    "函数",
                    "方法",
                    "接口",
                    "异常",
                    "符号",
                    "模块",
                    "变量",
                    "常量",
                )
            )
        )
        has_bugfix_markers = any(
            _text_contains_marker(lowered, token)
            for token in (
                "test",
                "pytest",
                "junit",
                "assert",
                "failure",
                "failing",
                "error",
                "stacktrace",
                "traceback",
                "fix",
                "bug",
                "报错",
                "错误",
                "异常",
                "失败",
                "崩溃",
                "修复",
                "排查",
                "超时",
            )
        )
        doc_markers = any(
            _text_contains_marker(lowered, token)
            for token in (
                "how ",
                "why ",
                "architecture",
                "design",
                "mechanism",
                "workflow",
                "principle",
                "overview",
                "explain",
                "架构",
                "设计",
                "机制",
                "流程",
                "原理",
                "概览",
                "解释",
                "为什么",
                "为何",
                "为啥",
                "如何",
                "怎么",
                "怎样",
                "docs",
                "doc ",
                "markdown",
                "readme",
                "planning",
                "progress",
                "status",
                "report",
                "roadmap",
                "runbook",
                "latest",
                "sync",
                "update",
                "requirements",
                "milestone",
                "phase",
                "state",
                "explainability",
                "contract",
                "文档",
                "说明",
                "同步",
                "更新",
                "最新",
                "状态",
                "进展",
                "报告",
                "路线图",
                "需求",
                "里程碑",
                "阶段",
                "可解释性",
                "合同",
                "契约",
            )
        )
        where_lookup = lowered.strip().startswith("where ")
        where_lookup = where_lookup or lowered.strip().startswith(("在哪", "在哪里"))
        # Check for requirement ID patterns (e.g., EXPL-01, REQ-01)
        has_req_id = bool(_REQ_ID_PATTERN.search(query))
        if (doc_markers or has_req_id) and not is_definition_lookup and not has_bugfix_markers:
            selected = "doc_intent"
        elif (is_definition_lookup or where_lookup) and not has_bugfix_markers:
            selected = "general"
        elif has_bugfix_markers or (
            inferred_intent == "troubleshoot" and not is_definition_lookup
        ):
            selected = "bugfix_test"
        elif any(
            token in lowered
            for token in (
                "refactor",
                "rename",
                "cleanup",
                "restructure",
                "重构",
                "改名",
                "重命名",
                "清理",
                "整理",
                "重组",
            )
        ):
            selected = "refactor"
        elif any(
            token in lowered
            for token in (
                "add",
                "implement",
                "feature",
                "build",
                "create",
                "新增",
                "增加",
                "添加",
                "实现",
                "功能",
                "构建",
                "创建",
            )
        ):
            selected = "feature"
        else:
            selected = "general"

    payload: dict[str, Any] = dict(profiles.get(selected, profiles["general"]))
    if selected in {"feature", "refactor"} and cochange_enabled:
        payload["cochange_enabled"] = True
    payload["embedding_enabled"] = bool(payload.get("embedding_enabled", True)) and bool(
        embedding_enabled
    )
    payload.setdefault("chunk_graph_closure_enabled", False)
    payload.setdefault(
        "chunk_graph_closure_seed_limit",
        int(payload.get("chunk_graph_seed_limit", 8) or 8),
    )
    payload.setdefault(
        "chunk_graph_closure_neighbor_limit",
        int(payload.get("chunk_graph_neighbor_limit", 4) or 4),
    )
    payload.setdefault(
        "chunk_graph_closure_max_candidates",
        int(payload.get("chunk_graph_max_candidates", 192) or 192),
    )
    payload.setdefault("chunk_graph_closure_bonus_weight", 0.0)
    payload.setdefault("chunk_graph_closure_bonus_cap", 0.0)
    payload.setdefault(
        "chunk_graph_closure_seed_min_lexical",
        float(payload.get("chunk_graph_seed_min_lexical", 1.0) or 1.0),
    )
    payload.setdefault(
        "chunk_graph_closure_seed_min_file_prior",
        float(payload.get("chunk_graph_seed_min_file_prior", 2.0) or 2.0),
    )
    payload.setdefault("source_plan_graph_closure_pack_enabled", True)
    payload["name"] = selected
    payload["version"] = policy_version
    payload["source"] = source

    normalized_version = str(policy_version or "").strip().lower()
    if normalized_version.startswith("v2"):
        payload["index_parallel_enabled"] = True
        if int(payload.get("index_parallel_time_budget_ms", 0) or 0) <= 0:
            payload["index_parallel_time_budget_ms"] = 250
    return payload


__all__ = [
    "resolve_online_bandit_gate",
    "resolve_retrieval_policy",
    "resolve_shadow_router_arm",
]
