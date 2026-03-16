from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ace_lite.index_stage.retrieval_runtime import build_index_retrieval_runtime


@dataclass
class _RetrievalCfg:
    candidate_ranker: str = "hybrid_re2"
    min_candidate_score: int = 2
    top_k_files: int = 4
    hybrid_re2_fusion_mode: str = "relative"
    hybrid_re2_rrf_k: int = 50
    hybrid_re2_bm25_weight: float = 0.5
    hybrid_re2_heuristic_weight: float = 0.3
    hybrid_re2_coverage_weight: float = 0.2
    hybrid_re2_combined_scale: float = 1.5


def test_build_index_retrieval_runtime_builds_profile_and_ranker() -> None:
    captured: dict[str, Any] = {}

    class _FakeRuntimeProfile:
        def rank_candidates(self, **kwargs):  # type: ignore[no-untyped-def]
            captured["rank_candidates"] = kwargs
            return [{"path": "src/app.py", "score": 1.0}]

    def fake_normalize_fusion_mode(value: str) -> str:
        captured["normalize"] = value
        return "rrf"

    def fake_build_retrieval_runtime_profile(**kwargs):  # type: ignore[no-untyped-def]
        captured["profile"] = kwargs
        return _FakeRuntimeProfile()

    runtime = build_index_retrieval_runtime(
        retrieval_cfg=_RetrievalCfg(),
        policy={"index_parallel_enabled": True, "index_parallel_time_budget_ms": 15},
        index_hash="idx",
        terms=["router"],
        effective_files_map={"src/app.py": {"module": "src.app"}},
        normalize_fusion_mode_fn=fake_normalize_fusion_mode,
        build_retrieval_runtime_profile_fn=fake_build_retrieval_runtime_profile,
    )

    ranked = runtime.rank_candidates(min_score=3, candidate_ranker="bm25")

    assert runtime.fusion_mode == "rrf"
    assert runtime.hybrid_weights["combined_scale"] == 1.5
    assert runtime.parallel_requested is True
    assert runtime.parallel_time_budget_ms == 15
    assert captured["normalize"] == "relative"
    assert captured["profile"]["hybrid_fusion_mode"] == "rrf"
    assert captured["profile"]["index_hash"] == "idx"
    assert captured["rank_candidates"]["files_map"] == {
        "src/app.py": {"module": "src.app"}
    }
    assert captured["rank_candidates"]["terms"] == ["router"]
    assert captured["rank_candidates"]["candidate_ranker"] == "bm25"
    assert captured["rank_candidates"]["min_score"] == 3
    assert ranked == [{"path": "src/app.py", "score": 1.0}]
