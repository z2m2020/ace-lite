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

