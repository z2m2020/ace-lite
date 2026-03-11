from __future__ import annotations

from pathlib import Path

from ace_lite.chunking.builder import build_candidate_chunks


def test_chunk_builder_selects_markdown_sections(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "guide.md").write_text(
        "# Title\nBody\n\n## Sub\nMore\n",
        encoding="utf-8",
    )

    files_map = {
        "docs/guide.md": {
            "module": "docs.guide",
            "language": "markdown",
            "symbols": [
                {
                    "name": "Title",
                    "qualified_name": "docs/guide.md#Title",
                    "kind": "section",
                    "lineno": 1,
                    "end_lineno": 5,
                },
                {
                    "name": "Sub",
                    "qualified_name": "docs/guide.md#Title/Sub",
                    "kind": "section",
                    "lineno": 4,
                    "end_lineno": 5,
                },
            ],
            "references": [],
            "imports": [],
        }
    }
    candidates = [
        {
            "path": "docs/guide.md",
            "score": 10.0,
            "language": "markdown",
            "module": "docs.guide",
            "retrieval_pass": "test",
            "score_breakdown": {"test": 1.0},
        }
    ]

    chunks, metrics = build_candidate_chunks(
        root=str(tmp_path),
        files_map=files_map,
        candidates=candidates,
        terms=["title"],
        top_k_files=1,
        top_k_chunks=6,
        per_file_limit=3,
        token_budget=1200,
        disclosure_mode="refs",
        snippet_max_lines=18,
        snippet_max_chars=1200,
        policy={},
        tokenizer_model="gpt-4o-mini",
        diversity_enabled=False,
        diversity_path_penalty=0.0,
        diversity_symbol_family_penalty=0.0,
        diversity_kind_penalty=0.0,
        diversity_locality_penalty=0.0,
        diversity_locality_window=24,
    )

    assert isinstance(metrics, dict)
    assert any(
        item.get("path") == "docs/guide.md" and item.get("kind") == "section"
        for item in chunks
    )

