from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from ace_lite.index_cache import build_or_refresh_index
from ace_lite.parsers.languages import parse_language_csv
from ace_lite.workspace.common import (
    ensure_non_empty_str as _ensure_non_empty_str,
)
from ace_lite.workspace.common import (
    tokenize as _tokenize,
)

SUMMARY_INDEX_V1_VERSION = "workspace_summary_index_v1"
SUMMARY_TEMPERATURE_TIERS: tuple[str, ...] = ("hot", "warm", "cold")


def _validate_positive_int(*, value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{context} must be an integer")
    if value <= 0:
        raise ValueError(f"{context} must be > 0")
    return int(value)


def _normalize_temperature(*, value: Any, context: str) -> str:
    normalized = _ensure_non_empty_str(value=value, context=context).lower()
    if normalized not in SUMMARY_TEMPERATURE_TIERS:
        allowed = ", ".join(SUMMARY_TEMPERATURE_TIERS)
        raise ValueError(f"{context} must be one of: {allowed}")
    return normalized


@dataclass(frozen=True, slots=True)
class RepoSummaryV1:
    name: str
    root: str
    file_count: int
    language_counts: dict[str, int]
    top_directories: tuple[str, ...]
    top_modules: tuple[str, ...]
    summary_tokens: tuple[str, ...]
    temperature: str = "warm"
    refreshed_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "root": self.root,
            "file_count": int(self.file_count),
            "language_counts": dict(self.language_counts),
            "top_directories": list(self.top_directories),
            "top_modules": list(self.top_modules),
            "summary_tokens": list(self.summary_tokens),
            "temperature": self.temperature,
            "refreshed_at": self.refreshed_at,
        }

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> RepoSummaryV1:
        if not isinstance(payload, dict):
            raise ValueError("repo summary entry must be a mapping")

        language_counts_raw = payload.get("language_counts", {})
        if not isinstance(language_counts_raw, dict):
            raise ValueError("repo summary language_counts must be a mapping")
        language_counts: dict[str, int] = {}
        for key, raw_value in language_counts_raw.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("repo summary language_counts keys must be non-empty strings")
            if isinstance(raw_value, bool) or not isinstance(raw_value, int):
                raise ValueError("repo summary language_counts values must be integers")
            if raw_value < 0:
                raise ValueError("repo summary language_counts values must be >= 0")
            language_counts[key.strip().lower()] = int(raw_value)

        top_directories_raw = payload.get("top_directories", [])
        if not isinstance(top_directories_raw, list):
            raise ValueError("repo summary top_directories must be a list")

        top_modules_raw = payload.get("top_modules", [])
        if not isinstance(top_modules_raw, list):
            raise ValueError("repo summary top_modules must be a list")

        summary_tokens_raw = payload.get("summary_tokens", [])
        if not isinstance(summary_tokens_raw, list):
            raise ValueError("repo summary summary_tokens must be a list")

        top_directories = tuple(
            sorted(
                {
                    _ensure_non_empty_str(value=item, context="repo summary top_directories[]").lower()
                    for item in top_directories_raw
                }
            )
        )
        top_modules = tuple(
            sorted(
                {
                    _ensure_non_empty_str(value=item, context="repo summary top_modules[]")
                    for item in top_modules_raw
                }
            )
        )
        summary_tokens = tuple(
            sorted(
                {
                    _ensure_non_empty_str(value=item, context="repo summary summary_tokens[]").lower()
                    for item in summary_tokens_raw
                }
            )
        )

        file_count_raw = payload.get("file_count", 0)
        if isinstance(file_count_raw, bool) or not isinstance(file_count_raw, int):
            raise ValueError("repo summary file_count must be an integer")
        if file_count_raw < 0:
            raise ValueError("repo summary file_count must be >= 0")

        temperature_raw = payload.get("temperature", "warm")
        if temperature_raw is None:
            temperature_raw = "warm"
        temperature = _normalize_temperature(value=temperature_raw, context="repo summary temperature")

        refreshed_at_raw = payload.get("refreshed_at")
        refreshed_at: str | None
        if refreshed_at_raw is None:
            refreshed_at = None
        else:
            refreshed_at = _ensure_non_empty_str(
                value=refreshed_at_raw,
                context="repo summary refreshed_at",
            )

        return RepoSummaryV1(
            name=_ensure_non_empty_str(value=payload.get("name"), context="repo summary name"),
            root=_ensure_non_empty_str(value=payload.get("root"), context="repo summary root"),
            file_count=int(file_count_raw),
            language_counts=dict(sorted(language_counts.items())),
            top_directories=top_directories,
            top_modules=top_modules,
            summary_tokens=summary_tokens,
            temperature=temperature,
            refreshed_at=refreshed_at,
        )


