from __future__ import annotations

from pathlib import Path

import pytest

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


def test_solidity_extracts_contract_symbols_and_imports(tmp_path: Path) -> None:
    _skip_if_parser_unavailable("solidity")

    file_path = tmp_path / "Vault.sol"
    file_path.write_text(
        "pragma solidity ^0.8.20;\n"
        "import \"./Foo.sol\";\n"
        "contract Vault {\n"
        "  event Withdraw(address indexed to, uint256 amount);\n"
        "  error Nope();\n"
        "  modifier onlyOwner() { _; }\n"
        "  constructor(uint256 x) {}\n"
        "  function withdraw(uint256 amount) external {}\n"
        "}\n",
        encoding="utf-8",
    )

    engine = TreeSitterEngine(["solidity"])
    entry = engine.parse_file(file_path, tmp_path)
    assert entry is not None
    assert entry["language"] == "solidity"

    qualified_names = {
        str(item.get("qualified_name"))
        for item in entry.get("symbols", [])
        if isinstance(item, dict) and "qualified_name" in item
    }
    assert "Vault" in qualified_names
    assert "Vault.Withdraw" in qualified_names
    assert "Vault.Nope" in qualified_names
    assert "Vault.onlyOwner" in qualified_names
    assert "Vault.constructor" in qualified_names
    assert "Vault.withdraw" in qualified_names

    modules = {
        str(item.get("module") or "")
        for item in entry.get("imports", [])
        if isinstance(item, dict)
    }
    assert "./Foo.sol" in modules

