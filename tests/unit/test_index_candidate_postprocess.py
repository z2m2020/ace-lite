from __future__ import annotations

from ace_lite.index_stage.candidate_postprocess import postprocess_candidates


def test_postprocess_candidates_applies_relative_threshold() -> None:
    candidates = [
        {"path": "src/high.py", "score": 10.0},
        {"path": "src/keep.py", "score": 6.0},
        {"path": "src/drop.py", "score": 2.0},
    ]

    result = postprocess_candidates(
        candidates=candidates,
        files_map={"src/high.py": {}, "src/keep.py": {}, "src/drop.py": {}},
        selected_ranker="heuristic",
        top_k_files=4,
        candidate_relative_threshold=0.5,
        refine_enabled=True,
        rank_candidates=lambda **kwargs: [],
        merge_candidate_lists=lambda **kwargs: kwargs["primary"],
    )

    assert [item["path"] for item in result.candidates] == ["src/high.py", "src/keep.py"]
    assert result.second_pass_payload == {
        "triggered": True,
        "applied": False,
        "reason": "low_candidate_count",
        "retry_ranker": "hybrid_re2",
        "candidate_count_before": 2,
        "candidate_count_after": 2,
    }
    assert result.refine_pass_payload == {
        "enabled": True,
        "trigger_condition_met": True,
        "triggered": True,
        "applied": False,
        "reason": "low_candidate_count",
        "retry_ranker": "hybrid_re2",
        "candidate_count_before": 2,
        "candidate_count_after": 2,
        "max_passes": 1,
    }


def test_postprocess_candidates_triggers_second_pass_retry() -> None:
    captured: dict[str, object] = {}
    primary = [{"path": "src/high.py", "score": 8.0}]
    retry = [
        {"path": "src/high.py", "score": 8.0},
        {"path": "src/new.py", "score": 4.0},
    ]

    def fake_rank_candidates(*, min_score, candidate_ranker):  # type: ignore[no-untyped-def]
        captured["retry_ranker"] = candidate_ranker
        captured["retry_min_score"] = min_score
        return list(retry)

    def fake_merge_candidate_lists(*, primary, secondary, limit):  # type: ignore[no-untyped-def]
        captured["merge_limit"] = limit
        return list(primary) + [item for item in secondary if item["path"] == "src/new.py"]

    result = postprocess_candidates(
        candidates=primary,
        files_map={"src/high.py": {}, "src/new.py": {}},
        selected_ranker="heuristic",
        top_k_files=4,
        candidate_relative_threshold=0.0,
        refine_enabled=True,
        rank_candidates=fake_rank_candidates,
        merge_candidate_lists=fake_merge_candidate_lists,
    )

    assert captured["retry_ranker"] == "hybrid_re2"
    assert captured["retry_min_score"] == 0
    assert captured["merge_limit"] == 16
    assert [item["path"] for item in result.candidates] == ["src/high.py", "src/new.py"]
    assert result.second_pass_payload == {
        "triggered": True,
        "applied": True,
        "reason": "low_candidate_count",
        "retry_ranker": "hybrid_re2",
        "candidate_count_before": 1,
        "candidate_count_after": 2,
    }
    assert result.refine_pass_payload == {
        "enabled": True,
        "trigger_condition_met": True,
        "triggered": True,
        "applied": True,
        "reason": "low_candidate_count",
        "retry_ranker": "hybrid_re2",
        "candidate_count_before": 1,
        "candidate_count_after": 2,
        "max_passes": 1,
    }


def test_postprocess_candidates_can_disable_refine_retry() -> None:
    result = postprocess_candidates(
        candidates=[{"path": "src/high.py", "score": 8.0}],
        files_map={"src/high.py": {}, "src/new.py": {}},
        selected_ranker="heuristic",
        top_k_files=4,
        candidate_relative_threshold=0.0,
        refine_enabled=False,
        rank_candidates=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("rank_candidates should not be called when refine is disabled")
        ),
        merge_candidate_lists=lambda **kwargs: kwargs["primary"],
    )

    assert [item["path"] for item in result.candidates] == ["src/high.py"]
    assert result.second_pass_payload == {
        "triggered": False,
        "applied": False,
        "reason": "",
        "retry_ranker": "",
        "candidate_count_before": 0,
        "candidate_count_after": 0,
    }
    assert result.refine_pass_payload == {
        "enabled": False,
        "trigger_condition_met": True,
        "triggered": False,
        "applied": False,
        "reason": "disabled",
        "retry_ranker": "hybrid_re2",
        "candidate_count_before": 1,
        "candidate_count_after": 1,
        "max_passes": 1,
    }


def test_postprocess_candidates_applies_structured_retrieval_refinement() -> None:
    result = postprocess_candidates(
        candidates=[
            {"path": "src/other.py", "score": 9.0},
            {"path": "src/app/auth.py", "score": 5.0},
        ],
        files_map={
            "src/other.py": {"module": "src.other", "language": "python"},
            "src/app/auth.py": {"module": "src.app.auth", "language": "python"},
            "src/app/session.py": {"module": "src.app.session", "language": "python"},
        },
        selected_ranker="heuristic",
        top_k_files=4,
        candidate_relative_threshold=0.0,
        refine_enabled=False,
        retrieval_refinement={
            "schema_version": "agent_loop_retrieval_refinement_v1",
            "iteration_index": 1,
            "action_type": "request_more_context",
            "query_hint": "auth syntax fix",
            "focus_paths": ["src/app/auth.py", "src/app/session.py"],
        },
        rank_candidates=lambda **kwargs: [],
        merge_candidate_lists=lambda **kwargs: kwargs["primary"],
    )

    assert [item["path"] for item in result.candidates[:3]] == [
        "src/app/auth.py",
        "src/app/session.py",
        "src/other.py",
    ]
    assert result.candidates[0]["agent_loop_focus"] is True
    assert result.candidates[1]["selection_reason"] == "agent_loop_retrieval_refinement"
    assert result.retrieval_refinement_payload["applied"] is True
    assert result.retrieval_refinement_payload["focus_paths"] == [
        "src/app/auth.py",
        "src/app/session.py",
    ]
    assert result.retrieval_refinement_payload["boosted_paths"] == [
        "src/app/auth.py",
        "src/app/session.py",
    ]
    assert result.retrieval_refinement_payload["injected_paths"] == [
        "src/app/session.py"
    ]
