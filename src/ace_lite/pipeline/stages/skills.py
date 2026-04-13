"""Skills stage for the orchestrator pipeline."""

from __future__ import annotations

import re
from time import perf_counter
from typing import Any

from ace_lite.pipeline.types import StageContext
from ace_lite.skills import load_sections, select_skills
from ace_lite.token_estimator import estimate_tokens

_DEFAULT_SKILL_TOP_N = 3

_TROUBLESHOOT_TOKENS = (
    "error",
    "bug",
    "fail",
    "exception",
    "fix",
    "traceback",
    "报错",
    "错误",
    "异常",
    "失败",
    "修复",
    "排查",
    "超时",
)
_HANDOFF_TOKENS = (
    "handoff",
    "hand-off",
    "context sync",
    "resume",
    "onboarding",
    "交接",
    "续接",
    "接手",
    "上下文同步",
)
_RELEASE_TOKENS = (
    "release",
    "freeze",
    "changelog",
    "compatibility",
    "go-no-go",
    "candidate",
    "发布",
    "发版",
    "冻结",
    "候选版本",
    "兼容性",
)
_BENCHMARK_TOKENS = (
    "benchmark",
    "latency",
    "precision",
    "recall",
    "ndcg",
    "mrr",
    "performance",
    "基准",
    "调优",
    "延迟",
    "精度",
    "召回",
    "性能",
    "噪声",
)
_RESEARCH_TOKENS = (
    "analyze",
    "analysis",
    "compare",
    "comparison",
    "study",
    "research",
    "inspiration",
    "inspired",
    "borrow",
    "borrowing",
    "reference implementation",
    "code taste",
    "architecture review",
    "workflow review",
    "graphify",
    "benchmark against",
    "对标",
    "借鉴",
    "灵感",
    "启发",
    "分析",
    "比较",
    "拆解",
    "复盘",
    "参考实现",
    "代码品味",
    "架构设计",
    "流程设计",
)
_REFACTOR_TOKENS = (
    "refactor",
    "cleanup",
    "maintainability",
    "rename",
    "restructure",
    "deduplicate",
    "duplication",
    "duplicated",
    "重构",
    "清理",
    "重命名",
    "重组",
    "去重",
    "重复",
)
_REVIEW_TOKENS = (
    "review",
    "audit",
    "check",
    "审查",
    "评审",
    "检查",
    "审计",
)
_MEMORY_TOKENS = (
    "memory",
    "context",
    "retrieval",
    "mem0",
    "openmemory",
    "记忆",
    "上下文",
    "检索",
    "回忆",
)
_INTENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("troubleshoot", _TROUBLESHOOT_TOKENS),
    ("handoff", _HANDOFF_TOKENS),
    ("release", _RELEASE_TOKENS),
    ("benchmark", _BENCHMARK_TOKENS),
    ("research", _RESEARCH_TOKENS),
    ("refactor", _REFACTOR_TOKENS),
    ("review", _REVIEW_TOKENS),
    ("memory", _MEMORY_TOKENS),
)


def _coerce_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def infer_intent(query: str) -> str:
    """Infer the dominant skill-routing intent from a query string."""

    text = query.lower()
    for intent, tokens in _INTENT_RULES:
        if any(token in text for token in tokens):
            return intent
    return "implement"


def infer_module(module_hint: str) -> str:
    """Normalize the upstream module hint without truncating nested segments."""

    normalized = str(module_hint).strip().lower()
    if not normalized:
        return ""

    normalized = normalized.replace("\\", ".").replace("/", ".").replace(" ", ".")
    normalized = re.sub(r"[^a-z0-9_.-]+", ".", normalized)
    normalized = re.sub(r"\.+", ".", normalized).strip(".")
    if normalized.endswith(".py"):
        normalized = normalized[:-3]
    return normalized


def extract_error_keywords(
    query: str, global_keywords: set[str] | None = None
) -> list[str]:
    """Extract error-related keywords from a query."""

    text = query.lower()
    keywords = set(re.findall(r"\b\d{3}\b", text))
    lexicon = {
        "timeout",
        "dimension",
        "mismatch",
        "error",
        "exception",
        "404",
        "405",
        "429",
        "500",
        "503",
        "超时",
        "维度",
        "不匹配",
        "错误",
        "异常",
    }
    if global_keywords:
        lexicon.update(global_keywords)

    for token in lexicon:
        if _keyword_in_text(text=text, keyword=token):
            keywords.add(token)
    return sorted(keywords)


def build_query_ctx(*, query: str, module_hint: str) -> dict[str, Any]:
    return {
        "query": query,
        "intent": infer_intent(query),
        "module": infer_module(module_hint),
        "error_keywords": extract_error_keywords(query),
    }


def route_skills(
    *,
    query: str,
    module_hint: str,
    skill_manifest: list[dict[str, Any]],
    top_n: int = _DEFAULT_SKILL_TOP_N,
) -> dict[str, Any]:
    started = perf_counter()
    query_ctx = build_query_ctx(query=query, module_hint=module_hint)
    selected = select_skills(
        query_ctx,
        skill_manifest,
        top_n=max(0, int(top_n)),
    )
    route_latency_ms = (perf_counter() - started) * 1000.0
    return {
        "query_ctx": query_ctx,
        "available_count": len(skill_manifest),
        "routing_mode": "metadata_only",
        "metadata_only_routing": True,
        "route_latency_ms": route_latency_ms,
        "selected_manifest_token_estimate_total": sum(
            _manifest_skill_token_estimate(item)
            for item in selected
            if isinstance(item, dict)
        ),
        "selected": selected,
    }


