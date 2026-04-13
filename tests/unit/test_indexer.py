from __future__ import annotations

import textwrap
from pathlib import Path

from ace_lite.indexer import build_index, classify_tier, discover_source_files, update_index


def _create_sample_repo(root: Path) -> None:
    package_dir = root / "pkg"
    package_dir.mkdir(parents=True, exist_ok=True)

    (package_dir / "__init__.py").write_text("from .mod import Greeter\n", encoding="utf-8")
    (package_dir / "mod.py").write_text(
        textwrap.dedent(
            """
            import os
            from typing import Any as TypingAny

            SCHEMA_VERSION = "3.0"

            class Greeter:
                def greet(self, name: str) -> str:
                    return f"hi {name}"

            def helper(value: TypingAny) -> str:
                return str(value)
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def test_build_index_extracts_symbols_imports_and_hash(tmp_path: Path) -> None:
    _create_sample_repo(tmp_path)

    index = build_index(tmp_path, languages=["python"])

    assert index["file_count"] == 2
    assert index["languages_covered"] == ["python"]
    assert "pkg/mod.py" in index["files"]

    mod_entry = index["files"]["pkg/mod.py"]
    assert mod_entry["module"] == "pkg.mod"
    assert mod_entry["language"] == "python"
    assert len(mod_entry["sha256"]) == 64

    class_symbols = {item["qualified_name"] for item in mod_entry["classes"]}
    function_symbols = {item["qualified_name"] for item in mod_entry["functions"]}
    import_modules = {item["module"] for item in mod_entry["imports"]}
    symbol_names = {item["name"] for item in mod_entry["symbols"]}

    assert "Greeter" in class_symbols
    assert "helper" in function_symbols
    assert "Greeter.greet" in function_symbols
    assert "os" in import_modules
    assert "typing" in import_modules
    assert "SCHEMA_VERSION" in symbol_names


def test_update_index_applies_incremental_changes(tmp_path: Path) -> None:
    _create_sample_repo(tmp_path)
    index = build_index(tmp_path, languages=["python"])

    mod_file = tmp_path / "pkg" / "mod.py"
    mod_file.write_text(
        mod_file.read_text(encoding="utf-8")
        + "\n\ndef another() -> int:\n    return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "pkg" / "__init__.py").unlink()
    (tmp_path / "notes.txt").write_text("not python", encoding="utf-8")

    updated = update_index(index, tmp_path, ["pkg/mod.py", "pkg/__init__.py", "notes.txt"], languages=["python"])

    assert "pkg/__init__.py" not in updated["files"]
    assert updated["file_count"] == 1

    updated_functions = {item["name"] for item in updated["files"]["pkg/mod.py"]["functions"]}
    assert "another" in updated_functions


def test_classify_tier_detects_dependencies() -> None:
    assert classify_tier(path="node_modules/pkg/index.js", language="javascript") == "dependency"
    assert classify_tier(path="lib/openzeppelin/Ownable.sol", language="solidity") == "dependency"
    assert classify_tier(path="contracts/MyToken.sol", language="solidity") == "first_party"


def test_build_index_extracts_python_references(tmp_path: Path) -> None:
    _create_sample_repo(tmp_path)

    index = build_index(tmp_path, languages=['python'])
    mod_entry = index['files']['pkg/mod.py']
    reference_names = {item.get('name') for item in mod_entry.get('references', []) if isinstance(item, dict)}

    assert 'str' in reference_names


def test_build_index_parser_failure_emits_empty_references(tmp_path: Path, monkeypatch) -> None:
    _create_sample_repo(tmp_path)

    import ace_lite.parsers.treesitter_engine as treesitter_engine

    monkeypatch.setattr(treesitter_engine, 'get_parser', None)
    index = build_index(tmp_path, languages=['python'])

    entry = index['files']['pkg/mod.py']
    assert entry.get('parse_error') == 'tree-sitter parser unavailable'
    assert entry.get('references') == []


def test_build_index_skips_default_artifacts_dir(tmp_path: Path) -> None:
    _create_sample_repo(tmp_path)

    artifacts_dir = tmp_path / "artifacts" / "generated"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "ignored.py").write_text(
        "def leaked() -> int\n    return 1\n",
        encoding="utf-8",
    )

    index = build_index(tmp_path, languages=["python"])

    assert "artifacts/generated/ignored.py" not in index["files"]
    assert index["file_count"] == 2


def test_update_index_ignores_default_excluded_dirs(tmp_path: Path) -> None:
    _create_sample_repo(tmp_path)
    index = build_index(tmp_path, languages=["python"])

    artifacts_file = tmp_path / "artifacts" / "generated.py"
    artifacts_file.parent.mkdir(parents=True, exist_ok=True)
    artifacts_file.write_text("def generated() -> int\n    return 7\n", encoding="utf-8")

    updated = update_index(
        index,
        tmp_path,
        ["artifacts/generated.py"],
        languages=["python"],
    )

    assert "artifacts/generated.py" not in updated["files"]
    assert updated["file_count"] == 2


def test_build_index_respects_aceignore_basename_pattern(tmp_path: Path) -> None:
    _create_sample_repo(tmp_path)
    (tmp_path / ".aceignore").write_text("mod.py\n", encoding="utf-8")

    index = build_index(tmp_path, languages=["python"])

    assert "pkg/mod.py" not in index["files"]
    assert "pkg/__init__.py" in index["files"]
    assert index["file_count"] == 1


def test_build_index_respects_aceignore_directory_pattern(tmp_path: Path) -> None:
    _create_sample_repo(tmp_path)
    (tmp_path / ".aceignore").write_text("pkg/\n", encoding="utf-8")

    index = build_index(tmp_path, languages=["python"])

    assert "pkg/mod.py" not in index["files"]
    assert "pkg/__init__.py" not in index["files"]
    assert index["file_count"] == 0


def test_update_index_respects_aceignore(tmp_path: Path) -> None:
    _create_sample_repo(tmp_path)
    index = build_index(tmp_path, languages=["python"])
    (tmp_path / ".aceignore").write_text("mod.py\n", encoding="utf-8")

    updated = update_index(index, tmp_path, ["pkg/mod.py"], languages=["python"])

    assert "pkg/mod.py" not in updated["files"]
    assert updated["file_count"] == 1


def test_discover_source_files_returns_repo_relative_sorted_paths(tmp_path: Path) -> None:
    (tmp_path / "z_dir").mkdir(parents=True, exist_ok=True)
    (tmp_path / "a_dir").mkdir(parents=True, exist_ok=True)
    (tmp_path / "z_dir" / "b_file.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "a_dir" / "a_file.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "a_dir" / "z_file.py").write_text("x = 1\n", encoding="utf-8")

    root_path, enabled_languages, files = discover_source_files(
        tmp_path,
        languages=["python"],
    )

    assert root_path == tmp_path.resolve()
    assert enabled_languages == ("python",)
    assert [path.relative_to(root_path).as_posix() for path in files] == [
        "a_dir/a_file.py",
        "a_dir/z_file.py",
        "z_dir/b_file.py",
    ]


def test_build_index_ignores_aceignore_permission_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _create_sample_repo(tmp_path)
    (tmp_path / ".aceignore").write_text("pkg/\n", encoding="utf-8")
    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args, **kwargs) -> str:
        if self.name == ".aceignore":
            raise PermissionError("access denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    index = build_index(tmp_path, languages=["python"])

    assert "pkg/mod.py" in index["files"]
    assert "pkg/__init__.py" in index["files"]


def test_update_index_skips_changed_path_when_resolve_raises_oserror(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _create_sample_repo(tmp_path)
    index = build_index(tmp_path, languages=["python"])
    blocked = tmp_path / "pkg" / "blocked.py"
    blocked.write_text("def blocked() -> int:\n    return 1\n", encoding="utf-8")
    original_resolve = Path.resolve

    def fake_resolve(self: Path, *args, **kwargs) -> Path:
        if self.name == "blocked.py":
            raise PermissionError("path locked")
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fake_resolve)

    updated = update_index(index, tmp_path, ["pkg/blocked.py"], languages=["python"])

    assert "pkg/blocked.py" not in updated["files"]
    assert updated["file_count"] == index["file_count"]
