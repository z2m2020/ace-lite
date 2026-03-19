from __future__ import annotations

from ace_lite.memory_long_term import (
    LONG_TERM_FACT_SCHEMA_VERSION,
    LONG_TERM_OBSERVATION_SCHEMA_VERSION,
    build_long_term_fact_contract_v1,
    build_long_term_observation_contract_v1,
    validate_long_term_fact_contract_v1,
    validate_long_term_observation_contract_v1,
)


def test_long_term_observation_contract_round_trip() -> None:
    contract = build_long_term_observation_contract_v1(
        observation_id="obs-1",
        kind="validation",
        repo="ace-lite-engine",
        root="/repo",
        namespace="repo/ace-lite-engine",
        user_id="tester",
        profile_key="bugfix",
        query="why did validation fallback",
        payload={"reason": "git_unavailable", "event_count": 1},
        observed_at="2026-03-19T09:40:00+08:00",
        as_of="2026-03-19T09:40:00+08:00",
        source_run_id="run-123",
        severity="warning",
        status="captured",
        metadata={"channel": "validation"},
    )

    payload = contract.as_dict()
    validation = validate_long_term_observation_contract_v1(contract=payload)

    assert payload["schema_version"] == LONG_TERM_OBSERVATION_SCHEMA_VERSION
    assert payload["repo"] == "ace-lite-engine"
    assert payload["namespace"] == "repo/ace-lite-engine"
    assert payload["profile_key"] == "bugfix"
    assert payload["as_of"] == "2026-03-19T01:40:00+00:00"
    assert validation["ok"] is True
    assert validation["normalized_contract"]["payload"]["reason"] == "git_unavailable"


def test_long_term_observation_contract_requires_as_of() -> None:
    payload = {
        "schema_version": LONG_TERM_OBSERVATION_SCHEMA_VERSION,
        "id": "obs-1",
        "kind": "validation",
        "repo": "ace-lite-engine",
        "root": "/repo",
        "namespace": "repo/ace-lite-engine",
        "user_id": "tester",
        "profile_key": "bugfix",
        "query": "why did validation fallback",
        "payload": {"reason": "git_unavailable"},
        "observed_at": "2026-03-19T01:40:00+00:00",
        "as_of": "",
        "source_run_id": "run-123",
        "severity": "warning",
        "status": "captured",
        "metadata": {},
    }

    validation = validate_long_term_observation_contract_v1(contract=payload)

    assert validation["ok"] is False
    assert validation["violation_count"] == 1
    assert "as_of" in validation["violation_details"][0]["message"]


def test_long_term_fact_contract_round_trip() -> None:
    contract = build_long_term_fact_contract_v1(
        fact_id="fact-1",
        fact_type="repo_policy",
        subject="runtime.validation.git",
        predicate="fallback_policy",
        object_value="reuse_checkout_or_skip",
        repo="ace-lite-engine",
        root="/repo",
        namespace="repo/ace-lite-engine",
        user_id="tester",
        profile_key="bugfix",
        as_of="2026-03-19T09:44:00+08:00",
        confidence=1.2,
        valid_from="2026-03-19T09:44:00+08:00",
        derived_from_observation_id="obs-1",
        metadata={"source": "wave61"},
    )

    payload = contract.as_dict()
    validation = validate_long_term_fact_contract_v1(contract=payload)

    assert payload["schema_version"] == LONG_TERM_FACT_SCHEMA_VERSION
    assert payload["repo"] == "ace-lite-engine"
    assert payload["namespace"] == "repo/ace-lite-engine"
    assert payload["profile_key"] == "bugfix"
    assert payload["confidence"] == 1.0
    assert validation["ok"] is True
    assert validation["normalized_contract"]["object"] == "reuse_checkout_or_skip"


def test_long_term_fact_contract_rejects_missing_observation_link() -> None:
    payload = {
        "schema_version": LONG_TERM_FACT_SCHEMA_VERSION,
        "id": "fact-1",
        "fact_type": "repo_policy",
        "subject": "runtime.validation.git",
        "predicate": "fallback_policy",
        "object": "reuse_checkout_or_skip",
        "repo": "ace-lite-engine",
        "root": "/repo",
        "namespace": "repo/ace-lite-engine",
        "user_id": "tester",
        "profile_key": "bugfix",
        "as_of": "2026-03-19T01:44:00+00:00",
        "confidence": 0.8,
        "valid_from": "",
        "valid_to": "",
        "superseded_by": "",
        "derived_from_observation_id": "",
        "metadata": {},
    }

    validation = validate_long_term_fact_contract_v1(contract=payload)

    assert validation["ok"] is False
    assert validation["violation_count"] == 1
    assert "derived_from_observation_id" in validation["violation_details"][0]["message"]
