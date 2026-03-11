from __future__ import annotations

from pathlib import Path

from ace_lite.indexer import build_index, update_index


def _seed_multilang_repo(root: Path) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)

    (root / "src" / "app.py").write_text(
        "import os\nclass Service:\n    def run(self):\n        return 1\n",
        encoding="utf-8",
    )
    (root / "src" / "worker.ts").write_text(
        'import {x} from "./lib";\nexport class Worker { run(){ return 1 } }\n',
        encoding="utf-8",
    )
    (root / "src" / "util.js").write_text(
        'import m from "pkg";\nfunction helper(){ return m }\n',
        encoding="utf-8",
    )
    (root / "src" / "main.go").write_text(
        'package main\nimport "fmt"\nfunc Run() int { return 1 }\n',
        encoding="utf-8",
    )


def test_build_index_multilang_profile(tmp_path: Path) -> None:
    _seed_multilang_repo(tmp_path)

    index = build_index(tmp_path, languages=["python", "typescript", "javascript", "go"])

    assert index["file_count"] == 4
    assert set(index["languages_covered"]) == {"python", "typescript", "javascript", "go"}
    assert index["parser"]["engine"] == "tree-sitter"

    assert index["files"]["src/app.py"]["language"] == "python"
    assert index["files"]["src/worker.ts"]["language"] == "typescript"
    assert index["files"]["src/util.js"]["language"] == "javascript"
    assert index["files"]["src/main.go"]["language"] == "go"

    go_symbols = {item["name"] for item in index["files"]["src/main.go"]["symbols"]}
    assert "Run" in go_symbols


def test_update_index_multilang_incremental(tmp_path: Path) -> None:
    _seed_multilang_repo(tmp_path)
    index = build_index(tmp_path, languages=["python", "typescript", "javascript", "go"])

    (tmp_path / "src" / "worker.ts").unlink()
    (tmp_path / "src" / "new.go").write_text(
        'package main\nfunc Added() int { return 2 }\n',
        encoding="utf-8",
    )

    updated = update_index(
        index,
        tmp_path,
        changed_files=["src/worker.ts", "src/new.go"],
        languages=["python", "typescript", "javascript", "go"],
    )

    assert "src/worker.ts" not in updated["files"]
    assert "src/new.go" in updated["files"]
    assert updated["files"]["src/new.go"]["language"] == "go"
def test_build_index_multilang_references_go_and_python(tmp_path: Path) -> None:
    src = tmp_path / 'src'
    src.mkdir(parents=True, exist_ok=True)

    (src / 'app.py').write_text(
        'import os\n\ndef helper() -> str:\n    return os.getenv(\'APP_ENV\', \'dev\')\n\nclass Service:\n    def run(self) -> str:\n        return helper()\n',
        encoding='utf-8',
    )
    (src / 'main.go').write_text(
        'package main\nimport `fmt`\nfunc helper() int { return 1 }\nfunc Run() int {\n    _ = fmt.Sprintf(`%d`, helper())\n    return helper()\n}\n',
        encoding='utf-8',
    )

    index = build_index(tmp_path, languages=['python', 'go'])

    py_refs = {
        str(item.get('qualified_name') or item.get('name'))
        for item in index['files']['src/app.py'].get('references', [])
        if isinstance(item, dict)
    }
    go_refs = {
        str(item.get('qualified_name') or item.get('name'))
        for item in index['files']['src/main.go'].get('references', [])
        if isinstance(item, dict)
    }

    assert 'helper' in py_refs
    assert 'os.getenv' in py_refs
    assert 'helper' in go_refs
    assert 'fmt.Sprintf' in go_refs
