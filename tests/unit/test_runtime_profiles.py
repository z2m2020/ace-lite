from __future__ import annotations

from ace_lite.config_models import validate_cli_config
from ace_lite.runtime_profiles import (
    RUNTIME_PROFILE_NAMES,
    get_runtime_profile,
    list_runtime_profiles,
)


def test_runtime_profile_catalog_contains_expected_first_party_profiles() -> None:
    assert RUNTIME_PROFILE_NAMES == (
        "bugfix",
        "refactor",
        "docs",
        "colbert_experiment",
        "benchmark",
        "wide_search",
        "fast_path",
    )


def test_runtime_profiles_are_case_insensitive_and_mergeable() -> None:
    profile = get_runtime_profile("BugFix")

    assert profile is not None
    assert profile.name == "bugfix"

    validated = validate_cli_config({"plan": profile.plan_overrides()})

    assert validated["plan"]["retrieval_policy"] == "bugfix_test"
    assert validated["plan"]["plan_replay_cache"]["enabled"] is True


def test_runtime_profiles_expose_explicit_retrieval_cache_and_budget_knobs() -> None:
    profiles = list_runtime_profiles()

    assert len(profiles) == len(RUNTIME_PROFILE_NAMES)

    for profile in profiles:
        payload = profile.to_payload()
        knob_paths = payload["knob_paths"]
        overrides = payload["plan_overrides"]

        assert knob_paths["retrieval"] != []
        assert knob_paths["cache"] != []
        assert knob_paths["budget"] != []
        assert overrides["retrieval"]["top_k_files"] >= 0
        assert "memory.cache.enabled" in knob_paths["cache"]
        assert "plan_replay_cache.enabled" in knob_paths["cache"]
        assert any(
            path == "retrieval_policy"
            or path.startswith("retrieval.")
            or path.startswith("repomap.")
            for path in knob_paths["retrieval"]
        )
        assert any(
            path.endswith("token_budget")
            or path.endswith("top_k_files")
            or path.endswith("budget_tokens")
            for path in knob_paths["budget"]
        )


def test_colbert_experiment_profile_enables_controlled_hash_colbert_rerank() -> None:
    profile = get_runtime_profile("colbert_experiment")

    assert profile is not None

    validated = validate_cli_config({"plan": profile.plan_overrides()})
    embeddings = validated["plan"]["embeddings"]

    assert embeddings["enabled"] is True
    assert embeddings["provider"] == "hash_colbert"
    assert embeddings["model"] == "hash-colbert-v1"
    assert embeddings["fail_open"] is True
    assert embeddings["rerank_pool"] == 24
