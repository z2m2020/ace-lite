from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LAYER1_EXECUTION_MODULES = (
    REPO_ROOT / "src" / "ace_lite" / "orchestrator.py",
    REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "memory.py",
    REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "index.py",
    REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "repomap.py",
    REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "augment.py",
    REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "skills.py",
    REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "source_plan.py",
    REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "validation.py",
)
FORBIDDEN_MODULE_IMPORTS = {
    "ace_lite.context_report",
    "ace_lite.retrieval_graph_view",
}
FORBIDDEN_IMPORTED_SYMBOLS = {
    "build_skill_catalog",
}
FORBIDDEN_TEXT_MARKERS = (
    ".context/",
    ".context\\",
    "artifacts/benchmark/",
    "artifacts\\benchmark\\",
)


def _parse_module(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def test_layer1_execution_modules_do_not_import_report_only_modules() -> None:
    violations: list[str] = []
    for path in LAYER1_EXECUTION_MODULES:
        tree = _parse_module(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_MODULE_IMPORTS:
                        violations.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                if module in FORBIDDEN_MODULE_IMPORTS:
                    violations.append(f"{path.name}: from {module} import ...")
                for alias in node.names:
                    if alias.name in FORBIDDEN_IMPORTED_SYMBOLS:
                        violations.append(
                            f"{path.name}: forbidden symbol {alias.name} from {module or '(relative import)'}"
                        )
        text = path.read_text(encoding="utf-8-sig")
        for marker in FORBIDDEN_TEXT_MARKERS:
            if marker in text:
                violations.append(f"{path.name}: forbidden Layer 3 marker {marker}")

    assert violations == []
