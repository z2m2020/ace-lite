from __future__ import annotations

from ace_lite.orchestrator_augment_support import (
    build_orchestrator_augment_runtime,
    resolve_augment_candidates,
)


def test_build_orchestrator_augment_runtime_normalizes_optional_state() -> None:
    runtime = build_orchestrator_augment_runtime(
        ctx_state={
            "index": {"candidate_files": [{"path": "src/a.py"}]},
            "repomap": {"focused_files": ["src/a.py"]},
            "__index_files": {"src/a.py": {"module": "demo.a"}},
            "__vcs_worktree": {"enabled": True},
            "__policy": {"name": "feature", "version": "v2"},
        }
    )

    assert runtime.index_stage == {"candidate_files": [{"path": "src/a.py"}]}
    assert runtime.repomap_stage == {"focused_files": ["src/a.py"]}
    assert runtime.index_files == {"src/a.py": {"module": "demo.a"}}
    assert runtime.vcs_worktree_override == {"enabled": True}
    assert runtime.policy == {"name": "feature", "version": "v2"}


def test_resolve_augment_candidates_prefers_focused_file_order() -> None:
    candidates = resolve_augment_candidates(
        index_stage={
            "candidate_files": [
                {"path": "src/a.py", "score": 2},
                {"path": "src/b.py", "score": 1},
            ]
        },
        repomap_stage={"focused_files": ["src/b.py", "src/a.py"]},
        index_files={},
    )

    assert candidates == [
        {"path": "src/b.py", "score": 1},
        {"path": "src/a.py", "score": 2},
    ]


def test_resolve_augment_candidates_backfills_from_index_files() -> None:
    candidates = resolve_augment_candidates(
        index_stage={"candidate_files": []},
        repomap_stage={"focused_files": ["src/c.py"]},
        index_files={
            "src/c.py": {
                "module": "demo.c",
                "language": "python",
                "symbols": ["c1", "c2"],
                "imports": [{"module": "demo.a"}],
            }
        },
    )

    assert candidates == [
        {
            "path": "src/c.py",
            "module": "demo.c",
            "language": "python",
            "score": 0,
            "symbol_count": 2,
            "import_count": 1,
        }
    ]
