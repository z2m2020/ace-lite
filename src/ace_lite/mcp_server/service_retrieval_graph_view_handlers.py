"""Handler for ace_retrieval_graph_view MCP tool."""

from __future__ import annotations

from typing import Any

from ace_lite.retrieval_graph_view import (
    RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION,
    build_retrieval_graph_view,
)


def handle_retrieval_graph_view_request(
    *,
    plan_payload: dict[str, Any],
    limit: int,
    max_hops: int,
    repo: str | None,
    root: str | None,
    query: str,
) -> dict[str, Any]:
    """Build a retrieval graph view from an already-computed plan payload.

    Parameters
    ----------
    plan_payload:
        The full plan payload from ace_plan (with include_full_payload=True).
    limit:
        Maximum number of nodes in the graph view.
    max_hops:
        Maximum hop depth for neighbor traversal.
    repo:
        Repository name for schema metadata.
    root:
        Root path for schema metadata.
    query:
        The original query for schema metadata.

    Returns
    -------
    dict[str, Any]
        The retrieval graph view payload.
    """
    return build_retrieval_graph_view(
        plan_payload=plan_payload,
        limit=limit,
        max_hops=max_hops,
        repo=repo,
        root=root,
        query=query,
    )


__all__ = [
    "RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION",
    "handle_retrieval_graph_view_request",
]