@dataclass(frozen=True, slots=True)
class WorkspaceSummaryIndexV1:
    generated_at: str
    repos: tuple[RepoSummaryV1, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": SUMMARY_INDEX_V1_VERSION,
            "generated_at": self.generated_at,
            "repo_count": len(self.repos),
            "repos": [repo.as_dict() for repo in self.repos],
        }

    def tokens_by_repo(self) -> dict[str, tuple[str, ...]]:
        return {repo.name: tuple(repo.summary_tokens) for repo in self.repos}

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> WorkspaceSummaryIndexV1:
        if not isinstance(payload, dict):
            raise ValueError("summary index payload must be a mapping")
        version = str(payload.get("version", "")).strip()
        if version != SUMMARY_INDEX_V1_VERSION:
            raise ValueError(
                f"unsupported summary index version: {version or '<missing>'}; expected {SUMMARY_INDEX_V1_VERSION}"
            )

        generated_at = _ensure_non_empty_str(
            value=payload.get("generated_at"), context="summary index generated_at"
        )
        repos_raw = payload.get("repos", [])
        if not isinstance(repos_raw, list):
            raise ValueError("summary index repos must be a list")

        repos: list[RepoSummaryV1] = []
        seen_names: set[str] = set()
        for item in repos_raw:
            repo = RepoSummaryV1.from_dict(item)
            if repo.name in seen_names:
                raise ValueError(f"duplicate repo summary entry: {repo.name}")
            seen_names.add(repo.name)
            repos.append(repo)
        repos.sort(key=lambda value: value.name)
        return WorkspaceSummaryIndexV1(generated_at=generated_at, repos=tuple(repos))


def build_repo_summary_v1_from_index_payload(
    *,
    repo_name: str,
    repo_root: str,
    index_payload: dict[str, Any],
    temperature: str = "warm",
    refreshed_at: str | None = None,
    token_limit: int = 64,
    directory_limit: int = 12,
    module_limit: int = 12,
) -> RepoSummaryV1:
    resolved_name = _ensure_non_empty_str(value=repo_name, context="repo_name")
    resolved_root = _ensure_non_empty_str(value=repo_root, context="repo_root")
    token_cap = _validate_positive_int(value=token_limit, context="token_limit")
    directory_cap = _validate_positive_int(value=directory_limit, context="directory_limit")
    module_cap = _validate_positive_int(value=module_limit, context="module_limit")
    resolved_temperature = _normalize_temperature(value=temperature, context="temperature")
    resolved_refreshed_at: str | None
    if refreshed_at is None:
        resolved_refreshed_at = None
    else:
        resolved_refreshed_at = _ensure_non_empty_str(value=refreshed_at, context="refreshed_at")

    if not isinstance(index_payload, dict):
        raise ValueError("index_payload must be a mapping")
    files_map = index_payload.get("files", {})
    if not isinstance(files_map, dict):
        files_map = {}

    language_counts: Counter[str] = Counter()
    directory_counts: Counter[str] = Counter()
    module_counts: Counter[str] = Counter()
    token_counts: Counter[str] = Counter()
    file_count = 0

    for token in _tokenize(resolved_name):
        token_counts[token] += 4

    for raw_path in sorted(files_map):
        if not isinstance(raw_path, str):
            continue
        normalized_path = raw_path.strip().replace("\\", "/")
        if not normalized_path:
            continue

        entry = files_map.get(raw_path, {})
        if not isinstance(entry, dict):
            entry = {}

        file_count += 1
        path_obj = PurePosixPath(normalized_path)
        language = str(entry.get("language", "")).strip().lower()
        if language:
            language_counts[language] += 1
            token_counts[language] += 2

        parts = path_obj.parts
        if len(parts) > 1:
            top_dir = str(parts[0]).strip().lower()
            if top_dir:
                directory_counts[top_dir] += 1
                for token in _tokenize(top_dir):
                    token_counts[token] += 1
            if len(parts) > 2:
                leaf_dir = str(parts[-2]).strip().lower()
                if leaf_dir:
                    for token in _tokenize(leaf_dir):
                        token_counts[token] += 1

        for token in _tokenize(path_obj.stem):
            token_counts[token] += 1

        module = str(entry.get("module", "")).strip().lower()
        if module:
            module_counts[module] += 1
            for segment in module.split("."):
                for token in _tokenize(segment):
                    token_counts[token] += 1

    top_directories = tuple(
        sorted(directory_counts, key=lambda value: (-int(directory_counts[value]), value))[:directory_cap]
    )
    top_modules = tuple(
        sorted(module_counts, key=lambda value: (-int(module_counts[value]), value))[:module_cap]
    )
    summary_tokens = tuple(
        token
        for token, _score in sorted(token_counts.items(), key=lambda item: (-int(item[1]), item[0]))[:token_cap]
    )

    return RepoSummaryV1(
        name=resolved_name,
        root=resolved_root,
        file_count=int(file_count),
        language_counts=dict(sorted((key, int(value)) for key, value in language_counts.items())),
        top_directories=top_directories,
        top_modules=top_modules,
        summary_tokens=summary_tokens,
        temperature=resolved_temperature,
        refreshed_at=resolved_refreshed_at,
    )


