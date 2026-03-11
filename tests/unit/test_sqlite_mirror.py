from __future__ import annotations

from pathlib import Path

import pytest

from ace_lite.sqlite_mirror import ensure_docs_fts_mirror, query_docs_fts, supports_fts5


def test_docs_mirror_rebuild_and_cache_hit(tmp_path: Path) -> None:
    if not supports_fts5():
        pytest.skip("sqlite FTS5 unavailable")

    db_path = tmp_path / "context-map" / "index.db"
    sections = [
        {
            "path": "docs/ARCHITECTURE.md",
            "heading": "Auth Architecture",
            "heading_path": "Auth Architecture",
            "body": "Retry mechanism overview for auth service.",
            "line_start": 1,
            "line_end": 3,
        },
        {
            "path": "docs/OTHER.md",
            "heading": "Other Notes",
            "heading_path": "Other Notes",
            "body": "Unrelated content.",
            "line_start": 1,
            "line_end": 2,
        },
    ]

    first = ensure_docs_fts_mirror(
        db_path=db_path,
        docs_fingerprint="fp-1",
        sections=sections,
    )
    assert first.enabled is True
    assert first.section_count == len(sections)

    second = ensure_docs_fts_mirror(
        db_path=db_path,
        docs_fingerprint="fp-1",
        sections=sections,
    )
    assert second.enabled is True
    assert second.cache_hit is True

    hits = query_docs_fts(db_path=db_path, query_expr='"retry"', limit=10)
    assert hits
    assert hits[0][0] == 1

