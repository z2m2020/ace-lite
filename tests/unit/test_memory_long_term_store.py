from __future__ import annotations

import sqlite3
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
    assert fetched_rows[0].to_record_metadata()["abstraction_level"] == "detail"
    assert fetched_rows[0].to_record_metadata()["support_count"] == 1
    assert fetched_rows[1].to_record_metadata()["captured_at"] == "2026-03-19T01:40:00+00:00"
    assert fetched_rows[1].to_record_metadata()["abstraction_level"] == "abstract"
    assert fetched_rows[1].to_record_metadata()["freshness_state"] == "unknown"


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


def test_long_term_memory_provider_prefers_abstract_hits_in_compact_results(
    tmp_path: Path,
) -> None:
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
            as_of="2026-03-19T09:44:00+08:00",
            valid_from="2026-03-19T09:44:00+08:00",
            derived_from_observation_id="obs-1",
        )
    )
    store.upsert_observation(
        build_long_term_observation_contract_v1(
            observation_id="obs-1",
            kind="validation",
            repo="ace-lite",
            namespace="repo/ace-lite",
            query="validation fallback policy",
            payload={"reason": "git_unavailable"},
            observed_at="2026-03-19T09:40:00+08:00",
            as_of="2026-03-19T09:40:00+08:00",
        )
    )
    provider = LongTermMemoryProvider(
        store,
        limit=4,
        container_tag="repo/ace-lite",
        prefer_abstract_memory=True,
    )

    hits = provider.search_compact("fallback policy")

    assert [hit.metadata["memory_kind"] for hit in hits[:2]] == ["observation", "fact"]


def test_long_term_memory_store_prefers_abstract_hits_before_limit_cutoff(
    tmp_path: Path,
) -> None:
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
            as_of="2026-03-19T09:44:00+08:00",
            valid_from="2026-03-19T09:44:00+08:00",
            derived_from_observation_id="obs-1",
        )
    )
    store.upsert_observation(
        build_long_term_observation_contract_v1(
            observation_id="obs-1",
            kind="validation",
            repo="ace-lite",
            namespace="repo/ace-lite",
            query="validation fallback policy",
            payload={"reason": "git_unavailable"},
            observed_at="2026-03-19T09:40:00+08:00",
            as_of="2026-03-19T09:40:00+08:00",
        )
    )

    default_rows = store.search(
        query="fallback policy",
        container_tag="repo/ace-lite",
        limit=1,
    )
    abstract_first_rows = store.search(
        query="fallback policy",
        container_tag="repo/ace-lite",
        limit=1,
        prefer_abstract=True,
    )

    assert [row.entry_kind for row in default_rows] == ["fact"]
    assert [row.entry_kind for row in abstract_first_rows] == ["observation"]


