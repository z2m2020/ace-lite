from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ace_lite.subprocess_utils import run_capture_output
from ace_lite.validation.patch_artifact import validate_patch_artifact_contract_v1

_COPY_IGNORE_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "context-map",
    "artifacts",
}
_GIT_ENV = {"GIT_TERMINAL_PROMPT": "0"}


@dataclass(frozen=True, slots=True)
class PatchSandboxSession:
    repo_root: str
    sandbox_root: str
    patch_artifact: dict[str, Any]
    patch_path: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "repo_root": self.repo_root,
            "sandbox_root": self.sandbox_root,
            "patch_artifact": dict(self.patch_artifact),
            "patch_path": self.patch_path,
        }


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in _COPY_IGNORE_NAMES}


def bootstrap_patch_sandbox(
    *,
    repo_root: str | Path,
    patch_artifact: dict[str, Any],
    sandbox_parent: str | Path | None = None,
) -> PatchSandboxSession:
    validation = validate_patch_artifact_contract_v1(
        contract=patch_artifact,
        strict=True,
        fail_closed=True,
    )
    if not validation.get("ok", False):
        violations = validation.get("violations", [])
        violation = (
            str(violations[0])
            if isinstance(violations, list) and violations
            else "patch_artifact_invalid"
        )
        raise ValueError(f"patch_artifact validation failed: {violation}")

    source_root = Path(repo_root).resolve()
    if not source_root.is_dir():
        raise ValueError("repo_root must be an existing directory")

    sandbox_base = Path(
        tempfile.mkdtemp(
            prefix="ace-lite-sandbox-",
            dir=str(Path(sandbox_parent).resolve()) if sandbox_parent is not None else None,
        )
    )
    sandbox_root = sandbox_base / "workspace"
    shutil.copytree(
        source_root,
        sandbox_root,
        ignore=_copy_ignore,
    )

    patch_path = sandbox_base / "artifact.patch"
    patch_path.write_text(
        str(patch_artifact.get("patch_text") or ""),
        encoding="utf-8",
    )
    return PatchSandboxSession(
        repo_root=str(source_root),
        sandbox_root=str(sandbox_root),
        patch_artifact=dict(patch_artifact),
        patch_path=str(patch_path),
    )


def apply_patch_artifact_in_sandbox(
    *,
    session: PatchSandboxSession,
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    sandbox_root = Path(session.sandbox_root)
    patch_path = Path(session.patch_path)
    if not sandbox_root.is_dir():
        raise ValueError("sandbox_root does not exist")
    if not patch_path.is_file():
        raise ValueError("patch_path does not exist")

    patch_text = patch_path.read_text(encoding="utf-8")
    if not patch_text.strip():
        return {
            "ok": False,
            "reason": "empty_patch_text",
            "returncode": 1,
            "timed_out": False,
            "stdout": "",
            "stderr": "empty patch_text",
        }

    returncode, stdout, stderr, timed_out = run_capture_output(
        ["git", "apply", "--unsafe-paths", str(patch_path)],
        cwd=sandbox_root,
        timeout_seconds=max(0.1, float(timeout_seconds)),
        env_overrides=_GIT_ENV,
    )
    return {
        "ok": (not timed_out) and int(returncode) == 0,
        "reason": "ok" if (not timed_out and int(returncode) == 0) else (
            "timeout" if timed_out else "apply_failed"
        ),
        "returncode": int(returncode),
        "timed_out": bool(timed_out),
        "stdout": str(stdout or ""),
        "stderr": str(stderr or ""),
    }


def restore_patch_sandbox(session: PatchSandboxSession) -> dict[str, Any]:
    repo_root = Path(session.repo_root)
    sandbox_root = Path(session.sandbox_root)
    anchors = session.patch_artifact.get("rollback_anchors", [])
    if not isinstance(anchors, list):
        anchors = []

    restored = 0
    deleted = 0
    skipped = 0
    for item in anchors:
        if not isinstance(item, dict):
            skipped += 1
            continue
        path = str(item.get("path") or "").strip().replace("\\", "/")
        if not path:
            skipped += 1
            continue
        source_path = repo_root / Path(*Path(path).parts)
        sandbox_path = sandbox_root / Path(*Path(path).parts)
        strategy = str(item.get("strategy") or "").strip() or "git_restore"
        sandbox_path.parent.mkdir(parents=True, exist_ok=True)
        if strategy == "delete_added_file":
            if sandbox_path.exists():
                sandbox_path.unlink()
                deleted += 1
            else:
                skipped += 1
            continue
        if source_path.exists():
            shutil.copy2(source_path, sandbox_path)
            restored += 1
        elif sandbox_path.exists():
            sandbox_path.unlink()
            deleted += 1
        else:
            skipped += 1

    return {
        "ok": True,
        "restored_count": restored,
        "deleted_count": deleted,
        "skipped_count": skipped,
    }


def cleanup_patch_sandbox(session: PatchSandboxSession) -> dict[str, Any]:
    sandbox_base = Path(session.patch_path).parent
    if sandbox_base.exists():
        shutil.rmtree(sandbox_base, ignore_errors=True)
    return {
        "ok": not sandbox_base.exists(),
        "sandbox_root": str(session.sandbox_root),
        "sandbox_base": str(sandbox_base),
    }


__all__ = [
    "PatchSandboxSession",
    "apply_patch_artifact_in_sandbox",
    "bootstrap_patch_sandbox",
    "cleanup_patch_sandbox",
    "restore_patch_sandbox",
]
