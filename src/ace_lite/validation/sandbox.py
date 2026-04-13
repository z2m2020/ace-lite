from __future__ import annotations

import re
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
_HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


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


@dataclass(frozen=True, slots=True)
class _UnifiedDiffHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class _UnifiedDiffFile:
    old_path: str
    new_path: str
    hunks: tuple[_UnifiedDiffHunk, ...]


def _strip_diff_path(value: str) -> str:
    token = str(value or "").strip().split("\t", 1)[0].strip()
    if token == "/dev/null":
        return token
    if token.startswith("a/") or token.startswith("b/"):
        return token[2:]
    return token


def _parse_unified_diff(patch_text: str) -> tuple[_UnifiedDiffFile, ...]:
    lines = str(patch_text or "").splitlines()
    files: list[_UnifiedDiffFile] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("diff --git "):
            index += 1
            continue
        if not line.startswith("--- "):
            index += 1
            continue
        old_path = _strip_diff_path(line[4:])
        index += 1
        if index >= len(lines) or not lines[index].startswith("+++ "):
            raise ValueError("unified diff missing +++ header")
        new_path = _strip_diff_path(lines[index][4:])
        index += 1

        hunks: list[_UnifiedDiffHunk] = []
        while index < len(lines):
            current = lines[index]
            if current.startswith("diff --git ") or current.startswith("--- "):
                break
            if not current.startswith("@@ "):
                index += 1
                continue
            match = _HUNK_HEADER_RE.match(current)
            if match is None:
                raise ValueError(f"invalid hunk header: {current}")
            old_start = int(match.group("old_start"))
            old_count = int(match.group("old_count") or "1")
            new_start = int(match.group("new_start"))
            new_count = int(match.group("new_count") or "1")
            index += 1
            hunk_lines: list[tuple[str, str]] = []
            while index < len(lines):
                current = lines[index]
                if current.startswith("diff --git ") or current.startswith("--- ") or current.startswith("@@ "):
                    break
                if current.startswith("\\"):
                    index += 1
                    continue
                if not current:
                    raise ValueError("invalid unified diff line")
                marker = current[0]
                if marker not in {" ", "+", "-"}:
                    raise ValueError(f"unsupported unified diff marker: {marker}")
                hunk_lines.append((marker, current[1:]))
                index += 1
            hunks.append(
                _UnifiedDiffHunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    lines=tuple(hunk_lines),
                )
            )
        files.append(
            _UnifiedDiffFile(
                old_path=old_path,
                new_path=new_path,
                hunks=tuple(hunks),
            )
        )
    if not files:
        raise ValueError("no unified diff file entries found")
    return tuple(files)


def _apply_unified_hunks(*, current_lines: list[str], hunks: tuple[_UnifiedDiffHunk, ...]) -> list[str]:
    result: list[str] = []
    cursor = 0
    for hunk in hunks:
        target_index = max(0, int(hunk.old_start) - 1)
        if target_index < cursor or target_index > len(current_lines):
            raise ValueError("hunk target out of bounds")
        result.extend(current_lines[cursor:target_index])
        position = target_index
        for marker, text in hunk.lines:
            if marker == " ":
                if position >= len(current_lines) or current_lines[position] != text:
                    raise ValueError("context line mismatch")
                result.append(current_lines[position])
                position += 1
                continue
            if marker == "-":
                if position >= len(current_lines) or current_lines[position] != text:
                    raise ValueError("delete line mismatch")
                position += 1
                continue
            result.append(text)
        cursor = position
    result.extend(current_lines[cursor:])
    return result


def _apply_patch_artifact_python_fallback(*, session: PatchSandboxSession) -> dict[str, Any]:
    patch_text = Path(session.patch_path).read_text(encoding="utf-8")
    parsed_files = _parse_unified_diff(patch_text)
    sandbox_root = Path(session.sandbox_root)
    operations_raw = session.patch_artifact.get("operations")
    operations = operations_raw if isinstance(operations_raw, list) else []
    operation_by_path = {
        str(item.get("path") or "").strip().replace("\\", "/"): str(item.get("op") or "").strip().lower()
        for item in operations
        if isinstance(item, dict)
    }

    for file_patch in parsed_files:
        rel_path = file_patch.new_path if file_patch.new_path != "/dev/null" else file_patch.old_path
        if not rel_path or rel_path == "/dev/null":
            raise ValueError("patch file path missing")
        target_path = sandbox_root / Path(*Path(rel_path).parts)
        target_exists = target_path.exists()
        current_text = target_path.read_text(encoding="utf-8") if target_exists else ""
        current_lines = current_text.splitlines()
        updated_lines = _apply_unified_hunks(current_lines=current_lines, hunks=file_patch.hunks)
        operation = operation_by_path.get(rel_path, "")
        if file_patch.new_path == "/dev/null" or operation == "delete":
            if target_path.exists():
                target_path.unlink()
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        rendered = "\n".join(updated_lines)
        if updated_lines:
            rendered += "\n"
        target_path.write_text(rendered, encoding="utf-8")

    return {
        "ok": True,
        "reason": "ok",
        "returncode": 0,
        "timed_out": False,
        "stdout": "",
        "stderr": "",
        "method": "python_fallback",
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
    if (timed_out is False) and int(returncode) != 0:
        try:
            fallback_result = _apply_patch_artifact_python_fallback(session=session)
        except Exception as exc:
            fallback_result = None
            stderr = f"{stderr or ''!s}\npython_fallback: {exc}".strip()
        if isinstance(fallback_result, dict) and fallback_result.get("ok", False):
            return fallback_result
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
