from __future__ import annotations

from ace_lite.index_stage.priors import apply_candidate_priors


def test_apply_candidate_priors_boosts_and_injects_worktree_seeds() -> None:
    files_map = {
        "src/core/auth.py": {
            "language": "python",
            "module": "src.core.auth",
            "symbols": [
                {"name": "refresh_session", "qualified_name": "src.core.auth.refresh_session"}
            ],
            "imports": [],
        },
        "src/core/service.py": {
            "language": "python",
            "module": "src.core.service",
            "symbols": [
                {"name": "run_service", "qualified_name": "src.core.service.run_service"}
            ],
            "imports": [{"module": "src.core.auth"}],
        },
    }
    candidates = [
        {
            "path": "src/core/service.py",
            "score": 3.0,
            "module": "src.core.service",
            "score_breakdown": {"heuristic": 3.0},
        }
    ]
    docs_payload = {
        "enabled": True,
        "section_count": 2,
        "hints": {
            "paths": ["src/core/auth.py"],
            "modules": ["src.core.auth"],
            "symbols": ["refresh_session"],
            "path_scores": [{"value": "src/core/auth.py", "score": 1.0}],
            "module_scores": [{"value": "src.core.auth", "score": 1.0}],
            "symbol_scores": [{"value": "refresh_session", "score": 1.0}],
        },
    }
    worktree_prior = {
        "enabled": True,
        "changed_count": 1,
        "changed_paths": ["src/core/auth.py"],
        "seed_paths": ["src/core/auth.py", "src/core/service.py"],
        "reverse_added_count": 1,
    }
    policy = {
        "docs_weight": 0.6,
        "docs_module_weight": 0.3,
        "docs_symbol_weight": 0.2,
        "worktree_weight": 1.2,
        "worktree_neighbor_weight": 0.6,
        "worktree_expand_candidates": True,
        "worktree_expand_limit": 4,
    }

    ranked, summary = apply_candidate_priors(
        candidates=candidates,
        files_map=files_map,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        policy=policy,
        top_k_files=4,
    )

    assert summary["docs_enabled"] is True
    assert summary["worktree_enabled"] is True
    assert summary["boosted_candidate_count"] >= 1
    assert summary["added_candidate_count"] >= 1
    assert ranked[0]["path"] == "src/core/auth.py"
    assert "worktree_seed_injection" in ranked[0]["score_breakdown"]


def test_apply_candidate_priors_worktree_query_guard_filters_unrelated_paths() -> None:
    files_map = {
        "src/core/auth.py": {
            "language": "python",
            "module": "src.core.auth",
            "symbols": [],
            "imports": [],
        },
        "src/cache/index_cache.py": {
            "language": "python",
            "module": "src.cache.index_cache",
            "symbols": [],
            "imports": [],
        },
    }
    candidates = [
        {"path": "src/core/auth.py", "score": 2.0, "module": "src.core.auth"},
        {"path": "src/cache/index_cache.py", "score": 2.0, "module": "src.cache.index_cache"},
    ]
    docs_payload = {"enabled": False, "section_count": 0, "hints": {}}
    worktree_prior = {
        "enabled": True,
        "changed_count": 2,
        "changed_paths": ["src/core/auth.py", "src/cache/index_cache.py"],
        "seed_paths": ["src/core/auth.py", "src/cache/index_cache.py"],
        "reverse_added_count": 0,
    }
    policy = {
        "docs_weight": 0.0,
        "worktree_weight": 1.0,
        "worktree_neighbor_weight": 0.5,
        "worktree_expand_candidates": False,
        "worktree_query_guard_enabled": True,
        "worktree_query_guard_min_overlap": 1,
    }

    ranked, summary = apply_candidate_priors(
        candidates=candidates,
        files_map=files_map,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        policy=policy,
        top_k_files=4,
        query_terms=["auth", "architecture"],
    )

    assert summary["worktree_guard_enabled"] is True
    assert summary["worktree_guard_applied"] is True
    assert "src/core/auth.py" in summary["worktree_effective_changed_paths"]
    assert "src/cache/index_cache.py" not in summary["worktree_effective_changed_paths"]
    assert ranked[0]["path"] == "src/core/auth.py"


