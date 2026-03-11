from __future__ import annotations

from pathlib import Path

from ace_lite.indexer import build_index


def test_build_index_includes_markdown_by_default(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)

    (tmp_path / "README.md").write_text(
        "# Title\n\nSee [Design](./design.md).\n\n## Sub\nDetails.\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "guide.md").write_text(
        "# Guide\n\nText.\n",
        encoding="utf-8",
    )

    index = build_index(tmp_path)

    assert index["file_count"] == 2
    assert "markdown" in index["languages_covered"]
    assert "README.md" in index["files"]
    assert "docs/guide.md" in index["files"]

    readme = index["files"]["README.md"]
    symbols = [item for item in readme.get("symbols", []) if isinstance(item, dict)]
    assert any(
        item.get("kind") == "section" and item.get("name") == "Title"
        for item in symbols
    )
    assert any(
        item.get("kind") == "section" and item.get("name") == "Sub"
        for item in symbols
    )

    references = [
        item for item in readme.get("references", []) if isinstance(item, dict)
    ]
    assert any(
        item.get("kind") == "doc_link" and item.get("name") == "./design.md"
        for item in references
    )

