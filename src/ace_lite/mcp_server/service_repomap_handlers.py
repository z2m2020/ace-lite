from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict


class RepomapBuildResponse(TypedDict):
    ok: bool
    root: str
    languages: str
    ranking_profile: str
    budget_tokens: int
    used_tokens: int
    selected_count: int
    output_json: str
    output_md: str


def handle_repomap_build_request(
    *,
    root_path: Path,
    language_csv: str,
    budget_tokens: int,
    top_k: int,
    ranking_profile: str,
    output_json: str | None,
    output_md: str | None,
    tokenizer_model: str,
    build_index_fn: Callable[..., dict[str, Any]],
    parse_language_csv_fn: Callable[[str], list[str]],
    build_repo_map_fn: Callable[..., dict[str, Any]],
    resolve_output_path_fn: Callable[..., Path],
) -> RepomapBuildResponse:
    normalized_languages = str(language_csv or "").strip()
    normalized_ranking_profile = (
        str(ranking_profile or "heuristic").strip().lower() or "heuristic"
    )
    index_payload = build_index_fn(
        root_dir=str(root_path),
        languages=parse_language_csv_fn(normalized_languages),
    )
    repo_map = build_repo_map_fn(
        index_payload=index_payload,
        budget_tokens=max(1, int(budget_tokens)),
        top_k=max(1, int(top_k)),
        ranking_profile=normalized_ranking_profile,
        tokenizer_model=str(tokenizer_model),
    )

    json_path = resolve_output_path_fn(
        root_path=root_path,
        output=output_json,
        default="context-map/repo_map.json",
    )
    md_path = resolve_output_path_fn(
        root_path=root_path,
        output=output_md,
        default="context-map/repo_map.md",
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    json_payload = dict(repo_map)
    markdown = str(json_payload.pop("markdown", "") or "")
    json_path.write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(markdown, encoding="utf-8")

    return {
        "ok": True,
        "root": str(root_path),
        "languages": normalized_languages,
        "ranking_profile": str(repo_map.get("ranking_profile", "")),
        "budget_tokens": int(repo_map.get("budget_tokens", budget_tokens) or 0),
        "used_tokens": int(repo_map.get("used_tokens", 0) or 0),
        "selected_count": int(repo_map.get("selected_count", 0) or 0),
        "output_json": str(json_path),
        "output_md": str(md_path),
    }


__all__ = ["RepomapBuildResponse", "handle_repomap_build_request"]
