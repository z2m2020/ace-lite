from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.index_stage.policy import resolve_retrieval_policy
from ace_lite.parsers.languages import parse_language_csv
from ace_lite.plan_quick_ranking import (
    build_candidate_details,
    build_history_summary,
    build_mixed_top_k_candidates,
    build_onboarding_view,
    build_upgrade_guidance,
)
from ace_lite.plan_quick_strategies import (
    BoostStrategyRegistry,
    DomainStrategyRegistry,
    IntentStrategyRegistry,
    NormalizationUtils,
    QueryFlags,
)
from ace_lite.repomap.builder import build_repo_map, build_stage_repo_map
from ace_lite.retrieval_shared import (
    CandidateSelectionResult,
    build_retrieval_runtime_profile,
    build_selection_observability,
    extract_retrieval_terms,
    load_retrieval_index_snapshot,
    select_initial_candidates,
)

PLAN_QUICK_STEPS: tuple[str, ...] = (
    "Inspect candidate_files in order.",
    "Open highest-fused files and confirm symbol-level relevance.",
    "Escalate to ace_plan only after narrowing to concrete edit targets.",
)
_ONBOARDING_MARKERS: tuple[str, ...] = (
    "onboarding",
    "familiarize",
    "familiarise",
    "familiarization",
    "familiarisation",
    "understand",
    "overview",
    "read first",
    "where to start",
    "entrypoint",
    "codebase",
    "repo map",
    "project structure",
    "熟悉",
    "先读",
    "先看",
    "入口",
    "上手",
    "导览",
    "代码地图",
    "架构概览",
)

_DOC_SYNC_MARKERS: tuple[str, ...] = (
    "doc",
    "docs",
    "markdown",
    "readme",
    "planning",
    "plan",
    "progress",
    "status",
    "report",
    "roadmap",
    "runbook",
    "sync",
    "update",
    "latest",
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
    "状态",
    "可解释性",
    "合同",
    "契约",
)
_LATEST_MARKERS: tuple[str, ...] = (
    "latest",
    "recent",
    "sync",
    "update",
    "current",
    "最近",
    "最新",
    "同步",
    "更新",
    "当前",
)
_DOC_PREFERRED_PREFIXES: tuple[str, ...] = (
    "docs/",
    "doc/",
    "planning/",
    ".planning/",
    "plans/",
    ".plans/",
    "repos/",
    "reports/",
    "milestones/",
    "phases/",
    "state/",
)
_DOC_PRIMARY_NAME_MARKERS: tuple[str, ...] = (
    "progress",
    "status",
    "runbook",
    "sync",
    "update",
    "latest",
    "current",
)
_DOC_SECONDARY_NAME_MARKERS: tuple[str, ...] = (
    "readme",
    "report",
    "roadmap",
    "overview",
    "summary",
    "changelog",
)
_DOC_PENALIZED_PREFIXES: tuple[tuple[str, float], ...] = (
    ("tests/", -3.5),
    ("test/", -3.5),
    ("research/", -6.0),
    ("reference/", -6.0),
    ("src/", -2.0),
    ("internal/", -2.0),
    ("pkg/", -2.0),
)
_DOC_SECONDARY_NAME_PENALTIES: tuple[tuple[str, float], ...] = (
    ("weekly", -2.5),
    ("matrix", -1.0),
)
_DOC_ENTRYPOINT_BASENAMES: tuple[str, ...] = (
    "readme",
    "index",
    "overview",
)
_MARKDOWN_LANGUAGES: frozenset[str] = frozenset({"markdown", "md"})
_LATEST_DOC_DOMAINS: frozenset[str] = frozenset(
    {"docs", "planning", "repos", "reports", "reference", "markdown"}
)
_QUERY_REFINEMENT_STOPWORDS: frozenset[str] = frozenset(
    {
        "doc",
        "docs",
        "markdown",
        "readme",
        "planning",
        "plan",
        "progress",
        "status",
        "report",
        "roadmap",
        "runbook",
        "sync",
        "update",
        "latest",
        "recent",
        "current",
        "repo",
        "repos",
        "reports",
        "code",
        "fix",
        "debug",
        "quick",
        "ace",
        "ace_plan_quick",
    }
)
_PATH_DATE_PATTERN = re.compile(r"(?<!\d)((?:19|20)\d{2})-(\d{2})-(\d{2})(?!\d)")
# Requirement ID patterns: EXPL-01, REQ-01, TASK-01, etc.
_REQ_ID_PATTERN = re.compile(r"\b([A-Z]{2,})-(\d+)\b", re.IGNORECASE)


def _extract_req_ids(query: str) -> list[str]:
    """Extract requirement IDs like EXPL-01, REQ-01 from query."""
    normalized = str(query or "").strip()
    matches = _REQ_ID_PATTERN.findall(normalized)
    return [f"{str(prefix).upper()}-{num}" for prefix, num in matches]


def _query_flags(query: str) -> dict[str, Any]:
    flags = IntentStrategyRegistry.get_instance().detect_intent(query)
    return {
        "doc_sync": flags.doc_sync,
        "code_intent": flags.code_intent,
        "latest_sensitive": flags.latest_sensitive,
        "onboarding": flags.onboarding,
        "has_req_id": flags.has_req_id,
        "req_ids": list(flags.req_ids),
    }


def _classify_path_domain(path: str) -> str:
    return str(DomainStrategyRegistry.classify(path))


