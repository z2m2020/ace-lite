from __future__ import annotations

from pathlib import Path

import pytest

from ace_lite.parsers.languages import detect_language, normalize_languages, supported_extensions
from ace_lite.parsers.treesitter_engine import TreeSitterEngine


def _skip_if_parser_unavailable(language: str) -> None:
    import ace_lite.parsers.treesitter_engine as treesitter_engine

    if treesitter_engine.get_parser is None:
        pytest.skip("tree-sitter-language-pack not installed")
    try:
        parser = treesitter_engine.get_parser(language)
    except Exception:
        pytest.skip(f"{language} parser not available")
    if parser is None:
        pytest.skip(f"{language} parser not available")


@pytest.mark.parametrize(
    ("filename", "expected_language"),
    [
        ("main.rs", "rust"),
        ("Main.java", "java"),
        ("add.c", "c"),
        ("add.h", "c"),
        ("main.cpp", "cpp"),
        ("main.hpp", "cpp"),
        ("Program.cs", "c_sharp"),
        ("app.rb", "ruby"),
        ("index.php", "php"),
        ("main.kt", "kotlin"),
        ("main.kts", "kotlin"),
        ("main.swift", "swift"),
        ("run.sh", "bash"),
        ("run.bash", "bash"),
        ("main.lua", "lua"),
        ("Vault.sol", "solidity"),
    ],
)
def test_detect_language_supports_more_extensions(filename: str, expected_language: str) -> None:
    assert detect_language(Path(filename)) == expected_language


def test_normalize_languages_supports_common_aliases() -> None:
    languages = normalize_languages(["C++", "C#", "JS", "TS", "Golang"])
    assert languages == ("cpp", "c_sharp", "javascript", "typescript", "tsx", "go")


@pytest.mark.parametrize(
    ("language", "filename", "source", "must_contain"),
    [
        ("rust", "main.rs", "pub fn hello_world() {}\nstruct MyType {}\n", ["hello_world", "MyType"]),
        (
            "java",
            "Main.java",
            "package com.example;\npublic class Hello { void run() {} }\n",
            ["Hello", "Hello.run"],
        ),
        ("c", "add.c", "int add(int a, int b) { return a + b; }\n", ["add"]),
        ("cpp", "main.cpp", "int baz() { return 0; }\n", ["baz"]),
        ("c_sharp", "Program.cs", "public class Foo { public void Bar() {} }\n", ["Foo", "Foo.Bar"]),
        ("ruby", "app.rb", "class Foo\n  def bar\n  end\nend\n", ["Foo"]),
        ("php", "index.php", "<?php class Foo { function bar() {} }\n", ["Foo"]),
        ("kotlin", "main.kt", "class Foo { fun bar() {} }\n", ["Foo", "Foo.bar"]),
        ("swift", "main.swift", "struct Foo { func bar() {} }\n", ["Foo", "Foo.bar"]),
        ("bash", "run.sh", "my_func() { echo hi; }\n", ["my_func"]),
        ("lua", "main.lua", "local function hello() end\n", ["hello"]),
        (
            "solidity",
            "Vault.sol",
            "pragma solidity ^0.8.20;\nimport \"./Foo.sol\";\ncontract Vault { event Withdraw(address indexed to, uint256 amount); function withdraw(uint256 amount) external {} }\n",
            ["Vault", "Vault.withdraw", "Vault.Withdraw"],
        ),
    ],
)
def test_treesitter_extracts_basic_symbols_for_more_languages(
    tmp_path: Path,
    language: str,
    filename: str,
    source: str,
    must_contain: list[str],
) -> None:
    _skip_if_parser_unavailable(language)

    file_path = tmp_path / filename
    file_path.write_text(source, encoding="utf-8")

    engine = TreeSitterEngine([language])
    entry = engine.parse_file(file_path, tmp_path)

    assert entry is not None
    assert entry["language"] == language

    qualified_names = {
        str(item.get("qualified_name"))
        for item in entry.get("symbols", [])
        if isinstance(item, dict) and "qualified_name" in item
    }
    for symbol_name in must_contain:
        assert symbol_name in qualified_names


def test_supported_extensions_expands_default_profile() -> None:
    # Ensure the default profile includes more than the original 4-language set.
    suffixes = supported_extensions(normalize_languages(None))
    assert ".py" in suffixes
    assert ".go" in suffixes
    assert ".rs" in suffixes
    assert ".java" in suffixes
    assert ".c" in suffixes
    assert ".cpp" in suffixes
