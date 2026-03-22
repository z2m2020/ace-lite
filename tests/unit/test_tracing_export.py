from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.pipeline.types import StageMetric
from ace_lite.tracing import export_stage_trace_jsonl, export_stage_trace_otlp


def _seed_repo(root: Path) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app.py").write_text(
        "def run(value: str) -> str:\n    return value.strip()\n",
        encoding="utf-8",
    )


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        rows.append(json.loads(text))
    return rows


def test_export_stage_trace_jsonl_writes_pipeline_and_stage_spans(tmp_path: Path) -> None:
    output_path = tmp_path / "trace" / "stage_spans.jsonl"
    metrics = [
        StageMetric(stage="memory", elapsed_ms=12.5, plugins=["p1"], tags={"cache_hit": True}),
        StageMetric(stage="index", elapsed_ms=8.0, plugins=[], tags={"candidate_count": 3}),
    ]

    result = export_stage_trace_jsonl(
        output_path=output_path,
        query="where Session class is implemented",
        repo="demo",
        root=str(tmp_path),
        started_at=datetime(2026, 2, 12, 0, 0, 0, tzinfo=timezone.utc),
        total_ms=25.0,
        stage_metrics=metrics,
        pipeline_order=["memory", "index"],
        plugin_policy_summary={"mode": "strict"},
    )

    assert result["enabled"] is True
    assert result["exported"] is True
    assert result["otel_compatible"] is True
    assert result["openinference_compatible"] is True
    assert result["schema_version"] == "ace-lite-trace-v2"
    assert output_path.exists()

    rows = _load_jsonl(output_path)
    assert len(rows) == 3
    assert rows[0]["kind"] == "pipeline"
    assert rows[0]["schema_version"] == "ace-lite-trace-v2"
    assert rows[0]["otel"]["trace_id"] == rows[0]["otel_trace_id"]
    assert rows[0]["openinference"]["span.kind"] == "CHAIN"
    assert rows[1]["kind"] == "stage"
    assert rows[1]["stage"] == "memory"
    assert rows[1]["openinference"]["span.kind"] == "TOOL"
    assert rows[1]["duration_ns"] >= 0
    assert rows[2]["stage"] == "index"