def _is_markdown_doc(*, path: str, language: str) -> bool:
    return bool(
        NormalizationUtils.is_markdown_language(language)
        or NormalizationUtils.is_markdown_path(path)
    )


def _extract_path_date(path: str) -> date | None:
    normalized_path = str(path or "").strip().replace("\\", "/")
    matched = _PATH_DATE_PATTERN.search(normalized_path)
    if not matched:
        return None
    try:
        return datetime.strptime(matched.group(0), "%Y-%m-%d").date()
    except ValueError:
        return None


def _path_stem(path: str) -> str:
    return str(NormalizationUtils.extract_path_stem(path))


def _is_doc_entrypoint_path(*, path: str, semantic_domain: str) -> bool:
    if semantic_domain not in {"docs", "planning", "repos", "reference", "markdown"}:
        return False
    stem = _path_stem(path)
    return stem in _DOC_ENTRYPOINT_BASENAMES


def _find_newest_dated_doc(rows: list[dict[str, Any]]) -> date | None:
    newest: date | None = None
    for item in rows:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "")
        language = str(item.get("language", "") or "")
        domain = _classify_path_domain(path)
        if domain not in _LATEST_DOC_DOMAINS:
            continue
        if not _is_markdown_doc(path=path, language=language):
            continue
        path_date = _extract_path_date(path)
        if path_date is None:
            continue
        if newest is None or path_date > newest:
            newest = path_date
    return newest


def _query_flags_as_registry_flags(query_flags: dict[str, Any]) -> QueryFlags:
    req_ids_raw = query_flags.get("req_ids", [])
    if isinstance(req_ids_raw, tuple | list):
        req_ids = tuple(str(item) for item in req_ids_raw if str(item).strip())
    else:
        req_ids = ()
    return QueryFlags(
        doc_sync=bool(query_flags.get("doc_sync", False)),
        code_intent=bool(query_flags.get("code_intent", False)),
        latest_sensitive=bool(query_flags.get("latest_sensitive", False)),
        onboarding=bool(query_flags.get("onboarding", False)),
        has_req_id=bool(query_flags.get("has_req_id", False)),
        req_ids=req_ids,
    )


def _doc_sync_intent_boost(*, path: str, language: str, query_flags: dict[str, Any]) -> float:
    flags = _query_flags_as_registry_flags(query_flags)
    return float(
        BoostStrategyRegistry.get_instance().calculate_doc_sync_boost(
            path=path,
            language=language,
            flags=flags,
            context={},
        )
    )


def _latest_doc_intent_boost(
    *,
    path: str,
    language: str,
    query_flags: dict[str, Any],
    newest_dated_doc: date | None,
) -> float:
    flags = _query_flags_as_registry_flags(query_flags)
    return float(
        BoostStrategyRegistry.get_instance().calculate_latest_doc_boost(
            path=path,
            language=language,
            flags=flags,
            context={"newest_dated_doc": newest_dated_doc},
        )
    )


def _build_plan_quick_risk_hints(
    *,
    query: str,
    rows: list[PlanQuickScoredRow],
    retrieval_policy_profile: str,
    index_cache: dict[str, Any],
) -> list[dict[str, Any]]:
    query_flags = _query_flags(query)
    hints: list[dict[str, Any]] = []
    top_rows = rows[:5]
    visible_rows = rows[:8]
    if bool(query_flags.get("doc_sync", False)) and not bool(query_flags.get("code_intent", False)):
        top_domains = {
            _classify_path_domain(item.path) for item in top_rows if str(item.path or "").strip()
        }
        if retrieval_policy_profile != "doc_intent":
            hints.append(
                {
                    "code": "doc_sync_policy_mismatch",
                    "severity": "medium",
                    "message": "query 更像文档同步任务, 但当前 retrieval policy 未落到 doc_intent。",
                    "action": "追加 docs/planning/progress/status 关键词, 或限制到 docs/ 目录。",
                    "next_step": "修改 query: 添加 'docs planning' 前缀",
                }
            )
        if len(top_domains) >= 3 and any(
            domain in top_domains for domain in ("code", "research", "tests")
        ):
            hints.append(
                {
                    "code": "cross_domain_mix",
                    "severity": "high",
                    "message": "前排候选混入多个语义域, 结果可能需要人工纠偏。",
                    "action": "优先阅读前 3 个 markdown/docs/planning 候选, 再决定是否升级到 ace_plan。",
                    "next_step": "查看前3个候选文件, 如不稳则运行 ace_plan",
                }
            )
        if any(item.semantic_domain in {"reports", "research"} for item in visible_rows):
            hints.append(
                {
                    "code": "secondary_doc_mix",
                    "severity": "medium",
                    "message": "前排候选仍混入周报或研究类文档, 当前状态入口可能还没有完全收敛。",
                    "action": "优先查看 planning/progress/status/sync 文档; 如仍不稳, 在 query 中追加 planning progress status current latest。",
                    "next_step": "追加关键词: planning progress status",
                }
            )
        if top_rows and not any(
            str(item.language or "").lower() in _MARKDOWN_LANGUAGES
            or str(item.path or "").lower().endswith((".md", ".mdx"))
            for item in top_rows[:3]
        ):
            hints.append(
                {
                    "code": "markdown_underweighted",
                    "severity": "medium",
                    "message": "文档同步 query 的前排结果缺少 markdown 入口文档。",
                    "action": "建议把 query 收紧到 docs planning repo progress status latest, 或直接指定 markdown 目录。",
                    "next_step": "添加关键词: docs planning latest",
                }
            )
    if str(index_cache.get("mode") or "").strip() == "full_build":
        full_build_reason = str(
            index_cache.get("full_build_reason") or index_cache.get("reason") or "cache_missing"
        )
        # ASF-8921: Improved cold-start messaging
        if full_build_reason == "cache_missing":
            message = "首次使用: 正在建立索引, 后续查询将更快。"
            action = "这是首次运行, 索引建立后下次查询将使用缓存。如需预热可运行: ace-lite index"
        elif full_build_reason == "index_stale":
            message = "索引已过期: 正在增量更新, 请稍候。"
            action = "索引正在更新, 完成后将恢复 cache_only 模式。"
        else:
            message = "本次 quick plan 触发了 full build, 首轮耗时会偏高。"
            action = "若仓库无本地改动, 后续再次运行通常会转为 cache_only; 也可先执行 ace-lite index 预热索引。"

        hints.append(
            {
                "code": "index_cold_start",
                "severity": "low",
                "message": message,
                "action": action,
                "reason": full_build_reason,
                "is_first_time": full_build_reason == "cache_missing",
            }
        )
    return hints


