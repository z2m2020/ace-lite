from pathlib import Path

from ace_lite.memory_long_term.contracts import build_long_term_fact_contract_v1
from ace_lite.memory_long_term.graph_view import build_long_term_graph_view
from ace_lite.memory_long_term.store import LongTermMemoryStore


def _seed_graph(store: LongTermMemoryStore) -> None:
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-1",
            fact_type="repo_policy",
            subject="runtime.validation.git",
            predicate="fallback_policy",
            object_value="reuse_checkout_or_skip",
            repo="ace-lite",
            namespace="repo/ace-lite",
            user_id="tester",
            profile_key="bugfix",
            as_of="2026-03-19T09:44:00+08:00",
            valid_from="2026-03-19T09:44:00+08:00",
            derived_from_observation_id="obs-1",
        )
    )
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-2",
            fact_type="repo_policy",
            subject="reuse_checkout_or_skip",
            predicate="recommended_for",
            object_value="runtime.validation.git",
            repo="ace-lite",
            namespace="repo/ace-lite",
            user_id="tester",
            profile_key="bugfix",
            as_of="2026-03-19T09:43:00+08:00",
            valid_from="2026-03-19T09:43:00+08:00",
            derived_from_observation_id="obs-2",
        )
    )
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-3",
            fact_type="repo_policy",
            subject="runtime.validation.git",
            predicate="fallback_owner",
            object_value="release_engineering",
            repo="ace-lite",
            namespace="repo/ace-lite",
            user_id="tester",
            profile_key="bugfix",
            as_of="2026-03-19T09:46:00+08:00",
            valid_from="2026-03-19T09:46:00+08:00",
            derived_from_observation_id="obs-3",
        )
    )


def test_build_long_term_graph_view_centers_fact_handle(tmp_path: Path) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "long-term.db")
    _seed_graph(store)

    payload = build_long_term_graph_view(
        store=store,
        fact_handle="fact-1",
        max_hops=2,
        limit=8,
    )

    assert payload["ok"] is True
    assert payload["schema_version"] == "ltm_graph_view_v1"
    assert payload["fact_handle"] == "fact-1"
    assert payload["summary"]["triple_count"] == 2
    assert payload["summary"]["node_count"] == 2
    assert payload["focus"]["predicate"] == "fallback_policy"
    assert payload["triples"][0]["is_focus"] is True
    assert {item["fact_handle"] for item in payload["triples"]} == {
        "fact-1",
        "fact-2",
    }
    seed_roles = {
        item["id"]: item["roles"]
        for item in payload["nodes"]
        if item["id"] in {"runtime.validation.git", "reuse_checkout_or_skip"}
    }
    assert "seed" in seed_roles["runtime.validation.git"]
    assert "focus_object" in seed_roles["reuse_checkout_or_skip"]


def test_build_long_term_graph_view_requires_repo_without_fact_handle(tmp_path: Path) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "long-term.db")
    _seed_graph(store)

    try:
        build_long_term_graph_view(
            store=store,
            seeds=["runtime.validation.git"],
        )
    except ValueError as exc:
        assert str(exc) == "repo is required when fact_handle is not provided"
    else:
        raise AssertionError("expected ValueError")