def test_orchestrator_trace_export_writes_jsonl(tmp_path: Path, fake_skill_manifest) -> None:
    _seed_repo(tmp_path)
    trace_path = tmp_path / "context-map" / "traces" / "pipeline.jsonl"

    orchestrator = AceOrchestrator(
        config=OrchestratorConfig(
            skills={"manifest": fake_skill_manifest},
            index={
                "languages": ["python"],
                "cache_path": tmp_path / "context-map" / "index.json",
            },
            retrieval={
                "adaptive_router_enabled": True,
                "adaptive_router_mode": "shadow",
                "adaptive_router_arm_set": "retrieval_policy_shadow",
            },
            repomap={"enabled": False},
            cochange={"enabled": False},
            scip={"enabled": False},
            trace={
                "export_enabled": True,
                "export_path": trace_path,
            },
        )
    )

    payload = orchestrator.plan(
        query="implement app run helper",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    trace_info = payload["observability"].get("trace_export", {})
    assert trace_info.get("enabled") is True
    assert trace_info.get("exported") is True
    assert trace_info.get("otel_compatible") is True
    assert trace_info.get("schema_version") == "ace-lite-trace-v2"
    assert Path(str(trace_info.get("path"))).exists()

    rows = _load_jsonl(trace_path)
    assert len(rows) == 8
    stage_rows = [row for row in rows if row.get("kind") == "stage"]
    assert len(stage_rows) == 7
    assert stage_rows[0]["stage"] == "memory"
    assert stage_rows[-1]["stage"] == "validation"
    index_rows = [row for row in stage_rows if row.get("stage") == "index"]
    assert len(index_rows) == 1
    index_tags = index_rows[0]["tags"]
    assert index_tags["router_enabled"] is True
    assert index_tags["router_mode"] == "shadow"
    assert index_tags["router_arm_set"] == "retrieval_policy_shadow"
    assert index_tags["router_arm_id"] == "feature"
    assert index_tags["router_shadow_arm_id"] == "feature_graph"
    assert index_tags["router_shadow_source"] == "fallback"
    assert index_tags["router_shadow_confidence"] == 0.25

    adaptive_router = payload["index"]["adaptive_router"]
    assert adaptive_router["enabled"] is True
    assert adaptive_router["mode"] == "shadow"
    assert adaptive_router["arm_set"] == "retrieval_policy_shadow"
    assert adaptive_router["arm_id"] == "feature"
    assert adaptive_router["shadow_arm_id"] == "feature_graph"
    assert adaptive_router["shadow_source"] == "fallback"
    assert adaptive_router["shadow_confidence"] == 0.25



def test_trace_rows_include_otel_resource_attributes(tmp_path: Path) -> None:
    output_path = tmp_path / "trace" / "stage_spans.jsonl"

    result = export_stage_trace_jsonl(
        output_path=output_path,
        query="q",
        repo="demo",
        root=str(tmp_path),
        started_at=datetime(2026, 2, 12, 0, 0, 0, tzinfo=timezone.utc),
        total_ms=5.0,
        stage_metrics=[StageMetric(stage="memory", elapsed_ms=5.0, plugins=[], tags={})],
        pipeline_order=["memory"],
        plugin_policy_summary={},
    )

    assert result["otel_trace_id"]

    rows = _load_jsonl(output_path)
    assert rows
    assert rows[0]["resource"]["attributes"]["service.name"] == "ace-lite-engine"
    assert rows[0]["start_time_unix_nano"] <= rows[0]["end_time_unix_nano"]
    assert rows[1]["attributes"]["ace.stage"] == "memory"



def test_export_stage_trace_otlp_file_transport(tmp_path: Path) -> None:
    endpoint_path = tmp_path / "trace" / "otlp_payload.json"

    result = export_stage_trace_otlp(
        endpoint=f"file://{endpoint_path}",
        query="find entrypoint",
        repo="demo",
        root=str(tmp_path),
        started_at=datetime(2026, 2, 12, 0, 0, 0, tzinfo=timezone.utc),
        total_ms=18.0,
        stage_metrics=[
            StageMetric(stage="memory", elapsed_ms=5.0, plugins=[], tags={"cache_hit": True}),
            StageMetric(stage="index", elapsed_ms=6.0, plugins=[], tags={"candidate_count": 2}),
        ],
        pipeline_order=["memory", "index"],
        plugin_policy_summary={"mode": "strict"},
    )

    assert result["enabled"] is True
    assert result["exported"] is True
    assert result["transport"] == "file"
    assert endpoint_path.exists()

    payload = json.loads(endpoint_path.read_text(encoding="utf-8"))
    resource_spans = payload.get("resourceSpans", [])
    assert isinstance(resource_spans, list)
    assert resource_spans


def test_orchestrator_trace_otlp_file_export(tmp_path: Path, fake_skill_manifest) -> None:
    _seed_repo(tmp_path)
    otlp_path = tmp_path / "context-map" / "traces" / "pipeline-otlp.json"

    orchestrator = AceOrchestrator(
        config=OrchestratorConfig(
            skills={"manifest": fake_skill_manifest},
            index={
                "languages": ["python"],
                "cache_path": tmp_path / "context-map" / "index.json",
            },
            repomap={"enabled": False},
            cochange={"enabled": False},
            scip={"enabled": False},
            trace={
                "export_enabled": False,
                "otlp_enabled": True,
                "otlp_endpoint": f"file://{otlp_path}",
            },
        )
    )

    payload = orchestrator.plan(
        query="implement app run helper",
        repo="ace-lite-engine",
        root=str(tmp_path),
    )

    trace_info = payload["observability"].get("trace_export", {})
    assert trace_info.get("enabled") is True
    otlp_info = trace_info.get("otlp", {})
    assert otlp_info.get("exported") is True
    assert otlp_info.get("transport") == "file"
    assert otlp_path.exists()
