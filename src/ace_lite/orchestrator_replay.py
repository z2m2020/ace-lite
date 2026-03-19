from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ace_lite.chunking.skeleton import CHUNK_SKELETON_SCHEMA_VERSION
from ace_lite.plan_replay_cache import (
    build_plan_component_fingerprint,
    build_plan_replay_cache_key,
    build_repo_root_fingerprint,
    content_version as plan_replay_content_version,
    normalize_plan_query,
)
from ace_lite.prompt_rendering.renderer import build_prompt_rendering_boundary


def build_memory_replay_fingerprint(*, memory_payload: dict[str, Any]) -> str:
    stable_payload = {
        "count": int(memory_payload.get("count", 0) or 0),
        "hits_preview": memory_payload.get("hits_preview", []),
        "hits": memory_payload.get("hits", []),
        "gate": memory_payload.get("gate", {}),
        "postprocess": memory_payload.get("postprocess", {}),
        "channel_used": str(memory_payload.get("channel_used", "")),
        "fallback_reason": str(memory_payload.get("fallback_reason") or ""),
        "strategy": str(memory_payload.get("strategy", "")),
        "temporal": memory_payload.get("temporal", {}),
        "namespace": memory_payload.get("namespace", {}),
        "timeline": memory_payload.get("timeline", {}),
        "notes": memory_payload.get("notes", {}),
        "disclosure": memory_payload.get("disclosure", {}),
        "cost": memory_payload.get("cost", {}),
        "profile": memory_payload.get("profile", {}),
        "capture": memory_payload.get("capture", {}),
    }
    return build_plan_component_fingerprint(stable_payload)


def build_index_replay_fingerprint(*, index_payload: dict[str, Any]) -> str:
    metadata = (
        index_payload.get("metadata", {})
        if isinstance(index_payload.get("metadata"), dict)
        else {}
    )
    stable_payload = {
        "candidate_files": index_payload.get("candidate_files", []),
        "candidate_chunks": index_payload.get("candidate_chunks", []),
        "chunk_contract": index_payload.get("chunk_contract", {}),
        "subgraph_payload": index_payload.get("subgraph_payload", {}),
        "module_hint": str(index_payload.get("module_hint", "")),
        "policy_name": str(index_payload.get("policy_name", "")),
        "policy_version": str(index_payload.get("policy_version", "")),
        "selection_fingerprint": str(metadata.get("selection_fingerprint", "")),
    }
    return build_plan_component_fingerprint(stable_payload)


def build_repomap_replay_fingerprint(*, repomap_payload: dict[str, Any]) -> str:
    stable_payload = {
        "enabled": bool(repomap_payload.get("enabled", False)),
        "focused_files": repomap_payload.get("focused_files", []),
        "seed_count": int(repomap_payload.get("seed_count", 0) or 0),
        "neighbor_count": int(repomap_payload.get("neighbor_count", 0) or 0),
        "neighbor_paths": repomap_payload.get("neighbor_paths", []),
    }
    return build_plan_component_fingerprint(stable_payload)


def build_repo_inputs_replay_fingerprint(
    *,
    root: str,
    index_payload: dict[str, Any],
    repomap_payload: dict[str, Any],
) -> str:
    candidate_files = index_payload.get("candidate_files", [])
    focused_files = repomap_payload.get("focused_files", [])
    relevant_paths: set[str] = set()
    if isinstance(candidate_files, list):
        for item in candidate_files:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").strip()
            if path:
                relevant_paths.add(path)
    if isinstance(focused_files, list):
        for item in focused_files:
            path = str(item or "").strip()
            if path:
                relevant_paths.add(path)

    snapshots: list[dict[str, str]] = []
    root_path = Path(root)
    for rel_path in sorted(relevant_paths):
        try:
            digest = hashlib.sha256((root_path / rel_path).read_bytes()).hexdigest()
        except OSError as exc:
            digest = f"missing:{exc.__class__.__name__}"
        snapshots.append({"path": rel_path, "sha256": digest})
    return build_plan_component_fingerprint({"files": snapshots})


def build_augment_replay_fingerprint(*, augment_payload: dict[str, Any]) -> str:
    augment_enabled = bool(augment_payload.get("enabled", False))
    stable_payload = {
        "enabled": augment_enabled,
        "reason": str(augment_payload.get("reason", "")),
        "diagnostics": augment_payload.get("diagnostics", []),
        "xref": augment_payload.get("xref", {}),
        "tests": augment_payload.get("tests", {}),
    }
    if augment_enabled:
        stable_payload["vcs_history"] = augment_payload.get("vcs_history", {})
        stable_payload["vcs_worktree"] = augment_payload.get("vcs_worktree", {})
    return build_plan_component_fingerprint(
        stable_payload,
        exclude_keys={"elapsed_ms"},
    )


def build_skills_replay_fingerprint(*, skills_payload: dict[str, Any]) -> str:
    stable_payload = {
        "enabled": bool(skills_payload.get("enabled", False)),
        "selected": [
            {
                "name": str(item.get("name", "")),
                "path": str(item.get("path", "")),
            }
            for item in skills_payload.get("selected", [])
            if isinstance(item, dict)
        ],
        "skipped_for_budget": [
            {
                "name": str(item.get("name", "")),
                "path": str(item.get("path", "")),
            }
            for item in skills_payload.get("skipped_for_budget", [])
            if isinstance(item, dict)
        ],
        "routing_source": str(skills_payload.get("routing_source", "")),
        "routing_mode": str(skills_payload.get("routing_mode", "")),
        "metadata_only_routing": bool(
            skills_payload.get("metadata_only_routing", False)
        ),
        "token_budget": int(skills_payload.get("token_budget", 0) or 0),
        "token_budget_used": int(
            skills_payload.get(
                "selected_token_estimate_total",
                skills_payload.get("token_budget_used", 0),
            )
            or 0
        ),
        "budget_exhausted": bool(skills_payload.get("budget_exhausted", False)),
    }
    return build_plan_component_fingerprint(stable_payload)


