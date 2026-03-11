"""Index cache helpers for build / refresh workflows.

The orchestration pipeline stores a distilled repository index on disk and
refreshes it incrementally when possible.
"""

from __future__ import annotations

import json
import os
from collections import deque
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from ace_lite.indexer import DEFAULT_EXCLUDE_DIRS, build_index, update_index
from ace_lite.parsers.languages import normalize_languages, supported_extensions
from ace_lite.subprocess_utils import run_capture_output

_INDEX_MEMORY_CACHE: dict[
    tuple[str, str, tuple[str, ...]], tuple[int, dict[str, Any]]
] = {}

_GIT_TIMEOUT_ENV = "ACE_LITE_GIT_TIMEOUT_SECONDS"
_DEFAULT_GIT_TIMEOUT_SECONDS = 2.0
_REVERSE_DEP_DEPTH_ENV = "ACE_LITE_INDEX_REVERSE_DEP_DEPTH"
_DEFAULT_REVERSE_DEP_DEPTH = 1
_REVERSE_DEP_MAX_EXTRA_ENV = "ACE_LITE_INDEX_REVERSE_DEP_MAX_EXTRA"
_DEFAULT_REVERSE_DEP_MAX_EXTRA = 256


def _is_hex_sha(value: str) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 40 and all(ch in "0123456789abcdef" for ch in text)


def _resolve_git_dir(*, root: Path) -> Path | None:
    git_entry = root / ".git"
    if git_entry.is_dir():
        return git_entry
    if not git_entry.is_file():
        return None
    try:
        payload = git_entry.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not payload.lower().startswith("gitdir:"):
        return None
    candidate = Path(payload.split(":", 1)[1].strip())
    if not candidate.is_absolute():
        candidate = (root / candidate).resolve()
    return candidate if candidate.exists() else None


def _read_git_ref_sha(*, git_dir: Path, ref: str) -> str | None:
    ref_name = str(ref or "").strip()
    if not ref_name:
        return None

    ref_path = git_dir / ref_name
    if ref_path.exists() and ref_path.is_file():
        try:
            sha = ref_path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            sha = ""
        if _is_hex_sha(sha):
            return sha.lower()

    packed_refs = git_dir / "packed-refs"
    if not packed_refs.exists() or not packed_refs.is_file():
        return None
    try:
        lines = packed_refs.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    suffix = f" {ref_name}"
    for line in lines:
        text = str(line or "").strip()
        if not text or text.startswith("#") or text.startswith("^"):
            continue
        if not text.endswith(suffix):
            continue
        sha = text.split(" ", 1)[0].strip()
        if _is_hex_sha(sha):
            return sha.lower()
    return None


def _read_git_head_sha_fast(*, root: Path) -> str | None:
    git_dir = _resolve_git_dir(root=root)
    if git_dir is None:
        return None

    head_path = git_dir / "HEAD"
    if not head_path.exists() or not head_path.is_file():
        return None
    try:
        head_raw = head_path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not head_raw:
        return None

    if _is_hex_sha(head_raw):
        return head_raw.lower()

    if head_raw.lower().startswith("ref:"):
        ref_name = head_raw.split(":", 1)[1].strip()
        return _read_git_ref_sha(git_dir=git_dir, ref=ref_name)
    return None


def _git_timeout_seconds() -> float:
    raw = str(os.getenv(_GIT_TIMEOUT_ENV, "")).strip()
    if not raw:
        return _DEFAULT_GIT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_GIT_TIMEOUT_SECONDS
    return max(0.1, value)


