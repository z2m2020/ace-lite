from __future__ import annotations

from pathlib import Path

from ace_lite.mcp_server.service_plan_handlers import handle_plan_request


def test_handle_plan_request_sanitizes_report_only_artifacts_in_full_payload(
    tmp_path: Path,
) -> None:
    result = handle_plan_request(
        query="inspect planner",
        repo="demo",
        root_path=tmp_path,
        default_repo="demo",
        skills_path=tmp_path / "skills",
        config_pack_path=None,
        time_range=None,
        start_date=None,
        end_date=None,
        memory_primary=None,
        memory_secondary=None,
        lsp_enabled=False,
        plugins_enabled=False,
        top_k_files=8,
        min_candidate_score=2,
        retrieval_policy="auto",
        include_full_payload=True,
        timeout_seconds=5.0,
        default_timeout_seconds=25.0,
        run_plan_payload_fn=lambda *args, **kwargs: {
            "observability": {"total_ms": 12.5},
            "context_report": {"schema_version": "context_report_v1"},
            "source_plan": {
                "steps": [{"stage": "source_plan"}],
                "candidate_files": [{"path": "src/app.py"}],
                "retrieval_graph_view": {
                    "schema_version": "retrieval_graph_view_v1"
                },
            },
            "index": {
                "chunk_contract": {"schema_version": "chunk-v1"},
                "subgraph_payload": {
                    "payload_version": "subgraph-v1",
                    "taxonomy_version": "taxonomy-v1",
                },
            },
        },
        plan_quick_fn=lambda **kwargs: {},
    )

    assert result["ok"] is True
    assert result["candidate_files"] == 1
    assert "context_report" not in result["plan"]
    assert "retrieval_graph_view" not in result["plan"]["source_plan"]