def build_repo_summary_v1_from_index_cache(
    *,
    repo_name: str,
    repo_root: str,
    index_cache_path: str | Path,
    temperature: str = "warm",
    refreshed_at: str | None = None,
    token_limit: int = 64,
    directory_limit: int = 12,
    module_limit: int = 12,
) -> RepoSummaryV1:
    path = Path(index_cache_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"index cache not found: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid index cache payload: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid index cache payload: {path}")

    return build_repo_summary_v1_from_index_payload(
        repo_name=repo_name,
        repo_root=repo_root,
        index_payload=payload,
        temperature=temperature,
        refreshed_at=refreshed_at,
        token_limit=token_limit,
        directory_limit=directory_limit,
        module_limit=module_limit,
    )


def build_repo_summary_v1(
    *,
    repo_name: str,
    repo_root: str,
    languages: str,
    index_cache_path: str | Path = "context-map/index.json",
    index_incremental: bool = True,
    temperature: str = "warm",
    refreshed_at: str | None = None,
    token_limit: int = 64,
    directory_limit: int = 12,
    module_limit: int = 12,
) -> RepoSummaryV1:
    root_path = Path(_ensure_non_empty_str(value=repo_root, context="repo_root")).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise ValueError(f"repo_root does not exist or is not a directory: {root_path}")

    cache_path = Path(index_cache_path).expanduser()
    if not cache_path.is_absolute():
        cache_path = root_path / cache_path
    cache_path = cache_path.resolve()

    language_csv = _ensure_non_empty_str(value=languages, context="languages")
    parsed_languages = parse_language_csv(language_csv)
    if not parsed_languages:
        raise ValueError("languages cannot be empty")

    index_payload, _cache_info = build_or_refresh_index(
        root_dir=str(root_path),
        cache_path=str(cache_path),
        languages=parsed_languages,
        incremental=bool(index_incremental),
    )
    return build_repo_summary_v1_from_index_payload(
        repo_name=repo_name,
        repo_root=str(root_path),
        index_payload=index_payload,
        temperature=temperature,
        refreshed_at=refreshed_at,
        token_limit=token_limit,
        directory_limit=directory_limit,
        module_limit=module_limit,
    )


def build_workspace_summary_index_v1(
    *,
    repo_summaries: list[RepoSummaryV1],
    generated_at: str | None = None,
) -> WorkspaceSummaryIndexV1:
    if not isinstance(repo_summaries, list):
        raise ValueError("repo_summaries must be a list")

    seen_names: set[str] = set()
    normalized: list[RepoSummaryV1] = []
    for item in repo_summaries:
        if not isinstance(item, RepoSummaryV1):
            raise ValueError("repo_summaries[] must be RepoSummaryV1 instances")
        if item.name in seen_names:
            raise ValueError(f"duplicate repo summary entry: {item.name}")
        seen_names.add(item.name)
        normalized.append(item)
    normalized.sort(key=lambda value: value.name)

    if generated_at is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    else:
        timestamp = _ensure_non_empty_str(value=generated_at, context="generated_at")

    return WorkspaceSummaryIndexV1(generated_at=timestamp, repos=tuple(normalized))


def save_summary_index_v1(*, summary_index: WorkspaceSummaryIndexV1, path: str | Path) -> str:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(summary_index.as_dict(), ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return str(target)


def load_summary_index_v1(path: str | Path) -> WorkspaceSummaryIndexV1:
    source = Path(path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise ValueError(f"summary index not found: {source}")

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid summary index payload: {source}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid summary index payload: {source}")

    return WorkspaceSummaryIndexV1.from_dict(payload)


def summary_tokens_for_repo(
    *,
    summary_index: WorkspaceSummaryIndexV1 | dict[str, Any],
    repo_name: str,
) -> tuple[str, ...]:
    target_name = _ensure_non_empty_str(value=repo_name, context="repo_name")

    payload: WorkspaceSummaryIndexV1
    if isinstance(summary_index, WorkspaceSummaryIndexV1):
        payload = summary_index
    elif isinstance(summary_index, dict):
        payload = WorkspaceSummaryIndexV1.from_dict(summary_index)
    else:
        raise ValueError("summary_index must be WorkspaceSummaryIndexV1 or a mapping payload")

    for repo in payload.repos:
        if repo.name == target_name:
            return tuple(repo.summary_tokens)
    return ()


__all__ = [
    "SUMMARY_INDEX_V1_VERSION",
    "SUMMARY_TEMPERATURE_TIERS",
    "RepoSummaryV1",
    "WorkspaceSummaryIndexV1",
    "build_repo_summary_v1",
    "build_repo_summary_v1_from_index_cache",
    "build_repo_summary_v1_from_index_payload",
    "build_workspace_summary_index_v1",
    "load_summary_index_v1",
    "save_summary_index_v1",
    "summary_tokens_for_repo",
]