def test_apply_candidate_priors_worktree_query_guard_ignores_repo_path_tokens() -> None:
    files_map = {
        "src/ace_lite/index_stage/docs_channel.py": {
            "language": "python",
            "module": "ace_lite.index_stage.docs_channel",
            "symbols": [],
            "imports": [],
        },
        "src/ace_lite/repomap/cache.py": {
            "language": "python",
            "module": "ace_lite.repomap.cache",
            "symbols": [],
            "imports": [],
        },
    }
    candidates = [
        {
            "path": "src/ace_lite/index_stage/docs_channel.py",
            "score": 2.0,
            "module": "ace_lite.index_stage.docs_channel",
        },
        {
            "path": "src/ace_lite/repomap/cache.py",
            "score": 2.0,
            "module": "ace_lite.repomap.cache",
        },
    ]
    docs_payload = {"enabled": False, "section_count": 0, "hints": {}}
    worktree_prior = {
        "enabled": True,
        "changed_count": 2,
        "changed_paths": [
            "src/ace_lite/index_stage/docs_channel.py",
            "src/ace_lite/repomap/cache.py",
        ],
        "seed_paths": [
            "src/ace_lite/index_stage/docs_channel.py",
            "src/ace_lite/repomap/cache.py",
        ],
        "reverse_added_count": 0,
    }
    policy = {
        "docs_weight": 0.0,
        "worktree_weight": 1.0,
        "worktree_neighbor_weight": 0.5,
        "worktree_expand_candidates": False,
        "worktree_query_guard_enabled": True,
        "worktree_query_guard_min_overlap": 1,
    }

    ranked, summary = apply_candidate_priors(
        candidates=candidates,
        files_map=files_map,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        policy=policy,
        top_k_files=4,
        query_terms=["src/ace_lite/index_stage/docs_channel.py"],
    )

    assert summary["worktree_guard_enabled"] is True
    assert summary["worktree_guard_applied"] is True
    assert "src/ace_lite/index_stage/docs_channel.py" in summary["worktree_effective_changed_paths"]
    assert "src/ace_lite/repomap/cache.py" not in summary["worktree_effective_changed_paths"]
    assert ranked[0]["path"] == "src/ace_lite/index_stage/docs_channel.py"


def test_apply_candidate_priors_injects_docs_hints_when_enabled() -> None:
    files_map = {
        "src/core/auth.py": {
            "language": "python",
            "module": "src.core.auth",
            "symbols": [
                {"name": "refresh_session", "qualified_name": "src.core.auth.refresh_session"}
            ],
            "imports": [],
        },
        "src/core/service.py": {
            "language": "python",
            "module": "src.core.service",
            "symbols": [{"name": "run_service", "qualified_name": "src.core.service.run_service"}],
            "imports": [{"module": "src.core.auth"}],
        },
    }
    candidates = [
        {
            "path": "src/core/service.py",
            "score": 1.0,
            "module": "src.core.service",
            "score_breakdown": {"heuristic": 1.0},
        }
    ]
    docs_payload = {
        "enabled": True,
        "section_count": 1,
        "hints": {
            "paths": ["src/core/auth.py"],
            "modules": ["src.core.auth"],
            "symbols": ["refresh_session"],
            "path_scores": [{"value": "src/core/auth.py", "score": 1.0}],
            "module_scores": [{"value": "src.core.auth", "score": 1.0}],
            "symbol_scores": [{"value": "refresh_session", "score": 1.0}],
        },
    }
    worktree_prior = {
        "enabled": False,
        "changed_count": 0,
        "changed_paths": [],
        "seed_paths": [],
        "reverse_added_count": 0,
    }
    policy = {
        "docs_weight": 0.6,
        "docs_module_weight": 0.3,
        "docs_symbol_weight": 0.2,
        "docs_expand_candidates": True,
        "docs_expand_limit": 3,
        "worktree_weight": 0.0,
        "worktree_neighbor_weight": 0.0,
        "worktree_expand_candidates": False,
    }

    ranked, summary = apply_candidate_priors(
        candidates=candidates,
        files_map=files_map,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        policy=policy,
        top_k_files=4,
    )

    assert summary["docs_injected_candidate_count"] == 1
    assert ranked[0]["path"] == "src/core/auth.py"
    assert ranked[0]["retrieval_pass"] == "docs_hint"
    assert "docs_hint_injection" in ranked[0]["score_breakdown"]


