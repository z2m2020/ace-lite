from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.plan_quick import build_plan_quick
from ace_lite.workspace.common import tokenize as _tokenize
from ace_lite.workspace.evidence import (
    build_workspace_evidence_contract_v1,
    validate_workspace_evidence_contract_v1,
)
from ace_lite.workspace.manifest import WorkspaceManifest, WorkspaceRepo, load_workspace_manifest
from ace_lite.workspace.summary_index import (
    SUMMARY_INDEX_V1_VERSION,
    SUMMARY_TEMPERATURE_TIERS,
    RepoSummaryV1,
    build_repo_summary_v1,
    build_repo_summary_v1_from_index_cache,
    build_workspace_summary_index_v1,
    load_summary_index_v1,
    save_summary_index_v1,
    summary_tokens_for_repo,
)

DEFAULT_WORKSPACE_LANGUAGES = (
    "python,typescript,javascript,go,solidity,rust,java,c,cpp,c_sharp,ruby,php,markdown"
)
DEFAULT_SUMMARY_TTL_SECONDS = 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class WorkspaceRepoCandidate:
    name: str
    root: str
    score: float
    rationale: str
    matched_terms: tuple[str, ...]
    matched_name_terms: tuple[str, ...] = ()
    matched_context_terms: tuple[str, ...] = ()
    matched_summary_terms: tuple[str, ...] = ()
    summary_terms_preview: tuple[str, ...] = ()
    base_weight: float = 0.0
    name_hits: int = 0
    context_hits: int = 0
    summary_hits: int = 0
    summary_score_contribution: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "root": self.root,
            "score": float(self.score),
            "rationale": self.rationale,
            "matched_terms": list(self.matched_terms),
            "matched_name_terms": list(self.matched_name_terms),
            "matched_context_terms": list(self.matched_context_terms),
            "matched_summary_terms": list(self.matched_summary_terms),
            "summary_terms_preview": list(self.summary_terms_preview),
            "routing_breakdown": {
                "base_weight": float(self.base_weight),
                "name_hits": int(self.name_hits),
                "context_hits": int(self.context_hits),
                "summary_hits": int(self.summary_hits),
                "summary_score_contribution": float(self.summary_score_contribution),
            },
        }


def _ensure_manifest(manifest: WorkspaceManifest | str | Path) -> WorkspaceManifest:
    if isinstance(manifest, WorkspaceManifest):
        return manifest
    return load_workspace_manifest(manifest)


