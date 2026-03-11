from __future__ import annotations

import json
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import ace_lite.memory.local_cache as local_cache_module
from ace_lite.memory import (
    HybridMemoryProvider,
    LocalCacheProvider,
    LocalNotesProvider,
    MemoryRecord,
    MemoryRecordCompact,
)


class _ImmediateLanePool:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def submit(self, lane: str, fn, *args, **kwargs) -> Future:
        self.calls.append(str(lane))
        future: Future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:  # pragma: no cover - defensive path
            future.set_exception(exc)
        return future


class _StubProvider:
    def __init__(
        self,
        *,
        channel: str,
        compact_rows: list[MemoryRecordCompact],
        full_rows: list[MemoryRecord],
    ) -> None:
        self.channel = channel
        self.last_channel_used = channel
        self.fallback_reason = None
        self.strategy = "semantic"
        self.compact_rows = compact_rows
        self.full_rows = {
            str(row.handle): MemoryRecord(
                text=row.text,
                score=row.score,
                metadata=dict(row.metadata),
                handle=str(row.handle),
                source=row.source,
            )
            for row in full_rows
        }
        self.search_calls = 0
        self.fetch_calls = 0
        self.last_container_tag_fallback: str | None = None

    def search_compact(
        self,
        query: str,
        *,
        limit: int | None = None,
        container_tag: str | None = None,
    ) -> list[MemoryRecordCompact]:
        self.search_calls += 1
        self.last_container_tag_fallback = None
        rows = list(self.compact_rows)
        if isinstance(limit, int) and limit > 0:
            return rows[:limit]
        return rows

    def fetch(self, handles: list[str]) -> list[MemoryRecord]:
        self.fetch_calls += 1
        rows: list[MemoryRecord] = []
        for handle in handles:
            row = self.full_rows.get(str(handle))
            if row is not None:
                rows.append(row)
        return rows