def test_apply_candidate_priors_docs_injection_respects_query_overlap() -> None:
    files_map = {
        "src/core/auth.py": {
            "language": "python",
            "module": "src.core.auth",
            "symbols": [],
            "imports": [],
        },
        "src/core/service.py": {
            "language": "python",
            "module": "src.core.service",
            "symbols": [],
            "imports": [{"module": "src.core.auth"}],
        },
    }
    candidates = [
        {"path": "src/core/service.py", "score": 1.0, "module": "src.core.service"}
    ]
    docs_payload = {
        "enabled": True,
        "section_count": 1,
        "hints": {
            "paths": ["src/core/auth.py"],
            "modules": ["src.core.auth"],
            "symbols": [],
            "path_scores": [{"value": "src/core/auth.py", "score": 1.0}],
            "module_scores": [{"value": "src.core.auth", "score": 1.0}],
            "symbol_scores": [],
        },
    }
    worktree_prior = {
        "enabled": False,
        "changed_count": 0,
        "changed_paths": [],
        "seed_paths": [],
        "reverse_added_count": 0,
    }
    policy = {
        "docs_weight": 0.6,
        "docs_module_weight": 0.3,
        "docs_symbol_weight": 0.0,
        "docs_expand_candidates": True,
        "docs_expand_limit": 3,
        "docs_injection_min_overlap": 1,
        "worktree_weight": 0.0,
        "worktree_neighbor_weight": 0.0,
        "worktree_expand_candidates": False,
    }

    ranked, summary = apply_candidate_priors(
        candidates=candidates,
        files_map=files_map,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        policy=policy,
        top_k_files=4,
        query_terms=["billing", "invoice"],
    )

    assert summary["docs_injected_candidate_count"] == 0
    assert all(item.get("retrieval_pass") != "docs_hint" for item in ranked)

    ranked, summary = apply_candidate_priors(
        candidates=candidates,
        files_map=files_map,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        policy=policy,
        top_k_files=4,
        query_terms=["auth", "refresh"],
    )

    assert summary["docs_injected_candidate_count"] == 1


def test_apply_candidate_priors_penalizes_tests_paths_in_auto_mode() -> None:
    files_map = {
        "src/ace_lite/index_cache.py": {
            "language": "python",
            "module": "src.ace_lite.index_cache",
            "symbols": [],
            "imports": [],
        },
        "tests/unit/test_index_cache.py": {
            "language": "python",
            "module": "tests.unit.test_index_cache",
            "symbols": [],
            "imports": [],
        },
    }
    candidates = [
        {
            "path": "tests/unit/test_index_cache.py",
            "score": 10.0,
            "module": "tests.unit.test_index_cache",
            "score_breakdown": {"heuristic": 10.0},
        },
        {
            "path": "src/ace_lite/index_cache.py",
            "score": 9.0,
            "module": "src.ace_lite.index_cache",
            "score_breakdown": {"heuristic": 9.0},
        },
    ]
    docs_payload = {"enabled": False, "section_count": 0, "hints": {}}
    worktree_prior = {"enabled": False, "changed_count": 0, "changed_paths": [], "seed_paths": []}
    policy = {
        "name": "general",
        "source": "auto",
        "tests_path_penalty": 6.0,
        "docs_weight": 0.0,
        "worktree_weight": 0.0,
        "worktree_expand_candidates": False,
    }

    ranked, summary = apply_candidate_priors(
        candidates=candidates,
        files_map=files_map,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        policy=policy,
        top_k_files=4,
        query="how does the index cache incremental refresh work",
        query_terms=["index", "cache", "incremental", "refresh"],
    )

    assert summary["tests_penalized_candidate_count"] == 1
    assert ranked[0]["path"] == "src/ace_lite/index_cache.py"


def test_apply_candidate_priors_keeps_tests_when_query_mentions_tests() -> None:
    files_map = {
        "src/ace_lite/index_cache.py": {
            "language": "python",
            "module": "src.ace_lite.index_cache",
            "symbols": [],
            "imports": [],
        },
        "tests/unit/test_index_cache.py": {
            "language": "python",
            "module": "tests.unit.test_index_cache",
            "symbols": [],
            "imports": [],
        },
    }
    candidates = [
        {
            "path": "tests/unit/test_index_cache.py",
            "score": 10.0,
            "module": "tests.unit.test_index_cache",
            "score_breakdown": {"heuristic": 10.0},
        },
        {
            "path": "src/ace_lite/index_cache.py",
            "score": 9.0,
            "module": "src.ace_lite.index_cache",
            "score_breakdown": {"heuristic": 9.0},
        },
    ]
    docs_payload = {"enabled": False, "section_count": 0, "hints": {}}
    worktree_prior = {"enabled": False, "changed_count": 0, "changed_paths": [], "seed_paths": []}
    policy = {
        "name": "general",
        "source": "auto",
        "tests_path_penalty": 6.0,
        "docs_weight": 0.0,
        "worktree_weight": 0.0,
        "worktree_expand_candidates": False,
    }

    ranked, summary = apply_candidate_priors(
        candidates=candidates,
        files_map=files_map,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        policy=policy,
        top_k_files=4,
        query="where is the test_index_cache module located",
        query_terms=["test_index_cache", "index", "cache"],
    )

    assert summary["tests_penalized_candidate_count"] == 0
    assert ranked[0]["path"] == "tests/unit/test_index_cache.py"


