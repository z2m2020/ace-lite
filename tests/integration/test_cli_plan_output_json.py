from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

import ace_lite.cli as cli_module
from ace_lite.memory import NullMemoryProvider


def _seed_root(root: Path) -> None:
    (root / "skills").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "sample.py").write_text("def demo() -> int:\n    return 1\n", encoding="utf-8")


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def test_cli_plan_output_json_writes_utf8(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    expected_payload = {"ok": True, "schema_version": "test"}

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        return dict(expected_payload)

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "output json demo",
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
    stdout_payload = json.loads(result.output)
    assert stdout_payload == expected_payload

    output_path = tmp_path / "artifacts" / "plan.json"
    assert output_path.exists()

    raw_prefix = output_path.read_bytes()[:2]
    assert raw_prefix not in (b"\xff\xfe", b"\xfe\xff")
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert file_payload == expected_payload


def test_cli_plan_output_json_adds_contract_summary_when_plan_payload_present(
    tmp_path: Path, monkeypatch
) -> None:
    _seed_root(tmp_path)

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    expected_payload = {
        "index": {
            "chunk_contract": {"schema_version": "chunk-v1"},
            "subgraph_payload": {
                "payload_version": "subgraph-v1",
                "taxonomy_version": "taxonomy-v1",
            },
        },
        "source_plan": {
            "steps": [],
            "chunk_contract": {"schema_version": "chunk-v1"},
            "prompt_rendering_boundary": {"boundary_version": "prompt-v1"},
            "subgraph_payload": {
                "payload_version": "subgraph-v2",
                "taxonomy_version": "taxonomy-v2",
            },
        },
    }

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        return dict(expected_payload)

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "contract summary demo",
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
            "artifacts/plan-with-summary.json",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    stdout_payload = json.loads(result.output)
    assert stdout_payload["contract_summary"] == {
        "index_chunk_contract_version": "chunk-v1",
        "source_plan_chunk_contract_version": "chunk-v1",
        "prompt_rendering_boundary_version": "prompt-v1",
        "index_subgraph_payload_version": "subgraph-v1",
        "source_plan_subgraph_payload_version": "subgraph-v2",
        "subgraph_taxonomy_version": "taxonomy-v2",
    }

    output_path = tmp_path / "artifacts" / "plan-with-summary.json"
    assert output_path.exists()
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert file_payload["contract_summary"] == stdout_payload["contract_summary"]


def test_cli_plan_output_json_preserves_pipeline_and_validation_contract_fields(
    tmp_path: Path, monkeypatch
) -> None:
    _seed_root(tmp_path)

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    expected_payload = {
        "schema_version": "2.0",
        "pipeline_order": [
            "memory",
            "index",
            "repomap",
            "augment",
            "skills",
            "source_plan",
            "validation",
        ],
        "validation": {
            "enabled": True,
            "reason": "ok",
            "diagnostic_count": 0,
        },
        "observability": {
            "stage_metrics": [
                {"stage": "memory", "elapsed_ms": 1.0},
                {"stage": "validation", "elapsed_ms": 2.0},
            ]
        },
    }

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        return dict(expected_payload)

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "pipeline validation contract",
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
            "artifacts/plan-contract.json",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    stdout_payload = json.loads(result.output)
    assert stdout_payload["pipeline_order"] == expected_payload["pipeline_order"]
    assert stdout_payload["validation"] == expected_payload["validation"]
    assert (
        stdout_payload["observability"]["stage_metrics"]
        == expected_payload["observability"]["stage_metrics"]
    )

    file_payload = json.loads(
        (tmp_path / "artifacts" / "plan-contract.json").read_text(encoding="utf-8")
    )
    assert file_payload["pipeline_order"] == expected_payload["pipeline_order"]
    assert file_payload["validation"] == expected_payload["validation"]


def test_cli_plan_output_json_keeps_contract_summary_with_validation_envelope(
    tmp_path: Path, monkeypatch
) -> None:
    _seed_root(tmp_path)

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    expected_payload = {
        "schema_version": "2.0",
        "pipeline_order": [
            "memory",
            "index",
            "repomap",
            "augment",
            "skills",
            "source_plan",
            "validation",
        ],
        "index": {
            "chunk_contract": {"schema_version": "chunk-v1"},
            "subgraph_payload": {
                "payload_version": "subgraph-v1",
                "taxonomy_version": "taxonomy-v1",
            },
        },
        "source_plan": {
            "steps": [],
            "chunk_contract": {"schema_version": "chunk-v1"},
            "prompt_rendering_boundary": {"boundary_version": "prompt-v1"},
            "subgraph_payload": {
                "payload_version": "subgraph-v2",
                "taxonomy_version": "taxonomy-v2",
            },
        },
        "validation": {
            "enabled": True,
            "reason": "ok",
            "diagnostic_count": 1,
        },
    }

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        return dict(expected_payload)

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "full contract envelope",
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
            "artifacts/plan-full-contract.json",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["contract_summary"] == {
        "index_chunk_contract_version": "chunk-v1",
        "source_plan_chunk_contract_version": "chunk-v1",
        "prompt_rendering_boundary_version": "prompt-v1",
        "index_subgraph_payload_version": "subgraph-v1",
        "source_plan_subgraph_payload_version": "subgraph-v2",
        "subgraph_taxonomy_version": "taxonomy-v2",
    }
    assert payload["validation"] == expected_payload["validation"]
    assert payload["pipeline_order"] == expected_payload["pipeline_order"]
