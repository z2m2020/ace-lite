from __future__ import annotations

from pathlib import Path
from typing import Any

from ace_lite.vcs_history import collect_git_commit_history


def build_mixed_top_k_candidates(
    *,
    rows: list[Any],
    top_k: int = 8,
    ensure_docs: int = 2,
    ensure_code: int = 2,
) -> list[Any]:
    """Ensure mixed domain coverage in top-k results for design/doc intent queries."""
    if not rows:
        return []

    doc_domains = {"docs", "planning", "reference", "markdown"}
    code_domains = {"code"}
    test_domains = {"tests"}

    docs_rows: list[Any] = []
    code_rows: list[Any] = []
    test_rows: list[Any] = []
    other_rows: list[Any] = []

    for row in rows:
        semantic_domain = str(getattr(row, "semantic_domain", "") or "")
        if semantic_domain in doc_domains:
            docs_rows.append(row)
        elif semantic_domain in code_domains:
            code_rows.append(row)
        elif semantic_domain in test_domains:
            test_rows.append(row)
        else:
            other_rows.append(row)

    mixed: list[Any] = []
    seen_paths: set[str] = set()

    for row in docs_rows[:ensure_docs]:
        path = str(getattr(row, "path", "") or "")
        if path and path not in seen_paths:
            mixed.append(row)
            seen_paths.add(path)

    for row in code_rows[:ensure_code]:
        path = str(getattr(row, "path", "") or "")
        if path and path not in seen_paths:
            mixed.append(row)
            seen_paths.add(path)

    for row in rows:
        path = str(getattr(row, "path", "") or "")
        if path and path not in seen_paths and len(mixed) < top_k:
            mixed.append(row)
            seen_paths.add(path)

    return mixed[:top_k]


def _normalize_path(path: str) -> str:
    return str(path or "").strip().replace("\\", "/").lower()


def build_history_summary(*, root: Path, candidate_paths: list[str]) -> dict[str, Any]:
    normalized_paths: list[str] = []
    for raw_path in candidate_paths:
        path = _normalize_path(raw_path)
        if path and path not in normalized_paths:
            normalized_paths.append(path)

    summary: dict[str, Any] = {
        "enabled": False,
        "reason": "no_candidate_paths",
        "path_count": len(normalized_paths),
        "commit_count": 0,
        "top_paths": [],
        "top_commits": [],
        "path_hits": {},
        "error": None,
    }
    if not normalized_paths:
        return summary

    payload = collect_git_commit_history(
        repo_root=root,
        paths=normalized_paths,
        limit=max(8, min(24, len(normalized_paths) * 2)),
    )
    if not isinstance(payload, dict):
        summary["enabled"] = True
        summary["reason"] = "invalid_history_payload"
        summary["error"] = "invalid_history_payload"
        return summary

    summary["enabled"] = bool(payload.get("enabled", False))
    summary["reason"] = str(payload.get("reason") or "unknown")
    summary["commit_count"] = max(0, int(payload.get("commit_count", 0) or 0))
    summary["error"] = payload.get("error")

    commits = payload.get("commits", [])
    if not isinstance(commits, list) or not commits:
        return summary

    path_hits: dict[str, dict[str, Any]] = {}
    top_commits: list[dict[str, Any]] = []
    for commit in commits:
        if not isinstance(commit, dict):
            continue
        matched_files: list[str] = []
        for raw_path in commit.get("files", []):
            path = _normalize_path(str(raw_path or ""))
            if not path or path not in normalized_paths:
                continue
            matched_files.append(path)
            bucket = path_hits.setdefault(
                path,
                {
                    "commit_count": 0,
                    "latest_committed_at": "",
                    "recent_subject": "",
                },
            )
            bucket["commit_count"] = int(bucket.get("commit_count", 0) or 0) + 1
            if not str(bucket.get("latest_committed_at") or "").strip():
                bucket["latest_committed_at"] = str(commit.get("committed_at") or "")
                bucket["recent_subject"] = str(commit.get("subject") or "")
        if matched_files:
            top_commits.append(
                {
                    "hash": str(commit.get("hash") or ""),
                    "subject": str(commit.get("subject") or ""),
                    "committed_at": str(commit.get("committed_at") or ""),
                    "matched_files": matched_files[:6],
                }
            )

    summary["path_hits"] = path_hits
    summary["top_paths"] = [
        {
            "path": path,
            "commit_count": int(item.get("commit_count", 0) or 0),
            "latest_committed_at": str(item.get("latest_committed_at") or ""),
            "recent_subject": str(item.get("recent_subject") or ""),
        }
        for path, item in sorted(
            path_hits.items(),
            key=lambda pair: (
                -int(pair[1].get("commit_count", 0) or 0),
                str(pair[0]),
            ),
        )[:8]
    ]
    summary["top_commits"] = top_commits[:6]
    return summary


