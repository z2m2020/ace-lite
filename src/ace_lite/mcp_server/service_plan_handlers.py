from __future__ import annotations

from pathlib import Path
from typing import Any

from ace_lite.config_pack import load_config_pack
from ace_lite.plan_contract_summary import build_plan_contract_summary
from ace_lite.plan_timeout import (
    PLAN_TIMEOUT_RECOMMENDATIONS,
    execute_with_timeout,
    is_plan_timeout_debug_enabled,
    resolve_plan_timeout_seconds,
)


def handle_plan_quick_request(
    *,
    query: str,
    repo: str | None,
    root_path: Path,
    default_repo: str,
    language_csv: str,
    top_k_files: int,
    repomap_top_k: int,
    candidate_ranker: str,
    index_cache_path: str,
    index_incremental: bool,
    repomap_expand: bool,
    repomap_neighbor_limit: int,
    repomap_neighbor_depth: int,
    budget_tokens: int,
    ranking_profile: str,
    include_rows: bool,
    tokenizer_model: str,
    build_plan_quick_fn: Any,
) -> dict[str, Any]:
    normalized_query = str(query or "").strip()
    if not normalized_query:
        raise ValueError("query cannot be empty")

    resolved_repo = str(repo or default_repo).strip() or default_repo
    quick = build_plan_quick_fn(
        query=normalized_query,
        root=root_path,
        languages=language_csv,
        top_k_files=max(1, int(top_k_files)),
        repomap_top_k=max(1, int(repomap_top_k)),
        candidate_ranker=str(candidate_ranker or "rrf_hybrid"),
        index_cache_path=str(index_cache_path or "context-map/index.json"),
        index_incremental=bool(index_incremental),
        repomap_expand=bool(repomap_expand),
        repomap_neighbor_limit=max(0, int(repomap_neighbor_limit)),
        repomap_neighbor_depth=max(1, int(repomap_neighbor_depth)),
        budget_tokens=max(1, int(budget_tokens)),
        ranking_profile=str(ranking_profile or "graph").strip().lower() or "graph",
        include_rows=include_rows,
        tokenizer_model=tokenizer_model,
    )
    response = {"ok": True, "repo": resolved_repo, **quick}
    response["root"] = str(root_path)
    return response


def handle_plan_request(
    *,
    query: str,
    repo: str | None,
    root_path: Path,
    default_repo: str,
    skills_path: Path,
    config_pack_path: str | None,
    time_range: str | None,
    start_date: str | None,
    end_date: str | None,
    memory_primary: str | None,
    memory_secondary: str | None,
    lsp_enabled: bool,
    plugins_enabled: bool,
    top_k_files: int,
    min_candidate_score: int,
    retrieval_policy: str,
    include_full_payload: bool,
    timeout_seconds: float | None,
    default_timeout_seconds: float,
    run_plan_payload_fn: Any,
    plan_quick_fn: Any,
) -> dict[str, Any]:
    normalized_query = str(query or "").strip()
    if not normalized_query:
        raise ValueError("query cannot be empty")

    resolved_repo = str(repo or default_repo).strip() or default_repo
    config_pack_result = load_config_pack(path=config_pack_path)
    config_pack_meta = config_pack_result.to_dict()
    config_pack_overrides = (
        dict(config_pack_result.overrides) if config_pack_result.enabled else {}
    )
    timeout_resolution = resolve_plan_timeout_seconds(
        timeout_seconds=timeout_seconds,
        default_timeout_seconds=default_timeout_seconds,
    )
    resolved_timeout = timeout_resolution.seconds
    debug_dump_enabled = is_plan_timeout_debug_enabled()

    outcome = execute_with_timeout(
        run_payload=lambda: run_plan_payload_fn(
            normalized_query,
            resolved_repo,
            root_path,
            skills_path,
            time_range,
            start_date,
            end_date,
            memory_primary,
            memory_secondary,
            lsp_enabled,
            plugins_enabled,
            top_k_files,
            min_candidate_score,
            retrieval_policy,
            config_pack_overrides,
        ),
        timeout_seconds=resolved_timeout,
        debug_root=root_path,
        debug_payload={
            "entrypoint": "mcp",
            "query": normalized_query,
            "repo": resolved_repo,
            "root": str(root_path),
            "config_pack": config_pack_meta,
            "timeout_source": timeout_resolution.source,
            "timeout_raw": timeout_resolution.raw,
        },
        debug_enabled=debug_dump_enabled,
    )

    if outcome.timed_out:
        fallback_paths: list[str] = []
        fallback_steps: list[str] = []
        try:
            quick = plan_quick_fn(
                query=normalized_query,
                repo=resolved_repo,
                root=str(root_path),
                top_k_files=max(1, int(top_k_files)),
                repomap_top_k=max(8, int(top_k_files) * 4),
                budget_tokens=800,
                ranking_profile="graph",
                include_rows=False,
            )
            quick_paths = quick.get("candidate_files", [])
            if isinstance(quick_paths, list):
                fallback_paths = [str(item).strip() for item in quick_paths if str(item).strip()]
            quick_steps = quick.get("steps", [])
            if isinstance(quick_steps, list):
                fallback_steps = [str(item).strip() for item in quick_steps if str(item).strip()]
        except Exception:
            fallback_paths = []
            fallback_steps = []
        return {
            "ok": False,
            "query": normalized_query,
            "repo": resolved_repo,
            "root": str(root_path),
            "config_pack": config_pack_meta,
            "source_plan_steps": len(fallback_steps),
            "candidate_files": len(fallback_paths),
            "candidate_file_paths": fallback_paths,
            "fallback_mode": "plan_quick" if fallback_paths else "none",
            "steps": fallback_steps,
            "total_ms": float(max(0.0, outcome.elapsed_ms)),
            "timed_out": True,
            "timeout_seconds": float(resolved_timeout),
            "reason": "ace_plan_timeout",
            "timeout_source": timeout_resolution.source,
            "debug_dump_path": outcome.debug_dump_path,
            "recommendations": list(PLAN_TIMEOUT_RECOMMENDATIONS),
        }

    summary = {
        "ok": True,
        "query": normalized_query,
        "repo": resolved_repo,
        "root": str(root_path),
        "config_pack": config_pack_meta,
        "source_plan_steps": len(
            outcome.payload.get("source_plan", {}).get("steps", [])
            if isinstance(outcome.payload, dict)
            and isinstance(outcome.payload.get("source_plan"), dict)
            else []
        ),
        "candidate_files": len(
            outcome.payload.get("source_plan", {}).get("candidate_files", [])
            if isinstance(outcome.payload, dict)
            and isinstance(outcome.payload.get("source_plan"), dict)
            else []
        ),
        "total_ms": float(
            outcome.payload.get("observability", {}).get("total_ms", 0.0)
            if isinstance(outcome.payload, dict)
            and isinstance(outcome.payload.get("observability"), dict)
            else 0.0
        ),
    }
    if isinstance(outcome.payload, dict):
        index_payload = (
            outcome.payload.get("index", {})
            if isinstance(outcome.payload.get("index"), dict)
            else {}
        )
        source_plan_payload = (
            outcome.payload.get("source_plan", {})
            if isinstance(outcome.payload.get("source_plan"), dict)
            else {}
        )
        summary.update(
            build_plan_contract_summary(
                index_payload=index_payload,
                source_plan_payload=source_plan_payload,
            )
        )
    if include_full_payload:
        summary["plan"] = outcome.payload
    return summary


__all__ = [
    "handle_plan_quick_request",
    "handle_plan_request",
]