def build_source_plan_contract_replay_fingerprint(
    *,
    chunk_disclosure: str,
    graph_payload_version: str,
    graph_taxonomy_version: str,
) -> str:
    stable_payload = {
        "chunk_contract_schema_version": CHUNK_SKELETON_SCHEMA_VERSION,
        "chunk_disclosure": str(chunk_disclosure or "refs"),
        "prompt_rendering_boundary": build_prompt_rendering_boundary(),
        "graph_payload_version": str(graph_payload_version or ""),
        "graph_taxonomy_version": str(graph_taxonomy_version or ""),
    }
    return build_plan_component_fingerprint(stable_payload)


def build_agent_loop_iteration_replay_fingerprint(
    *,
    query: str,
    action_payload: dict[str, Any],
    rerun_stages: list[str] | tuple[str, ...],
    source_plan_payload: dict[str, Any],
    validation_payload: dict[str, Any],
) -> str:
    source_plan_steps = source_plan_payload.get("steps", [])
    validation_summary = (
        validation_payload.get("result", {}).get("summary", {})
        if isinstance(validation_payload.get("result"), dict)
        else {}
    )
    diagnostics = validation_payload.get("diagnostics", [])
    stable_payload = {
        "query": str(query or ""),
        "action": action_payload if isinstance(action_payload, dict) else {},
        "rerun_stages": [str(item) for item in rerun_stages],
        "source_plan": {
            "step_count": len(source_plan_steps) if isinstance(source_plan_steps, list) else 0,
            "validation_tests": source_plan_payload.get("validation_tests", []),
            "candidate_files": [
                str(item.get("path") or "")
                for item in source_plan_payload.get("candidate_files", [])
                if isinstance(item, dict)
            ],
        },
        "validation": {
            "reason": str(validation_payload.get("reason", "")),
            "diagnostic_count": int(validation_payload.get("diagnostic_count", 0) or 0),
            "status": str(validation_summary.get("status", "")),
            "diagnostic_paths": [
                str(item.get("path") or "")
                for item in diagnostics
                if isinstance(item, dict) and str(item.get("path") or "").strip()
            ],
        },
    }
    return build_plan_component_fingerprint(stable_payload)


def build_orchestrator_plan_replay_key(
    *,
    query: str,
    repo: str,
    root: str,
    temporal_input: dict[str, Any],
    plugins_loaded: list[str],
    conventions_hashes: dict[str, str],
    memory_payload: dict[str, Any],
    index_payload: dict[str, Any],
    repomap_payload: dict[str, Any],
    augment_payload: dict[str, Any],
    skills_payload: dict[str, Any],
    retrieval_policy_version: str,
    candidate_ranker_default: str,
    budget_knobs: dict[str, Any],
    chunk_disclosure: str,
) -> str:
    subgraph_payload = (
        index_payload.get("subgraph_payload", {})
        if isinstance(index_payload.get("subgraph_payload"), dict)
        else {}
    )
    worktree_prior = (
        index_payload.get("worktree_prior", {})
        if isinstance(index_payload.get("worktree_prior"), dict)
        else {}
    )
    candidate_ranking = (
        index_payload.get("candidate_ranking", {})
        if isinstance(index_payload.get("candidate_ranking"), dict)
        else {}
    )
    return build_plan_replay_cache_key(
        normalized_query=normalize_plan_query(query),
        repo_root_fingerprint=build_repo_root_fingerprint(repo=repo, root=root),
        temporal_input=temporal_input,
        plugins_loaded=plugins_loaded,
        conventions_hashes=conventions_hashes,
        memory_fingerprint=build_memory_replay_fingerprint(
            memory_payload=memory_payload
        ),
        index_fingerprint=build_index_replay_fingerprint(index_payload=index_payload),
        index_hash=str(index_payload.get("index_hash", "")),
        worktree_state_hash=str(worktree_prior.get("state_hash", "")),
        retrieval_policy=str(index_payload.get("policy_name", "")),
        policy_version=str(
            index_payload.get("policy_version", retrieval_policy_version)
        ),
        candidate_ranker=str(
            candidate_ranking.get("selected", candidate_ranker_default)
        ),
        budget_knobs=budget_knobs,
        upstream_fingerprints={
            "repo_inputs": build_repo_inputs_replay_fingerprint(
                root=root,
                index_payload=index_payload,
                repomap_payload=repomap_payload,
            ),
            "repomap": build_repomap_replay_fingerprint(
                repomap_payload=repomap_payload
            ),
            "augment": build_augment_replay_fingerprint(
                augment_payload=augment_payload
            ),
            "skills": build_skills_replay_fingerprint(
                skills_payload=skills_payload
            ),
            "source_plan_contracts": build_source_plan_contract_replay_fingerprint(
                chunk_disclosure=chunk_disclosure,
                graph_payload_version=str(subgraph_payload.get("payload_version") or ""),
                graph_taxonomy_version=str(
                    subgraph_payload.get("taxonomy_version") or ""
                ),
            ),
        },
        content_version=plan_replay_content_version(),
    )


__all__ = [
    "build_agent_loop_iteration_replay_fingerprint",
    "build_augment_replay_fingerprint",
    "build_index_replay_fingerprint",
    "build_memory_replay_fingerprint",
    "build_orchestrator_plan_replay_key",
    "build_repomap_replay_fingerprint",
    "build_repo_inputs_replay_fingerprint",
    "build_skills_replay_fingerprint",
    "build_source_plan_contract_replay_fingerprint",
]