def test_apply_candidate_priors_keeps_tests_when_query_terms_mention_tests() -> None:
    files_map = {
        "src/ace_lite/index_cache.py": {
            "language": "python",
            "module": "src.ace_lite.index_cache",
            "symbols": [],
            "imports": [],
        },
        "tests/integration/test_orchestrator_cochange_gating.py": {
            "language": "python",
            "module": "tests.integration.test_orchestrator_cochange_gating",
            "symbols": [],
            "imports": [],
        },
    }
    candidates = [
        {
            "path": "tests/integration/test_orchestrator_cochange_gating.py",
            "score": 10.0,
            "module": "tests.integration.test_orchestrator_cochange_gating",
            "score_breakdown": {"heuristic": 10.0},
        },
        {
            "path": "src/ace_lite/index_cache.py",
            "score": 9.0,
            "module": "src.ace_lite.index_cache",
            "score_breakdown": {"heuristic": 9.0},
        },
    ]
    docs_payload = {"enabled": False, "section_count": 0, "hints": {}}
    worktree_prior = {"enabled": False, "changed_count": 0, "changed_paths": [], "seed_paths": []}
    policy = {
        "name": "general",
        "source": "auto",
        "tests_path_penalty": 6.0,
        "docs_weight": 0.0,
        "worktree_weight": 0.0,
        "worktree_expand_candidates": False,
    }

    ranked, summary = apply_candidate_priors(
        candidates=candidates,
        files_map=files_map,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        policy=policy,
        top_k_files=4,
        query="how worktree prior injection works",
        query_terms=["worktree_prior", "index_cache", "test_orchestrator_cochange_gating"],
    )

    assert summary["tests_penalized_candidate_count"] == 0
    assert ranked[0]["path"] == "tests/integration/test_orchestrator_cochange_gating.py"


def test_apply_candidate_priors_boosts_rankers_for_candidate_ranking_queries() -> None:
    files_map = {
        "src/ace_lite/repomap/ranking.py": {
            "language": "python",
            "module": "src.ace_lite.repomap.ranking",
            "symbols": [],
            "imports": [],
        },
        "src/ace_lite/rankers/hybrid_re2.py": {
            "language": "python",
            "module": "src.ace_lite.rankers.hybrid_re2",
            "symbols": [],
            "imports": [],
        },
    }
    candidates = [
        {
            "path": "src/ace_lite/repomap/ranking.py",
            "score": 10.0,
            "module": "src.ace_lite.repomap.ranking",
            "score_breakdown": {"heuristic": 10.0},
        },
        {
            "path": "src/ace_lite/rankers/hybrid_re2.py",
            "score": 9.9,
            "module": "src.ace_lite.rankers.hybrid_re2",
            "score_breakdown": {"heuristic": 9.9},
        },
    ]
    docs_payload = {"enabled": False, "section_count": 0, "hints": {}}
    worktree_prior = {"enabled": False, "changed_count": 0, "changed_paths": [], "seed_paths": []}
    policy = {
        "name": "doc_intent",
        "source": "auto",
        "rankers_focus_boost": 0.35,
        "docs_weight": 0.0,
        "worktree_weight": 0.0,
        "worktree_expand_candidates": False,
    }

    ranked, summary = apply_candidate_priors(
        candidates=candidates,
        files_map=files_map,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        policy=policy,
        top_k_files=4,
        query_terms=["candidate", "files", "rank"],
    )

    assert summary["rankers_focus_boosted_candidate_count"] == 1
    assert ranked[0]["path"] == "src/ace_lite/rankers/hybrid_re2.py"
