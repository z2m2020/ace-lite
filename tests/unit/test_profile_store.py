from __future__ import annotations

from pathlib import Path

from ace_lite.profile_store import ProfileStore


def test_profile_store_add_fact_dedupes_and_evicts_deterministically(tmp_path: Path) -> None:
    store = ProfileStore(path=tmp_path / "profile.json", max_facts=2)

    store.add_fact("B fact", confidence=0.4)
    store.add_fact("A fact", confidence=0.9)
    store.add_fact("B fact", confidence=0.8)
    store.add_fact("C fact", confidence=0.7)

    payload = store.load()
    facts = payload["facts"]
    assert [fact["text"] for fact in facts] == ["A fact", "B fact"]
    assert facts[0]["confidence"] == 0.9
    assert facts[1]["confidence"] == 0.8
    assert facts[1]["use_count"] >= 1
    assert 0.0 <= float(facts[1]["importance_score"]) <= 1.0


def test_profile_store_build_injection_respects_top_n_and_budget(tmp_path: Path) -> None:
    store = ProfileStore(path=tmp_path / "profile.json")
    store.add_fact("alpha", confidence=0.9)
    store.add_fact("beta", confidence=0.8)
    store.add_fact("gamma", confidence=0.7)

    payload = store.build_injection(
        top_n=3,
        token_budget=2,
        tokenizer_model="gpt-4o-mini",
    )

    assert payload["enabled"] is True
    assert payload["selected_count"] <= 2
    assert payload["selected_est_tokens_total"] <= 2
    assert [fact["text"] for fact in payload["facts"]] == ["alpha", "beta"]
    assert payload["facts"][0]["importance_score"] >= payload["facts"][1]["importance_score"]
    assert payload["ranking"] == "confidence_importance_recency_v1"


def test_profile_store_near_duplicate_dedupes_by_token_overlap(tmp_path: Path) -> None:
    store = ProfileStore(path=tmp_path / "profile.json", max_facts=8)
    store.add_fact(
        "prefer deterministic patches in python modules",
        confidence=0.6,
        importance_score=0.5,
    )
    store.add_fact(
        "Prefer deterministic patches in python modules!",
        confidence=0.9,
        importance_score=0.95,
    )

    payload = store.load()
    facts = payload["facts"]

    assert len(facts) == 1
    assert facts[0]["text"] == "Prefer deterministic patches in python modules!"
    assert facts[0]["confidence"] == 0.9
    assert facts[0]["importance_score"] == 0.95
    assert facts[0]["use_count"] >= 1


def test_profile_store_build_injection_prefers_importance_and_recency(tmp_path: Path) -> None:
    store = ProfileStore(path=tmp_path / "profile.json", expiry_enabled=False)
    store.save(
        {
            "facts": [
                {
                    "text": "beta high confidence stale",
                    "confidence": 0.9,
                    "importance_score": 0.4,
                    "use_count": 0,
                    "last_used_at": "2025-01-01T00:00:00+00:00",
                    "updated_at": "2025-01-01T00:00:00+00:00",
                    "source": "manual",
                    "metadata": {},
                },
                {
                    "text": "alpha balanced recent",
                    "confidence": 0.7,
                    "importance_score": 0.9,
                    "use_count": 1,
                    "last_used_at": "2026-02-12T00:00:00+00:00",
                    "updated_at": "2026-02-12T00:00:00+00:00",
                    "source": "manual",
                    "metadata": {},
                },
                {
                    "text": "gamma very important newest",
                    "confidence": 0.6,
                    "importance_score": 0.95,
                    "use_count": 0,
                    "last_used_at": "2026-02-13T00:00:00+00:00",
                    "updated_at": "2026-02-13T00:00:00+00:00",
                    "source": "manual",
                    "metadata": {},
                },
            ]
        }
    )

    injection = store.build_injection(
        top_n=3,
        token_budget=64,
        tokenizer_model="gpt-4o-mini",
    )

    assert [item["text"] for item in injection["facts"]] == [
        "alpha balanced recent",
        "gamma very important newest",
        "beta high confidence stale",
    ]


def test_profile_store_load_prunes_expired_items(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        """{
  "version": 1,
  "facts": [
    {
      "text": "stale fact",
      "confidence": 0.8,
      "importance_score": 0.8,
      "use_count": 0,
      "last_used_at": "2020-01-01T00:00:00+00:00",
      "updated_at": "2020-01-01T00:00:00+00:00",
      "source": "manual",
      "metadata": {}
    },
    {
      "text": "fresh fact",
      "confidence": 0.7,
      "importance_score": 0.7,
      "use_count": 0,
      "last_used_at": "2099-01-01T00:00:00+00:00",
      "updated_at": "2099-01-01T00:00:00+00:00",
      "source": "manual",
      "metadata": {}
    }
  ],
  "preferences": {},
  "recent_contexts": [
    {
      "query": "old query",
      "repo": "demo",
      "captured_at": "2020-01-01T00:00:00+00:00"
    },
    {
      "query": "fresh query",
      "repo": "demo",
      "captured_at": "2099-01-01T00:00:00+00:00"
    }
  ]
}
""",
        encoding="utf-8",
    )
    store = ProfileStore(path=profile_path, ttl_days=90, max_age_days=365)

    payload = store.load()

    assert [fact["text"] for fact in payload["facts"]] == ["fresh fact"]
    assert [row["query"] for row in payload["recent_contexts"]] == ["fresh query"]


def test_profile_store_vacuum_is_idempotent(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    store = ProfileStore(path=profile_path, expiry_enabled=False)
    store.save(
        {
            "facts": [
                {
                    "text": "stale fact",
                    "confidence": 0.6,
                    "importance_score": 0.6,
                    "use_count": 0,
                    "last_used_at": "2020-01-01T00:00:00+00:00",
                    "updated_at": "2020-01-01T00:00:00+00:00",
                    "source": "manual",
                    "metadata": {},
                },
                {
                    "text": "fresh fact",
                    "confidence": 0.7,
                    "importance_score": 0.8,
                    "use_count": 0,
                    "last_used_at": "2099-01-01T00:00:00+00:00",
                    "updated_at": "2099-01-01T00:00:00+00:00",
                    "source": "manual",
                    "metadata": {},
                },
            ],
            "recent_contexts": [
                {
                    "query": "old query",
                    "repo": "demo",
                    "captured_at": "2020-01-01T00:00:00+00:00",
                },
                {
                    "query": "fresh query",
                    "repo": "demo",
                    "captured_at": "2099-01-01T00:00:00+00:00",
                },
            ],
        }
    )

    first = store.vacuum(expiry_enabled=True, ttl_days=90, max_age_days=365)
    second = store.vacuum(expiry_enabled=True, ttl_days=90, max_age_days=365)
    payload = store.load()

    assert first["removed_facts"] == 1
    assert first["removed_recent_contexts"] == 1
    assert second["removed_facts"] == 0
    assert second["removed_recent_contexts"] == 0
    assert [fact["text"] for fact in payload["facts"]] == ["fresh fact"]