def build_plan_quick_policy_observability(
    *,
    query: str,
) -> tuple[str, dict[str, Any]]:
    policy = resolve_retrieval_policy(
        query=str(query or "").strip(),
        retrieval_policy="auto",
        policy_version="v1",
        cochange_enabled=True,
        embedding_enabled=True,
    )
    policy_name = str(policy.get("name", "general") or "general")
    return policy_name, {
        "requested": "auto",
        "selected": policy_name,
        "source": str(policy.get("source", "") or ""),
        "version": str(policy.get("version", "") or ""),
        "embedding_enabled": bool(policy.get("embedding_enabled", False)),
        "docs_enabled": bool(policy.get("docs_enabled", False)),
        "repomap_enabled": bool(policy.get("repomap_enabled", False)),
        "graph_lookup_enabled": bool(policy.get("graph_lookup_enabled", False)),
        "chunk_semantic_rerank_enabled": bool(policy.get("chunk_semantic_rerank_enabled", False)),
        "semantic_rerank_time_budget_ms": int(policy.get("semantic_rerank_time_budget_ms", 0) or 0),
    }


def _build_candidate_domain_summary(
    rows: list[PlanQuickScoredRow],
) -> dict[str, Any]:
    domain_counts = Counter(row.semantic_domain for row in rows if str(row.path or "").strip())
    ranked_domains = sorted(domain_counts.items(), key=lambda item: (-item[1], item[0]))
    markdown_count = sum(
        1 for row in rows if _is_markdown_doc(path=row.path, language=row.language)
    )
    latest_doc_candidates = [
        {
            "path": row.path,
            "date": path_date.isoformat(),
            "semantic_domain": row.semantic_domain,
        }
        for row in rows
        for path_date in [_extract_path_date(row.path)]
        if path_date is not None
    ]
    latest_doc_candidates.sort(
        key=lambda item: (str(item["date"]), str(item["path"])), reverse=True
    )
    domains = [{"domain": domain, "count": int(count)} for domain, count in ranked_domains]
    dominant_domain = domains[0]["domain"] if domains else None
    return {
        "top_k_considered": len(rows),
        "unique_domains": len(domains),
        "dominant_domain": dominant_domain,
        "primary_domain": dominant_domain,
        "mixed_domains": bool(len(domains) > 1),
        "cross_domain_mix": bool(len(domains) > 1),
        "top_domains": [item["domain"] for item in domains[:3]],
        "domain_counts": {domain: int(count) for domain, count in ranked_domains},
        "markdown_ratio": (float(markdown_count) / float(len(rows)) if rows else 0.0),
        "latest_doc_candidates": latest_doc_candidates[:3],
        "domains": domains,
    }


