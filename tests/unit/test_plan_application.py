from __future__ import annotations

import ace_lite.plan_application as plan_application_module
from ace_lite.plan_timeout import PlanTimeoutOutcome
from ace_lite.plan_application import (
    attach_plan_contract_summary,
    build_plan_contract_summary_from_payload,
    execute_timed_plan_with_fallback,
    resolve_plan_quick_fallback,
)


def test_resolve_plan_quick_fallback_collects_paths_and_steps() -> None:
    def fake_plan_quick(**kwargs):
        assert kwargs["query"] == "timeout"
        assert kwargs["languages"] == "python"
        return {
            "candidate_files": ["src/app.py", "tests/test_app.py"],
            "steps": ["Inspect candidate files."],
        }

    fallback = resolve_plan_quick_fallback(
        plan_quick_fn=fake_plan_quick,
        normalized_query="timeout",
        root_path=".",
        top_k_files=4,
        plan_quick_kwargs={"languages": "python"},
    )

    assert fallback.candidate_file_paths == ["src/app.py", "tests/test_app.py"]
    assert fallback.steps == ["Inspect candidate files."]
    assert fallback.fallback_mode == "plan_quick"


def test_execute_timed_plan_with_fallback_uses_resolver_on_timeout(
    tmp_path, monkeypatch
) -> None:
    def fake_fallback():
        return resolve_plan_quick_fallback(
            plan_quick_fn=lambda **kwargs: {
                "candidate_files": ["src/app.py"],
                "steps": ["Inspect candidate files."],
            },
            normalized_query="timeout",
            root_path=tmp_path,
            top_k_files=4,
        )

    monkeypatch.setattr(
        plan_application_module,
        "execute_with_timeout",
        lambda **kwargs: PlanTimeoutOutcome(
            payload=None,
            timed_out=True,
            timeout_seconds=1.0,
            elapsed_ms=123.0,
            debug_dump_path=None,
        ),
    )

    execution = execute_timed_plan_with_fallback(
        run_payload=lambda: {"ok": True},
        timeout_seconds=1.0,
        debug_root=tmp_path,
        debug_payload={"entrypoint": "test"},
        debug_enabled=False,
        fallback_resolver=fake_fallback,
    )

    assert execution.timed_out is True
    assert execution.fallback.candidate_file_paths == ["src/app.py"]
    assert execution.fallback.steps == ["Inspect candidate files."]


def test_build_plan_contract_summary_from_payload_handles_missing_sections() -> None:
    assert build_plan_contract_summary_from_payload({}) == {}
    assert build_plan_contract_summary_from_payload(None) == {}


def test_attach_plan_contract_summary_mutates_payload_when_available() -> None:
    payload = {
        "index": {
            "chunk_contract": {"schema_version": "chunk-v1"},
            "subgraph_payload": {
                "payload_version": "subgraph-v1",
                "taxonomy_version": "taxonomy-v1",
            },
        },
        "source_plan": {
            "steps": [],
            "chunk_contract": {"schema_version": "chunk-v2"},
            "prompt_rendering_boundary": {"boundary_version": "prompt-v1"},
            "subgraph_payload": {
                "payload_version": "subgraph-v2",
                "taxonomy_version": "taxonomy-v2",
            },
        },
    }

    normalized = attach_plan_contract_summary(payload)

    assert normalized["contract_summary"] == {
        "index_chunk_contract_version": "chunk-v1",
        "source_plan_chunk_contract_version": "chunk-v2",
        "prompt_rendering_boundary_version": "prompt-v1",
        "index_subgraph_payload_version": "subgraph-v1",
        "source_plan_subgraph_payload_version": "subgraph-v2",
        "subgraph_taxonomy_version": "taxonomy-v2",
    }
