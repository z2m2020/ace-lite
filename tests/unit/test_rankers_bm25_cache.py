from __future__ import annotations

from typing import Any

import ace_lite.rankers.bm25 as bm25_module


def test_rank_candidates_bm25_reuses_cached_docs(monkeypatch: Any) -> None:
    bm25_module._BM25_DOC_CACHE.clear()

    files_map = {
        "src/user_repo.py": {
            "language": "python",
            "module": "src.user_repo",
            "tier": "first_party",
            "symbols": [{"name": "getUserById", "qualified_name": "src.user_repo.getUserById"}],
            "imports": [],
        },
        "src/other.py": {
            "language": "python",
            "module": "src.other",
            "tier": "first_party",
            "symbols": [{"name": "unrelated", "qualified_name": "src.other.unrelated"}],
            "imports": [],
        },
    }

    first = bm25_module.rank_candidates_bm25(
        files_map,
        ["user", "id"],
        min_score=0,
        index_hash="idx-hash-1",
    )
    assert first

    def _boom(*_args: Any, **_kwargs: Any) -> list[str]:
        raise AssertionError("expected cached path to skip tokenization")

    monkeypatch.setattr(bm25_module, "_tokenize_words", _boom)

    second = bm25_module.rank_candidates_bm25(
        files_map,
        ["user", "id"],
        min_score=0,
        index_hash="idx-hash-1",
    )
    assert second


def test_rank_candidates_bm25_cache_isolated_by_files_map_scope() -> None:
    bm25_module._BM25_DOC_CACHE.clear()

    alpha_files_map = {
        "src/alpha.py": {
            "language": "python",
            "module": "src.alpha",
            "tier": "first_party",
            "symbols": [{"name": "alphaThing", "qualified_name": "src.alpha.alphaThing"}],
            "imports": [],
        },
    }
    beta_files_map = {
        "src/beta.py": {
            "language": "python",
            "module": "src.beta",
            "tier": "first_party",
            "symbols": [{"name": "betaThing", "qualified_name": "src.beta.betaThing"}],
            "imports": [],
        },
    }

    alpha_ranked = bm25_module.rank_candidates_bm25(
        alpha_files_map,
        ["alpha"],
        min_score=0,
        index_hash="shared-index-hash",
    )
    beta_ranked = bm25_module.rank_candidates_bm25(
        beta_files_map,
        ["beta"],
        min_score=0,
        index_hash="shared-index-hash",
    )

    assert [item["path"] for item in alpha_ranked] == ["src/alpha.py"]
    assert [item["path"] for item in beta_ranked] == ["src/beta.py"]
    assert len(bm25_module._BM25_DOC_CACHE) == 2