def _build_picked_because(*, row: Any, query_flags: dict[str, Any]) -> str:
    reasons: list[str] = []

    if bool(query_flags.get("has_req_id", False)) and query_flags.get("req_ids"):
        req_ids_raw: Any = query_flags.get("req_ids", [])
        req_ids: list[str] = (
            [str(item) for item in req_ids_raw if str(item).strip()]
            if isinstance(req_ids_raw, list)
            else []
        )
        normalized_path = str(getattr(row, "path", "") or "").lower()
        for req_id in req_ids:
            if str(req_id).lower() in normalized_path:
                reasons.append(f"ID match ({req_id})")
                break

    if int(getattr(row, "lexical_hits", 0) or 0) > 0:
        reasons.append("lexical match")

    if float(getattr(row, "intent_boost", 0.0) or 0.0) > 0:
        semantic_domain = str(getattr(row, "semantic_domain", "") or "")
        if semantic_domain in {"planning", "docs"}:
            reasons.append("planning domain")
        else:
            reasons.append("intent boost")

    if float(getattr(row, "recency_boost", 0.0) or 0.0) > 0:
        reasons.append("recency")

    role = str(getattr(row, "role", "") or "")
    if role == "entrypoint":
        reasons.append("entrypoint")
    elif role == "public_contract":
        reasons.append("public contract")
    elif role == "test_entry":
        reasons.append("test lock")

    semantic_domain = str(getattr(row, "semantic_domain", "") or "")
    if (
        bool(query_flags.get("doc_sync", False))
        and semantic_domain in {"planning", "docs", "reference"}
        and "planning domain" not in reasons
    ):
        reasons.append("domain match")

    if not reasons:
        reasons.append("fused score")

    return " + ".join(reasons[:3])