def _write_notes(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text((content + "\n") if content else "", encoding="utf-8")


def test_hybrid_memory_provider_rrf_merges_results() -> None:
    semantic = _StubProvider(
        channel="mcp",
        compact_rows=[
            MemoryRecordCompact(
                handle="a", preview="alpha", source="mcp", est_tokens=1
            ),
            MemoryRecordCompact(handle="b", preview="beta", source="mcp", est_tokens=1),
        ],
        full_rows=[
            MemoryRecord(text="alpha", handle="a", source="mcp"),
            MemoryRecord(text="beta", handle="b", source="mcp"),
        ],
    )
    keyword = _StubProvider(
        channel="rest",
        compact_rows=[
            MemoryRecordCompact(
                handle="b", preview="beta", source="rest", est_tokens=1
            ),
            MemoryRecordCompact(
                handle="c", preview="charlie", source="rest", est_tokens=1
            ),
        ],
        full_rows=[
            MemoryRecord(text="beta", handle="b", source="rest"),
            MemoryRecord(text="charlie", handle="c", source="rest"),
        ],
    )

    provider = HybridMemoryProvider(
        semantic=semantic, keyword=keyword, rrf_k=60, limit=5
    )
    rows = provider.search_compact("q")

    assert [row.handle for row in rows] == ["b", "a", "c"]
    assert provider.last_hybrid_stats["semantic_candidates"] == 2
    assert provider.last_hybrid_stats["keyword_candidates"] == 2
    assert provider.last_hybrid_stats["merged_candidates"] == 3

    fetched = provider.fetch(["c", "b"])
    assert [row.handle for row in fetched] == ["c", "b"]


def test_hybrid_memory_provider_uses_configured_lanes() -> None:
    semantic = _StubProvider(
        channel="mcp",
        compact_rows=[
            MemoryRecordCompact(
                handle="s1",
                preview="semantic result",
                source="mcp",
                est_tokens=2,
            )
        ],
        full_rows=[MemoryRecord(text="semantic result", handle="s1", source="mcp")],
    )
    keyword = _StubProvider(
        channel="rest",
        compact_rows=[
            MemoryRecordCompact(
                handle="k1",
                preview="keyword result",
                source="rest",
                est_tokens=2,
            )
        ],
        full_rows=[MemoryRecord(text="keyword result", handle="k1", source="rest")],
    )
    lanes = _ImmediateLanePool()
    provider = HybridMemoryProvider(
        semantic=semantic,
        keyword=keyword,
        lane_pool=lanes,
        search_lane="main",
        fetch_lane="sub",
    )

    search_rows = provider.search_compact("result")
    assert [row.handle for row in search_rows] == ["k1", "s1"]

    fetched = provider.fetch(["k1", "s1"])
    assert [row.handle for row in fetched] == ["k1", "s1"]
    assert lanes.calls == ["main", "main", "sub", "sub"]


def test_local_cache_provider_write_through_and_ttl(
    tmp_path: Path,
    monkeypatch,
) -> None:
    upstream = _StubProvider(
        channel="mcp",
        compact_rows=[
            MemoryRecordCompact(
                handle="m1",
                preview="cached memory",
                score=0.8,
                metadata={"path": "docs/a.md"},
                est_tokens=2,
                source="mcp",
            )
        ],
        full_rows=[
            MemoryRecord(
                text="cached memory",
                score=0.8,
                metadata={"path": "docs/a.md"},
                handle="m1",
                source="mcp",
            )
        ],
    )

    now = [1000.0]
    monkeypatch.setattr(local_cache_module.time, "time", lambda: now[0])

    provider = LocalCacheProvider(
        upstream,
        cache_path=tmp_path / "context-map" / "memory_cache.jsonl",
        ttl_seconds=1,
        max_entries=32,
    )

    first = provider.search_compact("query")
    assert [row.handle for row in first] == ["m1"]
    assert upstream.search_calls == 1
    assert provider.last_cache_stats["hit_count"] == 0

    second = provider.search_compact("query")
    assert [row.handle for row in second] == ["m1"]
    assert upstream.search_calls == 1
    assert provider.last_channel_used.endswith(":hit")
    assert provider.last_cache_stats["hit_count"] == 1

    fetched = provider.fetch(["m1"])
    assert fetched[0].text == "cached memory"

    now[0] = 1002.0
    third = provider.search_compact("query")
    assert [row.handle for row in third] == ["m1"]
    assert upstream.search_calls == 2


def test_local_cache_provider_isolates_namespace_fingerprint(tmp_path: Path) -> None:
    upstream = _StubProvider(
        channel="mcp",
        compact_rows=[
            MemoryRecordCompact(
                handle="m1",
                preview="cached memory",
                score=0.8,
                metadata={"path": "docs/a.md"},
                est_tokens=2,
                source="mcp",
            )
        ],
        full_rows=[
            MemoryRecord(
                text="cached memory",
                score=0.8,
                metadata={"path": "docs/a.md"},
                handle="m1",
                source="mcp",
            )
        ],
    )

    provider = LocalCacheProvider(
        upstream,
        cache_path=tmp_path / "context-map" / "memory_cache.jsonl",
        ttl_seconds=3600,
        max_entries=64,
    )

    rows_a_first = provider.search_compact("query", container_tag="repo:a")
    rows_b_first = provider.search_compact("query", container_tag="repo:b")
    rows_a_second = provider.search_compact("query", container_tag="repo:a")

    assert [row.handle for row in rows_a_first] == ["m1"]
    assert [row.handle for row in rows_b_first] == ["m1"]
    assert [row.handle for row in rows_a_second] == ["m1"]
    assert upstream.search_calls == 2


def test_local_cache_provider_defers_full_fetch_until_fetch_call(
    tmp_path: Path,
) -> None:
    upstream = _StubProvider(
        channel="mcp",
        compact_rows=[
            MemoryRecordCompact(
                handle="m2",
                preview="compact only",
                score=0.6,
                metadata={"path": "src/mod.py"},
                est_tokens=2,
                source="mcp",
            )
        ],
        full_rows=[
            MemoryRecord(
                text="full record text",
                score=0.6,
                metadata={"path": "src/mod.py"},
                handle="m2",
                source="mcp",
            )
        ],
    )
    provider = LocalCacheProvider(
        upstream,
        cache_path=tmp_path / "context-map" / "memory_cache.jsonl",
    )

    rows = provider.search_compact("query")
    assert [row.handle for row in rows] == ["m2"]
    assert upstream.fetch_calls == 0

    fetched = provider.fetch(["m2"])
    assert [row.handle for row in fetched] == ["m2"]
    assert fetched[0].text == "full record text"
    assert upstream.fetch_calls == 1

    fetched_again = provider.fetch(["m2"])
    assert [row.handle for row in fetched_again] == ["m2"]
    assert upstream.fetch_calls == 1


def test_local_cache_provider_fetch_returns_partial_when_upstream_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    upstream = _StubProvider(
        channel="mcp",
        compact_rows=[
            MemoryRecordCompact(
                handle="m1",
                preview="preview-one",
                score=0.7,
                metadata={"path": "docs/a.md"},
                est_tokens=2,
                source="mcp",
            ),
            MemoryRecordCompact(
                handle="m2",
                preview="preview-two",
                score=0.5,
                metadata={"path": "docs/b.md"},
                est_tokens=2,
                source="mcp",
            ),
        ],
        full_rows=[
            MemoryRecord(
                text="full-one",
                score=0.7,
                metadata={"path": "docs/a.md"},
                handle="m1",
                source="mcp",
            )
        ],
    )

    provider = LocalCacheProvider(
        upstream,
        cache_path=tmp_path / "context-map" / "memory_cache.jsonl",
    )

    provider.search_compact("query")
    warm = provider.fetch(["m1"])
    assert [row.handle for row in warm] == ["m1"]

    def _raise_fetch(handles: list[str]) -> list[MemoryRecord]:
        raise RuntimeError("upstream down")

    monkeypatch.setattr(upstream, "fetch", _raise_fetch)

    partial = provider.fetch(["m1", "m2"])
    assert [row.handle for row in partial] == ["m1"]
    assert provider.fallback_reason == "upstream_fetch_error:RuntimeError"
    assert provider.last_channel_used.endswith(":fetch_partial")


def test_local_cache_provider_concurrent_search_writes_jsonl(
    tmp_path: Path,
) -> None:
    upstream = _StubProvider(
        channel="mcp",
        compact_rows=[
            MemoryRecordCompact(
                handle="m1",
                preview="cached memory",
                score=0.8,
                metadata={"path": "docs/a.md"},
                est_tokens=2,
                source="mcp",
            )
        ],
        full_rows=[
            MemoryRecord(
                text="cached memory",
                score=0.8,
                metadata={"path": "docs/a.md"},
                handle="m1",
                source="mcp",
            )
        ],
    )

    cache_path = tmp_path / "context-map" / "memory_cache.jsonl"
    provider = LocalCacheProvider(
        upstream,
        cache_path=cache_path,
        ttl_seconds=3600,
        max_entries=128,
    )

    errors: list[Exception] = []

    def _run(i: int) -> None:
        try:
            provider.search_compact(f"query-{i}")
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_run, i) for i in range(24)]
        for future in futures:
            future.result()

    assert not errors
    assert cache_path.exists()
    lines = cache_path.read_text(encoding="utf-8").splitlines()
    assert lines
    for line in lines:
        payload = json.loads(line)
        assert isinstance(payload, dict)


