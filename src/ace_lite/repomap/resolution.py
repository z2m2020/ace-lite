from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath
from typing import Any

SOURCE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".sol")


def _build_resolution_maps(
    files: dict[str, dict[str, Any]],
) -> tuple[dict[str, str], dict[str, set[str]], dict[str, set[str]]]:
    module_to_path: dict[str, str] = {}
    path_style_to_paths: dict[str, set[str]] = defaultdict(set)
    stem_to_paths: dict[str, set[str]] = defaultdict(set)

    for path, entry in sorted(files.items()):
        if not isinstance(path, str):
            continue
        normalized_path = str(path).strip().replace("\\", "/")
        if not normalized_path:
            continue
        module = str(entry.get("module", "")).strip() if isinstance(entry, dict) else ""
        if module:
            module_to_path[module] = normalized_path

        def add_key(key: str) -> None:
            normalized = str(key or "").strip().lstrip("./")
            if normalized:
                path_style_to_paths[normalized].add(normalized_path)

        def add_path_keys(candidate_path: str) -> None:
            without = _remove_source_suffix(candidate_path)
            stem = without.rsplit("/", 1)[-1]
            add_key(without)
            add_key(stem)
            add_key(f"{without}/index")

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

        stem = PurePosixPath(normalized_path).stem
        if stem:
            stem_to_paths[stem].add(normalized_path)

    return module_to_path, dict(path_style_to_paths), dict(stem_to_paths)


def _path_locality_sort_key(*, seed_path: str, candidate_path: str) -> tuple[int, int, int, str]:
    seed_parts = PurePosixPath(str(seed_path).strip().replace("\\", "/")).parent.parts
    candidate_text = str(candidate_path).strip().replace("\\", "/")
    candidate_parts = PurePosixPath(candidate_text).parent.parts
    shared_prefix = 0
    for seed_part, candidate_part in zip(seed_parts, candidate_parts):
        if seed_part != candidate_part:
            break
        shared_prefix += 1
    relative_distance = (len(seed_parts) - shared_prefix) + (
        len(candidate_parts) - shared_prefix
    )
    return (-shared_prefix, relative_distance, len(candidate_text), candidate_text)


def _select_best_path_candidate(
    *,
    seed_path: str,
    files: dict[str, dict[str, Any]],
    candidates: set[str] | list[str] | tuple[str, ...],
) -> str | None:
    normalized_candidates = sorted(
        {
            str(path).strip().replace("\\", "/")
            for path in candidates
            if isinstance(path, str) and str(path).strip().replace("\\", "/") in files
        }
    )
    if not normalized_candidates:
        return None
    return min(
        normalized_candidates,
        key=lambda candidate_path: _path_locality_sort_key(
            seed_path=seed_path,
            candidate_path=candidate_path,
        ),
    )


def _resolve_import_target(
    *,
    seed_path: str,
    seed_entry: dict[str, Any],
    import_module: str,
    import_name: str,
    files: dict[str, dict[str, Any]],
    module_to_path: dict[str, str],
    path_style_to_paths: dict[str, set[str]],
    stem_to_paths: dict[str, set[str]],
) -> str | None:
    module = import_module.strip().strip('"`')
    module_no_dots = module.lstrip(".")

    for candidate in [module, module_no_dots]:
        if candidate and candidate in module_to_path:
            return module_to_path[candidate]

    if module.startswith("."):
        seed_module = str(seed_entry.get("module", "")).strip()
        resolved = _resolve_python_relative_module(
            seed_module=seed_module,
            relative_module=module,
        )
        if resolved and resolved in module_to_path:
            return module_to_path[resolved]

    for key in _module_path_keys(seed_path=seed_path, module=module_no_dots or module):
        mapped = _select_best_path_candidate(
            seed_path=seed_path,
            files=files,
            candidates=path_style_to_paths.get(key, set()),
        )
        if mapped:
            return mapped

    if module_no_dots and import_name:
        candidate = f"{module_no_dots}.{import_name}"
        if candidate in module_to_path:
            return module_to_path[candidate]

    tail = import_name or _tail_token(module_no_dots)
    if tail:
        stem_hits = stem_to_paths.get(tail, set())
        if len(stem_hits) == 1:
            only = next(iter(stem_hits))
            if only in files:
                return only

    return None


def _resolve_python_relative_module(*, seed_module: str, relative_module: str) -> str:
    dots = len(relative_module) - len(relative_module.lstrip("."))
    tail = relative_module[dots:]
    base_parts = [part for part in seed_module.split(".") if part]
    if dots > 0:
        trim = min(len(base_parts), dots)
        base_parts = base_parts[: len(base_parts) - trim]
    if tail:
        base_parts.extend([part for part in tail.split(".") if part])
    return ".".join(base_parts)


def _module_path_keys(*, seed_path: str, module: str) -> list[str]:
    value = module.strip().replace("\\", "/")
    if not value:
        return []

    keys: list[str] = []
    raw = value.lstrip("./")
    if raw:
        keys.extend([raw, _remove_source_suffix(raw), f"{_remove_source_suffix(raw)}/index"])

    if value.startswith("."):
        joined = PurePosixPath(PurePosixPath(seed_path).parent / value).as_posix()
        cleaned = joined.lstrip("./")
        if cleaned:
            keys.extend(
                [cleaned, _remove_source_suffix(cleaned), f"{_remove_source_suffix(cleaned)}/index"]
            )

    unique: list[str] = []
    for key in keys:
        normalized = key.strip().lstrip("./")
        if normalized and normalized not in unique:
            unique.append(normalized)
    return unique


def _tail_token(module: str) -> str:
    if not module:
        return ""
    parts = module.replace("/", ".").split(".")
    for item in reversed(parts):
        token = item.strip()
        if token:
            return token
    return ""


def _remove_source_suffix(path: str) -> str:
    text = str(path).strip().replace("\\", "/")
    for suffix in SOURCE_SUFFIXES:
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text