def build_candidate_details(
    rows: list[Any],
    *,
    query_flags: dict[str, Any] | None = None,
    history_summary: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    effective_query_flags = dict(query_flags or {})
    history_hits = (
        history_summary.get("path_hits", {})
        if isinstance(history_summary, dict)
        and isinstance(history_summary.get("path_hits"), dict)
        else {}
    )
    details: list[dict[str, Any]] = []
    for row in rows:
        label_list = [str(label) for label in getattr(row, "labels", ())]
        role = str(getattr(row, "role", "") or "")
        if role and role not in label_list:
            label_list.append(role)
        path = str(getattr(row, "path", "") or "")
        history_hit = history_hits.get(path, {}) if path else {}
        semantic_domain = str(getattr(row, "semantic_domain", "") or "")
        details.append(
            {
                "path": path,
                "module": str(getattr(row, "module", "") or ""),
                "language": str(getattr(row, "language", "") or ""),
                "semantic_domain": semantic_domain,
                "labels": label_list,
                "role": role,
                "why": f"role:{role};domain:{semantic_domain}",
                "picked_because": _build_picked_because(
                    row=row,
                    query_flags=effective_query_flags,
                ),
                "history": {
                    "commit_count": int(history_hit.get("commit_count", 0) or 0),
                    "latest_committed_at": str(
                        history_hit.get("latest_committed_at") or ""
                    ),
                    "recent_subject": str(history_hit.get("recent_subject") or ""),
                },
            }
        )
    return details


def _first_n_by_role(
    details: list[dict[str, Any]],
    *,
    labels: set[str],
    limit: int,
) -> list[str]:
    selected: list[str] = []
    for item in details:
        item_labels = {str(label).strip() for label in item.get("labels", [])}
        if not item_labels.intersection(labels):
            continue
        path = str(item.get("path") or "").strip()
        if path and path not in selected:
            selected.append(path)
        if len(selected) >= limit:
            break
    return selected


def _build_recommended_read_order(
    details: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    priority_labels = (
        {"entrypoint"},
        {"public_contract"},
        {"evaluation_orchestrator", "runtime_core", "persistence_layer"},
        {"test_entry"},
    )
    for label_group in priority_labels:
        for item in details:
            path = str(item.get("path") or "").strip()
            if not path or path in seen:
                continue
            item_labels = {str(label).strip() for label in item.get("labels", [])}
            if not item_labels.intersection(label_group):
                continue
            ordered.append(
                {
                    "path": path,
                    "role": str(item.get("role") or "").strip(),
                    "labels": list(item.get("labels") or []),
                    "why": str(item.get("why") or "").strip(),
                }
            )
            seen.add(path)
    for item in details:
        path = str(item.get("path") or "").strip()
        if not path or path in seen:
            continue
        ordered.append(
            {
                "path": path,
                "role": str(item.get("role") or "").strip(),
                "labels": list(item.get("labels") or []),
                "why": str(item.get("why") or "").strip(),
            }
        )
        seen.add(path)
    return ordered


def build_onboarding_view(
    *,
    query_flags: dict[str, Any] | None = None,
    details: list[dict[str, Any]],
) -> dict[str, Any]:
    effective_query_flags = dict(query_flags or {})
    recommended_read_order = _build_recommended_read_order(details)
    onboarding = bool(effective_query_flags.get("onboarding", False))
    return {
        "recommended": onboarding,
        "mode": "repository_onboarding" if onboarding else "standard",
        "entrypoints": _first_n_by_role(
            details,
            labels={"entrypoint"},
            limit=3,
        ),
        "public_contracts": _first_n_by_role(
            details,
            labels={"public_contract"},
            limit=3,
        ),
        "runtime_core": _first_n_by_role(
            details,
            labels={"runtime_core", "evaluation_orchestrator", "persistence_layer"},
            limit=4,
        ),
        "tests": _first_n_by_role(
            details,
            labels={"test_entry"},
            limit=3,
        ),
        "recommended_read_order": recommended_read_order[:6],
    }


def _estimate_plan_upgrade_cost_ms_band(
    *,
    index_cache: dict[str, Any],
    unique_domains: int,
    top_k: int,
) -> dict[str, int]:
    if str(index_cache.get("mode") or "").strip() == "full_build":
        return {"min": 14000, "max": 25000}
    if unique_domains >= 3 or top_k >= 6:
        return {"min": 9000, "max": 18000}
    return {"min": 5000, "max": 12000}


def build_upgrade_guidance(
    *,
    query_flags: dict[str, Any] | None = None,
    rows: list[Any],
    candidate_domain_summary: dict[str, Any],
    risk_hints: list[dict[str, Any]],
    index_cache: dict[str, Any],
) -> dict[str, Any]:
    effective_query_flags = dict(query_flags or {})
    unique_domains = int(candidate_domain_summary.get("unique_domains", 0) or 0)
    top_gap = (
        float(getattr(rows[0], "fused_score", 0.0) or 0.0)
        - float(getattr(rows[1], "fused_score", 0.0) or 0.0)
        if len(rows) >= 2
        else 99.0
    )
    high_risk_codes = {
        str(item.get("code") or "").strip()
        for item in risk_hints
        if str(item.get("severity") or "").strip() == "high"
    }
    concentrated = unique_domains <= 2 and top_gap >= 1.5
    onboarding_ready = bool(effective_query_flags.get("onboarding", False)) and any(
        "entrypoint" in getattr(row, "labels", ())
        or "public_contract" in getattr(row, "labels", ())
        for row in rows[:4]
    )

    expected_incremental_value = "medium"
    upgrade_recommended = True
    why_not_plan_yet = ""
    why_upgrade_now = ""

    if concentrated and not high_risk_codes:
        expected_incremental_value = "low"
        upgrade_recommended = False
        why_not_plan_yet = (
            "quick already narrowed the candidate set to a small, high-confidence file list."
        )
    if onboarding_ready and unique_domains <= 3 and not high_risk_codes:
        expected_incremental_value = "low"
        upgrade_recommended = False
        why_not_plan_yet = "This looks like repo onboarding, and quick already grouped entrypoints, contracts, and runtime files."
    elif high_risk_codes or (unique_domains >= 3 and top_gap < 1.5):
        expected_incremental_value = "high" if high_risk_codes else "medium"
        upgrade_recommended = True
        why_upgrade_now = "The shortlist still mixes multiple domains or carries high-risk hints, so full plan should add dependency-level evidence."
    elif upgrade_recommended:
        why_upgrade_now = "Quick has not fully narrowed the reading surface yet, so full plan may add useful dependency and symbol context."

    return {
        "upgrade_recommended": bool(upgrade_recommended),
        "expected_incremental_value": expected_incremental_value,
        "expected_cost_ms_band": _estimate_plan_upgrade_cost_ms_band(
            index_cache=index_cache,
            unique_domains=unique_domains,
            top_k=len(rows),
        ),
        "why_not_plan_yet": why_not_plan_yet,
        "why_upgrade_now": why_upgrade_now,
    }