def _coerce_positive_ttl_seconds(*, value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{context} must be an integer")
    if value <= 0:
        raise ValueError(f"{context} must be > 0")
    return int(value)


def _resolve_ttl_policy_seconds(
    *,
    summary_ttl_seconds: int,
    summary_ttl_hot_seconds: int | None,
    summary_ttl_warm_seconds: int | None,
    summary_ttl_cold_seconds: int | None,
) -> dict[str, int]:
    base_ttl = _coerce_positive_ttl_seconds(
        value=summary_ttl_seconds,
        context="summary_ttl_seconds",
    )
    policy = {
        "hot": max(1, int(base_ttl // 2)),
        "warm": int(base_ttl),
        "cold": max(int(base_ttl), int(base_ttl * 3)),
    }
    overrides = {
        "hot": summary_ttl_hot_seconds,
        "warm": summary_ttl_warm_seconds,
        "cold": summary_ttl_cold_seconds,
    }
    for tier, override in overrides.items():
        if override is None:
            continue
        policy[tier] = _coerce_positive_ttl_seconds(
            value=override,
            context=f"summary_ttl_{tier}_seconds",
        )
    policy["cold"] = max(int(policy["cold"]), int(policy["warm"]))
    return policy


def _derive_repo_temperature(tags: tuple[str, ...]) -> str:
    seen: set[str] = set()
    for raw_tag in tags:
        tag = str(raw_tag).strip().lower()
        if not tag:
            continue
        if tag in SUMMARY_TEMPERATURE_TIERS:
            seen.add(tag)
            continue
        for separator in (":", "/", "=", "."):
            if separator not in tag:
                continue
            prefix, suffix = tag.rsplit(separator, 1)
            if prefix in {"temp", "temperature", "tier"} and suffix in SUMMARY_TEMPERATURE_TIERS:
                seen.add(suffix)
                break
    for tier in SUMMARY_TEMPERATURE_TIERS:
        if tier in seen:
            return tier
    return "warm"


def _parse_iso8601_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_summary_entry_fresh(
    *,
    repo: WorkspaceRepo,
    entry: RepoSummaryV1,
    index_generated_at: str | None,
    now_utc: datetime,
    ttl_seconds: int,
) -> bool:
    if entry.root != repo.root:
        return False
    reference_time = _parse_iso8601_timestamp(entry.refreshed_at) or _parse_iso8601_timestamp(index_generated_at)
    if reference_time is None:
        return False
    age_seconds = max(0.0, float((now_utc - reference_time).total_seconds()))
    return age_seconds <= float(ttl_seconds)


def _normalize_repo_scope(
    *,
    repo_scope: list[str] | tuple[str, ...] | None,
    repos: tuple[WorkspaceRepo, ...],
) -> tuple[str, ...] | None:
    if repo_scope is None:
        return None
    if not isinstance(repo_scope, (list, tuple, set)):
        raise ValueError("repo_scope must be a list of repo names")
    if not repo_scope:
        raise ValueError("repo_scope cannot be empty")

    known_names = {repo.name for repo in repos}
    normalized: list[str] = []
    seen: set[str] = set()
    unknown: set[str] = set()

    for index, raw in enumerate(repo_scope):
        if not isinstance(raw, str):
            raise ValueError(f"repo_scope[{index}] must be a string")
        name = raw.strip()
        if not name:
            raise ValueError(f"repo_scope[{index}] cannot be empty")
        if name not in known_names:
            unknown.add(name)
            continue
        if name in seen:
            continue
        seen.add(name)
        normalized.append(name)

    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"unknown repo names in repo_scope: {names}")
    if not normalized:
        raise ValueError("repo_scope resolved to an empty repo set")
    return tuple(sorted(normalized))


def _resolve_repos_for_routing(
    *,
    repos: tuple[WorkspaceRepo, ...],
    repo_scope: tuple[str, ...] | None,
) -> tuple[WorkspaceRepo, ...]:
    if repo_scope is None:
        return repos
    scope_names = set(repo_scope)
    filtered = tuple(repo for repo in repos if repo.name in scope_names)
    if not filtered:
        raise ValueError("repo_scope resolved to an empty repo set")
    return filtered


def _score_repo(
    *,
    query_terms: tuple[str, ...],
    repo: WorkspaceRepo,
    summary_terms: tuple[str, ...] = (),
    summary_score_weight: float = 0.0,
) -> WorkspaceRepoCandidate:
    name_blob = repo.name.lower()
    context_blob = " ".join([repo.description.lower(), " ".join(repo.tags)])
    summary_blob = set(summary_terms)

    matched_name_set = {term for term in query_terms if term in name_blob}
    matched_context_set = {term for term in query_terms if term in context_blob}
    matched_summary_set = {term for term in query_terms if term in summary_blob}
    matched_name = tuple(sorted(matched_name_set))
    matched_context = tuple(sorted(matched_context_set))
    matched_summary = tuple(sorted(matched_summary_set))
    matched_terms = tuple(sorted(matched_name_set | matched_context_set | matched_summary_set))

    name_hits = len(matched_name)
    context_only = matched_context_set - matched_name_set
    summary_only = matched_summary_set - matched_name_set - matched_context_set
    context_hits = len(context_only)
    summary_hits = len(summary_only)

    base_weight = float(repo.weight)
    score = base_weight + float(name_hits) * 2.0 + float(context_hits)
    summary_score_contribution = 0.0
    if summary_hits > 0 and summary_score_weight > 0.0:
        summary_score_contribution = float(summary_hits) * float(summary_score_weight)
        score += summary_score_contribution

    if matched_terms:
        rationale = (
            f"weight={repo.weight:.3f}, name_hits={name_hits}, "
            f"context_hits={context_hits}, summary_hits={summary_hits}, "
            f"terms={', '.join(matched_terms)}"
        )
    else:
        rationale = (
            f"weight={repo.weight:.3f}, name_hits={name_hits}, "
            f"context_hits={context_hits}, summary_hits={summary_hits}, no query term overlap"
        )

    return WorkspaceRepoCandidate(
        name=repo.name,
        root=repo.root,
        score=score,
        rationale=rationale,
        matched_terms=matched_terms,
        matched_name_terms=matched_name,
        matched_context_terms=tuple(sorted(context_only)),
        matched_summary_terms=tuple(sorted(summary_only)),
        summary_terms_preview=tuple(summary_terms[:12]),
        base_weight=base_weight,
        name_hits=name_hits,
        context_hits=context_hits,
        summary_hits=summary_hits,
        summary_score_contribution=summary_score_contribution,
    )


def _build_summary_routing_observability(
    *,
    enabled: bool,
    selected: list[WorkspaceRepoCandidate],
    all_candidates: list[WorkspaceRepoCandidate],
    baseline_candidates: list[WorkspaceRepoCandidate] | None = None,
) -> dict[str, Any]:
    candidate_order = {
        candidate.name: index + 1 for index, candidate in enumerate(all_candidates)
    }
    baseline_order = {
        candidate.name: index + 1
        for index, candidate in enumerate(baseline_candidates or [])
    }

    repos_with_summary_tokens = [
        candidate.name for candidate in all_candidates if candidate.summary_terms_preview
    ]
    matched_repos = [
        candidate.name for candidate in all_candidates if candidate.matched_summary_terms
    ]
    selected_matched_repos = [
        candidate.name for candidate in selected if candidate.matched_summary_terms
    ]
    promoted_repos: list[str] = []
    for candidate in all_candidates:
        if not candidate.matched_summary_terms:
            continue
        before = baseline_order.get(candidate.name)
        after = candidate_order.get(candidate.name)
        if before is None or after is None:
            continue
        if after < before:
            promoted_repos.append(candidate.name)

    return {
        "enabled": bool(enabled),
        "repo_count_with_summary_tokens": len(repos_with_summary_tokens),
        "repo_count_with_summary_matches": len(matched_repos),
        "selected_repo_count_with_summary_matches": len(selected_matched_repos),
        "repos_with_summary_tokens": repos_with_summary_tokens,
        "matched_repos": matched_repos,
        "selected_matched_repos": selected_matched_repos,
        "promoted_repo_count": len(promoted_repos),
        "promoted_repos": promoted_repos,
    }


def _resolve_repo_option(
    *,
    key: str,
    explicit: Any,
    repo: WorkspaceRepo,
    manifest: WorkspaceManifest,
    fallback: Any,
) -> Any:
    if explicit is not None:
        return explicit
    if key in repo.plan_quick:
        return repo.plan_quick[key]
    if key in manifest.defaults:
        return manifest.defaults[key]
    return fallback


def _resolve_repo_index_cache_path(
    *,
    repo: WorkspaceRepo,
    manifest: WorkspaceManifest,
    explicit_index_cache_path: str | None,
) -> Path:
    option = _resolve_repo_option(
        key="index_cache_path",
        explicit=explicit_index_cache_path,
        repo=repo,
        manifest=manifest,
        fallback="context-map/index.json",
    )
    cache_path = Path(str(option)).expanduser()
    if not cache_path.is_absolute():
        cache_path = Path(repo.root) / cache_path
    return cache_path.resolve()


def _load_summary_tokens_by_repo(
    *,
    repos: tuple[WorkspaceRepo, ...],
    manifest: WorkspaceManifest,
    summary_index_path: str | Path | None,
    explicit_index_cache_path: str | None,
    summary_token_limit: int,
) -> dict[str, tuple[str, ...]]:
    tokens_by_repo: dict[str, tuple[str, ...]] = {}

    if summary_index_path is not None:
        try:
            summary_index = load_summary_index_v1(summary_index_path)
        except ValueError:
            summary_index = None
        if summary_index is not None:
            for repo in repos:
                tokens = summary_tokens_for_repo(summary_index=summary_index, repo_name=repo.name)
                if tokens:
                    tokens_by_repo[repo.name] = tokens

    for repo in repos:
        if repo.name in tokens_by_repo:
            continue
        cache_path = _resolve_repo_index_cache_path(
            repo=repo,
            manifest=manifest,
            explicit_index_cache_path=explicit_index_cache_path,
        )
        try:
            summary = build_repo_summary_v1_from_index_cache(
                repo_name=repo.name,
                repo_root=repo.root,
                index_cache_path=cache_path,
                token_limit=summary_token_limit,
            )
        except ValueError:
            continue
        if summary.summary_tokens:
            tokens_by_repo[repo.name] = summary.summary_tokens

    return tokens_by_repo


def route_workspace_repos(
    *,
    query: str,
    manifest: WorkspaceManifest | str | Path,
    top_k: int = 3,
    repo_scope: list[str] | tuple[str, ...] | None = None,
    summary_score_enabled: bool = False,
    summary_index_path: str | Path | None = None,
    summary_score_weight: float = 0.5,
    summary_token_limit: int = 64,
    index_cache_path: str | None = None,
) -> list[WorkspaceRepoCandidate]:
    normalized_query = str(query or "").strip()
    if not normalized_query:
        raise ValueError("query cannot be empty")

    if top_k <= 0:
        raise ValueError("top_k must be > 0")
    if summary_score_weight < 0.0:
        raise ValueError("summary_score_weight must be >= 0")
    if summary_token_limit <= 0:
        raise ValueError("summary_token_limit must be > 0")

    manifest_payload = _ensure_manifest(manifest)
    normalized_scope = _normalize_repo_scope(
        repo_scope=repo_scope,
        repos=manifest_payload.repos,
    )
    repos_for_routing = _resolve_repos_for_routing(
        repos=manifest_payload.repos,
        repo_scope=normalized_scope,
    )
    query_terms = _tokenize(normalized_query)

    summary_tokens_by_repo: dict[str, tuple[str, ...]] = {}
    if summary_score_enabled:
        summary_tokens_by_repo = _load_summary_tokens_by_repo(
            repos=repos_for_routing,
            manifest=manifest_payload,
            summary_index_path=summary_index_path,
            explicit_index_cache_path=index_cache_path,
            summary_token_limit=summary_token_limit,
        )

    candidates = [
        _score_repo(
            query_terms=query_terms,
            repo=repo,
            summary_terms=summary_tokens_by_repo.get(repo.name, ()),
            summary_score_weight=summary_score_weight if summary_score_enabled else 0.0,
        )
        for repo in repos_for_routing
    ]
    candidates.sort(key=lambda item: (-item.score, item.name))
    return candidates[:top_k]


def build_workspace_plan(
    *,
    query: str,
    manifest: WorkspaceManifest | str | Path,
    top_k_repos: int = 3,
    repo_scope: list[str] | tuple[str, ...] | None = None,
    languages: str | None = None,
    top_k_files: int | None = None,
    repomap_top_k: int | None = None,
    candidate_ranker: str | None = None,
    index_cache_path: str | None = None,
    index_incremental: bool | None = None,
    repomap_expand: bool | None = None,
    repomap_neighbor_limit: int | None = None,
    repomap_neighbor_depth: int | None = None,
    budget_tokens: int | None = None,
    ranking_profile: str | None = None,
    include_rows: bool | None = None,
    tokenizer_model: str | None = None,
    summary_score_enabled: bool = False,
    summary_index_path: str | Path | None = None,
    summary_score_weight: float = 0.5,
    summary_token_limit: int = 64,
    evidence_strict: bool = False,
    min_confidence: float = 0.85,
    fail_closed: bool = False,
) -> dict[str, Any]:
    if top_k_repos <= 0:
        raise ValueError("top_k_repos must be > 0")

    manifest_payload = _ensure_manifest(manifest)
    normalized_scope = _normalize_repo_scope(
        repo_scope=repo_scope,
        repos=manifest_payload.repos,
    )

    all_candidates = route_workspace_repos(
        query=query,
        manifest=manifest_payload,
        top_k=max(top_k_repos, len(manifest_payload.repos)),
        repo_scope=normalized_scope,
        summary_score_enabled=summary_score_enabled,
        summary_index_path=summary_index_path,
        summary_score_weight=summary_score_weight,
        summary_token_limit=summary_token_limit,
        index_cache_path=index_cache_path,
    )
    selected = all_candidates[:top_k_repos]
    summary_routing = _build_summary_routing_observability(
        enabled=bool(summary_score_enabled),
        selected=selected,
        all_candidates=all_candidates,
        baseline_candidates=(
            route_workspace_repos(
                query=query,
                manifest=manifest_payload,
                top_k=max(top_k_repos, len(manifest_payload.repos)),
                repo_scope=normalized_scope,
                summary_score_enabled=False,
                summary_index_path=summary_index_path,
                summary_score_weight=summary_score_weight,
                summary_token_limit=summary_token_limit,
                index_cache_path=index_cache_path,
            )
            if summary_score_enabled
            else None
        ),
    )

    repo_by_name = {repo.name: repo for repo in manifest_payload.repos}
    routed_payload: list[dict[str, Any]] = []

    for candidate in selected:
        repo = repo_by_name[candidate.name]
        quick_languages = _resolve_repo_option(
            key="languages",
            explicit=languages,
            repo=repo,
            manifest=manifest_payload,
            fallback=DEFAULT_WORKSPACE_LANGUAGES,
        )
        quick_plan = build_plan_quick(
            query=str(query).strip(),
            root=repo.root,
            languages=str(quick_languages),
            top_k_files=int(
                _resolve_repo_option(
                    key="top_k_files",
                    explicit=top_k_files,
                    repo=repo,
                    manifest=manifest_payload,
                    fallback=8,
                )
            ),
            repomap_top_k=int(
                _resolve_repo_option(
                    key="repomap_top_k",
                    explicit=repomap_top_k,
                    repo=repo,
                    manifest=manifest_payload,
                    fallback=24,
                )
            ),
            candidate_ranker=str(
                _resolve_repo_option(
                    key="candidate_ranker",
                    explicit=candidate_ranker,
                    repo=repo,
                    manifest=manifest_payload,
                    fallback="rrf_hybrid",
                )
            ),
            index_cache_path=str(
                _resolve_repo_option(
                    key="index_cache_path",
                    explicit=index_cache_path,
                    repo=repo,
                    manifest=manifest_payload,
                    fallback="context-map/index.json",
                )
            ),
            index_incremental=bool(
                _resolve_repo_option(
                    key="index_incremental",
                    explicit=index_incremental,
                    repo=repo,
                    manifest=manifest_payload,
                    fallback=True,
                )
            ),
            repomap_expand=bool(
                _resolve_repo_option(
                    key="repomap_expand",
                    explicit=repomap_expand,
                    repo=repo,
                    manifest=manifest_payload,
                    fallback=False,
                )
            ),
            repomap_neighbor_limit=int(
                _resolve_repo_option(
                    key="repomap_neighbor_limit",
                    explicit=repomap_neighbor_limit,
                    repo=repo,
                    manifest=manifest_payload,
                    fallback=20,
                )
            ),
            repomap_neighbor_depth=int(
                _resolve_repo_option(
                    key="repomap_neighbor_depth",
                    explicit=repomap_neighbor_depth,
                    repo=repo,
                    manifest=manifest_payload,
                    fallback=1,
                )
            ),
            budget_tokens=int(
                _resolve_repo_option(
                    key="budget_tokens",
                    explicit=budget_tokens,
                    repo=repo,
                    manifest=manifest_payload,
                    fallback=800,
                )
            ),
            ranking_profile=str(
                _resolve_repo_option(
                    key="ranking_profile",
                    explicit=ranking_profile,
                    repo=repo,
                    manifest=manifest_payload,
                    fallback="graph",
                )
            ),
            include_rows=bool(
                _resolve_repo_option(
                    key="include_rows",
                    explicit=include_rows,
                    repo=repo,
                    manifest=manifest_payload,
                    fallback=False,
                )
            ),
            tokenizer_model=_resolve_repo_option(
                key="tokenizer_model",
                explicit=tokenizer_model,
                repo=repo,
                manifest=manifest_payload,
                fallback=None,
            ),
        )

        routed_payload.append(
            {
                "name": repo.name,
                "root": repo.root,
                "score": float(candidate.score),
                "rationale": candidate.rationale,
                "matched_terms": list(candidate.matched_terms),
                "matched_name_terms": list(candidate.matched_name_terms),
                "matched_context_terms": list(candidate.matched_context_terms),
                "matched_summary_terms": list(candidate.matched_summary_terms),
                "summary_terms_preview": list(candidate.summary_terms_preview),
                "routing_breakdown": {
                    "base_weight": float(candidate.base_weight),
                    "name_hits": int(candidate.name_hits),
                    "context_hits": int(candidate.context_hits),
                    "summary_hits": int(candidate.summary_hits),
                    "summary_score_contribution": float(
                        candidate.summary_score_contribution
                    ),
                },
                "quick_plan": quick_plan,
            }
        )

    candidate_payload = [candidate.as_dict() for candidate in all_candidates]
    evidence_contract = build_workspace_evidence_contract_v1(
        decision_target=str(query).strip(),
        candidate_repos=candidate_payload,
        selected_repos=routed_payload,
    )
    evidence_contract_payload = evidence_contract.as_dict()
    evidence_validation: dict[str, Any] | None = None
    should_validate_evidence = bool(evidence_strict) or bool(fail_closed)
    if should_validate_evidence:
        evidence_validation = validate_workspace_evidence_contract_v1(
            contract=evidence_contract_payload,
            strict=bool(evidence_strict) or bool(fail_closed),
            min_confidence=min_confidence,
            fail_closed=bool(fail_closed),
        )
        if bool(fail_closed) and not bool(evidence_validation.get("ok")):
            violations_raw = evidence_validation.get("violations", [])
            key_violation = (
                str(violations_raw[0])
                if isinstance(violations_raw, list) and violations_raw
                else "unknown_violation"
            )
            raise ValueError(
                f"evidence validation failed: fail_closed=True, violation={key_violation}"
            )

    payload = {
        "query": str(query).strip(),
        "workspace": {
            "name": manifest_payload.workspace_name,
            "manifest_path": manifest_payload.manifest_path,
            "repo_count": len(manifest_payload.repos),
        },
        "top_k_repos": int(top_k_repos),
        "repo_scope": list(normalized_scope or ()),
        "summary_score_enabled": bool(summary_score_enabled),
        "summary_routing": summary_routing,
        "candidate_repos": candidate_payload,
        "selected_repos": routed_payload,
        "evidence_contract": evidence_contract_payload,
    }
    if evidence_validation is not None:
        payload["evidence_validation"] = evidence_validation
    return payload


def summarize_workspace(
    *,
    manifest: WorkspaceManifest | str | Path,
    repo_scope: list[str] | tuple[str, ...] | None = None,
    languages: str | None = None,
    index_cache_path: str | None = None,
    index_incremental: bool | None = None,
    summary_index_path: str | Path | None = None,
    summary_token_limit: int = 64,
    summary_directory_limit: int = 12,
    summary_module_limit: int = 12,
    summary_ttl_seconds: int = DEFAULT_SUMMARY_TTL_SECONDS,
    summary_ttl_hot_seconds: int | None = None,
    summary_ttl_warm_seconds: int | None = None,
    summary_ttl_cold_seconds: int | None = None,
) -> dict[str, Any]:
    if summary_token_limit <= 0:
        raise ValueError("summary_token_limit must be > 0")
    if summary_directory_limit <= 0:
        raise ValueError("summary_directory_limit must be > 0")
    if summary_module_limit <= 0:
        raise ValueError("summary_module_limit must be > 0")
    ttl_policy_seconds = _resolve_ttl_policy_seconds(
        summary_ttl_seconds=summary_ttl_seconds,
        summary_ttl_hot_seconds=summary_ttl_hot_seconds,
        summary_ttl_warm_seconds=summary_ttl_warm_seconds,
        summary_ttl_cold_seconds=summary_ttl_cold_seconds,
    )

    manifest_payload = _ensure_manifest(manifest)
    normalized_scope = _normalize_repo_scope(
        repo_scope=repo_scope,
        repos=manifest_payload.repos,
    )
    repos_for_summary = _resolve_repos_for_routing(
        repos=manifest_payload.repos,
        repo_scope=normalized_scope,
    )

    target_path = Path(summary_index_path).expanduser() if summary_index_path else (
        Path(manifest_payload.manifest_path).parent
        / "context-map"
        / "workspace"
        / "summary-index.v1.json"
    )
    if not target_path.is_absolute():
        target_path = (Path(manifest_payload.manifest_path).parent / target_path).resolve()

    existing_summary_index = None
    try:
        existing_summary_index = load_summary_index_v1(target_path)
    except ValueError:
        existing_summary_index = None
    existing_by_repo = (
        {entry.name: entry for entry in existing_summary_index.repos}
        if existing_summary_index is not None
        else {}
    )
    existing_generated_at = existing_summary_index.generated_at if existing_summary_index is not None else None

    now_utc = datetime.now(timezone.utc)
    run_timestamp = now_utc.isoformat()
    repo_summaries: list[RepoSummaryV1] = []
    reused_count = 0
    rebuilt_count = 0
    for repo in repos_for_summary:
        temperature = _derive_repo_temperature(repo.tags)
        tier_ttl_seconds = ttl_policy_seconds[temperature]
        existing_entry = existing_by_repo.get(repo.name)
        if existing_entry is not None and _is_summary_entry_fresh(
            repo=repo,
            entry=existing_entry,
            index_generated_at=existing_generated_at,
            now_utc=now_utc,
            ttl_seconds=tier_ttl_seconds,
        ):
            reused_refreshed_at = existing_entry.refreshed_at or existing_generated_at or run_timestamp
            reused_entry = existing_entry
            if reused_entry.temperature != temperature or reused_entry.refreshed_at != reused_refreshed_at:
                reused_entry = replace(
                    reused_entry,
                    temperature=temperature,
                    refreshed_at=reused_refreshed_at,
                )
            repo_summaries.append(reused_entry)
            reused_count += 1
            continue

        quick_languages = _resolve_repo_option(
            key="languages",
            explicit=languages,
            repo=repo,
            manifest=manifest_payload,
            fallback=DEFAULT_WORKSPACE_LANGUAGES,
        )
        summary = build_repo_summary_v1(
            repo_name=repo.name,
            repo_root=repo.root,
            languages=str(quick_languages),
            temperature=temperature,
            refreshed_at=run_timestamp,
            index_cache_path=str(
                _resolve_repo_option(
                    key="index_cache_path",
                    explicit=index_cache_path,
                    repo=repo,
                    manifest=manifest_payload,
                    fallback="context-map/index.json",
                )
            ),
            index_incremental=bool(
                _resolve_repo_option(
                    key="index_incremental",
                    explicit=index_incremental,
                    repo=repo,
                    manifest=manifest_payload,
                    fallback=True,
                )
            ),
            token_limit=int(summary_token_limit),
            directory_limit=int(summary_directory_limit),
            module_limit=int(summary_module_limit),
        )
        repo_summaries.append(summary)
        rebuilt_count += 1

    summary_index = build_workspace_summary_index_v1(
        repo_summaries=repo_summaries,
        generated_at=run_timestamp,
    )
    saved_path = save_summary_index_v1(summary_index=summary_index, path=target_path)

    return {
        "workspace": {
            "name": manifest_payload.workspace_name,
            "manifest_path": manifest_payload.manifest_path,
            "repo_count": len(manifest_payload.repos),
            "selected_repo_count": len(repos_for_summary),
        },
        "repo_scope": list(normalized_scope or ()),
        "total_selected": len(repos_for_summary),
        "reused_count": int(reused_count),
        "rebuilt_count": int(rebuilt_count),
        "refresh_policy": {
            "default_ttl_seconds": int(summary_ttl_seconds),
            "ttl_seconds_by_temperature": dict(ttl_policy_seconds),
        },
        "summary_index": {
            "version": SUMMARY_INDEX_V1_VERSION,
            "path": saved_path,
            "repo_count": len(summary_index.repos),
            "generated_at": summary_index.generated_at,
            "total_selected": len(repos_for_summary),
            "reused_count": int(reused_count),
            "rebuilt_count": int(rebuilt_count),
        },
        "repos": [repo_summary.as_dict() for repo_summary in summary_index.repos],
        "artifacts": {
            "summary": saved_path,
            "manifest": manifest_payload.manifest_path,
        },
    }


__all__ = [
    "DEFAULT_WORKSPACE_LANGUAGES",
    "DEFAULT_SUMMARY_TTL_SECONDS",
    "WorkspaceRepoCandidate",
    "build_workspace_plan",
    "route_workspace_repos",
    "summarize_workspace",
]
