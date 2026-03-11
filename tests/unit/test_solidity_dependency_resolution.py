from __future__ import annotations

from pathlib import Path

from ace_lite.index_cache import expand_changed_files_with_reverse_dependencies
from ace_lite.indexer import build_index, discover_source_files
from ace_lite.repomap.builder import build_stage_repo_map


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_solidity_discovers_node_modules_sol_only(tmp_path: Path) -> None:
    _write(
        tmp_path / "contracts" / "Main.sol",
        'import "@openzeppelin/contracts/token/ERC20/IERC20.sol";\n'
        "contract Main { IERC20 public token; }\n",
    )
    _write(
        tmp_path / "node_modules" / "@openzeppelin" / "contracts" / "token" / "ERC20" / "IERC20.sol",
        "interface IERC20 { function totalSupply() external view returns (uint256); }\n",
    )
    _write(
        tmp_path / "node_modules" / "noise.ts",
        "export const ignored = true;\n",
    )

    root, languages, files = discover_source_files(
        tmp_path, languages=["solidity", "typescript"]
    )
    assert root == tmp_path.resolve()
    assert "solidity" in set(languages)
    rels = [path.relative_to(root).as_posix() for path in files]
    assert "contracts/Main.sol" in rels
    assert (
        "node_modules/@openzeppelin/contracts/token/ERC20/IERC20.sol" in rels
    ), "should collect Solidity sources from node_modules"
    assert "node_modules/noise.ts" not in rels, "should not collect TS/JS from node_modules"


def test_solidity_dependency_tiering_and_import_resolution(tmp_path: Path) -> None:
    _write(
        tmp_path / "contracts" / "Main.sol",
        'import "@openzeppelin/contracts/token/ERC20/IERC20.sol";\n'
        "contract Main { IERC20 public token; }\n",
    )
    dep_path = (
        tmp_path
        / "node_modules"
        / "@openzeppelin"
        / "contracts"
        / "token"
        / "ERC20"
        / "IERC20.sol"
    )
    _write(
        dep_path,
        "interface IERC20 { function totalSupply() external view returns (uint256); }\n",
    )

    payload = build_index(tmp_path, languages=["solidity"])
    files_map = payload.get("files") or {}
    assert isinstance(files_map, dict)
    assert files_map["contracts/Main.sol"]["tier"] == "first_party"
    assert (
        files_map["node_modules/@openzeppelin/contracts/token/ERC20/IERC20.sol"]["tier"]
        == "dependency"
    )

    stage = build_stage_repo_map(
        index_files=files_map,
        seed_candidates=[{"path": "contracts/Main.sol"}],
        ranking_profile="graph",
        top_k=1,
        neighbor_limit=10,
        neighbor_depth=1,
        budget_tokens=10_000,
    )
    assert stage["enabled"] is True
    expected = stage.get("expected_neighbor_paths") or []
    assert (
        "node_modules/@openzeppelin/contracts/token/ERC20/IERC20.sol" in expected
    ), "repomap import expansion should resolve @openzeppelin/... to node_modules path"

    expanded, _count = expand_changed_files_with_reverse_dependencies(
        changed_files=["node_modules/@openzeppelin/contracts/token/ERC20/IERC20.sol"],
        index_files=files_map,
        max_depth=2,
        max_extra=10,
    )
    assert "contracts/Main.sol" in expanded, "reverse dependencies should include importer"


def test_solidity_discovers_lib_sol_only(tmp_path: Path) -> None:
    _write(
        tmp_path / "contracts" / "Main.sol",
        'import "forge-std/Test.sol";\n'
        "contract Main is Test {}\n",
    )
    _write(
        tmp_path / "lib" / "forge-std" / "src" / "Test.sol",
        "abstract contract Test {}\n",
    )
    _write(
        tmp_path / "lib" / "forge-std" / "README.md",
        "# dependency docs\n",
    )

    root, languages, files = discover_source_files(
        tmp_path,
        languages=["solidity"],
    )
    assert root == tmp_path.resolve()
    assert "solidity" in set(languages)
    rels = [path.relative_to(root).as_posix() for path in files]
    assert "contracts/Main.sol" in rels
    assert "lib/forge-std/src/Test.sol" in rels
    assert "lib/forge-std/README.md" not in rels


def test_solidity_lib_dependency_tiering_and_import_resolution(tmp_path: Path) -> None:
    _write(
        tmp_path / "contracts" / "Main.sol",
        'import "forge-std/Test.sol";\n'
        "contract Main is Test {}\n",
    )
    _write(
        tmp_path / "lib" / "forge-std" / "src" / "Test.sol",
        "abstract contract Test {}\n",
    )

    payload = build_index(tmp_path, languages=["solidity"])
    files_map = payload.get("files") or {}
    assert isinstance(files_map, dict)
    assert files_map["contracts/Main.sol"]["tier"] == "first_party"
    assert files_map["lib/forge-std/src/Test.sol"]["tier"] == "dependency"

    stage = build_stage_repo_map(
        index_files=files_map,
        seed_candidates=[{"path": "contracts/Main.sol"}],
        ranking_profile="graph",
        top_k=1,
        neighbor_limit=10,
        neighbor_depth=1,
        budget_tokens=10_000,
    )
    assert stage["enabled"] is True
    expected = stage.get("expected_neighbor_paths") or []
    assert (
        "lib/forge-std/src/Test.sol" in expected
    ), "repomap import expansion should resolve forge-std remapping style imports to lib path"

    expanded, _count = expand_changed_files_with_reverse_dependencies(
        changed_files=["lib/forge-std/src/Test.sol"],
        index_files=files_map,
        max_depth=2,
        max_extra=10,
    )
    assert "contracts/Main.sol" in expanded, "reverse dependencies should include lib importer"
