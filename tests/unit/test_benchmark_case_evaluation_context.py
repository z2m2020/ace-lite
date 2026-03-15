from __future__ import annotations

from ace_lite.benchmark.case_evaluation_context import build_candidate_context


def _coerce_chunk_refs(value):  # type: ignore[no-untyped-def]
    return [item for item in value if isinstance(item, dict)]


def test_build_candidate_context_filters_index_and_source_plan_candidates() -> None:
    context = build_candidate_context(
        case={"filters": {"include_globs": ["docs/*.md"]}},
        index_payload={
            "candidate_files": [
                {"path": "docs/guide.md"},
                {"path": "src/app.py"},
            ],
            "candidate_chunks": [
                {"path": "docs/guide.md", "qualified_name": "GUIDE"},
                {"path": "src/app.py", "qualified_name": "app"},
            ],
        },
        index_benchmark_filters={},
        source_plan_payload={
            "candidate_chunks": [
                {"path": "docs/guide.md", "qualified_name": "GUIDE"},
                {"path": "src/app.py", "qualified_name": "app"},
            ]
        },
        coerce_chunk_refs=_coerce_chunk_refs,
    )

    assert context.candidate_path_filters["include_globs"] == ["docs/*.md"]
    assert context.candidate_files == [{"path": "docs/guide.md"}]
    assert context.raw_candidate_chunks == [
        {"path": "docs/guide.md", "qualified_name": "GUIDE"}
    ]
    assert context.source_plan_candidate_chunks == [
        {"path": "docs/guide.md", "qualified_name": "GUIDE"}
    ]
    assert context.candidate_chunks == context.source_plan_candidate_chunks


def test_build_candidate_context_respects_upstream_filters_flag() -> None:
    context = build_candidate_context(
        case={"filters": {"include_globs": ["docs/*.md"]}},
        index_payload={
            "candidate_files": [{"path": "src/app.py"}],
            "candidate_chunks": [{"path": "src/app.py", "qualified_name": "app"}],
        },
        index_benchmark_filters={
            "requested": True,
            "include_paths": ["src/app.py"],
            "include_globs": [],
            "exclude_paths": [],
            "exclude_globs": [],
        },
        source_plan_payload={},
        coerce_chunk_refs=_coerce_chunk_refs,
    )

    assert context.filters_applied_upstream is True
    assert context.candidate_path_filters == {
        "include_paths": ["src/app.py"],
        "include_globs": [],
        "exclude_paths": [],
        "exclude_globs": [],
    }
    assert context.candidate_files == [{"path": "src/app.py"}]
    assert context.candidate_chunks == [{"path": "src/app.py", "qualified_name": "app"}]