def test_local_notes_provider_supplement_mode_merges_and_tracks_stats(
    tmp_path: Path,
) -> None:
    upstream = _StubProvider(
        channel="mcp",
        compact_rows=[
            MemoryRecordCompact(
                handle="upstream-1",
                preview="upstream fix memory",
                score=0.5,
                metadata={"namespace": "repo:a"},
                est_tokens=3,
                source="mcp",
            )
        ],
        full_rows=[
            MemoryRecord(
                text="upstream fix memory",
                score=0.5,
                metadata={"namespace": "repo:a"},
                handle="upstream-1",
                source="mcp",
            )
        ],
    )
    upstream.fallback_reason = "primary_error:RuntimeError"
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    _write_notes(
        notes_path,
        [
            {
                "text": "fix auth fallback in orchestrator stage",
                "namespace": "repo:a",
                "captured_at": "2026-02-13T00:00:00+00:00",
            },
            {
                "text": "unrelated note",
                "namespace": "repo:a",
            },
        ],
    )

    provider = LocalNotesProvider(
        upstream,
        notes_path=notes_path,
        default_limit=5,
        mode="supplement",
    )

    rows = provider.search_compact("fix auth", container_tag="repo:a")

    assert [row.source for row in rows] == ["mcp", "local_notes"]
    assert provider.last_channel_used == "mcp+local_notes"
    assert provider.fallback_reason == "primary_error:RuntimeError"
    assert provider.last_notes_stats["loaded_count"] == 2
    assert provider.last_notes_stats["matched_count"] == 1
    assert provider.last_notes_stats["selected_count"] == 1
    assert provider.last_notes_stats["namespace_filtered_count"] == 0


def test_local_notes_provider_namespace_filter_and_prefer_local_order(
    tmp_path: Path,
) -> None:
    upstream = _StubProvider(channel="mcp", compact_rows=[], full_rows=[])
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    _write_notes(
        notes_path,
        [
            {
                "text": "fix auth bug for repo a",
                "namespace": "repo:a",
                "captured_at": "2026-02-13T01:00:00+00:00",
            },
            {
                "text": "fix auth bug for repo b",
                "namespace": "repo:b",
                "captured_at": "2026-02-13T02:00:00+00:00",
            },
        ],
    )
    provider = LocalNotesProvider(
        upstream,
        notes_path=notes_path,
        default_limit=4,
        mode="prefer_local",
    )

    rows = provider.search_compact("fix auth", container_tag="repo:a")

    assert len(rows) == 1
    assert rows[0].source == "local_notes"
    assert rows[0].metadata.get("namespace") == "repo:a"
    assert provider.last_notes_stats["namespace_filtered_count"] == 1


