from __future__ import annotations

from ace_lite.index_stage.candidate_selection import select_initial_candidates


def test_select_initial_candidates_falls_back_for_tiny_corpus(monkeypatch) -> None:
    captured: list[tuple[str, int, list[str]]] = []

    def fake_rank_candidate_files(  # type: ignore[no-untyped-def]
        *,
        files_map,
        terms,
        candidate_ranker,
        min_score,
        top_k_files,
        hybrid_fusion_mode,
        hybrid_rrf_k,
        hybrid_weights,
        index_hash,
    ):
        captured.append((candidate_ranker, min_score, list(terms)))
        return [{"path": "src/router.py", "score": 3.0}]

    monkeypatch.setattr(
        "ace_lite.retrieval_shared.rank_candidate_files",
        fake_rank_candidate_files,
    )

    result = select_initial_candidates(
        files_map={"src/router.py": {"module": "src.router"}},
        terms=["token"],
        candidate_ranker="hybrid_re2",
        min_candidate_score=2,
        top_k_files=4,
        corpus_size=3,
        hybrid_fusion_mode="linear",
        hybrid_rrf_k=60,
        hybrid_weights={},
        index_hash="abc123",
    )

    assert result.requested_ranker == "hybrid_re2"
    assert result.selected_ranker == "heuristic"
    assert result.fallback_reasons == ["tiny_corpus"]
    assert captured == [("heuristic", 2, ["token"])]


def test_select_initial_candidates_falls_back_on_empty_retrieval(monkeypatch) -> None:
    captured: list[tuple[str, int, list[str]]] = []

    def fake_rank_candidate_files(  # type: ignore[no-untyped-def]
        *,
        files_map,
        terms,
        candidate_ranker,
        min_score,
        top_k_files,
        hybrid_fusion_mode,
        hybrid_rrf_k,
        hybrid_weights,
        index_hash,
    ):
        captured.append((candidate_ranker, min_score, list(terms)))
        if candidate_ranker == "bm25_lite":
            return []
        return [{"path": "src/fallback.py", "score": 1.0}]

    monkeypatch.setattr(
        "ace_lite.retrieval_shared.rank_candidate_files",
        fake_rank_candidate_files,
    )

    result = select_initial_candidates(
        files_map={"src/fallback.py": {"module": "src.fallback"}},
        terms=["needle"],
        candidate_ranker="bm25_lite",
        min_candidate_score=2,
        top_k_files=4,
        corpus_size=10,
        hybrid_fusion_mode="linear",
        hybrid_rrf_k=60,
        hybrid_weights={},
        index_hash="abc123",
    )

    assert result.selected_ranker == "heuristic"
    assert result.min_score_used == 2
    assert result.fallback_reasons == ["empty_retrieval"]
    assert captured == [
        ("bm25_lite", 2, ["needle"]),
        ("bm25_lite", 1, ["needle"]),
        ("heuristic", 2, ["needle"]),
    ]


def test_select_initial_candidates_uses_empty_terms_fail_open(monkeypatch) -> None:
    captured: list[tuple[str, int, list[str]]] = []

    def fake_rank_candidate_files(  # type: ignore[no-untyped-def]
        *,
        files_map,
        terms,
        candidate_ranker,
        min_score,
        top_k_files,
        hybrid_fusion_mode,
        hybrid_rrf_k,
        hybrid_weights,
        index_hash,
    ):
        captured.append((candidate_ranker, min_score, list(terms)))
        if terms:
            return []
        return [{"path": "src/open.py", "score": 0.5}]

    monkeypatch.setattr(
        "ace_lite.retrieval_shared.rank_candidate_files",
        fake_rank_candidate_files,
    )

    result = select_initial_candidates(
        files_map={"src/open.py": {"module": "src.open"}},
        terms=["missing"],
        candidate_ranker="heuristic",
        min_candidate_score=2,
        top_k_files=4,
        corpus_size=10,
        hybrid_fusion_mode="linear",
        hybrid_rrf_k=60,
        hybrid_weights={},
        index_hash="abc123",
    )

    assert result.selected_ranker == "heuristic"
    assert result.min_score_used == 1
    assert result.fallback_reasons == []
    assert result.candidates == [{"path": "src/open.py", "score": 0.5}]
    assert captured == [
        ("heuristic", 2, ["missing"]),
        ("heuristic", 1, ["missing"]),
        ("heuristic", 1, []),
    ]


def test_select_initial_candidates_can_skip_empty_terms_fail_open(
    monkeypatch,
) -> None:
    captured: list[tuple[str, int, list[str]]] = []

    def fake_rank_candidate_files(  # type: ignore[no-untyped-def]
        *,
        files_map,
        terms,
        candidate_ranker,
        min_score,
        top_k_files,
        hybrid_fusion_mode,
        hybrid_rrf_k,
        hybrid_weights,
        index_hash,
    ):
        captured.append((candidate_ranker, min_score, list(terms)))
        return []

    monkeypatch.setattr(
        "ace_lite.retrieval_shared.rank_candidate_files",
        fake_rank_candidate_files,
    )

    result = select_initial_candidates(
        files_map={"src/open.py": {"module": "src.open"}},
        terms=["missing"],
        candidate_ranker="heuristic",
        min_candidate_score=2,
        top_k_files=4,
        corpus_size=10,
        hybrid_fusion_mode="linear",
        hybrid_rrf_k=60,
        hybrid_weights={},
        index_hash="abc123",
        allow_empty_terms_fail_open=False,
    )

    assert result.selected_ranker == "heuristic"
    assert result.min_score_used == 1
    assert result.candidates == []
    assert captured == [
        ("heuristic", 2, ["missing"]),
        ("heuristic", 1, ["missing"]),
    ]


def test_select_initial_candidates_passes_runtime_ranker_configs(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_rank_candidate_files(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return [{"path": "src/runtime.py", "score": 5.0}]

    monkeypatch.setattr(
        "ace_lite.retrieval_shared.rank_candidate_files",
        fake_rank_candidate_files,
    )

    result = select_initial_candidates(
        files_map={"src/runtime.py": {"module": "src.runtime"}},
        terms=["runtime"],
        candidate_ranker="hybrid_re2",
        min_candidate_score=3,
        top_k_files=6,
        corpus_size=10,
        hybrid_fusion_mode="combined",
        hybrid_rrf_k=77,
        hybrid_weights={"bm25_weight": 0.5},
        bm25_config={"k1": 1.4},
        heuristic_config={"path_weight": 2.0},
        hybrid_config={"coverage_weight": 0.3},
        index_hash="shared-hash",
    )

    assert result.candidates == [{"path": "src/runtime.py", "score": 5.0}]
    assert captured["candidate_ranker"] == "hybrid_re2"
    assert captured["bm25_config"] == {"k1": 1.4}
    assert captured["heuristic_config"] == {"path_weight": 2.0}
    assert captured["hybrid_config"] == {"coverage_weight": 0.3}
