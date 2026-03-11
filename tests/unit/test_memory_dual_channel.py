from __future__ import annotations

from ace_lite.memory import (
    DualChannelMemoryProvider,
    MemoryRecord,
    MemoryRecordCompact,
)
from ace_lite.memory_clients.mcp_client import OpenMemoryMcpClient
from ace_lite.memory_clients.rest_client import OpenMemoryRestClient


class _StaticProvider:
    def __init__(self, records: list[MemoryRecord], *, channel: str = "static") -> None:
        self._records = records
        self.last_channel_used = channel

    def search_compact(self, query: str, *, limit: int | None = None) -> list[MemoryRecordCompact]:
        rows = [
            MemoryRecordCompact(
                handle=f"{self.last_channel_used}:{idx}",
                preview=record.text,
                score=record.score,
                metadata=dict(record.metadata),
                est_tokens=max(1, len(record.text.split())),
                source=self.last_channel_used,
            )
            for idx, record in enumerate(self._records, start=1)
        ]
        if isinstance(limit, int) and limit > 0:
            return rows[:limit]
        return rows

    def fetch(self, handles: list[str]) -> list[MemoryRecord]:
        records: list[MemoryRecord] = []
        for handle in handles:
            if not handle.startswith(f"{self.last_channel_used}:"):
                continue
            try:
                idx = int(handle.split(":", 1)[1]) - 1
            except (ValueError, IndexError):
                continue
            if idx < 0 or idx >= len(self._records):
                continue
            record = self._records[idx]
            records.append(
                MemoryRecord(
                    text=record.text,
                    score=record.score,
                    metadata=dict(record.metadata),
                    handle=handle,
                    source=self.last_channel_used,
                )
            )
        return records


class _ErrorProvider:
    last_channel_used = "error"

    def search_compact(self, query: str, *, limit: int | None = None) -> list[MemoryRecordCompact]:
        raise RuntimeError("boom")

    def fetch(self, handles: list[str]) -> list[MemoryRecord]:
        raise RuntimeError("boom")


def test_dual_channel_fallback_to_secondary_on_primary_error() -> None:
    primary = _ErrorProvider()
    secondary = _StaticProvider([MemoryRecord(text="fallback")], channel="rest")

    provider = DualChannelMemoryProvider(primary=primary, secondary=secondary)
    rows = provider.search_compact("query")

    assert [row.preview for row in rows] == ["fallback"]
    assert provider.last_channel_used == "rest"
    assert provider.fallback_reason == "primary_error:RuntimeError"


def test_dual_channel_dedupes_merged_records() -> None:
    duplicated = MemoryRecord(text="same", metadata={"path": "a.py"})
    primary = _StaticProvider([duplicated], channel="mcp")
    secondary = _StaticProvider([duplicated, MemoryRecord(text="extra")], channel="rest")

    provider = DualChannelMemoryProvider(
        primary=primary,
        secondary=secondary,
        fallback_on_empty=True,
        merge_on_fallback=True,
    )

    rows = provider.search_compact("query")
    assert [row.preview for row in rows] == ["same"]


def test_rest_client_endpoint_failover() -> None:
    client = OpenMemoryRestClient(
        base_url="http://localhost:8765",
        endpoints=("/v1", "/v2"),
        timeout_seconds=1,
    )

    calls: list[str] = []

    def fake_post(url: str, payload: dict[str, object]) -> object:
        calls.append(url)
        if url.endswith("/v1"):
            raise TimeoutError("timeout")
        return {"results": [{"memory": "ok", "score": 1.0}]}

    client._post_json = fake_post  # type: ignore[method-assign]
    payload = client.search(query="q")

    assert len(calls) == 2
    assert calls[0].endswith("/v1")
    assert calls[1].endswith("/v2")
    assert payload["results"][0]["memory"] == "ok"


def test_rest_client_normalizes_paginated_items() -> None:
    payload = OpenMemoryRestClient._normalize_response(
        {
            "items": [
                {
                    "id": "m1",
                    "content": "hello memory",
                    "metadata_": {"path": "docs/a.md"},
                    "app_name": "codex",
                }
            ],
            "total": 1,
            "page": 1,
            "size": 10,
            "pages": 1,
        },
        query="hello",
        limit=5,
    )

    assert payload["results"][0]["memory"] == "hello memory"
    assert payload["results"][0]["metadata"]["path"] == "docs/a.md"
    assert payload["results"][0]["metadata"]["app_name"] == "codex"


def test_rest_client_fallback_to_app_memories_without_user_id() -> None:
    client = OpenMemoryRestClient(
        base_url="http://localhost:8765",
        endpoints=("GET /api/v1/memories/",),
        timeout_seconds=1,
    )

    calls: list[tuple[str, dict[str, object]]] = []

    def fake_get(url: str, params: dict[str, object]) -> object:
        calls.append((url, params))
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
                "page_size": 20,
                "memories": [
                    {"content": "fix openmemory 405 issue", "metadata_": {"path": "docs/fix.md"}},
                    {"content": "random unrelated note", "metadata_": {}},
                ],
            }
        raise AssertionError(url)

    client._get_json = fake_get  # type: ignore[method-assign]
    payload = client.search(query="openmemory 405", user_id=None, app="codex", limit=3)

    assert payload["results"]
    assert payload["results"][0]["memory"] == "fix openmemory 405 issue"
    assert calls[0][0].endswith("/api/v1/apps/")


def test_mcp_client_normalizes_jsonrpc_content() -> None:
    client = OpenMemoryMcpClient(base_url="http://localhost:8765", endpoints=("/mcp",), timeout_seconds=1)

    def fake_post(url: str, payload: dict[str, object]) -> object:
        return {
            "jsonrpc": "2.0",
            "id": "ace-lite",
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": '{"results": [{"memory": "mcp-ok", "score": 0.9}]}',
                    }
                ]
            },
        }

    client._post_json = fake_post  # type: ignore[method-assign]
    payload = client.search(query="q")

    assert payload["results"][0]["memory"] == "mcp-ok"
