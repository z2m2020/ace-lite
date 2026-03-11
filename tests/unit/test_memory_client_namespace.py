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
