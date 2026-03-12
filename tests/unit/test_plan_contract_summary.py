from __future__ import annotations

from ace_lite.plan_contract_summary import build_plan_contract_summary


def test_build_plan_contract_summary_surfaces_versions() -> None:
    payload = build_plan_contract_summary(
        index_payload={
            "chunk_contract": {"schema_version": "chunk-v1"},
            "subgraph_payload": {
                "payload_version": "subgraph-v1",
                "taxonomy_version": "taxonomy-v1",
            },
        },
        source_plan_payload={
            "chunk_contract": {"schema_version": "chunk-v1"},
            "prompt_rendering_boundary": {"boundary_version": "prompt-v1"},
            "subgraph_payload": {
                "payload_version": "subgraph-v2",
                "taxonomy_version": "taxonomy-v2",
            },
        },
    )

    assert payload == {
        "index_chunk_contract_version": "chunk-v1",
        "source_plan_chunk_contract_version": "chunk-v1",
        "prompt_rendering_boundary_version": "prompt-v1",
        "index_subgraph_payload_version": "subgraph-v1",
        "source_plan_subgraph_payload_version": "subgraph-v2",
        "subgraph_taxonomy_version": "taxonomy-v2",
    }


def test_build_plan_contract_summary_is_fail_open_for_missing_fields() -> None:
    payload = build_plan_contract_summary(index_payload=None, source_plan_payload={})

    assert payload == {
        "index_chunk_contract_version": "",
        "source_plan_chunk_contract_version": "",
        "prompt_rendering_boundary_version": "",
        "index_subgraph_payload_version": "",
        "source_plan_subgraph_payload_version": "",
        "subgraph_taxonomy_version": "",
    }


def test_build_plan_contract_summary_accepts_legacy_subgraph_aliases() -> None:
    payload = build_plan_contract_summary(
        index_payload={
            "graph_payload": {
                "graph_payload_version": "graph-v1",
                "subgraph_taxonomy_version": "taxonomy-v1",
            }
        },
        source_plan_payload={
            "subgraph": {
                "version": "graph-v2",
            }
        },
    )

    assert payload == {
        "index_chunk_contract_version": "",
        "source_plan_chunk_contract_version": "",
        "prompt_rendering_boundary_version": "",
        "index_subgraph_payload_version": "graph-v1",
        "source_plan_subgraph_payload_version": "graph-v2",
        "subgraph_taxonomy_version": "taxonomy-v1",
    }
