from __future__ import annotations

from ace_lite.pipeline.stages.source_plan import _build_constraints


def test_constraints_prefer_profile_facts_and_cap() -> None:
    memory_hits = [
        {"handle": "a", "preview": "x" * 2000},
        {"handle": "b", "preview": "short memory hit"},
    ]
    profile = {
        "enabled": True,
        "facts": [
            {"text": "We decided to use repo-scoped memory tags."},
            {"text": "Prefer deterministic outputs."},
        ],
    }

    constraints = _build_constraints(memory_hits=memory_hits, profile=profile)
    assert constraints[0].startswith("We decided to use repo-scoped memory tags.")
    assert constraints[1].startswith("Prefer deterministic outputs.")
    assert len(constraints) <= 5
    assert constraints[2].endswith("...")


def test_constraints_exclude_cross_repo_memory_hits() -> None:
    memory_hits = [
        {
            "handle": "same-repo",
            "preview": "Keep ace-lite repo scoped notes eligible.",
            "metadata": {"repo": "ace-lite", "namespace": "repo:ace-lite"},
            "source_kind": "local_notes",
            "repo_scope_match": True,
            "namespace_scope_match": True,
            "constraint_eligible": True,
        },
        {
            "handle": "other-repo",
            "preview": "Do not inject tabiapp backend notes here.",
            "metadata": {"repo": "tabiapp-backend", "namespace": "repo:tabiapp-backend"},
            "source_kind": "local_notes",
            "repo_scope_match": False,
            "namespace_scope_match": False,
            "constraint_eligible": False,
            "constraint_exclusion_reason": "repo_mismatch",
        },
    ]

    (
        constraints,
        _ltm_constraints,
        _ltm_summary,
        memory_constraint_details,
        memory_constraint_summary,
    ) = _build_constraints(
        memory_hits=memory_hits,
        profile={},
        expected_repo="acelite",
        expected_namespace="repo:ace-lite",
        return_details=True,
    )

    assert constraints == ["Keep ace-lite repo scoped notes eligible."]
    assert memory_constraint_summary == {
        "considered_count": 2,
        "included_count": 1,
        "excluded_count": 1,
        "excluded_by_reason": {"repo_mismatch": 1},
    }
    excluded = next(
        item for item in memory_constraint_details if item["handle"] == "other-repo"
    )
    assert excluded["constraint_eligible"] is False
    assert excluded["constraint_exclusion_reason"] == "repo_mismatch"
    assert excluded["why_included"] == []


def test_constraints_keep_ltm_hit_without_explicit_repo_hint() -> None:
    (
        constraints,
        ltm_constraints,
        ltm_summary,
        memory_constraint_details,
        memory_constraint_summary,
    ) = _build_constraints(
        memory_hits=[
            {
                "handle": "fact-1",
                "preview": "[fact] preserve runtime fallback policy",
                "metadata": {"memory_kind": "fact", "namespace": "repo:ace-lite"},
                "source_kind": "ltm",
                "namespace_scope_match": True,
                "repo_scope_match": None,
                "constraint_eligible": True,
            }
        ],
        profile={},
        expected_repo="acelite",
        expected_namespace="repo:ace-lite",
        ltm_selected_map={
            "fact-1": {
                "handle": "fact-1",
                "memory_kind": "fact",
                "fact_type": "repo_policy",
            }
        },
        ltm_attribution_map={"fact-1": {"handle": "fact-1", "graph_neighborhood": {}}},
        return_details=True,
    )

    assert constraints == ["[fact] preserve runtime fallback policy"]
    assert ltm_summary["constraint_count"] == 1
    assert ltm_constraints[0]["handle"] == "fact-1"
    assert memory_constraint_summary["excluded_count"] == 0
    assert memory_constraint_details[0]["why_included"] == [
        "ltm_selected",
        "namespace_match",
        "repo_match",
    ]
