from __future__ import annotations

from ace_lite.rankers.bm25 import rank_candidates_bm25


def test_bm25_ranks_camel_case_symbols_with_split_terms() -> None:
    files_map = {
        "src/user_repo.py": {
            "language": "python",
            "module": "src.user_repo",
            "symbols": [{"name": "getUserById", "qualified_name": "src.user_repo.getUserById"}],
            "imports": [],
        },
        "src/other.py": {
            "language": "python",
            "module": "src.other",
            "symbols": [{"name": "unrelated", "qualified_name": "src.other.unrelated"}],
            "imports": [],
        },
    }

    ranked = rank_candidates_bm25(files_map, ["user", "id"], min_score=0)
    assert ranked
    assert ranked[0]["path"] == "src/user_repo.py"

