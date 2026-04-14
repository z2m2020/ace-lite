from __future__ import annotations

from ace_lite.orchestrator_validation_support import (
    build_orchestrator_validation_runtime,
)


def test_build_orchestrator_validation_runtime_normalizes_state() -> None:
    runtime = build_orchestrator_validation_runtime(
        ctx_state={
            "source_plan": {"steps": [{"stage": "validate"}]},
            "index": {"candidate_files": [{"path": "src/a.py"}]},
            "__policy": {"name": "feature", "version": "v2"},
            "_validation_patch_artifact": {"path": "patch.diff"},
        }
    )

    assert runtime.source_plan_stage == {"steps": [{"stage": "validate"}]}
    assert runtime.index_stage == {"candidate_files": [{"path": "src/a.py"}]}
    assert runtime.policy == {"name": "feature", "version": "v2"}
    assert runtime.patch_artifact == {"path": "patch.diff"}


def test_build_orchestrator_validation_runtime_falls_back_for_invalid_types() -> None:
    runtime = build_orchestrator_validation_runtime(
        ctx_state={
            "source_plan": [],
            "index": None,
            "__policy": "feature",
            "_validation_patch_artifact": ["patch.diff"],
        }
    )

    assert runtime.source_plan_stage == {}
    assert runtime.index_stage == {}
    assert runtime.policy == {}
    assert runtime.patch_artifact is None
