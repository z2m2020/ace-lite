from __future__ import annotations

from typing import Any

from ace_lite.index_stage.candidate_generation import InitialCandidateGenerationResult
from ace_lite.index_stage.candidate_generation_runtime import (
    run_index_candidate_generation,
)


def test_run_index_candidate_generation_builds_deps_and_include_globs() -> None:
    captured: dict[str, Any] = {}

    def fake_gather_initial_candidates(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return InitialCandidateGenerationResult(
            requested_ranker="hybrid_re2",
            selected_ranker="heuristic",
            ranker_fallbacks=["tiny_corpus"],
            min_score_used=2,
            candidates=[{"path": "src/app.py", "score": 1.0}],
            exact_search_payload={"enabled": False},
            docs_payload={"enabled": False},
            worktree_prior={"enabled": False},
            parallel_payload={"enabled": False},
            prior_payload={"enabled": False},
            docs_elapsed_ms=1.25,
            worktree_elapsed_ms=0.5,
            raw_worktree={"changed_paths": ["src/app.py"]},
        )

    def fake_mark_timing(label: str, started_at: float) -> None:
        _ = (label, started_at)

    result = run_index_candidate_generation(
        root="/tmp/demo",
        query="router",
        terms=["router"],
        files_map={"src/app.py": {"module": "src.app"}},
        corpus_size=1,
        runtime_profile=object(),
        top_k_files=4,
        exact_search_enabled=True,
        exact_search_time_budget_ms=25,
        exact_search_max_paths=10,
        languages=["python", "markdown"],
        docs_policy_enabled=True,
        worktree_prior_enabled=False,
        cochange_enabled=True,
        docs_intent_weight=1.0,
        parallel_requested=True,
        parallel_time_budget_ms=20,
        policy={"version": "v1"},
        gather_initial_candidates_fn=fake_gather_initial_candidates,
        build_exact_search_payload_fn=lambda **kwargs: {},
        select_initial_candidates_fn=lambda **kwargs: None,
        apply_exact_search_boost_fn=lambda **kwargs: None,
        collect_parallel_signals_fn=lambda **kwargs: None,
        apply_candidate_priors_fn=lambda **kwargs: ([], {}),
        collect_docs_fn=lambda **kwargs: {},
        collect_worktree_fn=lambda **kwargs: {},
        disabled_docs_payload_fn=lambda **kwargs: {},
        disabled_worktree_prior_fn=lambda **kwargs: {},
        get_executor_fn=lambda: None,
        resolve_future_fn=lambda **kwargs: (None, False, "timeout"),
        run_exact_search_fn=lambda **kwargs: None,
        score_exact_hits_fn=lambda **kwargs: {},
        normalize_repo_path_fn=lambda value: value,
        supported_extensions_fn=lambda languages: {".py", ".md"}
        if languages == ("python", "markdown")
        else set(),
        mark_timing_fn=fake_mark_timing,
    )

    assert captured["exact_search_include_globs"] == ["*.md", "*.py"]
    deps = captured["deps"]
    assert deps.mark_timing is fake_mark_timing
    assert result.docs_timing_ms == 1.25
    assert result.worktree_timing_ms == 0.5
    assert result.raw_worktree == {"changed_paths": ["src/app.py"]}
