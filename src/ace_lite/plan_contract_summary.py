from __future__ import annotations

from typing import Any


def _coerce_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _resolve_subgraph_payload(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("subgraph_payload", "subgraph", "graph_payload"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _resolve_payload_version(payload: dict[str, Any]) -> str:
    for key in ("payload_version", "graph_payload_version", "version"):
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _resolve_taxonomy_version(
    index_subgraph_payload: dict[str, Any],
    source_plan_subgraph_payload: dict[str, Any],
) -> str:
    for payload in (source_plan_subgraph_payload, index_subgraph_payload):
        for key in ("taxonomy_version", "subgraph_taxonomy_version"):
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
    return ""


def build_plan_contract_summary(
    index_payload: dict[str, Any] | None,
    source_plan_payload: dict[str, Any] | None,
) -> dict[str, str]:
    normalized_index_payload = _coerce_dict(index_payload)
    normalized_source_plan_payload = _coerce_dict(source_plan_payload)

    index_chunk_contract = _coerce_dict(normalized_index_payload.get("chunk_contract"))
    source_plan_chunk_contract = _coerce_dict(
        normalized_source_plan_payload.get("chunk_contract")
    )
    prompt_rendering_boundary = _coerce_dict(
        normalized_source_plan_payload.get("prompt_rendering_boundary")
    )
    index_subgraph_payload = _resolve_subgraph_payload(normalized_index_payload)
    source_plan_subgraph_payload = _resolve_subgraph_payload(
        normalized_source_plan_payload
    )

    return {
        "index_chunk_contract_version": str(
            index_chunk_contract.get("schema_version") or ""
        ),
        "source_plan_chunk_contract_version": str(
            source_plan_chunk_contract.get("schema_version") or ""
        ),
        "prompt_rendering_boundary_version": str(
            prompt_rendering_boundary.get("boundary_version") or ""
        ),
        "index_subgraph_payload_version": _resolve_payload_version(
            index_subgraph_payload
        ),
        "source_plan_subgraph_payload_version": _resolve_payload_version(
            source_plan_subgraph_payload
        ),
        "subgraph_taxonomy_version": _resolve_taxonomy_version(
            index_subgraph_payload=index_subgraph_payload,
            source_plan_subgraph_payload=source_plan_subgraph_payload,
        ),
    }


__all__ = ["build_plan_contract_summary"]
