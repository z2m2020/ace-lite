"""Shared helpers and markers for plan_quick strategy modules."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache


class NormalizationUtils:
    """Shared utilities for path and string normalization."""

    @staticmethod
    def normalize_path(path: str | None) -> str:
        """Normalize a path to POSIX format with lowercase."""
        return str(path or "").strip().replace("\\", "/").lower()

    @staticmethod
    def normalize_language(language: str | None) -> str:
        """Normalize a language identifier."""
        return str(language or "").strip().lower()

    @staticmethod
    def extract_path_stem(path: str | None) -> str:
        """Extract the stem (filename without extension) from a path."""
        normalized = NormalizationUtils.normalize_path(path)
        basename = normalized.rsplit("/", 1)[-1]
        stem = basename.rsplit(".", 1)[0]
        return stem

    @staticmethod
    @lru_cache(maxsize=1024)
    def is_markdown_path(path: str | None) -> bool:
        """Check if path points to a markdown file."""
        normalized = NormalizationUtils.normalize_path(path)
        return normalized.endswith((".md", ".mdx"))

    @staticmethod
    @lru_cache(maxsize=1024)
    def is_markdown_language(language: str | None) -> bool:
        """Check if language is markdown."""
        normalized = NormalizationUtils.normalize_language(language)
        return normalized in frozenset({"markdown", "md"})


QUERY_DOC_SYNC_MARKERS: tuple[str, ...] = (
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
    "可解释性",
    "合同",
    "契约",
)

QUERY_LATEST_MARKERS: tuple[str, ...] = (
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

QUERY_ONBOARDING_MARKERS: tuple[str, ...] = (
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

DOC_PRIMARY_NAME_MARKERS: tuple[str, ...] = (
    "progress",
    "status",
    "runbook",
    "sync",
    "update",
    "latest",
    "current",
)

DOC_SECONDARY_NAME_MARKERS: tuple[str, ...] = (
    "readme",
    "report",
    "roadmap",
    "overview",
    "summary",
    "changelog",
)

DOC_PREFERRED_PREFIXES: tuple[str, ...] = (
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

DOC_ENTRYPOINT_BASENAMES: frozenset[str] = frozenset({"readme", "index", "overview"})

_MARKDOWN_LANGUAGES: frozenset[str] = frozenset({"markdown", "md"})

_LATEST_DOC_DOMAINS: frozenset[str] = frozenset(
    {"docs", "planning", "repos", "reports", "reference", "markdown"}
)

_PATH_DATE_PATTERN = re.compile(r"(?<!\d)((?:19|20)\d{2})-(\d{2})-(\d{2})(?!\d)")
_REQ_ID_PATTERN = re.compile(r"\b([A-Z]{2,})-(\d+)\b", re.IGNORECASE)


def _extract_req_ids(query: str) -> list[str]:
    """Extract requirement IDs like EXPL-01, REQ-01 from query."""
    normalized = str(query or "").strip()
    matches = _REQ_ID_PATTERN.findall(normalized)
    return [f"{str(prefix).upper()}-{num}" for prefix, num in matches]


def _extract_path_date(path: str | None) -> date | None:
    """Extract date from path if present."""
    normalized = str(path or "").strip().replace("\\", "/")
    matched = _PATH_DATE_PATTERN.search(normalized)
    if not matched:
        return None
    try:
        return datetime.strptime(matched.group(0), "%Y-%m-%d").date()
    except ValueError:
        return None


@dataclass(frozen=True)
class QueryFlags:
    """Structured representation of query intent flags."""

    doc_sync: bool = False
    latest_sensitive: bool = False
    onboarding: bool = False
    has_req_id: bool = False
    req_ids: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_query(cls, query: str) -> QueryFlags:
        """Detect flags from a query string."""
        lowered = str(query or "").strip().lower()
        return cls(
            doc_sync=any(marker in lowered for marker in QUERY_DOC_SYNC_MARKERS),
            latest_sensitive=any(marker in lowered for marker in QUERY_LATEST_MARKERS),
            onboarding=any(marker in lowered for marker in QUERY_ONBOARDING_MARKERS),
            has_req_id=bool(_extract_req_ids(query)),
            req_ids=tuple(_extract_req_ids(query)),
        )


__all__ = [
    "DOC_ENTRYPOINT_BASENAMES",
    "DOC_PREFERRED_PREFIXES",
    "DOC_PRIMARY_NAME_MARKERS",
    "DOC_SECONDARY_NAME_MARKERS",
    "QUERY_DOC_SYNC_MARKERS",
    "QUERY_LATEST_MARKERS",
    "QUERY_ONBOARDING_MARKERS",
    "_LATEST_DOC_DOMAINS",
    "NormalizationUtils",
    "QueryFlags",
    "_extract_path_date",
    "_extract_req_ids",
]
