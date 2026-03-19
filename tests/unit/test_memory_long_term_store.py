from __future__ import annotations

from pathlib import Path

from ace_lite.memory_long_term import (
    LongTermMemoryProvider,
    LongTermMemoryStore,
    build_long_term_fact_contract_v1,
    build_long_term_observation_contract_v1,
)


def test_long_term_memory_store_search_and_fetch_round_trip(tmp_path: Path) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "long-term.db")
    observation = store.upsert_observation(
        build_long_term_observation_contract_v1(
            observation_id="obs-1",
            kind="validation",
            repo="ace-lite",
            root=str(tmp_path),
            namespace="repo/ace-lite",
            user_id="tester",
            profile_key="bugfix",
            query="validation git fallback",
            payload={"reason": "git_unavailable", "status": "degraded"},
            observed_at="2026-03-19T09:40:00+08:00",
            as_of="2026-03-19T09:40:00+08:00",
        )
    )
    fact = store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-1",
            fact_type="repo_policy",
            subject="runtime.validation.git",
            predicate="fallback_policy",
            object_value="reuse_checkout_or_skip",
            repo="ace-lite",
            root=str(tmp_path),
            namespace="repo/ace-lite",
            user_id="tester",
            profile_key="bugfix",
            as_of="2026-03-19T09:44:00+08:00",
            confidence=0.9,
            valid_from="2026-03-19T09:44:00+08:00",
            derived_from_observation_id="obs-1",
        )
    )

    search_rows = store.search(
        query="fallback",
        container_tag="repo/ace-lite",
        limit=4,
    )
    fetched_rows = store.fetch(handles=[fact.handle, observation.handle])

    assert [row.handle for row in fetched_rows] == [fact.handle, observation.handle]
    assert {row.handle for row in search_rows} == {fact.handle, observation.handle}
    assert fetched_rows[0].to_record_metadata()["fact_type"] == "repo_policy"
    assert fetched_rows[1].to_record_metadata()["captured_at"] == "2026-03-19T01:40:00+00:00"


def test_long_term_memory_store_respects_as_of_boundary(tmp_path: Path) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "long-term.db")
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-old",
            fact_type="repo_policy",
            subject="runtime.validation.git",
            predicate="fallback_policy",
            object_value="reuse_checkout_or_skip",
            repo="ace-lite",
            namespace="repo/ace-lite",
            as_of="2026-03-18T09:44:00+08:00",
            valid_from="2026-03-18T09:44:00+08:00",
            derived_from_observation_id="obs-old",
        )
    )
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-new",
            fact_type="repo_policy",
            subject="runtime.validation.git",
            predicate="fallback_policy",
            object_value="new_rule",
            repo="ace-lite",
            namespace="repo/ace-lite",
            as_of="2026-03-20T09:44:00+08:00",
            valid_from="2026-03-20T09:44:00+08:00",
            derived_from_observation_id="obs-new",
        )
    )

    rows = store.search(
        query="fallback policy",
        container_tag="repo/ace-lite",
        as_of="2026-03-19T00:00:00+00:00",
        limit=4,
    )

    assert [row.handle for row in rows] == ["fact-old"]


def test_long_term_memory_provider_maps_store_rows_to_memory_records(tmp_path: Path) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "long-term.db")
    store.upsert_observation(
        build_long_term_observation_contract_v1(
            observation_id="obs-1",
            kind="validation",
            repo="ace-lite",
            namespace="repo/ace-lite",
            query="validation git fallback",
            payload={"reason": "git_unavailable"},
            observed_at="2026-03-19T09:40:00+08:00",
            as_of="2026-03-19T09:40:00+08:00",
        )
    )
    provider = LongTermMemoryProvider(
        store,
        limit=3,
        container_tag="repo/ace-lite",
    )

    hits = provider.search_compact("git fallback")
    records = provider.fetch([hits[0].handle])

    assert len(hits) == 1
    assert hits[0].metadata["memory_kind"] == "observation"
    assert records[0].metadata["captured_at"] == "2026-03-19T01:40:00+00:00"
    assert records[0].source == "long_term"


def test_long_term_memory_store_can_expand_fact_neighborhood(tmp_path: Path) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "long-term.db")
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

    neighbors = store.expand_triple_neighborhood(
        seeds=["runtime.validation.git"],
        repo="ace-lite",
        namespace="repo/ace-lite",
        user_id="tester",
        profile_key="bugfix",
        as_of="2026-03-19T02:00:00+00:00",
        max_hops=2,
        limit=8,
    )

    assert {triple.fact_handle for triple in neighbors} == {"fact-1", "fact-2", "fact-3"}


def test_long_term_memory_provider_appends_graph_neighborhood_for_facts(tmp_path: Path) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "long-term.db")
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
    provider = LongTermMemoryProvider(
        store,
        limit=3,
        container_tag="repo/ace-lite",
        neighborhood_hops=1,
        neighborhood_limit=4,
    )

    hits = provider.search_compact("fallback policy")
    records = provider.fetch([hits[0].handle])

    assert "[graph-neighborhood]" in records[0].text
    assert records[0].metadata["neighborhood"]["triple_count"] == 1
    assert records[0].metadata["neighborhood"]["triples"][0]["fact_handle"] == "fact-2"