def _dedupe_tokens(tokens: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for token in tokens:
        normalized = str(token or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _build_refinement_query(
    *,
    fixed_tokens: list[str],
    topic_tokens: list[str],
) -> str:
    return " ".join(_dedupe_tokens([*fixed_tokens, *topic_tokens])).strip()


def _append_query_refinement(
    refinements: list[dict[str, Any]],
    *,
    code: str,
    query: str,
    reason: str,
    raw_tokens: list[str],
    strategy: str,
    target_domains: list[str],
) -> None:
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return
    if any(item.get("query") == normalized_query for item in refinements):
        return
    query_tokens = [token for token in normalized_query.lower().split() if token]
    added_terms = [token for token in query_tokens if token not in set(_dedupe_tokens(raw_tokens))]
    refinements.append(
        {
            "code": str(code or "").strip(),
            "query": normalized_query,
            "reason": str(reason or "").strip(),
            "reason_code": str(code or "").strip(),
            "strategy": str(strategy or "").strip(),
            "added_terms": added_terms,
            "target_domains": [domain for domain in target_domains if domain],
        }
    )


def _build_suggested_query_refinements(
    *,
    query: str,
    rows: list[PlanQuickScoredRow],
) -> list[dict[str, Any]]:
    query_flags = _query_flags(query)
    if bool(query_flags.get("code_intent", False)):
        return []
    # Also enable refinements for requirement ID queries
    is_req_query = bool(query_flags.get("has_req_id", False)) or any(
        marker in str(query or "").lower()
        for marker in ("requirements", "milestone", "phase", "contract", "explainability")
    )
    if not (
        bool(query_flags.get("doc_sync", False))
        or bool(query_flags.get("latest_sensitive", False))
        or is_req_query
    ):
        return []
    raw_tokens = [token for token in str(query or "").strip().lower().split() if token]
    topic_tokens = [token for token in raw_tokens if token not in _QUERY_REFINEMENT_STOPWORDS]
    domain_summary = _build_candidate_domain_summary(rows)
    ranked_domains = [
        str(item.get("domain", "") or "")
        for item in domain_summary.get("domains", [])
        if isinstance(item, dict)
    ]
    refinements: list[dict[str, Any]] = []

    primary_tokens = ["docs", "planning", "progress", "status"]
    if bool(query_flags.get("latest_sensitive", False)):
        primary_tokens.append("latest")
    _append_query_refinement(
        refinements,
        code="docs_status_focus",
        query=_build_refinement_query(
            fixed_tokens=primary_tokens,
            topic_tokens=topic_tokens,
        ),
        reason="Narrow the query toward status boards, planning docs, and current progress entrypoints.",
        raw_tokens=raw_tokens,
        strategy="add_doc_scope_terms",
        target_domains=["docs", "planning"],
    )

    if bool(domain_summary.get("mixed_domains", False)):
        mixed_tokens = ["markdown", "docs", "planning"]
        if bool(query_flags.get("latest_sensitive", False)):
            mixed_tokens.append("latest")
        _append_query_refinement(
            refinements,
            code="markdown_focus",
            query=_build_refinement_query(
                fixed_tokens=mixed_tokens,
                topic_tokens=topic_tokens,
            ),
            reason="Current candidates mix multiple domains, so prefer markdown entrypoints first.",
            raw_tokens=raw_tokens,
            strategy="prefer_markdown_entrypoints",
            target_domains=["docs", "planning", "markdown"],
        )

    if any(domain in {"repos", "reports", "planning"} for domain in ranked_domains[:3]):
        repo_tokens = ["repos", "reports", "progress", "status"]
        if bool(query_flags.get("latest_sensitive", False)):
            repo_tokens.append("latest")
        _append_query_refinement(
            refinements,
            code="repo_progress_focus",
            query=_build_refinement_query(
                fixed_tokens=repo_tokens,
                topic_tokens=topic_tokens,
            ),
            reason="Bias the query toward repo-sync progress reports and adjacent status documents.",
            raw_tokens=raw_tokens,
            strategy="bias_repo_progress_docs",
            target_domains=["repos", "reports", "planning"],
        )

    # Add domain-mixed strategy for design/doc intent with requirement IDs
    # This is inserted at the beginning for high priority
    if bool(query_flags.get("has_req_id", False)) or any(
        marker in str(query or "").lower()
        for marker in ("requirements", "milestone", "phase", "contract", "explainability")
    ):
        # Build domain_mixed refinement manually and insert at beginning
        domain_mixed_query = _build_refinement_query(
            fixed_tokens=["docs", "planning", "requirements"],
            topic_tokens=topic_tokens,
        )
        if domain_mixed_query:
            domain_mixed_refinement: dict[str, Any] = {
                "code": "domain_mixed",
                "query": domain_mixed_query,
                "reason": "Design/requirements clarification tasks benefit from mixed docs+code first screen.",
                "reason_code": "domain_mixed",
                "strategy": "domain_mixed_top_k",
                "added_terms": ["docs", "planning", "requirements"],
                "target_domains": ["docs", "planning", "code"],
            }
            refinements.insert(0, domain_mixed_refinement)

    return refinements[:3]


@dataclass(frozen=True, slots=True)
class PlanQuickScoredRow:
    path: str
    module: str
    language: str
    score: float
    lexical_hits: int
    lexical_boost: float
    intent_boost: float
    recency_boost: float
    semantic_domain: str
    fused_score: float
    labels: tuple[str, ...] = field(default_factory=tuple)
    role: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "module": self.module,
            "language": self.language,
            "score": float(self.score),
            "lexical_hits": int(self.lexical_hits),
            "lexical_boost": float(self.lexical_boost),
            "intent_boost": float(self.intent_boost),
            "recency_boost": float(self.recency_boost),
            "semantic_domain": self.semantic_domain,
            "fused_score": float(self.fused_score),
            "labels": list(self.labels),
            "role": self.role,
        }


def _normalize_path(path: str) -> str:
    return str(path or "").strip().replace("\\", "/").lower()


_TOOL_ARTIFACT_PREFIXES: tuple[str, ...] = (
    ".tmp/",
    ".context/",
    ".codex/tasks/",
)
_TOOL_ARTIFACT_NAME_MARKERS: tuple[str, ...] = (
    "ace-lite",
    "ace_lite",
    "context_report",
    "developer_feedback",
    "repo_validation",
    "borrowing_analysis",
)
_TOOL_ARTIFACT_PURPOSE_MARKERS: tuple[str, ...] = (
    "feedback",
    "assessment",
    "validation",
    "report",
    "plan",
    "task",
)
_TOOL_ARTIFACT_QUERY_ALLOWLIST: tuple[str, ...] = (
    "docs",
    "doc",
    "markdown",
    "report",
    "plan",
    "planning",
    "status",
    "progress",
    "assessment",
)
_CODE_INTENT_DOC_ALLOWLIST_MARKERS: tuple[str, ...] = (
    "schema",
    "contract",
    "interface",
    "architecture",
    "openapi",
    "proto",
    "swagger",
)
_CODE_INTENT_DOC_DOMAIN_PENALTIES: dict[str, float] = {
    "docs": -3.5,
    "planning": -4.0,
    "reports": -4.5,
    "reference": -2.5,
    "markdown": -3.0,
}
_CODE_INTENT_DOC_REBALANCE_GAP_THRESHOLD = 1.0
_CODE_INTENT_DOC_REBALANCE_PENALTY = -2.0


def _is_ace_lite_tooling_artifact_doc(*, path: str, language: str, semantic_domain: str) -> bool:
    normalized_path = _normalize_path(path)
    if semantic_domain not in {"docs", "planning", "reports", "reference", "markdown"}:
        return False
    if not _is_markdown_doc(path=path, language=language):
        return False
    if not any(marker in normalized_path for marker in _TOOL_ARTIFACT_PURPOSE_MARKERS):
        return False
    return any(marker in normalized_path for marker in _TOOL_ARTIFACT_NAME_MARKERS) or any(
        normalized_path.startswith(prefix) for prefix in _TOOL_ARTIFACT_PREFIXES
    )


def _self_feedback_doc_penalty(
    *,
    query: str,
    path: str,
    language: str,
    semantic_domain: str,
    query_flags: dict[str, Any],
) -> float:
    normalized_query = str(query or "").strip().lower()
    if not _is_ace_lite_tooling_artifact_doc(
        path=path,
        language=language,
        semantic_domain=semantic_domain,
    ):
        return 0.0
    if bool(query_flags.get("code_intent", False)):
        return -10.0
    if bool(query_flags.get("doc_sync", False)) and any(
        marker in normalized_query for marker in _TOOL_ARTIFACT_QUERY_ALLOWLIST
    ):
        return 0.0
    if any(marker in normalized_query for marker in ("ace-lite", "ace_lite", "ace lite", "mcp")):
        return 0.0
    return -8.0


def _code_intent_doc_penalty(
    *,
    query: str,
    path: str,
    language: str,
    semantic_domain: str,
    query_flags: dict[str, Any],
) -> float:
    if not bool(query_flags.get("code_intent", False)):
        return 0.0
    if bool(query_flags.get("doc_sync", False)):
        return 0.0
    if semantic_domain not in _CODE_INTENT_DOC_DOMAIN_PENALTIES:
        return 0.0
    if not _is_markdown_doc(path=path, language=language):
        return 0.0
    normalized_path = _normalize_path(path)
    normalized_query = str(query or "").strip().lower()
    matched_allowlist_markers = [
        marker for marker in _CODE_INTENT_DOC_ALLOWLIST_MARKERS if marker in normalized_path
    ]
    if matched_allowlist_markers and any(
        marker in normalized_query for marker in matched_allowlist_markers
    ):
        return 0.0
    return float(_CODE_INTENT_DOC_DOMAIN_PENALTIES.get(semantic_domain, -3.0))


def _is_code_intent_doc_candidate(*, path: str, language: str, semantic_domain: str) -> bool:
    if semantic_domain not in _CODE_INTENT_DOC_DOMAIN_PENALTIES:
        return False
    return _is_markdown_doc(path=path, language=language)


def _query_matches_contract_doc(*, query: str, path: str) -> bool:
    normalized_query = str(query or "").strip().lower()
    normalized_path = _normalize_path(path)
    matched_allowlist_markers = [
        marker for marker in _CODE_INTENT_DOC_ALLOWLIST_MARKERS if marker in normalized_path
    ]
    if not matched_allowlist_markers:
        return False
    return any(marker in normalized_query for marker in matched_allowlist_markers)


def _rebalance_code_intent_docs(
    *,
    query: str,
    rows: list[PlanQuickScoredRow],
    query_flags: dict[str, Any],
) -> list[PlanQuickScoredRow]:
    if not bool(query_flags.get("code_intent", False)):
        return rows
    if bool(query_flags.get("doc_sync", False)):
        return rows
    top_code_score = max(
        (
            float(row.fused_score)
            for row in rows
            if str(row.semantic_domain or "").strip() == "code"
        ),
        default=None,
    )
    if top_code_score is None:
        return rows
    rebalanced: list[PlanQuickScoredRow] = []
    for row in rows:
        if not _is_code_intent_doc_candidate(
            path=row.path,
            language=row.language,
            semantic_domain=row.semantic_domain,
        ):
            rebalanced.append(row)
            continue
        if _query_matches_contract_doc(query=query, path=row.path):
            rebalanced.append(row)
            continue
        score_gap = float(top_code_score) - float(row.fused_score)
        if score_gap > _CODE_INTENT_DOC_REBALANCE_GAP_THRESHOLD:
            rebalanced.append(row)
            continue
        extra_penalty = float(_CODE_INTENT_DOC_REBALANCE_PENALTY)
        rebalanced.append(
            PlanQuickScoredRow(
                path=row.path,
                module=row.module,
                language=row.language,
                score=row.score,
                lexical_hits=row.lexical_hits,
                lexical_boost=row.lexical_boost,
                intent_boost=row.intent_boost + extra_penalty,
                recency_boost=row.recency_boost,
                semantic_domain=row.semantic_domain,
                fused_score=row.fused_score + extra_penalty,
                labels=row.labels,
                role=row.role,
            )
        )
    return rebalanced


def _infer_candidate_labels(
    *,
    path: str,
    module: str,
    language: str,
    semantic_domain: str,
    repomap_neighbors: set[str] | None = None,
) -> tuple[str, ...]:
    normalized_path = _normalize_path(path)
    stem = _path_stem(path)
    labels: list[str] = []

    if semantic_domain == "tests":
        labels.append("test_entry")
    if semantic_domain in {"docs", "reference", "markdown", "planning"} and (
        stem in _DOC_ENTRYPOINT_BASENAMES
        or any(
            marker in normalized_path
            for marker in ("schema", "contract", "interface", "overview", "architecture")
        )
    ):
        labels.append("public_contract")
    if any(
        marker in normalized_path
        for marker in (
            "/cli",
            "cli.py",
            "/main.",
            "/app.",
            "/server.",
            "/entrypoint",
            "readme.md",
        )
    ):
        labels.append("entrypoint")
    if any(
        marker in normalized_path
        for marker in (
            "orchestrator",
            "evaluation",
            "benchmark",
            "runner",
            "pipeline",
        )
    ):
        labels.append("evaluation_orchestrator")
    if any(
        marker in normalized_path
        for marker in (
            "store",
            "sqlite",
            "ledger",
            "snapshot",
            "persist",
            "cache",
            "repository",
            "db",
        )
    ):
        labels.append("persistence_layer")
    if semantic_domain == "code" and not labels:
        labels.append("runtime_core")
    if repomap_neighbors and normalized_path in repomap_neighbors:
        labels.append("repomap_neighbor")

    if "entrypoint" in labels:
        role = "entrypoint"
    elif "public_contract" in labels:
        role = "public_contract"
    elif "evaluation_orchestrator" in labels:
        role = "evaluation_orchestrator"
    elif "persistence_layer" in labels:
        role = "persistence_layer"
    elif "test_entry" in labels:
        role = "test_entry"
    elif "repomap_neighbor" in labels:
        role = "repomap_neighbor"
    elif semantic_domain != "code":
        role = semantic_domain
    else:
        role = "runtime_core"

    if not labels:
        if _is_markdown_doc(path=path, language=language):
            labels.append("public_contract")
            role = "public_contract"
        else:
            labels.append("runtime_core")
            role = "runtime_core"
    return tuple(dict.fromkeys([*labels, role]))


def score_plan_quick_rows(
    *,
    query: str,
    rows: list[dict[str, Any]],
    repomap_neighbors: set[str] | None = None,
    lexical_boost_per_hit: float = 5.0,
) -> list[PlanQuickScoredRow]:
    normalized_query = str(query or "").strip()
    tokens = [token for token in normalized_query.lower().split() if token]
    boost_per_hit = float(lexical_boost_per_hit)
    query_flags = _query_flags(normalized_query)
    newest_dated_doc = _find_newest_dated_doc(rows)

    scored: list[PlanQuickScoredRow] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "")
        module = str(item.get("module", "") or "")
        language = str(item.get("language", "") or "")
        base_score = float(item.get("score", 0.0) or 0.0)
        blob = f"{path} {module}".lower()
        lexical_hits = sum(1 for token in tokens if token in blob)
        lexical_boost = float(lexical_hits) * boost_per_hit
        semantic_domain = _classify_path_domain(path)
        intent_boost = _doc_sync_intent_boost(
            path=path,
            language=language,
            query_flags=query_flags,
        )
        recency_boost = _latest_doc_intent_boost(
            path=path,
            language=language,
            query_flags=query_flags,
            newest_dated_doc=newest_dated_doc,
        )
        intent_boost += _self_feedback_doc_penalty(
            query=normalized_query,
            path=path,
            language=language,
            semantic_domain=semantic_domain,
            query_flags=query_flags,
        )
        intent_boost += _code_intent_doc_penalty(
            query=normalized_query,
            path=path,
            language=language,
            semantic_domain=semantic_domain,
            query_flags=query_flags,
        )
        fused_score = base_score + lexical_boost + intent_boost + recency_boost
        scored.append(
            PlanQuickScoredRow(
                path=path,
                module=module,
                language=language,
                score=base_score,
                lexical_hits=lexical_hits,
                lexical_boost=lexical_boost,
                intent_boost=intent_boost,
                recency_boost=recency_boost,
                semantic_domain=semantic_domain,
                fused_score=fused_score,
                labels=_infer_candidate_labels(
                    path=path,
                    module=module,
                    language=language,
                    semantic_domain=semantic_domain,
                    repomap_neighbors=repomap_neighbors,
                ),
                role="",
            )
        )

    scored = _rebalance_code_intent_docs(
        query=normalized_query,
        rows=scored,
        query_flags=query_flags,
    )
    scored.sort(key=lambda row: (-float(row.fused_score), str(row.path)))
    normalized_scored: list[PlanQuickScoredRow] = []
    for row in scored:
        labels = tuple(row.labels)
        role = next(
            (
                label
                for label in labels
                if label
                in {
                    "entrypoint",
                    "public_contract",
                    "evaluation_orchestrator",
                    "persistence_layer",
                    "test_entry",
                    "repomap_neighbor",
                    "runtime_core",
                    "planning",
                    "docs",
                    "reference",
                    "research",
                    "reports",
                    "markdown",
                }
            ),
            "runtime_core",
        )
        normalized_scored.append(
            PlanQuickScoredRow(
                path=row.path,
                module=row.module,
                language=row.language,
                score=row.score,
                lexical_hits=row.lexical_hits,
                lexical_boost=row.lexical_boost,
                intent_boost=row.intent_boost,
                recency_boost=row.recency_boost,
                semantic_domain=row.semantic_domain,
                fused_score=row.fused_score,
                labels=labels,
                role=role,
            )
        )
    return normalized_scored


