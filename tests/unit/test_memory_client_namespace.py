from __future__ import annotations

from typing import Any

from ace_lite.memory_clients.mcp_client import OpenMemoryMcpClient
from ace_lite.memory_clients.rest_client import OpenMemoryRestClient


def test_rest_client_falls_back_without_container_tag() -> None:
    client = OpenMemoryRestClient(
        base_url="http://localhost:8765",
        endpoints=["POST /api/v1/memories/search"],
    )

    payloads: list[dict[str, Any]] = []

    def fake_post_json(url: str, payload: dict[str, Any]) -> Any:
        payloads.append(dict(payload))
        if "containerTag" in payload:
            raise ValueError("unsupported containerTag")
        return {"results": [{"memory": "ok", "metadata": {}}]}

    client._post_json = fake_post_json  # type: ignore[method-assign]

    result = client.search(query="q", container_tag="repo:demo", limit=3)

    assert isinstance(result, dict)
    assert isinstance(result.get("results"), list)
    assert payloads
    assert any("containerTag" in payload for payload in payloads)
    assert any("containerTag" not in payload for payload in payloads)
    assert client.last_container_tag_fallback == "backend_unsupported_container_tag"


def test_mcp_client_falls_back_without_container_tag() -> None:
    client = OpenMemoryMcpClient(
        base_url="http://localhost:8765",
        endpoints=["/mcp/tools/search_memory"],
    )

    payloads: list[dict[str, Any]] = []

    def fake_post_json(url: str, payload: dict[str, Any]) -> Any:
        payloads.append(dict(payload))
        if "containerTag" in payload or "container_tag" in payload:
            raise ValueError("unsupported containerTag")
        return {"results": [{"memory": "ok", "metadata": {}}]}

    client._post_json = fake_post_json  # type: ignore[method-assign]

    result = client.search(query="q", container_tag="repo:demo", limit=3)

    assert isinstance(result, dict)
    assert isinstance(result.get("results"), list)
    assert payloads
    assert any("containerTag" in payload for payload in payloads)
    assert any("container_tag" in payload for payload in payloads)
    assert any(
        "containerTag" not in payload and "container_tag" not in payload
        for payload in payloads
    )
    assert client.last_container_tag_fallback == "backend_unsupported_container_tag"


def test_rest_client_app_fallback_respects_container_tag_scope() -> None:
    client = OpenMemoryRestClient(
        base_url="http://localhost:8765",
        endpoints=("GET /api/v1/memories/",),
    )

    def fake_get(url: str, params: dict[str, object]) -> object:
        if url.endswith("/api/v1/memories/"):
            return {"items": [], "total": 0, "page": 1, "size": 5, "pages": 0}
        if url.endswith("/api/v1/apps/"):
            return {
                "apps": [
                    {
                        "id": "app-1",
                        "name": "codex",
                        "is_active": True,
                    }
                ]
            }
        if url.endswith("/api/v1/apps/app-1/memories"):
            return {
                "total": 3,
                "page": 1,
                "page_size": 50,
                "memories": [
                    {
                        "content": "repo scoped memory",
                        "namespace": "repo:demo",
                        "repo": "demo",
                    },
                    {
                        "content": "same repo via metadata",
                        "metadata_": {"repo_identity": "demo"},
                    },
                    {
                        "content": "cross repo memory",
                        "namespace": "repo:other",
                        "repo": "other",
                    },
                ],
            }
        raise AssertionError(url)

    client._get_json = fake_get  # type: ignore[method-assign]

    payload = client.search(
        query="repo memory",
        user_id=None,
        app="codex",
        container_tag="repo:demo",
        limit=5,
    )

    assert [row["memory"] for row in payload["results"]] == [
        "repo scoped memory",
        "same repo via metadata",
    ]


def test_rest_client_app_fallback_drops_unscoped_results_when_container_tag_set() -> None:
    client = OpenMemoryRestClient(
        base_url="http://localhost:8765",
        endpoints=("GET /api/v1/memories/",),
    )

    def fake_get(url: str, params: dict[str, object]) -> object:
        if url.endswith("/api/v1/memories/"):
            return {"items": [], "total": 0, "page": 1, "size": 5, "pages": 0}
        if url.endswith("/api/v1/apps/"):
            return {
                "apps": [
                    {
                        "id": "app-1",
                        "name": "codex",
                        "is_active": True,
                    }
                ]
            }
        if url.endswith("/api/v1/apps/app-1/memories"):
            return {
                "total": 2,
                "page": 1,
                "page_size": 50,
                "memories": [
                    {"content": "global memory one", "metadata_": {}},
                    {"content": "global memory two", "metadata_": {}},
                ],
            }
        raise AssertionError(url)

    client._get_json = fake_get  # type: ignore[method-assign]

    payload = client.search(
        query="global memory",
        user_id=None,
        app="codex",
        container_tag="repo:demo",
        limit=5,
    )

    assert payload["results"] == []
