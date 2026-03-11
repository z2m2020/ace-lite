from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import ace_lite.workspace.benchmark as workspace_benchmark
from ace_lite.workspace.manifest import WorkspaceManifest, WorkspaceRepo


def _write_cases(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _build_manifest(tmp_path: Path) -> WorkspaceManifest:
    repo_alpha_root = tmp_path / "repos" / "repo-alpha"
    repo_beta_root = tmp_path / "repos" / "repo-beta"
    repo_alpha_root.mkdir(parents=True, exist_ok=True)
    repo_beta_root.mkdir(parents=True, exist_ok=True)
    return WorkspaceManifest(
        manifest_path=str(tmp_path / "workspace.yaml"),
        workspace_name="demo-workspace",
        defaults={},
        repos=(
            WorkspaceRepo(
                name="repo-alpha",
                root=str(repo_alpha_root.resolve()),
                description="alpha repo",
                tags=(),
                weight=1.0,
                plan_quick={},
            ),
            WorkspaceRepo(
                name="repo-beta",
                root=str(repo_beta_root.resolve()),
                description="beta repo",
                tags=(),
                weight=1.0,
                plan_quick={},
            ),
        ),
    )


def test_load_workspace_benchmark_cases_supports_top_level_list() -> None:
    loaded = workspace_benchmark.load_workspace_benchmark_cases(
        [
            {
                "id": "case-001",
                "query": "alpha query",
                "expected_repos": ["repo-beta", "repo-alpha", "repo-alpha"],
            }
        ]
    )

    assert len(loaded) == 1
    assert loaded[0].id == "case-001"
    assert loaded[0].query == "alpha query"
    assert loaded[0].expected_repos == ("repo-alpha", "repo-beta")


def test_load_workspace_benchmark_cases_supports_cases_object_and_case_id(tmp_path: Path) -> None:
    cases_path = _write_cases(
        tmp_path / "cases.json",
        {
            "cases": [
                {
                    "case_id": "legacy-001",
                    "query": "beta query",
                    "expected_repos": ["repo-beta"],
                }
            ]
        },
    )

    loaded = workspace_benchmark.load_workspace_benchmark_cases(cases_path)

    assert len(loaded) == 1
    assert loaded[0].id == "legacy-001"


def test_load_workspace_benchmark_cases_prefers_id_over_case_id() -> None:
    loaded = workspace_benchmark.load_workspace_benchmark_cases(
        [
            {
                "id": "new-id",
                "case_id": "legacy-id",
                "query": "alpha query",
                "expected_repos": ["repo-alpha"],
            }
        ]
    )

    assert loaded[0].id == "new-id"


def test_load_workspace_benchmark_cases_errors_for_missing_cases_field(tmp_path: Path) -> None:
    cases_path = _write_cases(
        tmp_path / "cases.json",
        {"items": []},
    )
    with pytest.raises(ValueError, match="must contain a 'cases' field"):
        workspace_benchmark.load_workspace_benchmark_cases(cases_path)


def test_load_workspace_benchmark_cases_errors_for_empty_cases_list(tmp_path: Path) -> None:
    cases_path = _write_cases(
        tmp_path / "cases.json",
        {"cases": []},
    )
    with pytest.raises(ValueError, match="field 'cases' must be a non-empty list"):
        workspace_benchmark.load_workspace_benchmark_cases(cases_path)


def test_load_workspace_benchmark_cases_errors_use_id_when_present() -> None:
    with pytest.raises(ValueError, match=r"cases\[0\]\.id cannot be empty"):
        workspace_benchmark.load_workspace_benchmark_cases(
            [
                {
                    "id": "   ",
                    "case_id": "legacy-id",
                    "query": "alpha query",
                    "expected_repos": ["repo-alpha"],
                }
            ]
        )


def test_load_workspace_benchmark_cases_errors_for_missing_id_and_case_id() -> None:
    with pytest.raises(ValueError, match=r"cases\[0\]\.case_id must be a string"):
        workspace_benchmark.load_workspace_benchmark_cases(
            [
                {
                    "query": "alpha query",
                    "expected_repos": ["repo-alpha"],
                }
            ]
        )


def test_run_workspace_benchmark_reports_basic_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _build_manifest(tmp_path)
    cases = [
        {"id": "case-hit", "query": "query-hit", "expected_repos": ["repo-alpha"]},
        {"id": "case-miss", "query": "query-miss", "expected_repos": ["repo-beta"]},
    ]

    routed_by_query = {
        "query-hit": [SimpleNamespace(name="repo-alpha"), SimpleNamespace(name="repo-beta")],
        "query-miss": [SimpleNamespace(name="repo-alpha")],
    }

    def _fake_route_workspace_repos(**kwargs: object) -> list[SimpleNamespace]:
        return list(routed_by_query[str(kwargs["query"])])

    clock = iter([10.0, 10.010, 20.0, 20.020])
    monkeypatch.setattr(workspace_benchmark, "route_workspace_repos", _fake_route_workspace_repos)
    monkeypatch.setattr(workspace_benchmark, "perf_counter", lambda: next(clock))

    payload = workspace_benchmark.run_workspace_benchmark(
        manifest=manifest,
        cases_json=cases,
        top_k_repos=2,
    )

    assert payload["metrics"]["cases_total"] == 2
    assert payload["metrics"]["hit_at_k"] == 0.5
    assert payload["metrics"]["mrr"] == 0.5
    assert payload["metrics"]["avg_latency_ms"] == 15.0
    assert [item["id"] for item in payload["cases"]] == ["case-hit", "case-miss"]


def test_run_workspace_benchmark_full_plan_includes_evidence_completeness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _build_manifest(tmp_path)
    cases = [
        {"id": "case-1", "query": "query-1", "expected_repos": ["repo-alpha"]},
        {"id": "case-2", "query": "query-2", "expected_repos": ["repo-alpha"]},
    ]

    monkeypatch.setattr(
        workspace_benchmark,
        "route_workspace_repos",
        lambda **_: [SimpleNamespace(name="repo-alpha")],
    )

    def _fake_build_workspace_plan(**kwargs: object) -> dict[str, object]:
        query = str(kwargs["query"])
        if query == "query-1":
            return {"evidence_contract": {"confidence": 0.8}}
        return {"evidence_contract": {"confidence": "invalid"}}

    clock = iter([30.0, 30.001, 40.0, 40.001])
    monkeypatch.setattr(workspace_benchmark, "build_workspace_plan", _fake_build_workspace_plan)
    monkeypatch.setattr(workspace_benchmark, "perf_counter", lambda: next(clock))

    payload = workspace_benchmark.run_workspace_benchmark(
        manifest=manifest,
        cases_json=cases,
        full_plan=True,
    )

    assert payload["metrics"]["cases_total"] == 2
    assert payload["metrics"]["evidence_completeness"] == 0.4
    assert payload["cases"][0]["evidence_completeness"] == 0.8
    assert payload["cases"][1]["evidence_completeness"] == 0.0


def test_load_workspace_benchmark_baseline_derives_default_checks() -> None:
    loaded = workspace_benchmark.load_workspace_benchmark_baseline(
        {
            "metrics": {
                "hit_at_k": 0.7,
                "mrr": 0.6,
                "avg_latency_ms": 120.0,
            }
        }
    )

    assert loaded["metrics"]["hit_at_k"] == 0.7
    assert loaded["metrics"]["mrr"] == 0.6
    assert loaded["metrics"]["avg_latency_ms"] == 120.0
    assert loaded["checks"]["hit_at_k"] == {"min": 0.7}
    assert loaded["checks"]["mrr"] == {"min": 0.6}
    assert loaded["checks"]["avg_latency_ms"] == {"max": 120.0}


def test_evaluate_workspace_benchmark_against_baseline_reports_violations() -> None:
    result = workspace_benchmark.evaluate_workspace_benchmark_against_baseline(
        current_metrics={"hit_at_k": 0.4, "mrr": 0.5, "avg_latency_ms": 130.0},
        baseline_metrics={"hit_at_k": 0.5, "mrr": 0.5, "avg_latency_ms": 120.0},
        checks={
            "hit_at_k": {"min": 0.5},
            "mrr": {"min": 0.5},
            "avg_latency_ms": {"max": 120.0},
        },
    )

    assert result["ok"] is False
    assert result["checked_metrics"] == ["avg_latency_ms", "hit_at_k", "mrr"]
    assert len(result["violations"]) == 2
    assert result["violations"][0]["metric"] == "hit_at_k"
    assert result["violations"][1]["metric"] == "avg_latency_ms"


def test_evaluate_workspace_benchmark_against_baseline_flags_missing_metric() -> None:
    result = workspace_benchmark.evaluate_workspace_benchmark_against_baseline(
        current_metrics={"hit_at_k": 0.9, "mrr": 0.8},
        baseline_metrics={"avg_latency_ms": 120.0},
        checks={"avg_latency_ms": {"max": 120.0}},
    )

    assert result["ok"] is False
    assert result["violations"] == [
        {
            "metric": "avg_latency_ms",
            "operator": "present_numeric",
            "current": None,
            "threshold": "required",
        }
    ]


def test_compare_workspace_benchmark_metrics_returns_delta() -> None:
    delta = workspace_benchmark.compare_workspace_benchmark_metrics(
        current={"hit_at_k": 0.8, "mrr": 0.6, "avg_latency_ms": 90.0},
        baseline={"hit_at_k": 0.5, "mrr": 0.4, "avg_latency_ms": 100.0},
    )

    assert delta["hit_at_k"] == pytest.approx(0.3)
    assert delta["mrr"] == pytest.approx(0.2)
    assert delta["avg_latency_ms"] == pytest.approx(-10.0)


def test_run_workspace_benchmark_includes_baseline_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _build_manifest(tmp_path)
    cases = [{"id": "case-hit", "query": "query-hit", "expected_repos": ["repo-alpha"]}]

    monkeypatch.setattr(
        workspace_benchmark,
        "route_workspace_repos",
        lambda **_: [SimpleNamespace(name="repo-alpha")],
    )
    clock = iter([10.0, 10.020])
    monkeypatch.setattr(workspace_benchmark, "perf_counter", lambda: next(clock))

    payload = workspace_benchmark.run_workspace_benchmark(
        manifest=manifest,
        cases_json=cases,
        top_k_repos=1,
        baseline_json={
            "metrics": {"hit_at_k": 0.8, "mrr": 0.75, "avg_latency_ms": 25.0},
            "checks": {
                "hit_at_k": {"min": 0.8},
                "mrr": {"min": 0.75},
                "avg_latency_ms": {"max": 25.0},
            },
        },
    )

    baseline_check = payload.get("baseline_check")
    assert isinstance(baseline_check, dict)
    assert baseline_check.get("ok") is True
    delta = baseline_check.get("delta")
    assert isinstance(delta, dict)
    assert delta.get("hit_at_k") == pytest.approx(0.2)
    assert delta.get("mrr") == pytest.approx(0.25)
    assert delta.get("avg_latency_ms") == pytest.approx(-5.0)


def test_run_workspace_benchmark_fail_on_baseline_requires_baseline_json(
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(tmp_path)
    with pytest.raises(ValueError, match="fail_on_baseline requires baseline_json"):
        workspace_benchmark.run_workspace_benchmark(
            manifest=manifest,
            cases_json=[{"id": "case-1", "query": "q", "expected_repos": ["repo-alpha"]}],
            fail_on_baseline=True,
        )


def test_run_workspace_benchmark_fail_on_baseline_raises_on_failed_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _build_manifest(tmp_path)
    cases = [{"id": "case-hit", "query": "query-hit", "expected_repos": ["repo-alpha"]}]

    monkeypatch.setattr(
        workspace_benchmark,
        "route_workspace_repos",
        lambda **_: [SimpleNamespace(name="repo-alpha")],
    )
    clock = iter([10.0, 10.050])
    monkeypatch.setattr(workspace_benchmark, "perf_counter", lambda: next(clock))

    with pytest.raises(ValueError, match="workspace benchmark baseline check failed"):
        workspace_benchmark.run_workspace_benchmark(
            manifest=manifest,
            cases_json=cases,
            top_k_repos=1,
            baseline_json={
                "checks": {
                    "avg_latency_ms": {"max": 25.0},
                },
            },
            fail_on_baseline=True,
        )
