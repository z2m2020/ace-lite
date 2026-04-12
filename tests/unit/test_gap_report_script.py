from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


def _load_module():  # type: ignore[no-untyped-def]
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "build_gap_report.py"
    spec = importlib.util.spec_from_file_location("build_gap_report_script", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load build_gap_report.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_build_gap_report_writes_json_and_markdown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    repo_root = tmp_path
    date = "2026-04-12"

    _write_json(
        repo_root / "artifacts" / "context-reports" / date / "context_report.json",
        {
            "schema_version": "context_report_v1",
            "query": "trace retrieval gaps",
            "repo": "ace-lite-engine",
            "root": str(repo_root),
            "summary": {
                "candidate_file_count": 2,
                "candidate_chunk_count": 3,
                "validation_test_count": 1,
                "stage_count": 6,
                "degraded_reason_count": 0,
                "has_validation_payload": False,
            },
            "confidence_breakdown": {
                "extracted_count": 1,
                "inferred_count": 1,
                "ambiguous_count": 1,
                "unknown_count": 0,
                "total_count": 3,
            },
            "warnings": [],
        },
    )
    _write_json(
        repo_root / "artifacts" / "retrieval-graphs" / date / "retrieval_graph_view.json",
        {
            "ok": True,
            "schema_version": "retrieval_graph_view_v1",
            "repo": "ace-lite-engine",
            "root": str(repo_root),
            "query": "trace retrieval gaps",
            "scope": {
                "repo": "ace-lite-engine",
                "root": str(repo_root),
                "limit": 50,
                "max_hops": 1,
            },
            "summary": {
                "node_count": 4,
                "edge_count": 1,
                "node_limit_applied": True,
                "max_hops": 1,
                "limit": 50,
            },
            "nodes": [
                {
                    "id": "src/a.py",
                    "kind": "file",
                    "path": "src/a.py",
                    "score": 9.0,
                    "source": "source_plan",
                },
                {
                    "id": "src/a.py::do_work",
                    "kind": "function",
                    "path": "src/a.py",
                    "score": 9.0,
                    "source": "source_plan",
                    "evidence_confidence": "EXTRACTED",
                },
                {
                    "id": "src/b.py::helper",
                    "kind": "function",
                    "path": "src/b.py",
                    "score": 6.0,
                    "source": "source_plan",
                    "evidence_confidence": "INFERRED",
                },
                {
                    "id": "tests/test_a.py::test_do_work",
                    "kind": "function",
                    "path": "tests/test_a.py",
                    "score": 3.0,
                    "source": "source_plan",
                    "evidence_confidence": "AMBIGUOUS",
                },
            ],
            "edges": [],
            "warnings": ["node_limit_applied: truncated from 60 to 50 nodes"],
        },
    )
    _write_json(
        repo_root
        / "artifacts"
        / "checkpoints"
        / "phase1"
        / "2026-04-10"
        / "checkpoint_manifest.json",
        {"schema_version": "checkpoint_manifest_v1"},
    )
    _write_json(
        repo_root / "artifacts" / "checkpoints" / "phase1" / date / "checkpoint_manifest.json",
        {"schema_version": "checkpoint_manifest_v1"},
    )

    class _Completed:
        returncode = 0
        stdout = "abc123def\n"

    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: _Completed())

    result = module.build_gap_report(
        date=date,
        output_root=repo_root / "artifacts" / "gap-reports",
        repo_root=repo_root,
    )

    payload = result["payload"]
    assert payload["schema_version"] == "retrieval_task_gap_report_v1"
    assert payload["git_sha"] == "abc123def"
    assert payload["phase"] == "phase1"
    assert (
        payload["checkpoint_id"] == f"artifacts/checkpoints/phase1/{date}/checkpoint_manifest.json"
    )
    assert (
        payload["prior_checkpoint_id"]
        == "artifacts/checkpoints/phase1/2026-04-10/checkpoint_manifest.json"
    )
    assert payload["gap_summary"]["severity_breakdown"]["medium"] >= 1
    assert payload["retrieval_signals"]["grounded_ratio"] == 0.5
    assert payload["retrieval_signals"]["node_limit_applied"] is True
    assert payload["gate_mode"] == "report_only"

    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])
    assert json_path.exists()
    assert md_path.exists()
    markdown = md_path.read_text(encoding="utf-8")
    assert "## Executive Summary" in markdown
    assert "## Top Findings" in markdown
    assert "| Severity | Gap ID | Description |" in markdown


def test_build_gap_report_is_fail_open_with_missing_inputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    repo_root = tmp_path
    date = "2026-04-12"

    class _Completed:
        returncode = 0
        stdout = "feedface\n"

    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: _Completed())

    result = module.build_gap_report(
        date=date,
        output_root=repo_root / "artifacts" / "gap-reports",
        repo_root=repo_root,
    )

    payload = result["payload"]
    assert payload["schema_version"] == "retrieval_task_gap_report_v1"
    assert payload["gap_summary"]["overall_severity"] == "critical"
    assert payload["gaps"][0]["severity"] == "critical"
    assert any("context_report_missing_or_invalid" in warning for warning in payload["warnings"])
    assert any(
        "retrieval_graph_view_missing_or_invalid" in warning for warning in payload["warnings"]
    )

    written = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert written["warnings"] == payload["warnings"]


def test_main_uses_default_output_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_module()
    calls: list[tuple[str, Path, Path]] = []

    def _fake_build_gap_report(*, date: str, output_root: Path, repo_root: Path) -> dict[str, str]:
        calls.append((date, output_root, repo_root))
        return {
            "json_path": str(output_root / date / "gap_report.json"),
            "md_path": str(output_root / date / "gap_report.md"),
        }

    monkeypatch.setattr(module, "build_gap_report", _fake_build_gap_report)
    monkeypatch.setattr(sys, "argv", ["build_gap_report.py", "--date", "2026-04-12"])

    script_path = tmp_path / "scripts" / "build_gap_report.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("# placeholder\n", encoding="utf-8")
    monkeypatch.setattr(module, "__file__", str(script_path))

    assert module.main() == 0
    assert calls == [
        (
            "2026-04-12",
            tmp_path / "artifacts" / "gap-reports",
            tmp_path,
        )
    ]