def build_plan_quick(
    *,
    query: str,
    root: str | Path,
    languages: str,
    top_k_files: int = 8,
    repomap_top_k: int = 24,
    candidate_ranker: str = "rrf_hybrid",
    index_cache_path: str = "context-map/index.json",
    index_incremental: bool = True,
    repomap_expand: bool = False,
    repomap_neighbor_limit: int = 20,
    repomap_neighbor_depth: int = 1,
    budget_tokens: int = 800,
    ranking_profile: str = "graph",
    include_rows: bool = False,
    tokenizer_model: str | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    normalized_query = str(query or "").strip()
    if not normalized_query:
        raise ValueError("query cannot be empty")

    root_path = Path(root).expanduser().resolve()
    language_csv = str(languages or "").strip()
    languages_parsed = parse_language_csv(language_csv)

    cache_path = Path(str(index_cache_path or "context-map/index.json")).expanduser()
    if not cache_path.is_absolute():
        cache_path = root_path / cache_path

    snapshot = load_retrieval_index_snapshot(
        root_dir=str(root_path),
        cache_path=str(cache_path),
        languages=languages_parsed or [],
        incremental=bool(index_incremental),
        fail_open=False,
        include_index_hash=False,
    )
    index_payload = snapshot.index_payload
    cache_info = snapshot.cache_info
    if isinstance(cache_info, dict) and str(cache_info.get("mode") or "") == "full_build":
        cache_info = dict(cache_info)
        cache_info["full_build_reason"] = str(
            cache_info.get("full_build_reason") or cache_info.get("reason") or "cache_missing"
        )
    repo_map: dict[str, Any] = {}
    files_map = snapshot.files_map

    ranking_source = "ranker"
    pool_size = max(1, int(repomap_top_k))
    top_k = max(1, int(top_k_files))
    candidate_pool_size = max(pool_size, top_k)
    corpus_size = snapshot.corpus_size

    terms = extract_retrieval_terms(query=normalized_query, memory_stage={})
    retrieval_policy_profile, retrieval_policy_observability = (
        build_plan_quick_policy_observability(query=normalized_query)
    )
    runtime_profile = build_retrieval_runtime_profile(
        candidate_ranker=str(candidate_ranker or ""),
        min_candidate_score=1,
        top_k_files=candidate_pool_size,
        hybrid_fusion_mode="linear",
        hybrid_rrf_k=60,
        hybrid_weights={},
        index_hash=None,
        allow_empty_terms_fail_open=False,
    )
    selection: CandidateSelectionResult = select_initial_candidates(
        files_map=files_map,
        terms=terms,
        **runtime_profile.selection_kwargs(corpus_size=corpus_size),
    )
    pooled_candidates = list(selection.candidates)[: int(runtime_profile.top_k_files)]
    selection_observability = build_selection_observability(
        requested_ranker=selection.requested_ranker,
        selected_ranker=selection.selected_ranker,
        fallback_reasons=list(selection.fallback_reasons),
        min_score_used=int(selection.min_score_used),
        corpus_size=corpus_size,
        terms_count=len(terms),
    )

    rows: list[dict[str, Any]] = []
    for item in pooled_candidates:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "")
        if not path:
            continue
        entry = files_map.get(path, {})
        if not isinstance(entry, dict):
            entry = {}
        rows.append(
            {
                "path": path,
                "module": str(item.get("module", "") or ""),
                "language": str(item.get("language", "") or ""),
                "score": float(item.get("score", 0.0) or 0.0),
                "generated": bool(entry.get("generated")),
            }
        )

    repomap_stage: dict[str, Any] | None = None
    repomap_neighbors: set[str] = set()
    if repomap_expand:
        try:
            repomap_stage = build_stage_repo_map(
                index_files=files_map,
                seed_candidates=pooled_candidates,
                ranking_profile=str(ranking_profile or "graph").strip().lower() or "graph",
                top_k=min(top_k, len(pooled_candidates)),
                neighbor_limit=max(0, int(repomap_neighbor_limit)),
                neighbor_depth=max(1, int(repomap_neighbor_depth)),
                budget_tokens=max(1, int(budget_tokens)),
                tokenizer_model=tokenizer_model,
            )
            repomap_neighbors = {
                _normalize_path(item)
                for item in repomap_stage.get("neighbor_paths", [])
                if str(item).strip()
            }
        except Exception:
            repomap_stage = {
                "enabled": False,
                "seed_paths": [],
                "neighbor_paths": [],
                "focused_files": [],
                "error": "repomap_expand_failed",
            }

    if not rows:
        # Safety fallback: if heuristic ranking yields nothing (for example, bad
        # language detection or indexing anomalies), fall back to a static repo
        # map so callers still get deterministic suggestions.
        ranking_source = "repomap"
        repo_map = build_repo_map(
            index_payload=index_payload,
            budget_tokens=max(1, int(budget_tokens)),
            top_k=max(1, int(repomap_top_k)),
            ranking_profile=str(ranking_profile or "graph").strip().lower() or "graph",
            tokenizer_model=tokenizer_model,
        )

        rows = repo_map.get("files", [])
        if not isinstance(rows, list):
            rows = []
        rescored_rows = score_plan_quick_rows(
            query=normalized_query,
            rows=rows,
            repomap_neighbors=repomap_neighbors,
            lexical_boost_per_hit=5.0,
        )
    else:
        rescored_rows = score_plan_quick_rows(
            query=normalized_query,
            rows=rows,
            repomap_neighbors=repomap_neighbors,
            lexical_boost_per_hit=0.0,
        )

    # Apply domain-mixed strategy for design/doc intent queries with requirement IDs
    query_flags = _query_flags(normalized_query)
    if bool(query_flags.get("has_req_id", False)) or (
        bool(query_flags.get("doc_sync", False))
        and any(
            marker in normalized_query.lower()
            for marker in ("requirements", "milestone", "phase", "contract", "explainability")
        )
    ):
        limited_rows = build_mixed_top_k_candidates(
            rows=rescored_rows,
            top_k=top_k,
            ensure_docs=2,
            ensure_code=2,
        )
    else:
        limited_rows = rescored_rows[:top_k]
    candidate_paths = [row.path for row in limited_rows if row.path]
    if (
        repomap_expand
        and isinstance(repomap_stage, dict)
        and not repomap_stage.get("focused_files")
    ):
        repomap_stage["focused_files"] = list(candidate_paths)

    candidate_domain_summary = _build_candidate_domain_summary(limited_rows)
    risk_hints = _build_plan_quick_risk_hints(
        query=normalized_query,
        rows=limited_rows,
        retrieval_policy_profile=retrieval_policy_profile,
        index_cache=dict(cache_info or {}),
    )
    history_summary = build_history_summary(
        root=root_path,
        candidate_paths=candidate_paths,
    )
    candidate_details = build_candidate_details(
        limited_rows,
        query_flags=query_flags,
        history_summary=history_summary,
    )
    onboarding_view = build_onboarding_view(
        query_flags=query_flags,
        details=candidate_details,
    )
    upgrade_guidance = build_upgrade_guidance(
        query_flags=query_flags,
        rows=limited_rows,
        candidate_domain_summary=candidate_domain_summary,
        risk_hints=risk_hints,
        index_cache=dict(cache_info or {}),
    )

    response: dict[str, Any] = {
        "query": normalized_query,
        "root": str(root_path),
        "languages": language_csv,
        "candidate_files": candidate_paths,
        "source_plan_steps": len(PLAN_QUICK_STEPS),
        "steps": list(PLAN_QUICK_STEPS),
        "ranking_source": ranking_source,
        "candidate_ranker": str(selection_observability["requested"]),
        "candidate_ranker_selected": str(selection_observability["selected"]),
        "candidate_ranker_fallbacks": list(selection_observability["fallbacks"]),
        "candidate_min_score_used": int(selection_observability["min_score_used"]),
        "retrieval_policy_profile": retrieval_policy_profile,
        "retrieval_policy_observability": retrieval_policy_observability,
        "terms": list(terms),
        "index_cache_path": str(cache_path),
        "index_cache": dict(cache_info or {}),
        "repomap_stage": repomap_stage,
        "total_ms": float(
            max(
                0.0,
                (datetime.now(timezone.utc) - started_at).total_seconds() * 1000.0,
            )
        ),
        "repomap_used_tokens": int(repo_map.get("used_tokens", 0) or 0)
        if ranking_source == "repomap"
        else int((repomap_stage or {}).get("used_tokens", 0) or 0),
        "repomap_budget_tokens": int(repo_map.get("budget_tokens", budget_tokens) or 0)
        if ranking_source == "repomap"
        else int((repomap_stage or {}).get("budget_tokens", budget_tokens) or budget_tokens),
        "ranking_profile": str(
            repo_map.get("ranking_profile", "") or str(ranking_profile or "graph")
        )
        if ranking_source == "repomap"
        else str(ranking_profile or "graph"),
        "query_profile": _query_flags(normalized_query),
        "candidate_domain_summary": candidate_domain_summary,
        "history_summary": history_summary,
        "candidate_details": candidate_details,
        "onboarding_view": onboarding_view,
        "suggested_query_refinements": _build_suggested_query_refinements(
            query=normalized_query,
            rows=limited_rows,
        ),
        "risk_hints": risk_hints,
        **upgrade_guidance,
        # ALH1-0202.T1: report-only outcome logging fields
        "outcome_label": "plan_quick_success",
        "upgrade_outcome_hint": {
            "expected_incremental_value": upgrade_guidance["expected_incremental_value"],
            "expected_cost_ms_band": upgrade_guidance["expected_cost_ms_band"],
            "upgrade_recommended": upgrade_guidance["upgrade_recommended"],
        },
    }
    if include_rows:
        response["rows"] = [row.as_dict() for row in limited_rows]
    return response


__all__ = [
    "PLAN_QUICK_STEPS",
    "PlanQuickScoredRow",
    "build_plan_quick",
    "build_plan_quick_policy_observability",
    "score_plan_quick_rows",
]
