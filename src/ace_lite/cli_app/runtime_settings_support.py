from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ace_lite.cli_app.runtime_mcp_ops import (
    load_mcp_env_snapshot,
    mcp_env_snapshot_path,
)
from ace_lite.runtime_settings import RuntimeSettingsManager
from ace_lite.runtime_settings_store import (
    build_runtime_settings_record,
    inspect_runtime_settings_record,
    load_valid_runtime_settings_record,
    load_runtime_settings_with_fallback,
    persist_runtime_settings_record,
    resolve_user_runtime_settings_last_known_good_path,
    resolve_user_runtime_settings_path,
)


def load_runtime_snapshot(
    *,
    root: str,
    mcp_name: str,
    use_snapshot: bool,
    snapshot_path_fn: Any,
    load_snapshot_fn: Any,
) -> tuple[dict[str, str], Path]:
    snapshot_env: dict[str, str] = {}
    snapshot_path = snapshot_path_fn(root=root, mcp_name=mcp_name)
    if use_snapshot:
        snapshot_env, snapshot_path = load_snapshot_fn(root=root, mcp_name=mcp_name)
    return snapshot_env, snapshot_path


def evaluate_runtime_memory_state(
    *,
    payload: dict[str, Any],
    root: str,
    skills_dir: str,
    extract_memory_channels_fn: Any,
    memory_channels_disabled_fn: Any,
    memory_config_recommendations_fn: Any,
) -> dict[str, Any]:
    primary, secondary = extract_memory_channels_fn(payload)
    memory_disabled = memory_channels_disabled_fn(primary=primary, secondary=secondary)
    warnings: list[str] = []
    recommendations: list[str] = []
    if memory_disabled:
        warnings.append(
            "Memory providers are disabled (memory_primary=none, memory_secondary=none)."
        )
        recommendations.extend(
            memory_config_recommendations_fn(root=root, skills_dir=skills_dir)
        )
    return {
        "primary": primary,
        "secondary": secondary,
        "memory_disabled": memory_disabled,
        "warnings": warnings,
        "recommendations": recommendations,
    }


def selected_profile_from_resolved_settings(
    *,
    resolved: Any,
    persisted_record: dict[str, Any] | None,
) -> str | None:
    selected_profile = resolved.metadata.get("selected_profile")
    if selected_profile is None and isinstance(persisted_record, dict):
        metadata = persisted_record.get("metadata", {})
        if isinstance(metadata, dict):
            selected_profile = metadata.get("selected_profile")
    return str(selected_profile) if selected_profile is not None else None


def resolve_runtime_settings_bundle(
    *,
    root: str,
    config_file: str,
    mcp_name: str,
    runtime_profile: str | None,
    use_snapshot: bool,
    current_path: str,
    last_known_good_path: str,
    snapshot_path_fn: Any = mcp_env_snapshot_path,
    load_snapshot_fn: Any = load_mcp_env_snapshot,
) -> dict[str, Any]:
    snapshot_env, snapshot_path = load_runtime_snapshot(
        root=root,
        mcp_name=mcp_name,
        use_snapshot=use_snapshot,
        snapshot_path_fn=snapshot_path_fn,
        load_snapshot_fn=load_snapshot_fn,
    )
    resolved = RuntimeSettingsManager().resolve(
        root=root,
        cwd=Path.cwd(),
        config_file=config_file,
        plan_runtime_profile=runtime_profile,
        mcp_env=dict(os.environ),
        mcp_snapshot_env=snapshot_env if snapshot_env else None,
    )
    resolved_current_path = resolve_user_runtime_settings_path(
        configured_path=current_path,
    )
    resolved_lkg_path = resolve_user_runtime_settings_last_known_good_path(
        configured_path=last_known_good_path,
    )
    persisted_record, persisted_source = load_runtime_settings_with_fallback(
        current_path=resolved_current_path,
        last_known_good_path=resolved_lkg_path,
    )
    persisted_dict = persisted_record if isinstance(persisted_record, dict) else None
    bundle = {
        "snapshot_env": snapshot_env,
        "snapshot_path": snapshot_path,
        "resolved": resolved,
        "resolved_current_path": resolved_current_path,
        "resolved_lkg_path": resolved_lkg_path,
        "persisted_record": persisted_dict,
        "persisted_source": persisted_source,
        "selected_profile": selected_profile_from_resolved_settings(
            resolved=resolved,
            persisted_record=persisted_dict,
        ),
    }
    bundle["governance"] = build_runtime_settings_governance_payload(bundle)
    return bundle