def run_skills(
    *,
    ctx: StageContext,
    skill_manifest: list[dict[str, Any]],
    top_n: int = _DEFAULT_SKILL_TOP_N,
    token_budget: int | None = None,
    routed_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the skills stage and hydrate the selected sections."""

    index_stage = ctx.state.get("index", {})
    routed = routed_payload if isinstance(routed_payload, dict) else route_skills(
        query=ctx.query,
        module_hint=str(index_stage.get("module_hint", "") or ""),
        skill_manifest=skill_manifest,
        top_n=max(0, int(top_n)),
    )
    query_ctx = (
        routed.get("query_ctx")
        if isinstance(routed.get("query_ctx"), dict)
        else build_query_ctx(
            query=ctx.query,
            module_hint=str(index_stage.get("module_hint", "") or ""),
        )
    )
    selected: list[dict[str, Any]] = [
        item for item in _coerce_list(routed.get("selected")) if isinstance(item, dict)
    ]
    available_count = max(
        0,
        _coerce_int(routed.get("available_count", len(skill_manifest))),
    )
    routing_source = "precomputed" if isinstance(routed_payload, dict) else "same_stage"
    resolved_budget = _normalize_skill_token_budget(token_budget)
    route_latency_ms = float(routed.get("route_latency_ms", 0.0) or 0.0)
    routing_mode = str(routed.get("routing_mode") or "metadata_only").strip()
    selected_manifest_token_estimate_total = _coerce_int(
        routed.get(
            "selected_manifest_token_estimate_total",
            sum(
                _manifest_skill_token_estimate(item)
                for item in selected
                if isinstance(item, dict)
            ),
        )
        or 0
    )

    hydrated: list[dict[str, Any]] = []
    selected_token_estimate_total = 0
    skipped_for_budget: list[dict[str, Any]] = []
    hydrated_sections_count = 0
    hydration_started = perf_counter()
    for item in selected:
        estimated_tokens = _manifest_skill_token_estimate(item)
        if (
            resolved_budget is not None
            and selected_token_estimate_total + estimated_tokens > resolved_budget
        ):
            skipped_for_budget.append(
                {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "estimated_tokens": estimated_tokens,
                }
            )
            continue
        headings = list(item.get("default_sections") or [])
        if not headings:
            headings = list(item.get("headings") or [])[:2]
        sections = load_sections(item["path"], headings)
        hydrated_sections_count += len(sections)
        estimated_tokens = _estimate_selected_skill_tokens(item=item, sections=sections)
        selected_token_estimate_total += estimated_tokens
        hydrated.append(
            {
                "name": item.get("name"),
                "path": item.get("path"),
                "score": item.get("score"),
                "matched": item.get("matched", []),
                "estimated_tokens": estimated_tokens,
                "sections": sections,
            }
        )
    hydration_latency_ms = (perf_counter() - hydration_started) * 1000.0

    return {
        "query_ctx": query_ctx,
        "available_count": available_count,
        "routing_source": routing_source,
        "routing_mode": routing_mode or "metadata_only",
        "metadata_only_routing": bool(routed.get("metadata_only_routing", True)),
        "route_latency_ms": route_latency_ms,
        "hydration_latency_ms": hydration_latency_ms,
        "routed_count": len(selected),
        "token_budget": resolved_budget,
        "token_budget_used": selected_token_estimate_total,
        "selected_token_estimate_total": selected_token_estimate_total,
        "selected_manifest_token_estimate_total": selected_manifest_token_estimate_total,
        "hydrated_skill_count": len(hydrated),
        "hydrated_sections_count": hydrated_sections_count,
        "budget_exhausted": bool(skipped_for_budget),
        "skipped_for_budget": skipped_for_budget,
        "selected": hydrated,
    }


def _estimate_selected_skill_tokens(
    *, item: dict[str, Any], sections: dict[str, str]
) -> int:
    declared = _coerce_int(item.get("token_estimate"))
    if declared > 0:
        return declared

    if sections:
        text = "\n\n".join(
            f"## {title}\n{content}".strip() for title, content in sections.items()
        )
        if text:
            return int(estimate_tokens(text))

    fallback = str(item.get("description") or item.get("name") or "").strip()
    return int(estimate_tokens(fallback)) if fallback else 1


def _manifest_skill_token_estimate(item: dict[str, Any]) -> int:
    declared = _coerce_int(item.get("token_estimate"))
    if declared > 0:
        return declared
    fallback = str(item.get("description") or item.get("name") or "").strip()
    return int(estimate_tokens(fallback)) if fallback else 1


def _normalize_skill_token_budget(value: int | None) -> int | None:
    if value is None:
        return None
    try:
        return max(1, int(value))
    except Exception:
        return None


def _keyword_in_text(*, text: str, keyword: str) -> bool:
    token = str(keyword or "").strip().lower()
    if not token:
        return False
    if token.isdigit():
        return token in text
    if re.fullmatch(r"[a-z0-9_]+", token):
        pattern = rf"(?<![a-z0-9_]){re.escape(token)}(?![a-z0-9_])"
        return re.search(pattern, text) is not None
    return token in text


__all__ = [
    "build_query_ctx",
    "extract_error_keywords",
    "infer_intent",
    "infer_module",
    "route_skills",
    "run_skills",
]
