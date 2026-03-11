from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ace_lite.embeddings_providers import EmbeddingProvider, _coerce_vector
from ace_lite.sqlite_mirror import resolve_mirror_db_path, write_embeddings_mirror


def build_or_load_embedding_index(
    *,
    files_map: dict[str, dict[str, Any]],
    provider: EmbeddingProvider,
    index_path: str | Path,
    index_hash: str | None = None,
) -> tuple[dict[str, list[float]], bool]:
    target = Path(index_path)
    if not target.is_absolute():
        target = Path(index_path)

    normalized_index_hash = str(index_hash or "").strip().lower()
    cached_payload = _load_embedding_index_payload(
        path=target,
        provider=provider,
    )

    paths = [
        path
        for path, entry in sorted(files_map.items())
        if isinstance(path, str) and isinstance(entry, dict)
    ]
    desired_hashes: dict[str, str] = {}
    desired_texts: dict[str, str] = {}
    for path in paths:
        entry = files_map.get(path, {})
        text = _build_file_embedding_text(
            path=path,
            entry=entry if isinstance(entry, dict) else {},
        )
        desired_texts[path] = text
        desired_hashes[path] = _sha256_text(text)

    if cached_payload is not None:
        cached_vectors = dict(cached_payload.get("vectors") or {})
        cached_hashes = dict(cached_payload.get("file_hashes") or {})
        cached_fingerprint = str(cached_payload.get("fingerprint") or "").strip()
        cached_index_hash = str(cached_payload.get("index_hash") or "").strip().lower()
        if not cached_hashes and cached_fingerprint:
            fingerprint = _compute_files_fingerprint(files_map)
            index_hash_match = (
                not normalized_index_hash
                or not cached_index_hash
                or cached_index_hash == normalized_index_hash
            )
            if fingerprint == cached_fingerprint and index_hash_match:
                return cached_vectors, True

        changed_paths: list[str] = []
        changed_texts: list[str] = []
        for path in paths:
            expected_hash = desired_hashes.get(path, "")
            if not expected_hash:
                continue
            if cached_hashes.get(path) == expected_hash and path in cached_vectors:
                continue
            changed_paths.append(path)
            changed_texts.append(desired_texts.get(path, ""))

        removed_paths = [path for path in list(cached_vectors) if path not in desired_hashes]

        if not changed_paths and not removed_paths:
            if (
                not normalized_index_hash
                or not cached_index_hash
                or cached_index_hash == normalized_index_hash
            ):
                return cached_vectors, True
            _write_embedding_index(
                path=target,
                provider=provider,
                file_hashes=desired_hashes,
                vectors=cached_vectors,
                index_hash=normalized_index_hash,
            )
            return cached_vectors, False

        if changed_texts:
            encoded = provider.encode(changed_texts)
            for path, vector in zip(changed_paths, encoded, strict=False):
                cached_vectors[path] = _coerce_vector(vector, dimension=provider.dimension)

        for path in removed_paths:
            cached_vectors.pop(path, None)

        _write_embedding_index(
            path=target,
            provider=provider,
            file_hashes=desired_hashes,
            vectors=cached_vectors,
            index_hash=normalized_index_hash,
        )
        return cached_vectors, False

    vectors: dict[str, list[float]] = {}
    if paths:
        corpus_texts = [desired_texts.get(path, "") for path in paths]
        encoded = provider.encode(corpus_texts)
        for path, vector in zip(paths, encoded, strict=False):
            vectors[path] = _coerce_vector(vector, dimension=provider.dimension)

    _write_embedding_index(
        path=target,
        provider=provider,
        file_hashes=desired_hashes,
        vectors=vectors,
        index_hash=normalized_index_hash,
    )
    return vectors, False


