from __future__ import annotations

from typing import Any

from ace_lite.retrieval_shared import (
    build_retrieval_runtime_profile,
    build_selection_observability,
    load_retrieval_index_snapshot,
    extract_retrieval_terms,
    normalize_candidate_ranker,
    rank_candidate_files,
)


def test_extract_retrieval_terms_normalizes_missing_memory_stage(monkeypatch) -> None:
    import ace_lite.retrieval_shared as retrieval_shared

    captured: dict[str, Any] = {}

    def fake_extract_terms(*, query: str, memory_stage: dict[str, Any]) -> list[str]:
        captured["query"] = query
        captured["memory_stage"] = memory_stage
        return ["token"]

    monkeypatch.setattr(retrieval_shared, "extract_terms", fake_extract_terms)

    terms = extract_retrieval_terms(query="token lookup", memory_stage=None)

    assert terms == ["token"]
    assert captured == {
        "query": "token lookup",
        "memory_stage": {},
    }


def test_normalize_candidate_ranker_defaults_to_heuristic() -> None:
    assert normalize_candidate_ranker("not-a-ranker") == "heuristic"


def test_build_retrieval_runtime_profile_normalizes_runtime_controls() -> None:
    profile = build_retrieval_runtime_profile(
        candidate_ranker="not-a-ranker",
        min_candidate_score=0,
        top_k_files=0,
        hybrid_fusion_mode=" Combined ",
        hybrid_rrf_k=0,
        hybrid_weights={
            "bm25_weight": "0.5",
            "coverage_weight": 1,
            "": 2,
            "skip": "bad",
        },
        index_hash="abc123",
        allow_empty_terms_fail_open=False,
    )

    assert profile.candidate_ranker == "heuristic"
    assert profile.min_candidate_score == 1
    assert profile.top_k_files == 1
    assert profile.hybrid_fusion_mode == "combined"
    assert profile.hybrid_rrf_k == 1
    assert profile.hybrid_weights == {
        "bm25_weight": 0.5,
        "coverage_weight": 1.0,
    }
    assert profile.index_hash == "abc123"
    assert profile.allow_empty_terms_fail_open is False
    assert profile.selection_kwargs(corpus_size=3) == {
        "candidate_ranker": "heuristic",
        "min_candidate_score": 1,
        "top_k_files": 1,
        "corpus_size": 3,
        "hybrid_fusion_mode": "combined",
        "hybrid_rrf_k": 1,
        "hybrid_weights": {
            "bm25_weight": 0.5,
            "coverage_weight": 1.0,
        },
        "index_hash": "abc123",
        "allow_empty_terms_fail_open": False,
    }


def test_build_selection_observability_normalizes_rrf_payload() -> None:
    payload = build_selection_observability(
        requested_ranker="rrf_hybrid",
        selected_ranker="rrf_hybrid",
        fallback_reasons=["tiny_corpus"],
        min_score_used=1,
        corpus_size=3,
        terms_count=2,
        fusion_mode="linear",
        rrf_k=75,
    )

    assert payload == {
        "requested": "rrf_hybrid",
        "selected": "rrf_hybrid",
        "fallbacks": ["tiny_corpus"],
        "min_score_used": 1,
        "corpus_size": 3,
        "terms_count": 2,
        "fusion_mode": "rrf",
        "rrf_k": 75,
    }


def test_build_selection_observability_omits_optional_fields_and_linearizes_lexical() -> None:
    base_payload = build_selection_observability(
        requested_ranker="hybrid_re2",
        selected_ranker="heuristic",
        fallback_reasons=["", "empty_retrieval"],
        min_score_used=2,
    )

    assert base_payload == {
        "requested": "hybrid_re2",
        "selected": "heuristic",
        "fallbacks": ["empty_retrieval"],
        "min_score_used": 2,
    }

    lexical_payload = build_selection_observability(
        requested_ranker="bm25_lite",
        selected_ranker="bm25_lite",
        fallback_reasons=[],
        min_score_used=1,
        fusion_mode="combined",
        rrf_k=60,
    )

    assert lexical_payload["fusion_mode"] == "linear"
    assert lexical_payload["rrf_k"] == 60


