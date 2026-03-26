from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

import ace_lite.workspace.planner as workspace_planner
from ace_lite.workspace.manifest import WorkspaceManifest, WorkspaceRepo
from ace_lite.workspace.summary_index import (
    RepoSummaryV1,
    build_workspace_summary_index_v1,
    save_summary_index_v1,
)
from ace_lite.workspace.planner import build_workspace_plan, route_workspace_repos


def _seed_repo(root: Path, marker: str) -> None:
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "main.py").write_text(
        f"def {marker}() -> str:\n    return '{marker}'\n",
        encoding="utf-8",
    )


def _write_manifest(tmp_path: Path) -> Path:
    _seed_repo(tmp_path / "repos" / "billing-api", "billing")
    _seed_repo(tmp_path / "repos" / "frontend-ui", "frontend")
    _seed_repo(tmp_path / "repos" / "ops-observability", "ops")

    manifest = tmp_path / "workspace.yaml"
    manifest.write_text(
        "\n".join(
            [
                "workspace:",
                "  name: Demo Hub",
                "repos:",
                "  - name: billing-api",
                "    path: repos/billing-api",
                "    description: billing invoices payment",
                "  - name: frontend-ui",
                "    path: repos/frontend-ui",
                "    description: checkout ui",
                "  - name: ops-observability",
                "    path: repos/ops-observability",
                "    description: traces alerts",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return manifest


def test_route_workspace_repos_orders_query_relevant_repos(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    ranked = route_workspace_repos(
        query="billing invoice payment",
        manifest=manifest,
        top_k=2,
    )
    assert [item.name for item in ranked] == ["billing-api", "frontend-ui"]


def test_build_workspace_plan_repo_scope_filters_selected_repos(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    payload = build_workspace_plan(
        query="billing checkout",
        manifest=manifest,
        top_k_repos=3,
        repo_scope=["billing-api", "frontend-ui"],
        languages="python",
    )
    names = [item["name"] for item in payload["selected_repos"]]
    assert set(names) <= {"billing-api", "frontend-ui"}
    assert "ops-observability" not in names


def test_build_workspace_plan_unknown_repo_scope_raises(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    with pytest.raises(ValueError, match="unknown repo names in repo_scope"):
        build_workspace_plan(
            query="billing",
            manifest=manifest,
            top_k_repos=2,
            repo_scope=["billing-api", "missing-repo"],
            languages="python",
        )


def test_build_workspace_plan_emits_evidence_contract(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    payload = build_workspace_plan(
        query="billing rollout risk",
        manifest=manifest,
        top_k_repos=2,
        languages="python",
    )
    contract = payload["evidence_contract"]
    assert contract["decision_target"] == "billing rollout risk"
    assert isinstance(contract["candidate_repos"], list)
    assert isinstance(contract["selected_repos"], list)
    assert isinstance(contract["impacted_files_by_repo"], dict)
    assert isinstance(contract["dependency_chain"], list)
    assert isinstance(contract["rollback_points"], list)
    assert isinstance(contract["impacted_symbols"], list)
    assert isinstance(contract["risks"], list)
    assert isinstance(contract["missing_evidence_flags"], list)
    assert 0.0 <= float(contract["confidence"]) <= 1.0


def test_route_workspace_repos_summary_routing_promotes_repo_with_summary_match(
    tmp_path: Path,
) -> None:
    manifest = _write_manifest(tmp_path)
    manifest_payload = workspace_planner.load_workspace_manifest(manifest)
    summary_path = tmp_path / "context-map" / "workspace" / "summary-index.v1.json"
    summary_index = build_workspace_summary_index_v1(
        repo_summaries=[
            RepoSummaryV1(
                name="billing-api",
                root=manifest_payload.repos[0].root,
                file_count=1,
                language_counts={"python": 1},
                top_directories=("src",),
                top_modules=("billing.main",),
                summary_tokens=("payment",),
            ),
            RepoSummaryV1(
                name="frontend-ui",
                root=manifest_payload.repos[1].root,
                file_count=1,
                language_counts={"python": 1},
                top_directories=("src",),
                top_modules=("frontend.main",),
                summary_tokens=("checkout",),
            ),
            RepoSummaryV1(
                name="ops-observability",
                root=manifest_payload.repos[2].root,
                file_count=1,
                language_counts={"python": 1},
                top_directories=("src",),
                top_modules=("ops.main",),
                summary_tokens=("incident", "pager"),
            ),
        ],
        generated_at="2026-03-26T00:00:00+00:00",
    )
    save_summary_index_v1(summary_index=summary_index, path=summary_path)

    baseline = route_workspace_repos(
        query="incident pager",
        manifest=manifest,
        top_k=3,
    )
    routed = route_workspace_repos(
        query="incident pager",
        manifest=manifest,
        top_k=3,
        summary_score_enabled=True,
        summary_index_path=summary_path,
    )

    assert [item.name for item in baseline] == [
        "billing-api",
        "frontend-ui",
        "ops-observability",
    ]
    assert routed[0].name == "ops-observability"
    assert routed[0].matched_summary_terms == ("incident", "pager")
    assert routed[0].summary_terms_preview == ("incident", "pager")
    assert routed[0].summary_score_contribution > 0.0
    assert routed[0].as_dict()["routing_breakdown"]["summary_hits"] == 2


def test_build_workspace_plan_emits_summary_routing_observability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _write_manifest(tmp_path)
    manifest_payload = workspace_planner.load_workspace_manifest(manifest)
    summary_path = tmp_path / "context-map" / "workspace" / "summary-index.v1.json"
    summary_index = build_workspace_summary_index_v1(
        repo_summaries=[
            RepoSummaryV1(
                name="billing-api",
                root=manifest_payload.repos[0].root,
                file_count=1,
                language_counts={"python": 1},
                top_directories=("src",),
                top_modules=("billing.main",),
                summary_tokens=("payment",),
            ),
            RepoSummaryV1(
                name="frontend-ui",
                root=manifest_payload.repos[1].root,
                file_count=1,
                language_counts={"python": 1},
                top_directories=("src",),
                top_modules=("frontend.main",),
                summary_tokens=("checkout",),
            ),
            RepoSummaryV1(
                name="ops-observability",
                root=manifest_payload.repos[2].root,
                file_count=1,
                language_counts={"python": 1},
                top_directories=("src",),
                top_modules=("ops.main",),
                summary_tokens=("incident", "pager"),
            ),
        ],
        generated_at="2026-03-26T00:00:00+00:00",
    )
    save_summary_index_v1(summary_index=summary_index, path=summary_path)

    monkeypatch.setattr(
        workspace_planner,
        "build_plan_quick",
        lambda **kwargs: {"candidate_files": [f"{kwargs['root']}/src/app.py"]},
    )

    payload = build_workspace_plan(
        query="incident pager",
        manifest=manifest,
        top_k_repos=2,
        languages="python",
        summary_score_enabled=True,
        summary_index_path=summary_path,
    )

    assert payload["summary_routing"]["enabled"] is True
    assert payload["summary_routing"]["repo_count_with_summary_tokens"] == 3
    assert payload["summary_routing"]["repo_count_with_summary_matches"] == 1
    assert payload["summary_routing"]["selected_repo_count_with_summary_matches"] == 1
    assert payload["summary_routing"]["promoted_repos"] == ["ops-observability"]
    assert payload["selected_repos"][0]["name"] == "ops-observability"
    assert payload["selected_repos"][0]["matched_summary_terms"] == ["incident", "pager"]
    assert payload["selected_repos"][0]["routing_breakdown"]["summary_hits"] == 2


def test_build_workspace_plan_strict_gate_adds_evidence_validation(
    tmp_path: Path,
) -> None:
    manifest = _write_manifest(tmp_path)
    payload = build_workspace_plan(
        query="billing rollout risk",
        manifest=manifest,
        top_k_repos=2,
        languages="python",
        evidence_strict=True,
        min_confidence=1.0,
        fail_closed=False,
    )

    validation = payload["evidence_validation"]
    assert validation["strict"] is True
    assert validation["fail_closed"] is False
    assert isinstance(validation["violations"], list)
    assert "confidence_below_min_confidence" in validation["violations"]


def test_build_workspace_plan_strict_gate_fail_closed_raises(
    tmp_path: Path,
) -> None:
    manifest = _write_manifest(tmp_path)
    with pytest.raises(
        ValueError,
        match=r"fail_closed=True.*confidence_below_min_confidence",
    ):
        build_workspace_plan(
            query="billing rollout risk",
            manifest=manifest,
            top_k_repos=2,
            languages="python",
            evidence_strict=True,
            min_confidence=1.0,
            fail_closed=True,
        )


def test_build_workspace_plan_fail_closed_enforces_validation_without_strict_flag(
    tmp_path: Path,
) -> None:
    manifest = _write_manifest(tmp_path)
    with pytest.raises(
        ValueError,
        match=r"fail_closed=True.*confidence_below_min_confidence",
    ):
        build_workspace_plan(
            query="billing rollout risk",
            manifest=manifest,
            top_k_repos=2,
            languages="python",
            evidence_strict=False,
            min_confidence=1.0,
            fail_closed=True,
        )


def _workspace_manifest_payload(tmp_path: Path) -> WorkspaceManifest:
    repo_root = tmp_path / "repos" / "billing-api"
    _seed_repo(repo_root, "billing")
    return WorkspaceManifest(
        manifest_path=str(tmp_path / "workspace.yaml"),
        workspace_name="Demo Hub",
        defaults={"summary_ttl_seconds": 3600},
        repos=(
            WorkspaceRepo(
                name="billing-api",
                root=str(repo_root.resolve()),
                description="billing invoices payment",
                tags=(),
                weight=1.0,
                plan_quick={},
            ),
        ),
    )


def _write_summary_index(
    *,
    summary_path: Path,
    generated_at: str,
    summary_tokens: tuple[str, ...],
    repo_root: str,
) -> None:
    summary = RepoSummaryV1(
        name="billing-api",
        root=repo_root,
        file_count=1,
        language_counts={"python": 1},
        top_directories=("src",),
        top_modules=("main",),
        summary_tokens=summary_tokens,
    )
    summary_index = build_workspace_summary_index_v1(
        repo_summaries=[summary],
        generated_at=generated_at,
    )
    save_summary_index_v1(summary_index=summary_index, path=summary_path)


def test_summarize_workspace_reuses_fresh_summary_within_ttl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_payload = _workspace_manifest_payload(tmp_path)
    summary_path = tmp_path / "context-map" / "workspace" / "summary-index.v1.json"
    _write_summary_index(
        summary_path=summary_path,
        generated_at="2099-01-01T00:00:00+00:00",
        summary_tokens=("billing", "invoice"),
        repo_root=manifest_payload.repos[0].root,
    )

    def _unexpected_rebuild(**_: object) -> RepoSummaryV1:
        raise AssertionError("fresh summary should be reused instead of rebuilt")

    monkeypatch.setattr(workspace_planner, "build_repo_summary_v1", _unexpected_rebuild)

    payload = workspace_planner.summarize_workspace(
        manifest=manifest_payload,
        languages="python",
        summary_index_path=summary_path,
    )

    assert payload["artifacts"]["summary"] == str(summary_path.resolve())
    assert payload["repos"][0]["summary_tokens"] == ["billing", "invoice"]


def test_summarize_workspace_rebuilds_stale_summary_outside_ttl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_payload = _workspace_manifest_payload(tmp_path)
    summary_path = tmp_path / "context-map" / "workspace" / "summary-index.v1.json"
    stale_generated_at = "2000-01-01T00:00:00+00:00"
    _write_summary_index(
        summary_path=summary_path,
        generated_at=stale_generated_at,
        summary_tokens=("old",),
        repo_root=manifest_payload.repos[0].root,
    )

    rebuild_calls: list[str] = []

    def _fake_rebuild(**kwargs: object) -> RepoSummaryV1:
        rebuild_calls.append(str(kwargs["repo_name"]))
        return RepoSummaryV1(
            name=str(kwargs["repo_name"]),
            root=str(kwargs["repo_root"]),
            file_count=2,
            language_counts={"python": 2},
            top_directories=("src",),
            top_modules=("billing.main",),
            summary_tokens=("rebuilt",),
        )

    monkeypatch.setattr(workspace_planner, "build_repo_summary_v1", _fake_rebuild)

    payload = workspace_planner.summarize_workspace(
        manifest=manifest_payload,
        languages="python",
        summary_index_path=summary_path,
    )

    assert rebuild_calls == ["billing-api"]
    assert payload["repos"][0]["summary_tokens"] == ["rebuilt"]
    assert payload["summary_index"]["generated_at"] != stale_generated_at
    parsed = datetime.fromisoformat(payload["summary_index"]["generated_at"])
    assert parsed.tzinfo is not None
    assert parsed >= datetime(2000, 1, 1, tzinfo=timezone.utc)


def test_summarize_workspace_ttl_policy_keeps_cold_not_lower_than_warm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_payload = _workspace_manifest_payload(tmp_path)

    def _fake_rebuild(**kwargs: object) -> RepoSummaryV1:
        return RepoSummaryV1(
            name=str(kwargs["repo_name"]),
            root=str(kwargs["repo_root"]),
            file_count=1,
            language_counts={"python": 1},
            top_directories=("src",),
            top_modules=("billing.main",),
            summary_tokens=("rebuilt",),
            temperature="warm",
            refreshed_at="2026-03-05T00:00:00+00:00",
        )

    monkeypatch.setattr(workspace_planner, "build_repo_summary_v1", _fake_rebuild)

    payload = workspace_planner.summarize_workspace(
        manifest=manifest_payload,
        languages="python",
        summary_ttl_seconds=100,
        summary_ttl_warm_seconds=900,
        summary_ttl_cold_seconds=None,
    )

    ttl = payload["refresh_policy"]["ttl_seconds_by_temperature"]
    assert int(ttl["cold"]) >= int(ttl["warm"])