def _build_file_embedding_text(*, path: str, entry: dict[str, Any]) -> str:
    module = str(entry.get("module") or "").strip()
    language = str(entry.get("language") or "").strip()

    symbols = entry.get("symbols")
    symbol_labels: list[str] = []
    if isinstance(symbols, list):
        for symbol in symbols:
            if not isinstance(symbol, dict):
                continue
            qualified = str(
                symbol.get("qualified_name") or symbol.get("name") or ""
            ).strip()
            if qualified:
                symbol_labels.append(qualified)

    imports = entry.get("imports")
    import_labels: list[str] = []
    if isinstance(imports, list):
        for item in imports:
            if not isinstance(item, dict):
                continue
            module_name = str(item.get("module") or "").strip()
            import_name = str(item.get("name") or "").strip()
            if module_name and import_name:
                import_labels.append(f"{module_name}.{import_name}")
            elif module_name:
                import_labels.append(module_name)
            elif import_name:
                import_labels.append(import_name)

    references = entry.get("references")
    reference_labels: list[str] = []
    if isinstance(references, list):
        for item in references:
            if not isinstance(item, dict):
                continue
            qualified = str(
                item.get("qualified_name") or item.get("name") or ""
            ).strip()
            if qualified:
                reference_labels.append(qualified)

    chunks = [
        path,
        module,
        language,
        " ".join(symbol_labels[:128]),
        " ".join(import_labels[:128]),
        " ".join(reference_labels[:128]),
    ]
    return "\n".join(part for part in chunks if part)


def _build_row_embedding_key(*, row: dict[str, Any], index: int) -> str:
    path = str(row.get("path") or "").strip()
    qualified = str(row.get("qualified_name") or row.get("name") or "").strip()
    kind = str(row.get("kind") or "").strip()
    lineno = int(row.get("lineno", 0) or 0)
    end_lineno = int(row.get("end_lineno", 0) or 0)
    parts = [path, qualified, kind, str(lineno), str(end_lineno)]
    if not any(parts):
        return f"row::{int(index)}"
    return "|".join(part for part in parts if part)


def _compute_files_fingerprint(files_map: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for path in sorted(files_map):
        entry = files_map.get(path, {})
        if not isinstance(entry, dict):
            continue
        digest.update(path.encode("utf-8", errors="ignore"))
        digest.update(b"\x00")
        digest.update(
            _build_file_embedding_text(path=path, entry=entry).encode(
                "utf-8",
                errors="ignore",
            )
        )
        digest.update(b"\x1f")
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", errors="ignore")).hexdigest()


def _load_embedding_index_payload(
    *,
    path: Path,
    provider: EmbeddingProvider,
    max_hashes: int = 100_000,
) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None

    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return None
    if str(meta.get("provider") or "").strip() != provider.provider:
        return None
    if str(meta.get("model") or "").strip() != provider.model:
        return None
    if int(meta.get("dimension", 0) or 0) != int(provider.dimension):
        return None

    vectors_raw = payload.get("vectors")
    if not isinstance(vectors_raw, dict):
        return None

    vectors: dict[str, list[float]] = {}
    for key, value in vectors_raw.items():
        vector = _coerce_vector(value, dimension=provider.dimension)
        if vector:
            vectors[str(key)] = vector

    file_hashes_raw = meta.get("file_hashes")
    file_hashes: dict[str, str] = {}
    if isinstance(file_hashes_raw, dict):
        for key, value in list(file_hashes_raw.items())[: max(0, int(max_hashes))]:
            path_key = str(key or "").strip()
            digest = str(value or "").strip().lower()
            if path_key and digest:
                file_hashes[path_key] = digest

    return {
        "vectors": vectors,
        "file_hashes": file_hashes,
        "fingerprint": str(meta.get("fingerprint") or "").strip(),
        "index_hash": str(meta.get("index_hash") or "").strip().lower(),
    }


def _infer_repo_root_for_sqlite_mirror(*, index_path: Path) -> Path | None:
    resolved = index_path.resolve()
    parts = list(resolved.parts)
    for idx, part in enumerate(parts):
        if str(part).lower() != "context-map":
            continue
        if idx <= 0:
            return None
        return Path(*parts[:idx])
    return None


def _write_embedding_index(
    *,
    path: Path,
    provider: EmbeddingProvider,
    file_hashes: dict[str, str],
    vectors: dict[str, list[float]],
    index_hash: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {
            "provider": provider.provider,
            "model": provider.model,
            "dimension": provider.dimension,
            "file_hashes": dict(file_hashes),
            "index_hash": str(index_hash or "").strip().lower(),
        },
        "vectors": vectors,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        root = _infer_repo_root_for_sqlite_mirror(index_path=path)
        if root is None:
            return
        write_embeddings_mirror(
            db_path=resolve_mirror_db_path(root=root),
            provider=provider.provider,
            model=provider.model,
            dimension=provider.dimension,
            file_hashes=file_hashes,
            vectors=vectors,
        )
    except Exception:
        return


__all__ = [
    "build_or_load_embedding_index",
]