def test_rank_candidate_files_dispatches_bm25(monkeypatch) -> None:
    import ace_lite.retrieval_shared as retrieval_shared

    captured: dict[str, Any] = {}

    def fake_bm25(
        files_map: Any,
        terms: list[str],
        *,
        min_score: int = 1,
        top_k_files: int = 8,
        heuristic_ranker: Any,
        index_hash: str | None = None,
    ) -> list[dict[str, Any]]:
        captured["files_map"] = files_map
        captured["terms"] = terms
        captured["min_score"] = min_score
        captured["top_k_files"] = top_k_files
        captured["heuristic_ranker"] = heuristic_ranker
        captured["index_hash"] = index_hash
        return [{"path": "src/auth.py", "score": 4.0}]

    monkeypatch.setattr(retrieval_shared, "rank_candidates_bm25_two_stage", fake_bm25)

    ranked = rank_candidate_files(
        files_map={"src/auth.py": {"module": "src.auth"}},
        terms=["auth"],
        candidate_ranker="bm25_lite",
        min_score=2,
        top_k_files=17,
        index_hash="abc123",
    )

    assert ranked == [{"path": "src/auth.py", "score": 4.0}]
    assert captured["files_map"] == {"src/auth.py": {"module": "src.auth"}}
    assert captured["terms"] == ["auth"]
    assert captured["min_score"] == 2
    assert captured["top_k_files"] == 17
    assert captured["heuristic_ranker"] is retrieval_shared.rank_candidates_heuristic
    assert captured["index_hash"] == "abc123"


def test_rank_candidate_files_dispatches_rrf_hybrid(monkeypatch) -> None:
    import ace_lite.retrieval_shared as retrieval_shared

    captured: dict[str, Any] = {}

    def fake_hybrid(
        files_map: Any,
        terms: list[str],
        *,
        min_score: int = 1,
        top_n: int = 8,
        fusion_mode: str = "linear",
        rrf_k: int = 60,
        weights: dict[str, float] | None = None,
        index_hash: str | None = None,
    ) -> list[dict[str, Any]]:
        captured["files_map"] = files_map
        captured["terms"] = terms
        captured["min_score"] = min_score
        captured["top_n"] = top_n
        captured["fusion_mode"] = fusion_mode
        captured["rrf_k"] = rrf_k
        captured["weights"] = weights
        captured["index_hash"] = index_hash
        return [{"path": "src/session.py", "score": 3.0}]

    monkeypatch.setattr(retrieval_shared, "rank_candidates_hybrid_re2", fake_hybrid)

    ranked = rank_candidate_files(
        files_map={"src/session.py": {"module": "src.session"}},
        terms=["session"],
        candidate_ranker="rrf_hybrid",
        min_score=1,
        top_k_files=9,
        hybrid_fusion_mode="linear",
        hybrid_rrf_k=97,
        hybrid_weights={"bm25_weight": 0.5},
        index_hash="index-hash",
    )

    assert ranked == [{"path": "src/session.py", "score": 3.0}]
    assert captured["files_map"] == {"src/session.py": {"module": "src.session"}}
    assert captured["terms"] == ["session"]
    assert captured["min_score"] == 1
    assert captured["top_n"] == 9
    assert captured["fusion_mode"] == "rrf"
    assert captured["rrf_k"] == 97
    assert captured["weights"] == {"bm25_weight": 0.5}
    assert captured["index_hash"] == "index-hash"


def test_rank_candidate_files_invalid_ranker_falls_back_to_heuristic(monkeypatch) -> None:
    import ace_lite.retrieval_shared as retrieval_shared

    captured: dict[str, Any] = {}

    def fake_heuristic(
        files_map: Any,
        terms: list[str],
        *,
        min_score: int = 1,
    ) -> list[dict[str, Any]]:
        captured["files_map"] = files_map
        captured["terms"] = terms
        captured["min_score"] = min_score
        return [{"path": "src/fallback.py", "score": 1.0}]

    monkeypatch.setattr(retrieval_shared, "rank_candidates_heuristic", fake_heuristic)

    ranked = rank_candidate_files(
        files_map={"src/fallback.py": {"module": "src.fallback"}},
        terms=["fallback"],
        candidate_ranker="nope",
        min_score=4,
    )

    assert ranked == [{"path": "src/fallback.py", "score": 1.0}]
    assert captured["files_map"] == {"src/fallback.py": {"module": "src.fallback"}}
    assert captured["terms"] == ["fallback"]
    assert captured["min_score"] == 4


