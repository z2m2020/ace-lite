from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import yaml
from ace_lite.workspace.common import ensure_non_empty_str as _ensure_non_empty_str

PLAN_QUICK_OPTION_KEYS: tuple[str, ...] = (
    "budget_tokens",
    "candidate_ranker",
    "include_rows",
    "index_cache_path",
    "index_incremental",
    "languages",
    "ranking_profile",
    "repomap_expand",
    "repomap_neighbor_depth",
    "repomap_neighbor_limit",
    "repomap_top_k",
    "tokenizer_model",
    "top_k_files",
)


@dataclass(frozen=True, slots=True)
class WorkspaceRepo:
    name: str
    root: str
    description: str
    tags: tuple[str, ...]
    weight: float
    plan_quick: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "root": self.root,
            "description": self.description,
            "tags": list(self.tags),
            "weight": float(self.weight),
            "plan_quick": dict(self.plan_quick),
        }


@dataclass(frozen=True, slots=True)
class WorkspaceManifest:
    manifest_path: str
    workspace_name: str
    defaults: dict[str, Any]
    repos: tuple[WorkspaceRepo, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "manifest_path": self.manifest_path,
            "workspace_name": self.workspace_name,
            "defaults": dict(self.defaults),
            "repos": [repo.as_dict() for repo in self.repos],
        }


def _ensure_mapping(*, value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _normalize_tags(*, value: Any, context: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list of strings")

    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{context}[{index}] must be a string")
        token = item.strip().lower()
        if token:
            normalized.append(token)

    return tuple(sorted(set(normalized)))


def _validate_plan_quick_options(
    *,
    value: Any,
    context: str,
) -> dict[str, Any]:
    if value is None:
        return {}

    options = _ensure_mapping(value=value, context=context)
    validated: dict[str, Any] = {}

    for key, raw in options.items():
        if key not in PLAN_QUICK_OPTION_KEYS:
            raise ValueError(
                f"{context}.{key} is not supported; allowed keys: {', '.join(PLAN_QUICK_OPTION_KEYS)}"
            )

        if key in {"languages", "candidate_ranker", "index_cache_path", "ranking_profile"}:
            validated[key] = _ensure_non_empty_str(value=raw, context=f"{context}.{key}")
            continue

        if key == "tokenizer_model":
            if raw is None:
                validated[key] = None
            elif isinstance(raw, str):
                normalized = raw.strip()
                validated[key] = normalized or None
            else:
                raise ValueError(f"{context}.{key} must be a string or null")
            continue

        if key in {"index_incremental", "repomap_expand", "include_rows"}:
            if not isinstance(raw, bool):
                raise ValueError(f"{context}.{key} must be a boolean")
            validated[key] = bool(raw)
            continue

        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ValueError(f"{context}.{key} must be an integer")

        if key == "repomap_neighbor_limit":
            if raw < 0:
                raise ValueError(f"{context}.{key} must be >= 0")
            validated[key] = int(raw)
            continue

        if raw <= 0:
            raise ValueError(f"{context}.{key} must be > 0")
        validated[key] = int(raw)

    return validated


def _extract_repo_plan_quick(*, repo_payload: dict[str, Any], context: str) -> dict[str, Any]:
    nested = repo_payload.get("plan_quick")
    nested_options = _validate_plan_quick_options(value=nested, context=f"{context}.plan_quick")

    flat_keys = [key for key in PLAN_QUICK_OPTION_KEYS if key in repo_payload]
    collisions = [key for key in flat_keys if key in nested_options]
    if collisions:
        names = ", ".join(collisions)
        raise ValueError(f"{context} duplicates plan_quick keys in both nested and flat fields: {names}")

    if flat_keys:
        flat_payload = {key: repo_payload[key] for key in flat_keys}
        flat_options = _validate_plan_quick_options(value=flat_payload, context=context)
        nested_options.update(flat_options)

    return nested_options


def _resolve_repo_root(*, raw_path: str, manifest_dir: Path, context: str) -> str:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = manifest_dir / path
    resolved = path.resolve()

    if not resolved.exists():
        raise ValueError(f"{context} does not exist: {resolved}")
    if not resolved.is_dir():
        raise ValueError(f"{context} must point to a directory: {resolved}")
    return str(resolved)


def load_workspace_manifest(path: str | Path) -> WorkspaceManifest:
    manifest_path = Path(path).expanduser().resolve()
    if not manifest_path.exists() or not manifest_path.is_file():
        raise ValueError(f"workspace manifest not found: {manifest_path}")

    try:
        payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"failed to read workspace manifest: {manifest_path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in workspace manifest: {manifest_path}") from exc

    root_payload = _ensure_mapping(value=payload, context="workspace manifest")
    workspace_payload = root_payload.get("workspace", {})
    if workspace_payload is None:
        workspace_payload = {}
    workspace_payload = _ensure_mapping(value=workspace_payload, context="workspace")

    workspace_name_raw = workspace_payload.get("name", manifest_path.stem)
    workspace_name = _ensure_non_empty_str(value=workspace_name_raw, context="workspace.name")

    defaults = _validate_plan_quick_options(
        value=root_payload.get("defaults"),
        context="defaults",
    )

    repos_payload = root_payload.get("repos")
    if not isinstance(repos_payload, list) or not repos_payload:
        raise ValueError("repos must be a non-empty list")

    manifest_dir = manifest_path.parent
    seen_names: set[str] = set()
    repos: list[WorkspaceRepo] = []

    for index, raw_repo in enumerate(repos_payload):
        context = f"repos[{index}]"
        repo_payload = _ensure_mapping(value=raw_repo, context=context)

        name = _ensure_non_empty_str(value=repo_payload.get("name"), context=f"{context}.name")
        if name in seen_names:
            raise ValueError(f"duplicate repo name: {name}")
        seen_names.add(name)

        path_raw = _ensure_non_empty_str(value=repo_payload.get("path"), context=f"{context}.path")
        root = _resolve_repo_root(
            raw_path=path_raw,
            manifest_dir=manifest_dir,
            context=f"{context}.path",
        )

        description_raw = repo_payload.get("description", "")
        if description_raw is None:
            description_raw = ""
        if not isinstance(description_raw, str):
            raise ValueError(f"{context}.description must be a string")
        description = description_raw.strip()

        tags = _normalize_tags(value=repo_payload.get("tags", []), context=f"{context}.tags")

        weight_raw = repo_payload.get("weight", 1.0)
        if isinstance(weight_raw, bool) or not isinstance(weight_raw, (int, float)):
            raise ValueError(f"{context}.weight must be a number")
        weight = float(weight_raw)
        if not math.isfinite(weight):
            raise ValueError(f"{context}.weight must be finite")
        if weight < 0.0:
            raise ValueError(f"{context}.weight must be >= 0")

        plan_quick = _extract_repo_plan_quick(repo_payload=repo_payload, context=context)

        repos.append(
            WorkspaceRepo(
                name=name,
                root=root,
                description=description,
                tags=tags,
                weight=weight,
                plan_quick=plan_quick,
            )
        )

    repos.sort(key=lambda item: item.name)

    return WorkspaceManifest(
        manifest_path=str(manifest_path),
        workspace_name=workspace_name,
        defaults=defaults,
        repos=tuple(repos),
    )


__all__ = [
    "PLAN_QUICK_OPTION_KEYS",
    "WorkspaceManifest",
    "WorkspaceRepo",
    "load_workspace_manifest",
]
