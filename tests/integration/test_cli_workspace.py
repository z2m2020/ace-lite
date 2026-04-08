from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

import click
from click.testing import CliRunner

from ace_lite.cli import cli


def _seed_repo(root: Path, name: str, body: str) -> None:
    src = root / "repos" / name / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "app.py").write_text(body, encoding="utf-8")


def _write_workspace_manifest(root: Path) -> Path:
    manifest = root / "workspace.yaml"
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
                "    description: ui checkout",
                "  - name: ops-observability",
                "    path: repos/ops-observability",
                "    description: traces alerts",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return manifest


def _env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def _write_workspace_benchmark_cases(root: Path) -> Path:
    cases = root / "workspace-benchmark-cases.json"
    cases.write_text(
        json.dumps(
            [
                {
                    "id": "c1",
                    "query": "billing checkout impact",
                    "expected_repos": ["billing-api"],
                }
            ]
        ),
        encoding="utf-8",
    )
    return cases


def _preferred_option_name(option: click.Option) -> str:
    for candidate in option.opts:
        if candidate.startswith("--"):
            return candidate
    return option.opts[0]


def _required_value_for_param(
    *,
    param: click.Parameter,
    manifest: Path,
    cases: Path,
    output_dir: Path,
) -> str:
    name = str(param.name or "").strip().lower()
    if "manifest" in name:
        return str(manifest)
    if "case" in name:
        return str(cases)
    if "output" in name:
        return str(output_dir)
    if "query" in name:
        return "billing checkout impact"
    if "repo_scope" in name:
        return "billing-api,frontend-ui"
    if "language" in name:
        return "python"
    if "top_k" in name or name.endswith("_k"):
        return "2"
    if isinstance(param.type, click.types.IntParamType):
        return "2"
    if isinstance(param.type, click.types.FloatParamType):
        return "1.0"
    if isinstance(param.type, click.types.Path):
        return str(output_dir / f"{name or 'input'}.json")
    return "value"