def test_retrieval_runtime_profile_rank_candidates_reuses_shared_ranker(monkeypatch) -> None:
    import ace_lite.retrieval_shared as retrieval_shared

    captured: dict[str, Any] = {}

    def fake_rank_candidate_files(**kwargs: Any) -> list[dict[str, Any]]:
        captured.update(kwargs)
        return [{"path": "src/shared.py", "score": 2.0}]

    monkeypatch.setattr(retrieval_shared, "rank_candidate_files", fake_rank_candidate_files)

    profile = build_retrieval_runtime_profile(
        candidate_ranker="rrf_hybrid",
        min_candidate_score=2,
        top_k_files=5,
        hybrid_fusion_mode="linear",
        hybrid_rrf_k=91,
        hybrid_weights={"bm25_weight": 0.4},
        index_hash="shared-index",
    )
    ranked = profile.rank_candidates(
        files_map={"src/shared.py": {"module": "src.shared"}},
        terms=["shared"],
        min_score=3,
        candidate_ranker="bm25_lite",
    )

    assert ranked == [{"path": "src/shared.py", "score": 2.0}]
    assert captured == {
        "files_map": {"src/shared.py": {"module": "src.shared"}},
        "terms": ["shared"],
        "candidate_ranker": "bm25_lite",
        "min_score": 3,
        "top_k_files": 5,
        "hybrid_fusion_mode": "linear",
        "hybrid_rrf_k": 91,
        "hybrid_weights": {"bm25_weight": 0.4},
        "index_hash": "shared-index",
    }


def test_load_retrieval_index_snapshot_normalizes_files_and_hash(monkeypatch) -> None:
    import ace_lite.retrieval_shared as retrieval_shared

    monkeypatch.setattr(
        retrieval_shared,
        "build_or_refresh_index",
        lambda **kwargs: (
            {
                "git_head_sha": "abc",
                "file_count": 2,
                "languages_covered": ["python"],
                "files": {
                    "src/a.py": {"sha256": "111"},
                    "src/b.py": {"sha256": "222"},
                    "bad": "skip",
                },
            },
            {"cache_hit": True, "mode": "cache_only", "changed_files": 0},
        ),
    )

    snapshot = load_retrieval_index_snapshot(
        root_dir="repo",
        cache_path="context-map/index.json",
        languages=["python"],
        incremental=True,
    )

    assert snapshot.cache_info["cache_hit"] is True
    assert sorted(snapshot.files_map) == ["bad", "src/a.py", "src/b.py"]
    assert snapshot.corpus_size == 2
    assert isinstance(snapshot.index_hash, str)
    assert snapshot.index_hash


def test_load_retrieval_index_snapshot_fail_open_on_value_error(monkeypatch) -> None:
    import ace_lite.retrieval_shared as retrieval_shared

    def raise_value_error(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        _ = kwargs
        raise ValueError("boom")

    monkeypatch.setattr(retrieval_shared, "build_or_refresh_index", raise_value_error)

    snapshot = load_retrieval_index_snapshot(
        root_dir="repo",
        cache_path="context-map/index.json",
        languages=["python"],
        incremental=True,
        fail_open=True,
    )

    assert snapshot.index_payload["files"] == {}
    assert snapshot.cache_info["mode"] == "error"
    assert snapshot.files_map == {}
    assert snapshot.corpus_size == 0


def test_load_retrieval_index_snapshot_raises_without_fail_open(monkeypatch) -> None:
    import ace_lite.retrieval_shared as retrieval_shared

    def raise_value_error(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        _ = kwargs
        raise ValueError("boom")

    monkeypatch.setattr(retrieval_shared, "build_or_refresh_index", raise_value_error)

    try:
        load_retrieval_index_snapshot(
            root_dir="repo",
            cache_path="context-map/index.json",
            languages=["python"],
            incremental=True,
            fail_open=False,
        )
    except ValueError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected ValueError")