def test_long_term_memory_store_prefers_abstract_hits_with_spaced_metadata_json(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "long-term.db"
    store = LongTermMemoryStore(db_path=db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO long_term_memory_entries (
                handle, entry_kind, schema_version, repo, root, namespace,
                user_id, profile_key, as_of, observed_at, valid_from, valid_to,
                confidence, derived_from_observation_id, text, preview,
                metadata_json, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "obs-spaced",
                "observation",
                "long_term_observation_v1",
                "ace-lite",
                str(tmp_path),
                "repo/ace-lite",
                "",
                "",
                "2026-03-19T01:40:00+00:00",
                "2026-03-19T01:40:00+00:00",
                "",
                "",
                1.0,
                "",
                "[observation:validation] fallback policy",
                "[observation:validation] fallback policy",
                '{ "abstraction_level": "abstract" }',
                '{"kind":"validation","query":"fallback policy","payload":{"reason":"git_unavailable"}}',
            ),
        )
        conn.execute(
            """
            INSERT INTO long_term_memory_entries (
                handle, entry_kind, schema_version, repo, root, namespace,
                user_id, profile_key, as_of, observed_at, valid_from, valid_to,
                confidence, derived_from_observation_id, text, preview,
                metadata_json, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "fact-spaced",
                "fact",
                "long_term_fact_v1",
                "ace-lite",
                str(tmp_path),
                "repo/ace-lite",
                "",
                "",
                "2026-03-19T01:41:00+00:00",
                "",
                "2026-03-19T01:41:00+00:00",
                "",
                1.0,
                "obs-spaced",
                "[fact:repo_policy] runtime.validation.git fallback_policy reuse_checkout_or_skip",
                "[fact:repo_policy] runtime.validation.git fallback_policy reuse_checkout_or_skip",
                '{ "abstraction_level": "detail" }',
                '{"fact_type":"repo_policy","subject":"runtime.validation.git","predicate":"fallback_policy","object":"reuse_checkout_or_skip"}',
            ),
        )
        conn.execute(
            """
            INSERT INTO long_term_memory_fts (
                handle, text, repo, namespace, profile_key, user_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "obs-spaced",
                "[observation:validation] fallback policy",
                "ace-lite",
                "repo/ace-lite",
                "",
                "",
            ),
        )
        conn.execute(
            """
            INSERT INTO long_term_memory_fts (
                handle, text, repo, namespace, profile_key, user_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "fact-spaced",
                "[fact:repo_policy] runtime.validation.git fallback_policy reuse_checkout_or_skip",
                "ace-lite",
                "repo/ace-lite",
                "",
                "",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    rows = store.search(
        query="fallback policy",
        container_tag="repo/ace-lite",
        limit=1,
        prefer_abstract=True,
    )

    assert [row.handle for row in rows] == ["obs-spaced"]


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


def test_long_term_memory_provider_skips_neighborhood_for_non_detail_facts(
    tmp_path: Path,
) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "long-term.db")
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-1",
            fact_type="retrieval_heuristic",
            subject="memory",
            predicate="prefer",
            object_value="abstract_first",
            repo="ace-lite",
            namespace="repo/ace-lite",
            as_of="2026-03-19T09:44:00+08:00",
            valid_from="2026-03-19T09:44:00+08:00",
            derived_from_observation_id="obs-1",
            metadata={"abstraction_level": "overview"},
        )
    )
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-2",
            fact_type="retrieval_heuristic",
            subject="abstract_first",
            predicate="recommended_for",
            object_value="memory",
            repo="ace-lite",
            namespace="repo/ace-lite",
            as_of="2026-03-19T09:45:00+08:00",
            valid_from="2026-03-19T09:45:00+08:00",
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

    hits = provider.search_compact("abstract first")
    records = provider.fetch([hits[0].handle])

    assert records[0].metadata["abstraction_level"] == "overview"
    assert "[graph-neighborhood]" not in records[0].text
    assert "neighborhood" not in records[0].metadata


def test_long_term_memory_store_backfills_missing_metadata_to_unknown_not_fresh(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "long-term.db"
    store = LongTermMemoryStore(db_path=db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO long_term_memory_entries (
                handle, entry_kind, schema_version, repo, root, namespace,
                user_id, profile_key, as_of, observed_at, valid_from, valid_to,
                confidence, derived_from_observation_id, text, preview,
                metadata_json, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "obs-legacy",
                "observation",
                "long_term_observation_v1",
                "ace-lite",
                str(tmp_path),
                "repo/ace-lite",
                "",
                "",
                "2026-03-19T01:40:00+00:00",
                "2026-03-19T01:40:00+00:00",
                "",
                "",
                1.0,
                "",
                "[observation:validation] legacy",
                "[observation:validation] legacy",
                "{}",
                '{"kind":"validation","query":"legacy","payload":{"reason":"git_unavailable"}}',
            ),
        )
        conn.execute(
            """
            INSERT INTO long_term_memory_fts (
                handle, text, repo, namespace, profile_key, user_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "obs-legacy",
                "[observation:validation] legacy",
                "ace-lite",
                "repo/ace-lite",
                "",
                "",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    rows = store.fetch(handles=["obs-legacy"])

    assert len(rows) == 1
    metadata = rows[0].to_record_metadata()
    assert metadata["abstraction_level"] == "abstract"
    assert metadata["freshness_state"] == "unknown"
    assert metadata["contradiction_state"] == "unknown"
    assert metadata["last_confirmed_at"] == ""