def build_runtime_settings_governance_payload(bundle: dict[str, Any]) -> dict[str, Any]:
    resolved = bundle["resolved"]
    current_path = bundle["resolved_current_path"]
    lkg_path = bundle["resolved_lkg_path"]
    current_record = inspect_runtime_settings_record(current_path)
    lkg_record = inspect_runtime_settings_record(lkg_path)
    current_valid_payload = load_valid_runtime_settings_record(current_path)
    lkg_valid_payload = load_valid_runtime_settings_record(lkg_path)
    current_fingerprint = str(current_record.get("fingerprint") or "").strip()
    lkg_fingerprint = str(lkg_record.get("fingerprint") or "").strip()
    persisted_record = (
        bundle["persisted_record"] if isinstance(bundle.get("persisted_record"), dict) else None
    )
    persisted_metadata = (
        persisted_record.get("metadata", {})
        if isinstance(persisted_record, dict)
        and isinstance(persisted_record.get("metadata"), dict)
        else {}
    )
    persisted_fingerprint = (
        str(persisted_record.get("fingerprint") or "").strip()
        if isinstance(persisted_record, dict)
        else ""
    )
    resolved_matches_current = bool(current_fingerprint) and current_fingerprint == resolved.fingerprint
    resolved_matches_last_known_good = bool(lkg_fingerprint) and lkg_fingerprint == resolved.fingerprint
    resolved_matches_persisted = bool(persisted_fingerprint) and persisted_fingerprint == resolved.fingerprint
    governance_state = "unpersisted"
    if resolved_matches_current and resolved_matches_last_known_good:
        governance_state = "aligned"
    elif resolved_matches_current:
        governance_state = "current_only_aligned"
    elif bundle.get("persisted_source") == "last_known_good" and lkg_record["valid"]:
        governance_state = "fallback_to_last_known_good"
    elif current_record["valid"]:
        governance_state = "drifted"
    elif lkg_record["valid"]:
        governance_state = "current_invalid_using_last_known_good"
    elif current_record["exists"]:
        governance_state = "current_invalid"
    return {
        "governance_state": governance_state,
        "current_path": str(current_path),
        "last_known_good_path": str(lkg_path),
        "persisted_source": bundle.get("persisted_source"),
        "resolved_fingerprint": resolved.fingerprint,
        "persisted_fingerprint": persisted_fingerprint or None,
        "current_record": current_record,
        "last_known_good_record": lkg_record,
        "current_record_valid": current_valid_payload is not None,
        "last_known_good_record_valid": lkg_valid_payload is not None,
        "current_fingerprint": current_fingerprint or None,
        "last_known_good_fingerprint": lkg_fingerprint or None,
        "resolved_matches_current": resolved_matches_current,
        "resolved_matches_last_known_good": resolved_matches_last_known_good,
        "resolved_matches_persisted": resolved_matches_persisted,
        "persist_recommended": not (
            resolved_matches_current and resolved_matches_last_known_good
        ),
        "persisted_selected_profile": (
            str(persisted_metadata.get("selected_profile")).strip()
            if persisted_metadata.get("selected_profile") is not None
            else None
        ),
    }


