from __future__ import annotations

import hashlib
import json
from typing import Any

CHUNK_CACHE_CONTRACT_SCHEMA_VERSION = "chunk-cache-contract-v1"
CHUNK_FINGERPRINT_SCHEMA_VERSION = "chunk-fingerprint-v1"


def _normalize_symbol_payload(symbol: dict[str, Any]) -> dict[str, Any]:
    return {
        "qualified_name": str(
            symbol.get("qualified_name") or symbol.get("name") or ""
        ).strip(),
        "name": str(symbol.get("name") or "").strip(),
        "kind": str(symbol.get("kind") or "").strip().lower(),
        "lineno": int(symbol.get("lineno", 0) or 0),
        "end_lineno": int(symbol.get("end_lineno", 0) or 0),
    }


def _normalize_imports(entry: dict[str, Any]) -> list[str]:
    imports_raw = entry.get("imports")
    if not isinstance(imports_raw, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in imports_raw:
        if isinstance(item, str):
            rendered = str(item).strip()
        elif isinstance(item, dict):
            import_type = str(item.get("type") or "").strip().lower()
            module = str(item.get("module") or "").strip()
            name = str(item.get("name") or "").strip()
            alias = str(item.get("alias") or "").strip()
            parts = [import_type, module, name, alias]
            rendered = "|".join(part for part in parts if part)
        else:
            rendered = ""
        if not rendered or rendered in seen:
            continue
        seen.add(rendered)
        normalized.append(rendered)
    return normalized


def _normalize_references(entry: dict[str, Any]) -> list[str]:
    references_raw = entry.get("references")
    if not isinstance(references_raw, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in references_raw:
        if isinstance(item, str):
            rendered = str(item).strip()
        elif isinstance(item, dict):
            rendered = str(
                item.get("qualified_name") or item.get("name") or ""
            ).strip()
        else:
            rendered = ""
        if not rendered or rendered in seen:
            continue
        seen.add(rendered)
        normalized.append(rendered)
    return normalized


def _sha256_json(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def build_chunk_fingerprint_records(
    *,
    path: str,
    entry: dict[str, Any],
) -> list[dict[str, Any]]:
    normalized_path = str(path or "").strip()
    if not normalized_path or not isinstance(entry, dict):
        return []

    module = str(entry.get("module") or "").strip()
    language = str(entry.get("language") or "").strip().lower()
    imports = _normalize_imports(entry)
    references = _normalize_references(entry)
    symbols = entry.get("symbols")
    if not isinstance(symbols, list):
        return []

    records: list[dict[str, Any]] = []
    for index, raw_symbol in enumerate(symbols):
        if not isinstance(raw_symbol, dict):
            continue
        normalized_symbol = _normalize_symbol_payload(raw_symbol)
        key_parts = [
            normalized_path,
            normalized_symbol["qualified_name"] or normalized_symbol["name"],
            normalized_symbol["kind"],
            str(normalized_symbol["lineno"]),
            str(normalized_symbol["end_lineno"]),
        ]
        if any(part for part in key_parts if str(part).strip()):
            key = "|".join(str(part) for part in key_parts)
        else:
            key = f"{normalized_path}|chunk::{int(index)}"
        fingerprint = _sha256_json(
            {
                "schema_version": CHUNK_FINGERPRINT_SCHEMA_VERSION,
                "path": normalized_path,
                "module": module,
                "language": language,
                "symbol": normalized_symbol,
                "imports": imports,
                "references": references,
            }
        )
        records.append(
            {
                "key": key,
                "fingerprint": fingerprint,
                "qualified_name": normalized_symbol["qualified_name"],
                "name": normalized_symbol["name"],
                "kind": normalized_symbol["kind"],
                "lineno": normalized_symbol["lineno"],
                "end_lineno": normalized_symbol["end_lineno"],
            }
        )
    return records


def build_chunk_cache_contract(
    files_map: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    files: dict[str, Any] = {}
    aggregate_rows: list[dict[str, Any]] = []
    total_chunk_count = 0

    normalized_map = files_map if isinstance(files_map, dict) else {}
    for path in sorted(item for item in normalized_map if isinstance(item, str)):
        entry = normalized_map.get(path, {})
        if not isinstance(entry, dict):
            continue
        records = build_chunk_fingerprint_records(path=path, entry=entry)
        chunk_fingerprint = _sha256_json(
            {
                "schema_version": CHUNK_CACHE_CONTRACT_SCHEMA_VERSION,
                "path": path,
                "module": str(entry.get("module") or "").strip(),
                "language": str(entry.get("language") or "").strip().lower(),
                "imports": _normalize_imports(entry),
                "references": _normalize_references(entry),
                "chunks": [
                    {
                        "key": str(item.get("key") or ""),
                        "fingerprint": str(item.get("fingerprint") or ""),
                    }
                    for item in records
                ],
            }
        )
        chunk_count = len(records)
        total_chunk_count += chunk_count
        files[path] = {
            "fingerprint": chunk_fingerprint,
            "chunk_count": chunk_count,
        }
        aggregate_rows.append(
            {
                "path": path,
                "fingerprint": chunk_fingerprint,
                "chunk_count": chunk_count,
            }
        )

    return {
        "schema_version": CHUNK_CACHE_CONTRACT_SCHEMA_VERSION,
        "file_count": len(files),
        "chunk_count": total_chunk_count,
        "fingerprint": _sha256_json(aggregate_rows),
        "files": files,
    }


def diff_chunk_cache_contract_paths(
    previous: dict[str, Any] | None,
    current: dict[str, Any] | None,
) -> dict[str, list[str]]:
    previous_files = (
        previous.get("files", {})
        if isinstance(previous, dict) and isinstance(previous.get("files"), dict)
        else {}
    )
    current_files = (
        current.get("files", {})
        if isinstance(current, dict) and isinstance(current.get("files"), dict)
        else {}
    )

    changed_paths: list[str] = []
    unchanged_paths: list[str] = []
    removed_paths: list[str] = []

    current_keys = sorted(str(path) for path in current_files if isinstance(path, str))
    previous_keys = {str(path) for path in previous_files if isinstance(path, str)}
    for path in current_keys:
        current_entry = current_files.get(path, {})
        previous_entry = previous_files.get(path, {})
        current_fingerprint = (
            str(current_entry.get("fingerprint") or "").strip()
            if isinstance(current_entry, dict)
            else ""
        )
        previous_fingerprint = (
            str(previous_entry.get("fingerprint") or "").strip()
            if isinstance(previous_entry, dict)
            else ""
        )
        if current_fingerprint and current_fingerprint == previous_fingerprint:
            unchanged_paths.append(path)
        else:
            changed_paths.append(path)

    for path in sorted(previous_keys - set(current_keys)):
        removed_paths.append(path)

    return {
        "changed_paths": changed_paths,
        "unchanged_paths": unchanged_paths,
        "removed_paths": removed_paths,
    }


__all__ = [
    "CHUNK_CACHE_CONTRACT_SCHEMA_VERSION",
    "CHUNK_FINGERPRINT_SCHEMA_VERSION",
    "build_chunk_cache_contract",
    "build_chunk_fingerprint_records",
    "diff_chunk_cache_contract_paths",
]
