from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ace_lite.version import get_version_info

_FULL_PYTEST_PREFIXES = (
    "src/ace_lite/",
    "tests/integration/",
    "tests/e2e/",
    "scripts/",
)
_FULL_PYTEST_FILES = {
    "pyproject.toml",
    ".github/workflows/ci.yml",
}
_DOC_PREFIXES = ("docs/",)


@dataclass(frozen=True)
class ValidationPlan:
    changed_files: tuple[str, ...]
    commands: tuple[tuple[str, ...], ...]
    requires_version_sync: bool
    reason: str


def _normalize_paths(lines: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw in lines:
        value = str(raw or "").strip().replace("\\", "/")
        if value:
            normalized.append(value)
    return tuple(dict.fromkeys(normalized))


def _run_capture(*, root: Path, command: Sequence[str]) -> tuple[int, str]:
    completed = subprocess.run(
        list(command),
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = str(completed.stdout or completed.stderr or "").strip()
    return int(completed.returncode), output


def _list_changed_files(*, root: Path, staged: bool) -> tuple[str, ...]:
    diff_cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR"]
    if staged:
        diff_cmd.insert(2, "--cached")
    returncode, output = _run_capture(root=root, command=diff_cmd)
    if returncode != 0:
        raise RuntimeError(output or "git diff failed")
    files = _normalize_paths(output.splitlines())
    if staged:
        return files

    untracked_code, untracked_output = _run_capture(
        root=root,
        command=["git", "ls-files", "--others", "--exclude-standard"],
    )
    if untracked_code != 0:
        raise RuntimeError(untracked_output or "git ls-files failed")
    return _normalize_paths([*files, *untracked_output.splitlines()])


def _build_validation_plan(*, changed_files: Sequence[str]) -> ValidationPlan:
    normalized = _normalize_paths(changed_files)
    if not normalized:
        return ValidationPlan(
            changed_files=(),
            commands=(),
            requires_version_sync=False,
            reason="no_changes",
        )

    pyproject_changed = "pyproject.toml" in normalized
    if any(path in _FULL_PYTEST_FILES for path in normalized) or any(
        path.startswith(prefix) for prefix in _FULL_PYTEST_PREFIXES for path in normalized
    ):
        return ValidationPlan(
            changed_files=normalized,
            commands=(("python", "-m", "pytest", "-q"),),
            requires_version_sync=pyproject_changed,
            reason="full_pytest_required",
        )

    unit_tests = tuple(
        path
        for path in normalized
        if path.startswith("tests/unit/") and path.endswith(".py")
    )
    if unit_tests:
        return ValidationPlan(
            changed_files=normalized,
            commands=(("python", "-m", "pytest", "-q", *unit_tests),),
            requires_version_sync=pyproject_changed,
            reason="unit_tests_only",
        )

    if any(path.startswith(prefix) for prefix in _DOC_PREFIXES for path in normalized):
        return ValidationPlan(
            changed_files=normalized,
            commands=(("python", "scripts/validate_docs_cli_snippets.py"),),
            requires_version_sync=pyproject_changed,
            reason="docs_validation",
        )

    return ValidationPlan(
        changed_files=normalized,
        commands=(),
        requires_version_sync=pyproject_changed,
        reason="no_validation_required",
    )


def _ensure_version_sync(*, root: Path) -> None:
    _ = root
    info = get_version_info()
    if not bool(info.get("drifted", False)):
        return
    version = str(info.get("version") or "").strip()
    installed_version = str(info.get("installed_version") or "").strip()
    pyproject_version = str(info.get("pyproject_version") or "").strip()
    raise SystemExit(
        "Version drift detected before commit: "
        f"pyproject={pyproject_version or version}, installed={installed_version or 'missing'}. "
        "Run `python -m pip install -e .[dev]` and retry."
    )


def _run_plan(*, root: Path, plan: ValidationPlan) -> int:
    if plan.requires_version_sync:
        _ensure_version_sync(root=root)
    if not plan.commands:
        print(f"[precommit] no-op ({plan.reason})")
        return 0

    for command in plan.commands:
        print(f"[precommit] running: {' '.join(command)}")
        completed = subprocess.run(
            list(command),
            cwd=str(root),
            check=False,
        )
        if int(completed.returncode) != 0:
            return int(completed.returncode)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run lightweight commit-time validation based on changed files."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root. Defaults to current directory.",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Validate staged changes only (recommended for pre-commit hooks).",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="Explicit changed file list. When provided, git is not queried.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = Path(args.root).resolve()
    changed_files = (
        _normalize_paths(args.files)
        if args.files is not None
        else _list_changed_files(root=root, staged=bool(args.staged))
    )
    plan = _build_validation_plan(changed_files=changed_files)
    return _run_plan(root=root, plan=plan)


if __name__ == "__main__":
    raise SystemExit(main())