def test_cli_workspace_validate_outputs_summary(tmp_path: Path) -> None:
    _seed_repo(tmp_path, "billing-api", "def total() -> int:\n    return 1\n")
    _seed_repo(tmp_path, "frontend-ui", "def render() -> None:\n    return None\n")
    _seed_repo(tmp_path, "ops-observability", "def alert() -> str:\n    return 'ok'\n")
    manifest = _write_workspace_manifest(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["workspace", "validate", "--manifest", str(manifest)],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["workspace"]["name"] == "Demo Hub"
    assert payload["workspace"]["repo_count"] == 3


def test_cli_workspace_install_agent_hints_dry_run_new_file(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text("# Repository Guidelines\n\nUse Python conventions.\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["workspace", "install-agent-hints", "--target", str(target)],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["mode"] == "dry-run"
    assert payload["target"] == str(target.resolve())
    assert payload["has_existing_section"] is False
    assert payload["would_append"] is True
    assert payload["would_remove"] is False
    assert "append" in payload["changes_preview"]


def test_cli_workspace_install_agent_hints_append_creates_section(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text("# Repository Guidelines\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "workspace",
            "install-agent-hints",
            "--target",
            str(target),
            "--mode",
            "append",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    content = target.read_text(encoding="utf-8")
    assert payload["ok"] is True
    assert payload["mode"] == "append"
    assert payload["file_updated"] is True
    assert payload["bytes_written"] == len(content.encode("utf-8"))
    assert "<!-- AGENT_HINTS_START -->" in content
    assert "## Agent Hints" in content
    assert "- Write tests for new functionality" in content
    assert "<!-- AGENT_HINTS_END -->" in content


def test_cli_workspace_install_agent_hints_append_creates_missing_file(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "workspace",
            "install-agent-hints",
            "--target",
            str(target),
            "--mode",
            "append",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["mode"] == "append"
    assert payload["file_updated"] is True
    assert payload["file_created"] is True
    content = target.read_text(encoding="utf-8")
    assert "context-map/CONTEXT_REPORT.md" in content
    assert "<!-- AGENT_HINTS_START -->" in content


def test_cli_workspace_install_agent_hints_dry_run_existing_section(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(
        "\n".join(
            [
                "# Repository Guidelines",
                "",
                "<!-- AGENT_HINTS_START -->",
                "## Agent Hints",
                "",
                "- Existing hint",
                "<!-- AGENT_HINTS_END -->",
                "",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["workspace", "install-agent-hints", "--target", str(target)],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["has_existing_section"] is True
    assert payload["would_append"] is True
    assert payload["would_remove"] is True
    assert "replace" in payload["changes_preview"]


def test_cli_workspace_install_agent_hints_remove_existing_section(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(
        "\n".join(
            [
                "# Repository Guidelines",
                "",
                "<!-- AGENT_HINTS_START -->",
                "## Agent Hints",
                "",
                "- Existing hint",
                "<!-- AGENT_HINTS_END -->",
                "",
                "Keep this line.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "workspace",
            "install-agent-hints",
            "--target",
            str(target),
            "--mode",
            "remove",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    content = target.read_text(encoding="utf-8")
    assert payload["ok"] is True
    assert payload["mode"] == "remove"
    assert payload["file_updated"] is True
    assert payload["bytes_written"] == len(content.encode("utf-8"))
    assert "<!-- AGENT_HINTS_START -->" not in content
    assert "<!-- AGENT_HINTS_END -->" not in content
    assert "Keep this line." in content


def test_cli_workspace_install_agent_hints_remove_nonexistent_section(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    original = "# Repository Guidelines\n\nNo agent hints yet.\n"
    target.write_text(original, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "workspace",
            "install-agent-hints",
            "--target",
            str(target),
            "--mode",
            "remove",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["mode"] == "remove"
    assert payload["file_updated"] is False
    assert payload["bytes_written"] == 0
    assert target.read_text(encoding="utf-8") == original


def test_cli_workspace_summarize_writes_summary_artifact(tmp_path: Path) -> None:
    _seed_repo(tmp_path, "billing-api", "def total() -> int:\n    return 1\n")
    _seed_repo(tmp_path, "frontend-ui", "def render() -> None:\n    return None\n")
    _seed_repo(tmp_path, "ops-observability", "def alert() -> str:\n    return 'ok'\n")
    manifest = _write_workspace_manifest(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "workspace",
            "summarize",
            "--manifest",
            str(manifest),
            "--languages",
            "python",
            "--repo-scope",
            "billing-api,frontend-ui",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["workspace"]["selected_repo_count"] == 2
    summary_path = Path(payload["artifacts"]["summary"])
    assert summary_path.exists()
    assert summary_path.is_file()


def test_cli_workspace_plan_supports_repo_scope_and_evidence_contract(tmp_path: Path) -> None:
    _seed_repo(tmp_path, "billing-api", "def total() -> int:\n    return 1\n")
    _seed_repo(tmp_path, "frontend-ui", "def render() -> None:\n    return None\n")
    _seed_repo(tmp_path, "ops-observability", "def alert() -> str:\n    return 'ok'\n")
    manifest = _write_workspace_manifest(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "workspace",
            "plan",
            "--manifest",
            str(manifest),
            "--query",
            "billing checkout impact",
            "--top-k-repos",
            "3",
            "--repo-scope",
            "billing-api,frontend-ui",
            "--languages",
            "python",
            "--summary-routing",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    selected_names = [item["name"] for item in payload["selected_repos"]]
    assert set(selected_names) <= {"billing-api", "frontend-ui"}
    assert "ops-observability" not in selected_names
    assert payload["summary_routing"]["enabled"] is True
    contract = payload["evidence_contract"]
    assert isinstance(contract["candidate_repos"], list)
    assert isinstance(contract["selected_repos"], list)
    assert isinstance(contract["confidence"], (int, float))


def test_cli_workspace_plan_strict_emits_evidence_validation(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "workspace.yaml"
    manifest.write_text("workspace:\n  name: demo\nrepos: []\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_build_workspace_plan(**kwargs):
        captured.update(kwargs)
        payload = {
            "selected_repos": [],
            "candidate_repos": [],
            "evidence_contract": {"confidence": 0.92},
        }
        if bool(kwargs.get("evidence_strict")):
            payload["evidence_validation"] = {
                "ok": True,
                "confidence": 0.92,
                "min_confidence": float(kwargs.get("min_confidence", 0.0)),
                "fail_closed": bool(kwargs.get("fail_closed")),
                "strict": True,
                "violations": [],
            }
        return payload

    def fake_workspace_callable(name: str):
        if name == "build_workspace_plan":
            return fake_build_workspace_plan
        raise AssertionError(f"unexpected workspace callable: {name}")

    import ace_lite.cli_app.commands.workspace as workspace_command_module

    monkeypatch.setattr(
        workspace_command_module,
        "_workspace_callable",
        fake_workspace_callable,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "workspace",
            "plan",
            "--manifest",
            str(manifest),
            "--query",
            "billing checkout impact",
            "--evidence-strict",
            "--min-confidence",
            "0.80",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    evidence_validation = payload.get("evidence_validation")
    assert isinstance(evidence_validation, dict)
    assert evidence_validation.get("ok") is True
    assert evidence_validation.get("confidence") == 0.92
    assert evidence_validation.get("min_confidence") == 0.8
    assert captured.get("evidence_strict") is True
    assert captured.get("min_confidence") == 0.8
    assert captured.get("fail_closed") is False


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_cli_workspace_plan_rejects_non_finite_min_confidence(tmp_path: Path, value: str) -> None:
    _seed_repo(tmp_path, "billing-api", "def total() -> int:\n    return 1\n")
    _seed_repo(tmp_path, "frontend-ui", "def render() -> None:\n    return None\n")
    _seed_repo(tmp_path, "ops-observability", "def alert() -> str:\n    return 'ok'\n")
    manifest = _write_workspace_manifest(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "workspace",
            "plan",
            "--manifest",
            str(manifest),
            "--query",
            "billing checkout impact",
            "--min-confidence",
            value,
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code != 0
    assert "min-confidence" in result.output
    assert "finite" in result.output


def test_cli_workspace_plan_fail_closed_errors_on_low_confidence(
    tmp_path: Path, monkeypatch
) -> None:
    manifest = tmp_path / "workspace.yaml"
    manifest.write_text("workspace:\n  name: demo\nrepos: []\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_build_workspace_plan(**kwargs):
        captured.update(kwargs)
        if bool(kwargs.get("evidence_strict")) and bool(kwargs.get("fail_closed")):
            raise ValueError(
                "evidence validation failed: fail_closed=True, "
                "violation=confidence_below_min_confidence"
            )
        return {
            "selected_repos": [],
            "candidate_repos": [],
            "evidence_contract": {"confidence": 0.2},
        }

    def fake_workspace_callable(name: str):
        if name == "build_workspace_plan":
            return fake_build_workspace_plan
        raise AssertionError(f"unexpected workspace callable: {name}")

    import ace_lite.cli_app.commands.workspace as workspace_command_module

    monkeypatch.setattr(
        workspace_command_module,
        "_workspace_callable",
        fake_workspace_callable,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "workspace",
            "plan",
            "--manifest",
            str(manifest),
            "--query",
            "billing checkout impact",
            "--evidence-strict",
            "--fail-closed",
            "--min-confidence",
            "0.90",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code != 0
    assert "evidence validation failed" in result.output
    assert "fail_closed=True" in result.output
    assert captured.get("evidence_strict") is True
    assert captured.get("min_confidence") == 0.9
    assert captured.get("fail_closed") is True


def test_cli_workspace_benchmark_command_outputs_metrics(
    tmp_path: Path,
) -> None:
    _seed_repo(tmp_path, "billing-api", "def total() -> int:\n    return 1\n")
    _seed_repo(tmp_path, "frontend-ui", "def render() -> None:\n    return None\n")
    _seed_repo(tmp_path, "ops-observability", "def alert() -> str:\n    return 'ok'\n")
    manifest = _write_workspace_manifest(tmp_path)
    cases = _write_workspace_benchmark_cases(tmp_path)
    output_dir = tmp_path / "artifacts" / "workspace-benchmark"

    workspace_group = cast(click.Group | None, cli.commands.get("workspace"))
    assert workspace_group is not None
    benchmark_command = workspace_group.commands.get("benchmark")
    assert benchmark_command is not None, "workspace benchmark command missing"

    args = ["workspace", "benchmark"]
    for param in benchmark_command.params:
        if isinstance(param, click.Option):
            if not param.required:
                continue
            if param.is_flag:
                args.append(_preferred_option_name(param))
                continue
            option_name = _preferred_option_name(param)
            value = _required_value_for_param(
                param=param,
                manifest=manifest,
                cases=cases,
                output_dir=output_dir,
            )
            args.extend([option_name, value])
            continue
        if isinstance(param, click.Argument) and param.required:
            args.append(
                _required_value_for_param(
                    param=param,
                    manifest=manifest,
                    cases=cases,
                    output_dir=output_dir,
                )
            )

    runner = CliRunner()
    result = runner.invoke(cli, args, env=_env(tmp_path))

    assert result.exit_code == 0
    payload = json.loads(result.output)
    metrics = payload["metrics"]
    assert int(metrics.get("cases_total", 0)) == 1
    hit_at_k = metrics.get("hit_at_k", metrics.get("chunk_hit_at_k"))
    assert isinstance(hit_at_k, (int, float))
    assert isinstance(metrics.get("mrr"), (int, float))
    assert isinstance(metrics.get("avg_latency_ms"), (int, float))

    cases_rows = payload["cases"]
    assert isinstance(cases_rows, list)
    assert len(cases_rows) == 1
    first = cases_rows[0]
    assert first["id"] == "c1"
    assert first["query"] == "billing checkout impact"
    assert first["expected_repos"] == ["billing-api"]
    assert isinstance(first.get("predicted_repos"), list)
    assert isinstance(first.get("hit"), bool)
    assert isinstance(first.get("reciprocal_rank"), (int, float))


def test_cli_workspace_benchmark_with_baseline_passes(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "workspace.yaml"
    manifest.write_text("workspace:\n  name: demo\nrepos: []\n", encoding="utf-8")
    cases = tmp_path / "cases.json"
    cases.write_text("[]", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"metrics": {"hit_at_k": 0.7, "mrr": 0.6, "avg_latency_ms": 25.0}}),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def fake_run_workspace_benchmark(**kwargs):
        captured.update(kwargs)
        return {
            "metrics": {"cases_total": 1, "hit_at_k": 1.0, "mrr": 1.0, "avg_latency_ms": 10.0},
            "cases": [],
            "baseline_check": {
                "ok": True,
                "checked_metrics": ["avg_latency_ms", "hit_at_k", "mrr"],
                "violations": [],
            },
        }

    def fake_workspace_callable(name: str):
        if name == "run_workspace_benchmark":
            return fake_run_workspace_benchmark
        raise AssertionError(f"unexpected workspace callable: {name}")

    import ace_lite.cli_app.commands.workspace as workspace_command_module

    monkeypatch.setattr(
        workspace_command_module,
        "_workspace_callable",
        fake_workspace_callable,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "workspace",
            "benchmark",
            "--manifest",
            str(manifest),
            "--cases-json",
            str(cases),
            "--baseline-json",
            str(baseline),
            "--fail-on-baseline",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["baseline_check"]["ok"] is True
    assert captured.get("baseline_json") == str(baseline)
    assert captured.get("fail_on_baseline") is True


def test_cli_workspace_benchmark_with_baseline_failures_can_fail_closed(
    tmp_path: Path, monkeypatch
) -> None:
    manifest = tmp_path / "workspace.yaml"
    manifest.write_text("workspace:\n  name: demo\nrepos: []\n", encoding="utf-8")
    cases = tmp_path / "cases.json"
    cases.write_text("[]", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"metrics": {"hit_at_k": 0.7, "mrr": 0.6, "avg_latency_ms": 25.0}}),
        encoding="utf-8",
    )

    def fake_run_workspace_benchmark(**kwargs):
        if bool(kwargs.get("fail_on_baseline")):
            raise ValueError("workspace benchmark baseline check failed (1 violation(s))")
        return {"metrics": {"cases_total": 1}, "cases": []}

    def fake_workspace_callable(name: str):
        if name == "run_workspace_benchmark":
            return fake_run_workspace_benchmark
        raise AssertionError(f"unexpected workspace callable: {name}")

    import ace_lite.cli_app.commands.workspace as workspace_command_module

    monkeypatch.setattr(
        workspace_command_module,
        "_workspace_callable",
        fake_workspace_callable,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "workspace",
            "benchmark",
            "--manifest",
            str(manifest),
            "--cases-json",
            str(cases),
            "--baseline-json",
            str(baseline),
            "--fail-on-baseline",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code != 0
    assert "workspace benchmark baseline check failed" in result.output
