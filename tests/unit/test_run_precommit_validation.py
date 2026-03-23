from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_module():  # type: ignore[no-untyped-def]
    script_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "run_precommit_validation.py"
    )
    spec = importlib.util.spec_from_file_location(
        "run_precommit_validation",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load run_precommit_validation.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_build_validation_plan = _load_module()._build_validation_plan


def test_precommit_validation_uses_full_pytest_for_runtime_code_changes() -> None:
    plan = _build_validation_plan(
        changed_files=[
            "src/ace_lite/runtime_fingerprint.py",
            "tests/unit/test_runtime_fingerprint.py",
        ]
    )

    assert plan.reason == "full_pytest_required"
    assert plan.commands == (("python", "-m", "pytest", "-q"),)


def test_precommit_validation_uses_changed_unit_tests_when_only_unit_tests_change() -> None:
    plan = _build_validation_plan(
        changed_files=[
            "tests/unit/test_runtime_fingerprint.py",
            "tests/unit/test_vcs_worktree.py",
        ]
    )

    assert plan.reason == "unit_tests_only"
    assert plan.commands == (
        (
            "python",
            "-m",
            "pytest",
            "-q",
            "tests/unit/test_runtime_fingerprint.py",
            "tests/unit/test_vcs_worktree.py",
        ),
    )


def test_precommit_validation_checks_version_sync_when_pyproject_changes() -> None:
    plan = _build_validation_plan(changed_files=["pyproject.toml"])

    assert plan.reason == "full_pytest_required"
    assert plan.requires_version_sync is True


def test_precommit_validation_uses_docs_validator_for_docs_only_changes() -> None:
    plan = _build_validation_plan(
        changed_files=["docs/design/LONG_TERM_MEMORY_FEEDBACK_REQUIREMENTS.md"]
    )

    assert plan.reason == "docs_validation"
    assert plan.commands == (("python", "scripts/validate_docs_cli_snippets.py"),)