def test_local_notes_provider_local_only_skips_upstream_fetch(tmp_path: Path) -> None:
    upstream = _StubProvider(
        channel="mcp",
        compact_rows=[
            MemoryRecordCompact(
                handle="upstream-1",
                preview="upstream memory",
                est_tokens=2,
                source="mcp",
            )
        ],
        full_rows=[
            MemoryRecord(text="upstream memory", handle="upstream-1", source="mcp")
        ],
    )
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    _write_notes(
        notes_path,
        [
            {
                "text": "fix local-only note",
                "namespace": "repo:a",
            }
        ],
    )
    provider = LocalNotesProvider(
        upstream,
        notes_path=notes_path,
        default_limit=4,
        mode="local_only",
    )

    rows = provider.search_compact("fix local", container_tag="repo:a")

    assert len(rows) == 1
    assert rows[0].source == "local_notes"
    assert upstream.search_calls == 0

    fetched = provider.fetch([rows[0].handle])
    assert len(fetched) == 1
    assert fetched[0].source == "local_notes"
    assert upstream.fetch_calls == 0


def test_local_notes_provider_prunes_expired_notes(tmp_path: Path) -> None:
    upstream = _StubProvider(channel="mcp", compact_rows=[], full_rows=[])
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    _write_notes(
        notes_path,
        [
            {
                "text": "stale memory note",
                "namespace": "repo:a",
                "captured_at": "2020-01-01T00:00:00+00:00",
            },
            {
                "text": "fresh memory note",
                "namespace": "repo:a",
                "captured_at": "2099-01-01T00:00:00+00:00",
            },
        ],
    )
    provider = LocalNotesProvider(
        upstream,
        notes_path=notes_path,
        mode="local_only",
        expiry_enabled=True,
        ttl_days=90,
        max_age_days=365,
    )

    rows = provider.search_compact("memory note", container_tag="repo:a")

    assert len(rows) == 1
    assert rows[0].preview == "fresh memory note"
    assert provider.last_notes_stats["expired_count"] == 1
    persisted = [line for line in notes_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(persisted) == 1


def test_local_notes_provider_uses_cached_rows_when_file_unchanged(
    tmp_path: Path,
) -> None:
    upstream = _StubProvider(channel="mcp", compact_rows=[], full_rows=[])
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    _write_notes(
        notes_path,
        [
            {
                "text": "cache me for repeated query",
                "namespace": "repo:a",
                "captured_at": "2026-02-13T03:00:00+00:00",
            },
        ],
    )
    provider = LocalNotesProvider(
        upstream,
        notes_path=notes_path,
        default_limit=3,
        mode="local_only",
    )

    first = provider.search_compact("cache me", container_tag="repo:a")
    assert len(first) == 1
    assert provider.last_notes_stats["cache_hit"] is False

    second = provider.search_compact("cache me", container_tag="repo:a")
    assert len(second) == 1
    assert provider.last_notes_stats["cache_hit"] is True


def test_local_notes_provider_invalidates_cache_when_notes_file_changes(
    tmp_path: Path,
) -> None:
    upstream = _StubProvider(channel="mcp", compact_rows=[], full_rows=[])
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    _write_notes(
        notes_path,
        [
            {
                "text": "alpha seed note",
                "namespace": "repo:a",
            },
        ],
    )
    provider = LocalNotesProvider(
        upstream,
        notes_path=notes_path,
        default_limit=4,
        mode="local_only",
    )

    baseline = provider.search_compact("beta", container_tag="repo:a")
    assert baseline == []
    assert provider.last_notes_stats["cache_hit"] is False

    _write_notes(
        notes_path,
        [
            {
                "text": "alpha seed note",
                "namespace": "repo:a",
            },
            {
                "text": "beta follow-up note",
                "namespace": "repo:a",
            },
        ],
    )

    refreshed = provider.search_compact("beta", container_tag="repo:a")
    assert len(refreshed) == 1
    assert refreshed[0].preview == "beta follow-up note"
    assert provider.last_notes_stats["cache_hit"] is False

    warm = provider.search_compact("beta", container_tag="repo:a")
    assert len(warm) == 1
    assert provider.last_notes_stats["cache_hit"] is True