def build_runtime_settings_payload(bundle: dict[str, Any]) -> dict[str, Any]:
    resolved = bundle["resolved"]
    return {
        "settings": resolved.snapshot,
        "provenance": resolved.provenance,
        "fingerprint": resolved.fingerprint,
        "selected_profile": bundle["selected_profile"],
        "persisted_source": bundle["persisted_source"],
        "current_path": str(bundle["resolved_current_path"]),
        "last_known_good_path": str(bundle["resolved_lkg_path"]),
        "snapshot_loaded": bool(bundle["snapshot_env"]),
        "snapshot_path": str(bundle["snapshot_path"]),
        "stats_tags": resolved.metadata.get("stats_tags", {}),
        "metadata": resolved.metadata,
        "governance": bundle.get("governance")
        if isinstance(bundle.get("governance"), dict)
        else build_runtime_settings_governance_payload(bundle),
    }


def collect_runtime_settings_persist_payload(
    *,
    root: str,
    config_file: str,
    mcp_name: str,
    runtime_profile: str | None,
    use_snapshot: bool,
    current_path: str,
    last_known_good_path: str,
    update_last_known_good: bool,
    snapshot_path_fn: Any = mcp_env_snapshot_path,
    load_snapshot_fn: Any = load_mcp_env_snapshot,
) -> dict[str, Any]:
    bundle = resolve_runtime_settings_bundle(
        root=root,
        config_file=config_file,
        mcp_name=mcp_name,
        runtime_profile=runtime_profile,
        use_snapshot=use_snapshot,
        current_path=current_path,
        last_known_good_path=last_known_good_path,
        snapshot_path_fn=snapshot_path_fn,
        load_snapshot_fn=load_snapshot_fn,
    )
    resolved = bundle["resolved"]
    record = build_runtime_settings_record(
        snapshot=resolved.snapshot,
        provenance=resolved.provenance,
        metadata=resolved.metadata,
    )
    persist_runtime_settings_record(
        current_path=bundle["resolved_current_path"],
        last_known_good_path=bundle["resolved_lkg_path"],
        payload=record,
        update_last_known_good=update_last_known_good,
    )
    persisted_bundle = dict(bundle)
    persisted_bundle["persisted_record"] = record
    persisted_bundle["persisted_source"] = "current"
    persisted_bundle["governance"] = build_runtime_settings_governance_payload(
        persisted_bundle
    )
    payload = build_runtime_settings_payload(persisted_bundle)
    payload["persisted_path"] = str(bundle["resolved_current_path"])
    payload["last_known_good_updated"] = bool(update_last_known_good)
    return {
        "ok": True,
        "event": "runtime_settings_persist",
        **payload,
    }


def resolve_effective_runtime_skills_dir(
    settings: dict[str, Any],
    *,
    skills_dir: str = "",
) -> str:
    if skills_dir:
        return str(skills_dir)
    plan = settings.get("plan", {}) if isinstance(settings.get("plan"), dict) else {}
    plan_skills = plan.get("skills", {}) if isinstance(plan.get("skills"), dict) else {}
    return str(plan_skills.get("dir", "skills"))


def collect_runtime_settings_show_payload(
    *,
    root: str,
    config_file: str,
    mcp_name: str,
    runtime_profile: str | None,
    use_snapshot: bool,
    current_path: str,
    last_known_good_path: str,
    snapshot_path_fn: Any = mcp_env_snapshot_path,
    load_snapshot_fn: Any = load_mcp_env_snapshot,
) -> dict[str, Any]:
    bundle = resolve_runtime_settings_bundle(
        root=root,
        config_file=config_file,
        mcp_name=mcp_name,
        runtime_profile=runtime_profile,
        use_snapshot=use_snapshot,
        current_path=current_path,
        last_known_good_path=last_known_good_path,
        snapshot_path_fn=snapshot_path_fn,
        load_snapshot_fn=load_snapshot_fn,
    )
    return {
        "ok": True,
        "event": "runtime_settings_show",
        **build_runtime_settings_payload(bundle),
    }


__all__ = [
    "build_runtime_settings_governance_payload",
    "build_runtime_settings_payload",
    "collect_runtime_settings_persist_payload",
    "collect_runtime_settings_show_payload",
    "evaluate_runtime_memory_state",
    "load_runtime_snapshot",
    "resolve_effective_runtime_skills_dir",
    "resolve_runtime_settings_bundle",
]
