from ace_lite.cli_app import orchestrator_factory_memory_payload
from ace_lite.cli_app.orchestrator_factory_support import build_memory_payload


def test_orchestrator_factory_support_reexports_memory_payload_builder() -> None:
    assert (
        build_memory_payload
        is orchestrator_factory_memory_payload.build_memory_payload
    )


def test_build_memory_payload_reads_nested_grouped_values() -> None:
    payload = build_memory_payload(
        memory_group={
            "gate": {"enabled": True, "mode": "never"},
            "timeline": {"enabled": False},
            "capture": {
                "enabled": True,
                "keywords": ["alpha", "beta"],
                "min_query_length": 12,
            },
            "notes": {
                "enabled": True,
                "mode": "prefer_local",
                "limit": 5,
            },
            "postprocess": {
                "enabled": True,
                "diversity_similarity_threshold": 0.77,
            },
        },
        memory_gate_enabled=False,
        memory_gate_mode="auto",
        memory_timeline_enabled=True,
        memory_capture_enabled=False,
        memory_capture_keywords=None,
        memory_capture_min_query_length=24,
        memory_notes_enabled=False,
        memory_notes_mode="supplement",
        memory_notes_limit=8,
        memory_postprocess_enabled=False,
        memory_postprocess_diversity_similarity_threshold=0.9,
    )

    assert payload["gate"] == {"enabled": True, "mode": "never"}
    assert payload["timeline_enabled"] is False
    assert payload["capture"]["enabled"] is True
    assert payload["capture"]["keywords"] == ["alpha", "beta"]
    assert payload["capture"]["min_query_length"] == 12
    assert payload["notes"]["enabled"] is True
    assert payload["notes"]["mode"] == "prefer_local"
    assert payload["notes"]["limit"] == 5
    assert payload["postprocess"]["enabled"] is True
    assert payload["postprocess"]["diversity_similarity_threshold"] == 0.77


def test_build_memory_payload_explicit_values_override_grouped_defaults() -> None:
    payload = build_memory_payload(
        memory_group={
            "gate": {"enabled": False, "mode": "never"},
            "profile": {"enabled": False, "top_n": 2},
            "notes": {"mode": "prefer_local", "limit": 5},
        },
        memory_gate_enabled=True,
        memory_gate_mode="always",
        memory_profile_enabled=True,
        memory_profile_top_n=7,
        memory_notes_limit=11,
        memory_notes_mode="merge",
    )

    assert payload["gate"]["enabled"] is True
    assert payload["gate"]["mode"] == "always"
    assert payload["profile"]["enabled"] is True
    assert payload["profile"]["top_n"] == 7
    assert payload["notes"]["limit"] == 11
    assert payload["notes"]["mode"] == "merge"
