"""Integration tests for ace-lite plan --context-report-path (L8502)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

import ace_lite.cli as cli_module
from ace_lite.context_report import (
    build_context_report_payload,
    validate_context_report_payload,
)
from ace_lite.memory import NullMemoryProvider


def _seed_root(root: Path) -> None:
    (root / "skills").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "sample.py").write_text("def demo() -> int:\n    return 1\n", encoding="utf-8")


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def _minimal_plan_payload() -> dict[str, Any]:
    return {
        "query": "context report demo",
        "repo": "demo",
        "root": "/fake/root",
        "schema_version": "context_report_v1",
        "candidate_chunks": [
            {
                "path": "src/sample.py",
                "qualified_name": "demo",
                "kind": "function",
                "lineno": 1,
                "end_lineno": 2,
                "score": 9.5,
                "evidence": {
                    "role": "direct",
                    "direct_retrieval": True,
                    "neighbor_context": False,
                    "hint_only": False,
                    "hint_support": False,
                    "reference_sidecar": False,
                    "sources": ["direct_candidate"],
                    "granularity": ["symbol"],
                },
            }
        ],
        "candidate_files": [{"path": "src/sample.py", "score": 9.5}],
        "evidence_summary": {
            "direct_count": 1.0,
            "neighbor_context_count": 0.0,
            "hint_only_count": 0.0,
            "direct_ratio": 1.0,
            "neighbor_context_ratio": 0.0,
            "hint_only_ratio": 0.0,
        },
        "stages": ["memory", "index", "repomap", "augment", "skills", "source_plan"],
    }


def test_cli_plan_context_report_path_writes_file(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)
    plan_payload = _minimal_plan_payload()

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        return dict(plan_payload)

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "context report demo",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--context-report-path",
            "context-map/CONTEXT_REPORT.md",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0, f"CLI exit non-zero: {result.output}"

    report_path = tmp_path / "context-map" / "CONTEXT_REPORT.md"
    assert report_path.exists(), f"Report not found at {report_path}"
    content = report_path.read_text(encoding="utf-8")
    assert "# Context Report" in content
    assert "src/sample.py" in content
    assert "EXTRACTED" in content


def test_cli_plan_without_context_report_path_does_not_create_file(
    tmp_path: Path, monkeypatch
) -> None:
    _seed_root(tmp_path)
    plan_payload = _minimal_plan_payload()

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        return dict(plan_payload)

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "no report demo",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    report_path = tmp_path / "context-map" / "CONTEXT_REPORT.md"
    assert not report_path.exists(), (
        f"Report should NOT exist when --context-report-path is not passed: {report_path}"
    )


def test_cli_plan_json_and_context_report_are_independent(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)
    plan_payload = _minimal_plan_payload()
    plan_payload["query"] = "dual output demo"

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        return dict(plan_payload)

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "dual output demo",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--output-json",
            "artifacts/plan.json",
            "--context-report-path",
            "context-map/CONTEXT_REPORT.md",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0

    json_path = tmp_path / "artifacts" / "plan.json"
    report_path = tmp_path / "context-map" / "CONTEXT_REPORT.md"

    assert json_path.exists(), "JSON output should exist"
    assert report_path.exists(), "Context report should exist"

    json_content = json.loads(json_path.read_text(encoding="utf-8"))
    report_content = report_path.read_text(encoding="utf-8")

    assert json_content["query"] == "dual output demo"
    assert "# Context Report" in report_content


def test_cli_plan_context_report_with_timeout_fallback(tmp_path: Path, monkeypatch) -> None:
    """Plan timeout fallback should still produce a context report with degraded info."""
    _seed_root(tmp_path)

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        # Simulate a plan that times out (returns partial payload)
        raise TimeoutError("simulated timeout")

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "timeout demo",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--timeout-seconds",
            "0.001",
            "--context-report-path",
            "context-map/TIMEOUT_REPORT.md",
        ],
        env=_cli_env(tmp_path),
    )

    # Should still succeed and produce a report
    report_path = tmp_path / "context-map" / "TIMEOUT_REPORT.md"
    assert report_path.exists(), f"Timeout report not found: {result.output}"
    content = report_path.read_text(encoding="utf-8")
    assert "# Context Report" in content


def test_cli_plan_context_report_creates_parent_directories(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        return {
            "query": "mkdir demo",
            "repo": "demo",
            "root": str(tmp_path),
            "candidate_chunks": [],
            "candidate_files": [],
            "evidence_summary": {},
            "stages": [],
        }

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "mkdir demo",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--context-report-path",
            "deeply/nested/path/report.md",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0, f"CLI failed: {result.output}"
    report_path = tmp_path / "deeply" / "nested" / "path" / "report.md"
    assert report_path.exists()


def test_cli_plan_context_report_payload_passes_schema_guard(tmp_path: Path, monkeypatch) -> None:
    """CLI-generated plan payload produces a ContextReport that passes the schema guard."""
    _seed_root(tmp_path)
    plan_payload = _minimal_plan_payload()

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        return dict(plan_payload)

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "schema guard test",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--output-json",
            "artifacts/plan.json",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    json_path = tmp_path / "artifacts" / "plan.json"
    assert json_path.exists(), f"JSON not found at {json_path}: {result.output}"
    json_content = json.loads(json_path.read_text(encoding="utf-8"))

    # Build and validate the ContextReport payload
    context_payload = build_context_report_payload(json_content)
    validated = validate_context_report_payload(context_payload)
    assert validated["schema_version"] == "context_report_v1"
    assert validated["ok"] is True