def _read_positive_int_env(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return max(0, int(default))
    try:
        value = int(raw)
    except ValueError:
        return max(0, int(default))
    return max(0, value)


def _reverse_dep_depth() -> int:
    return _read_positive_int_env(
        _REVERSE_DEP_DEPTH_ENV, _DEFAULT_REVERSE_DEP_DEPTH
    )


def _reverse_dep_max_extra() -> int:
    return _read_positive_int_env(
        _REVERSE_DEP_MAX_EXTRA_ENV, _DEFAULT_REVERSE_DEP_MAX_EXTRA
    )


def _get_git_head_sha(*, root_dir: str | Path) -> str | None:
    root = Path(root_dir)
    if not (root / ".git").exists():
        return None

    fast = _read_git_head_sha_fast(root=root)
    if _is_hex_sha(str(fast or "")):
        return str(fast).lower()

    returncode, stdout, _stderr, timed_out = run_capture_output(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        timeout_seconds=_git_timeout_seconds(),
        env_overrides={"GIT_TERMINAL_PROMPT": "0"},
    )
    if timed_out:
        return None

    if returncode != 0:
        return None

    sha = str(stdout or "").strip().lower()
    if not _is_hex_sha(sha):
        return None
    return sha


def load_index_cache(
    *,
    cache_path: str | Path,
    root_dir: str | Path,
    languages: Iterable[str] | None,
    current_sha: str | None = None,
) -> dict[str, Any] | None:
    path = Path(cache_path)
    if not path.exists() or not path.is_file():
        return None

    resolved_root = str(Path(root_dir).resolve())
    expected_langs = normalize_languages(
        tuple(languages) if languages is not None else None
    )
    resolved_current_sha = (
        str(current_sha).strip().lower()
        if _is_hex_sha(str(current_sha or ""))
        else _get_git_head_sha(root_dir=root_dir)
    )
    cache_key = (str(path.resolve()), resolved_root, tuple(expected_langs))

    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        return None

    cached = _INDEX_MEMORY_CACHE.get(cache_key)
    if cached is not None and cached[0] == mtime_ns:
        if resolved_current_sha is not None:
            cached_sha = cached[1].get("git_head_sha")
            if (
                isinstance(cached_sha, str)
                and cached_sha
                and cached_sha != resolved_current_sha
            ):
                _INDEX_MEMORY_CACHE.pop(cache_key, None)
                return None
        return cached[1]

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    payload_root = str(payload.get("root_dir", ""))
    payload_langs = tuple(str(item) for item in payload.get("configured_languages", []))
    payload_sha = payload.get("git_head_sha")

    if (
        Path(payload_root).resolve().as_posix()
        != Path(resolved_root).resolve().as_posix()
    ):
        return None
    if tuple(payload_langs) != tuple(expected_langs):
        return None
    if (
        resolved_current_sha is not None
        and isinstance(payload_sha, str)
        and payload_sha
        and payload_sha != resolved_current_sha
    ):
        return None

    _INDEX_MEMORY_CACHE[cache_key] = (mtime_ns, payload)
    return payload


def save_index_cache(*, payload: dict[str, Any], cache_path: str | Path) -> None:
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def detect_changed_files_from_git(*, root_dir: str | Path) -> list[str]:
    root = Path(root_dir)
    if not (root / ".git").exists():
        return []

    returncode, stdout, _stderr, timed_out = run_capture_output(
        ["git", "status", "--porcelain", "-z"],
        cwd=root,
        timeout_seconds=_git_timeout_seconds(),
        env_overrides={"GIT_TERMINAL_PROMPT": "0"},
    )
    if timed_out:
        return []

    if returncode != 0:
        return []

    changed = _parse_git_status_output(str(stdout or ""))

    normalized: list[str] = []
    seen: set[str] = set()
    for item in changed:
        path = _normalize_changed_path(item)
        if not path or path in seen:
            continue
        seen.add(path)
        normalized.append(path)

    return normalized


def _parse_git_status_output(stdout: str) -> list[str]:
    text = str(stdout or "")
    if "\0" in text:
        return _parse_git_status_porcelain_z(text)
    return _parse_git_status_porcelain_lines(text)


def _parse_git_status_porcelain_lines(stdout: str) -> list[str]:
    changed: list[str] = []
    for line in str(stdout or "").splitlines():
        if not line:
            continue
        path = line[3:].strip()
        if not path:
            continue
        if "->" in path:
            old_path, new_path = path.split("->", 1)
            changed.extend([old_path.strip(), new_path.strip()])
            continue
        changed.append(path)
    return changed


def _parse_git_status_porcelain_z(stdout: str) -> list[str]:
    changed: list[str] = []
    rows = str(stdout or "").split("\0")
    cursor = 0
    total = len(rows)

    while cursor < total:
        row = rows[cursor]
        cursor += 1
        if not row:
            continue

        status = str(row[:2])
        path = str(row[3:] if len(row) >= 3 else "").strip()
        if path:
            changed.append(path)

        if ("R" in status or "C" in status) and cursor < total:
            renamed = str(rows[cursor] or "").strip()
            cursor += 1
            if renamed:
                changed.append(renamed)

    return changed


def _normalize_changed_path(value: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def _filter_index_changed_files(
    *, changed_files: Iterable[str], languages: Iterable[str] | None
) -> list[str]:
    enabled_languages = normalize_languages(
        tuple(languages) if languages is not None else None
    )
    suffixes = supported_extensions(enabled_languages)
    filtered: list[str] = []
    seen: set[str] = set()

    for item in changed_files:
        path = _normalize_changed_path(str(item or ""))
        if not path or path in seen:
            continue
        seen.add(path)

        parts = PurePosixPath(path).parts
        if any(part in DEFAULT_EXCLUDE_DIRS for part in parts[:-1]):
            continue

        if PurePosixPath(path).suffix.lower() not in suffixes:
            continue
        filtered.append(path)

    return filtered


def _file_fingerprint(*, path: Path) -> tuple[int, int] | None:
    try:
        stat_result = path.stat()
    except OSError:
        return None

    mtime_ns = getattr(stat_result, "st_mtime_ns", None)
    if not isinstance(mtime_ns, int):
        mtime_seconds = float(getattr(stat_result, "st_mtime", 0.0) or 0.0)
        mtime_ns = int(mtime_seconds * 1_000_000_000)
    size_bytes = int(getattr(stat_result, "st_size", 0) or 0)
    return max(0, int(mtime_ns)), max(0, int(size_bytes))


def _filter_effective_index_changes(
    *,
    root_dir: Path,
    changed_files: Iterable[str],
    index_files: dict[str, Any],
) -> list[str]:
    effective: list[str] = []
    for item in changed_files:
        path = _normalize_changed_path(str(item or ""))
        if not path:
            continue

        relative = PurePosixPath(path)
        if relative.is_absolute() or any(part == ".." for part in relative.parts):
            effective.append(path)
            continue

        cached_entry = index_files.get(path)
        absolute_path = root_dir / Path(*relative.parts)
        fingerprint = _file_fingerprint(path=absolute_path)
        if fingerprint is None:
            if cached_entry is not None:
                effective.append(path)
            continue

        if not isinstance(cached_entry, dict):
            effective.append(path)
            continue

        try:
            cached_mtime_ns = int(cached_entry.get("mtime_ns", -1) or -1)
            cached_size_bytes = int(cached_entry.get("size_bytes", -1) or -1)
        except (TypeError, ValueError):
            cached_mtime_ns = -1
            cached_size_bytes = -1

        if cached_mtime_ns == fingerprint[0] and cached_size_bytes == fingerprint[1]:
            continue
        effective.append(path)
    return effective


def _resolve_imported_paths(
    *,
    source_path: str,
    module_name: str,
    module_to_paths: dict[str, set[str]],
    path_style_to_paths: dict[str, set[str]],
) -> set[str]:
    raw = str(module_name or "").strip()
    normalized = raw.strip().strip('"`').replace("\\", "/").lstrip(".")
    if not normalized:
        return set()

    hits: set[str] = set()

    # Solidity import paths frequently look like:
    # - "./Foo.sol"
    # - "@openzeppelin/contracts/token/ERC20/IERC20.sol"
    # - "forge-std/Test.sol" (Foundry remappings)
    def _remove_source_suffix(path: str) -> str:
        text = str(path or "").strip().replace("\\", "/")
        for suffix in (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".sol"):
            if text.endswith(suffix):
                return text[: -len(suffix)]
        return text

    def _module_path_keys(seed_path: str, module: str) -> list[str]:
        value = str(module or "").strip().replace("\\", "/")
        if not value:
            return []
        keys: list[str] = []
        raw_key = value.lstrip("./")
        if raw_key:
            keys.append(raw_key)
            keys.append(_remove_source_suffix(raw_key))
        if value.startswith("."):
            joined = PurePosixPath(PurePosixPath(seed_path).parent / value).as_posix()
            cleaned = joined.lstrip("./")
            if cleaned:
                keys.append(cleaned)
                keys.append(_remove_source_suffix(cleaned))
        unique: list[str] = []
        for key in keys:
            candidate = str(key or "").strip().lstrip("./")
            if candidate and candidate not in unique:
                unique.append(candidate)
        return unique

    for key in _module_path_keys(source_path, normalized):
        hits.update(path_style_to_paths.get(key, set()))

    queue: deque[str] = deque([normalized])
    seen: set[str] = set()
    while queue:
        candidate = queue.popleft()
        if candidate in seen:
            continue
        seen.add(candidate)
        hits.update(module_to_paths.get(candidate, set()))
        if "." in candidate:
            queue.append(candidate.rsplit(".", 1)[0])
    return hits


def expand_changed_files_with_reverse_dependencies(
    *,
    changed_files: list[str],
    index_files: dict[str, dict[str, Any]],
    max_depth: int,
    max_extra: int,
) -> tuple[list[str], int]:
    ordered_seeds: list[str] = []
    seen_seed: set[str] = set()
    for item in changed_files:
        path = _normalize_changed_path(item)
        if not path or path in seen_seed:
            continue
        seen_seed.add(path)
        ordered_seeds.append(path)

    if not ordered_seeds or max_depth <= 0 or max_extra <= 0:
        return ordered_seeds, 0

    module_to_paths: dict[str, set[str]] = {}
    path_style_to_paths: dict[str, set[str]] = {}
    normalized_entries: dict[str, dict[str, Any]] = {}
    for raw_path, entry in index_files.items():
        if not isinstance(raw_path, str) or not isinstance(entry, dict):
            continue
        path = _normalize_changed_path(raw_path)
        if not path:
            continue
        normalized_entries[path] = entry
        module = str(entry.get("module") or "").strip().lstrip(".")
        if module:
            module_to_paths.setdefault(module, set()).add(path)

        normalized_path = str(path).strip().replace("\\", "/")

        def _remove_source_suffix(path_value: str) -> str:
            text = str(path_value or "").strip().replace("\\", "/")
            for suffix in (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".sol"):
                if text.endswith(suffix):
                    return text[: -len(suffix)]
            return text

        def add_path_keys(candidate_path: str) -> None:
            without = _remove_source_suffix(candidate_path)
            stem = without.rsplit("/", 1)[-1]
            for key in (without, stem, f"{without}/index"):
                normalized_key = str(key or "").strip().lstrip("./")
                if not normalized_key:
                    continue
                path_style_to_paths.setdefault(normalized_key, set()).add(normalized_path)

        add_path_keys(normalized_path)
        if normalized_path.startswith("node_modules/"):
            add_path_keys(normalized_path[len("node_modules/") :])
        if normalized_path.startswith("lib/"):
            without = _remove_source_suffix(normalized_path)
            parts = [part for part in without.split("/") if part]
            if len(parts) >= 3:
                pkg = parts[1]
                add_path_keys("/".join(parts[1:]))
                if len(parts) >= 4 and parts[2] in {"src", "contracts"}:
                    add_path_keys("/".join([pkg, *parts[3:]]))

    reverse_imports: dict[str, set[str]] = {}
    for source_path, entry in normalized_entries.items():
        imports = entry.get("imports", [])
        if not isinstance(imports, list):
            continue
        for item in imports:
            if not isinstance(item, dict):
                continue
            module_name = str(item.get("module") or "").strip().lstrip(".")
            if not module_name:
                continue
            for target_path in _resolve_imported_paths(
                source_path=source_path,
                module_name=module_name,
                module_to_paths=module_to_paths,
                path_style_to_paths=path_style_to_paths,
            ):
                if target_path == source_path:
                    continue
                reverse_imports.setdefault(target_path, set()).add(source_path)

    discovered: list[str] = []
    discovered_set: set[str] = set()
    frontier = {path for path in ordered_seeds if path in reverse_imports}
    for _depth in range(max_depth):
        if not frontier:
            break
        next_frontier: set[str] = set()
        for target in sorted(frontier):
            for dependent in sorted(reverse_imports.get(target, set())):
                if dependent in seen_seed or dependent in discovered_set:
                    continue
                discovered.append(dependent)
                discovered_set.add(dependent)
                next_frontier.add(dependent)
                if len(discovered) >= max_extra:
                    break
            if len(discovered) >= max_extra:
                break
        frontier = next_frontier
        if len(discovered) >= max_extra:
            break

    return [*ordered_seeds, *discovered], len(discovered)


def build_or_refresh_index(
    *,
    root_dir: str | Path,
    cache_path: str | Path,
    languages: Iterable[str] | None,
    incremental: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_sha = _get_git_head_sha(root_dir=root_dir)
    cache = load_index_cache(
        cache_path=cache_path,
        root_dir=root_dir,
        languages=languages,
        current_sha=current_sha,
    )

    if cache is None:
        payload = build_index(root_dir, languages=languages)
        if current_sha is not None:
            payload["git_head_sha"] = current_sha
        save_index_cache(payload=payload, cache_path=cache_path)
        return payload, {"cache_hit": False, "mode": "full_build", "changed_files": 0}

    if not incremental:
        return cache, {"cache_hit": True, "mode": "cache_only", "changed_files": 0}

    changed_files_detected = detect_changed_files_from_git(root_dir=root_dir)
    if not changed_files_detected:
        return cache, {"cache_hit": True, "mode": "cache_only", "changed_files": 0}

    if any(
        _normalize_changed_path(str(item or "")).lower() == ".aceignore"
        for item in changed_files_detected
    ):
        payload = build_index(root_dir, languages=languages)
        if current_sha is not None:
            payload["git_head_sha"] = current_sha
        save_index_cache(payload=payload, cache_path=cache_path)
        return payload, {
            "cache_hit": True,
            "mode": "full_build",
            "changed_files": 0,
            "changed_files_detected": len(changed_files_detected),
            "reason": "aceignore_changed",
        }

    changed_files_index = _filter_index_changed_files(
        changed_files=changed_files_detected, languages=languages
    )
    if not changed_files_index:
        return cache, {
            "cache_hit": True,
            "mode": "cache_only",
            "changed_files": 0,
            "changed_files_detected": len(changed_files_detected),
            "reason": "non_indexable_changes",
        }

    index_files = cache.get("files", {}) if isinstance(cache.get("files"), dict) else {}
    effective_changed_files = _filter_effective_index_changes(
        root_dir=Path(root_dir).resolve(),
        changed_files=changed_files_index,
        index_files=index_files,
    )
    if not effective_changed_files:
        return cache, {
            "cache_hit": True,
            "mode": "cache_only",
            "changed_files": 0,
            "changed_files_detected": len(changed_files_detected),
            "reason": "worktree_dirty_no_effective_changes",
        }
    expanded_changed_files, reverse_added = expand_changed_files_with_reverse_dependencies(
        changed_files=effective_changed_files,
        index_files=index_files,
        max_depth=_reverse_dep_depth(),
        max_extra=_reverse_dep_max_extra(),
    )

    refreshed = update_index(
        cache,
        root_dir,
        expanded_changed_files,
        languages=languages,
    )
    if current_sha is not None:
        refreshed["git_head_sha"] = current_sha
    save_index_cache(payload=refreshed, cache_path=cache_path)
    info: dict[str, Any] = {
        "cache_hit": True,
        "mode": "incremental_update",
        "changed_files": len(expanded_changed_files),
    }
    if reverse_added > 0:
        info["changed_files_detected"] = len(changed_files_detected)
        info["reverse_dependencies_added"] = int(reverse_added)
    return refreshed, info


__all__ = [
    "build_or_refresh_index",
    "detect_changed_files_from_git",
    "expand_changed_files_with_reverse_dependencies",
    "load_index_cache",
    "save_index_cache",
]
