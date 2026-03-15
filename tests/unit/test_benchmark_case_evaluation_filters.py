from __future__ import annotations

from ace_lite.benchmark.case_evaluation_filters import (
    candidate_path_matches_filters,
    coerce_string_list,
    filter_candidate_path_items,
    normalize_benchmark_path,
    resolve_candidate_path_filters,
)


def test_resolve_candidate_path_filters_normalizes_strings_and_slashes() -> None:
    filters = resolve_candidate_path_filters(
        {
            "filters": {
                "include_paths": ["src\\app.py", " "],
                "include_globs": "src/**/*.py",
                "exclude_paths": ["tests\\test_app.py"],
                "exclude_globs": ["docs/*.md"],
            }
        }
    )

    assert filters == {
        "include_paths": ["src/app.py"],
        "include_globs": ["src/**/*.py"],
        "exclude_paths": ["tests/test_app.py"],
        "exclude_globs": ["docs/*.md"],
    }


def test_candidate_path_matches_filters_honors_include_and_exclude() -> None:
    assert (
        candidate_path_matches_filters(
            "src/app.py",
            include_paths=[],
            include_globs=["src/*.py"],
            exclude_paths=[],
            exclude_globs=[],
        )
        is True
    )
    assert (
        candidate_path_matches_filters(
            "docs/readme.md",
            include_paths=[],
            include_globs=["src/*.py"],
            exclude_paths=[],
            exclude_globs=[],
        )
        is False
    )
    assert (
        candidate_path_matches_filters(
            "src/app.py",
            include_paths=[],
            include_globs=["src/*.py"],
            exclude_paths=["src/app.py"],
            exclude_globs=[],
        )
        is False
    )


def test_filter_candidate_path_items_preserves_non_dict_items_and_filters_dicts() -> None:
    filtered = filter_candidate_path_items(
        [
            {"path": "src/app.py", "score": 1.0},
            {"path": "docs/readme.md", "score": 0.5},
            "raw-note",
        ],
        include_paths=[],
        include_globs=["src/*.py"],
        exclude_paths=[],
        exclude_globs=[],
    )

    assert filtered == [
        {"path": "src/app.py", "score": 1.0},
        "raw-note",
    ]


def test_small_string_helpers_cover_non_list_inputs() -> None:
    assert coerce_string_list(" alpha ") == ["alpha"]
    assert coerce_string_list(None) == []
    assert normalize_benchmark_path("src\\app.py") == "src/app.py"
