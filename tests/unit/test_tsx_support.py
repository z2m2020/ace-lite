from __future__ import annotations

from pathlib import Path

import pytest

from ace_lite.parsers.languages import detect_language, normalize_languages, supported_extensions
from ace_lite.parsers.treesitter_engine import TreeSitterEngine


def test_normalize_languages_expands_typescript_to_tsx() -> None:
    languages = normalize_languages(["typescript"])

    assert "typescript" in languages
    assert "tsx" in languages
    assert ".tsx" in supported_extensions(languages)


def test_detect_language_returns_tsx() -> None:
    assert detect_language(Path("component.tsx")) == "tsx"


def test_treesitter_parses_tsx(tmp_path: Path) -> None:
    import ace_lite.parsers.treesitter_engine as treesitter_engine

    if treesitter_engine.get_parser is None:
        pytest.skip("tree-sitter-language-pack not installed")

    try:
        parser = treesitter_engine.get_parser("tsx")
    except Exception:
        pytest.skip("tsx parser not available")
    if parser is None:
        pytest.skip("tsx parser not available")

    file_path = tmp_path / "useApiFetch.tsx"
    file_path.write_text(
        "export default function useApiFetch() { return null; }\n",
        encoding="utf-8",
    )

    engine = TreeSitterEngine(["typescript"])
    entry = engine.parse_file(file_path, tmp_path)

    assert entry is not None
    assert entry["language"] == "tsx"
    assert any(
        symbol.get("qualified_name") == "useApiFetch"
        for symbol in entry.get("symbols", [])
        if isinstance(symbol, dict)
    )

