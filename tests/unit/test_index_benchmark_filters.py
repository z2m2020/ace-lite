from __future__ import annotations

from ace_lite.index_stage import (
    filter_candidate_rows,
    filter_files_map_for_benchmark,
    resolve_benchmark_candidate_filters,
    resolve_docs_policy_for_benchmark,
    resolve_worktree_policy_for_benchmark,
)
from ace_lite.pipeline.types import StageContext


def test_resolve_benchmark_candidate_filters_normalizes_lists() -> None:
    ctx = StageContext(
        query="q",
        repo="demo",
        root=".",
        state={
            "benchmark_filters": {
                "include_paths": ["src\\alpha.py", "", None],
                "include_globs": "*.py",
                "exclude_paths": ["docs\\guide.md"],
            }
        },
    )

    payload = resolve_benchmark_candidate_filters(ctx)

    assert payload == {
        "requested": True,
        "include_paths": ["src/alpha.py"],
        "include_globs": ["*.py"],
        "exclude_paths": ["docs/guide.md"],
        "exclude_globs": [],
    }


def test_resolve_docs_and_worktree_policy_for_benchmark() -> None:
    docs_enabled, docs_reason = resolve_docs_policy_for_benchmark(
        policy_docs_enabled=True,
        benchmark_filter_payload={"include_paths": ["docs/guide.md"]},
    )
    code_only_enabled, code_only_reason = resolve_docs_policy_for_benchmark(
        policy_docs_enabled=True,
        benchmark_filter_payload={"include_paths": ["src/alpha.py"]},
    )
    worktree_enabled, worktree_reason = resolve_worktree_policy_for_benchmark(
        worktree_prior_enabled=True,
        benchmark_filter_payload={"include_paths": ["src/alpha.py"], "include_globs": []},
    )

    assert (docs_enabled, docs_reason) == (
        True,
        "benchmark_include_paths_contains_docs",
    )
    assert (code_only_enabled, code_only_reason) == (
        False,
        "benchmark_include_paths_code_only",
    )
    assert (worktree_enabled, worktree_reason) == (
        False,
        "benchmark_filter_explicit_scope",
    )


def test_filter_candidate_rows_and_files_map_for_benchmark() -> None:
    rows = [
        {"path": "src/alpha.py", "score": 8.0},
        {"path": "docs/guide.md", "score": 5.0},
        {"path": "tests/test_alpha.py", "score": 3.0},
    ]
    files_map = {
        "src/alpha.py": {"language": "python"},
        "docs/guide.md": {"language": "markdown"},
        "tests/test_alpha.py": {"language": "python"},
    }

    filtered_rows, removed_rows = filter_candidate_rows(
        rows,
        include_paths=[],
        include_globs=["*.py"],
        exclude_paths=["tests/test_alpha.py"],
        exclude_globs=[],
    )
    filtered_files_map, removed_files = filter_files_map_for_benchmark(
        files_map,
        include_paths=[],
        include_globs=["*.py"],
        exclude_paths=["tests/test_alpha.py"],
        exclude_globs=[],
    )

    assert removed_rows == 2
    assert filtered_rows == [{"path": "src/alpha.py", "score": 8.0}]
    assert removed_files == 2
    assert filtered_files_map == {"src/alpha.py": {"language": "python"}}
