from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any

ROBUST_SIGNATURE_LITE_VERSION = "v1"
ROBUST_SIGNATURE_ENTITY_VOCAB_LIMIT = 12
_ROW_SCAN_LIMIT = 24
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z0-9]|$)|[A-Z]?[a-z0-9]+")
_STOP_TOKENS = {
    "a",
    "an",
    "and",
    "args",
    "bool",
    "cls",
    "def",
    "debug",
    "dict",
    "for",
    "from",
    "func",
    "function",
    "in",
    "is",
    "method",
    "noise",
    "noisy",
    "path",
    "py",
    "repo",
    "of",
    "or",
    "self",
    "src",
    "the",
    "to",
    "tmp",
    "true",
    "false",
    "none",
}


def _normalize_identifier_tokens(value: Any) -> list[str]:
    normalized = str(value or "").strip()
    if not normalized:
        return []

    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(normalized.replace("/", " ").replace(".", " ")):
        parts = _CAMEL_RE.findall(raw) or [raw]
        for part in parts:
            token = str(part).strip().lower()
            if (
                not token
                or len(token) <= 1
                or token.isdigit()
                or token in _STOP_TOKENS
            ):
                continue
            tokens.append(token)
    return tokens


def _count_signature_params(signature: str) -> int:
    text = str(signature or "").strip()
    if not text:
        return 0

    left = text.find("(")
    right = text.find(")", left + 1)
    if left < 0 or right <= left:
        return 0

    params = [
        item.strip()
        for item in text[left + 1 : right].split(",")
        if str(item).strip()
    ]
    return len(params)


def chunk_identity_key(*, chunk: dict[str, Any]) -> str:
    if not isinstance(chunk, dict):
        return ""

    path = str(chunk.get("path") or "").strip()
    qualified_name = str(chunk.get("qualified_name") or "").strip()
    lineno = int(chunk.get("lineno") or 0)
    end_lineno = int(chunk.get("end_lineno") or lineno)
    if end_lineno < lineno:
        end_lineno = lineno
    if not path or lineno <= 0 or (not qualified_name and not str(chunk.get("kind") or "").strip()):
        return ""
    return f"{path}|{lineno}|{end_lineno}|{qualified_name}"


def extract_entity_vocab(
    *,
    path: str,
    qualified_name: str,
    name: str,
    signature: str,
    imports: list[dict[str, Any]] | None,
    references: list[dict[str, Any]] | None,
    max_terms: int = ROBUST_SIGNATURE_ENTITY_VOCAB_LIMIT,
) -> list[str]:
    counter: Counter[str] = Counter()

    for raw in (path, qualified_name, name, signature):
        for token in _normalize_identifier_tokens(raw):
            counter[token] += 1

    for row in (imports or [])[:_ROW_SCAN_LIMIT]:
        if not isinstance(row, dict):
            continue
        for raw in (row.get("module"), row.get("name"), row.get("alias")):
            for token in _normalize_identifier_tokens(raw):
                counter[token] += 1

    for row in (references or [])[:_ROW_SCAN_LIMIT]:
        if not isinstance(row, dict):
            continue
        for raw in (row.get("qualified_name"), row.get("name")):
            for token in _normalize_identifier_tokens(raw):
                counter[token] += 1

    if not counter:
        return []

    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    selected = sorted(token for token, _ in ranked[: max(1, int(max_terms))])
    return selected


def extract_shape_features(
    *,
    kind: str,
    qualified_name: str,
    signature: str,
) -> list[str]:
    normalized_kind = str(kind or "").strip().lower() or "unknown"
    depth = max(0, str(qualified_name or "").strip().count("."))
    param_count = _count_signature_params(signature)
    stripped_signature = str(signature or "").strip()
    returns_value = "->" in stripped_signature
    is_async = stripped_signature.startswith("async ")
    has_variadic = "*" in stripped_signature

    return [
        f"kind:{normalized_kind}",
        f"depth:{min(depth, 8)}",
        f"params:{min(param_count, 8)}",
        f"returns:{1 if returns_value else 0}",
        f"async:{1 if is_async else 0}",
        f"variadic:{1 if has_variadic else 0}",
    ]


def build_compatibility_domain(
    *,
    path: str,
    kind: str,
    qualified_name: str,
) -> str:
    normalized_path = str(path or "").strip().replace("\\", "/")
    if not normalized_path:
        return ""

    normalized_kind = str(kind or "").strip().lower() or "unknown"
    normalized_qualified = str(qualified_name or "").strip()
    parent_scope = (
        normalized_qualified.rsplit(".", 1)[0]
        if "." in normalized_qualified
        else normalized_path
    )
    return f"{normalized_path}|{normalized_kind}|{parent_scope}"


def build_robust_signature_lite(
    *,
    path: str,
    qualified_name: str,
    name: str,
    kind: str,
    signature: str,
    imports: list[dict[str, Any]] | None,
    references: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    normalized_path = str(path or "").strip()
    normalized_kind = str(kind or "").strip().lower()
    normalized_qualified_name = str(qualified_name or "").strip()
    normalized_name = str(name or "").strip()
    normalized_signature = str(signature or "").strip()

    if (
        not normalized_path
        or not normalized_kind
        or not (normalized_qualified_name or normalized_name)
    ):
        return {
            "version": ROBUST_SIGNATURE_LITE_VERSION,
            "available": False,
            "compatibility_domain": "",
            "entity_vocab": (),
            "entity_vocab_count": 0,
            "shape_features_count": 0,
            "shape_hash": "",
        }

    compatibility_domain = build_compatibility_domain(
        path=normalized_path,
        kind=normalized_kind,
        qualified_name=normalized_qualified_name or normalized_name,
    )
    shape_features = extract_shape_features(
        kind=normalized_kind,
        qualified_name=normalized_qualified_name or normalized_name,
        signature=normalized_signature,
    )
    entity_vocab = extract_entity_vocab(
        path=normalized_path,
        qualified_name=normalized_qualified_name or normalized_name,
        name=normalized_name or normalized_qualified_name.rsplit(".", 1)[-1],
        signature=normalized_signature,
        imports=imports,
        references=references,
    )

    shape_hash = ""
    if shape_features:
        source = "|".join(shape_features).encode("utf-8", errors="ignore")
        shape_hash = hashlib.sha256(source).hexdigest()[:12]

    available = bool(
        normalized_path
        and normalized_kind
        and (normalized_qualified_name or normalized_name)
        and compatibility_domain
        and shape_hash
    )
    return {
        "version": ROBUST_SIGNATURE_LITE_VERSION,
        "available": available,
        "compatibility_domain": compatibility_domain if available else "",
        "entity_vocab": tuple(entity_vocab) if available else (),
        "entity_vocab_count": len(entity_vocab) if available else 0,
        "shape_features_count": len(shape_features) if available else 0,
        "shape_hash": shape_hash if available else "",
    }


def summarize_robust_signature(value: dict[str, Any] | None) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    if not bool(payload.get("available", False)):
        return {
            "version": ROBUST_SIGNATURE_LITE_VERSION,
            "available": False,
            "compatibility_domain": "",
            "shape_hash": "",
            "entity_vocab_count": 0,
        }
    return {
        "version": str(payload.get("version") or ROBUST_SIGNATURE_LITE_VERSION),
        "available": True,
        "compatibility_domain": str(payload.get("compatibility_domain") or ""),
        "shape_hash": str(payload.get("shape_hash") or ""),
        "entity_vocab_count": int(payload.get("entity_vocab_count", 0) or 0),
    }


def build_chunk_robust_signature_sidecar(
    *,
    candidate_chunks: list[dict[str, Any]],
    files_map: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    chunks = candidate_chunks if isinstance(candidate_chunks, list) else []
    file_rows = files_map if isinstance(files_map, dict) else {}
    sidecar: dict[str, dict[str, Any]] = {}

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        key = chunk_identity_key(chunk=chunk)
        if not key:
            continue
        path = str(chunk.get("path") or "").strip()
        signature = build_robust_signature_lite(
            path=path,
            qualified_name=str(chunk.get("qualified_name") or "").strip(),
            name=str(chunk.get("name") or "").strip()
            or str(chunk.get("qualified_name") or "").strip().rsplit(".", 1)[-1],
            kind=str(chunk.get("kind") or "").strip(),
            signature=str(chunk.get("signature") or "").strip(),
            imports=(
                file_rows.get(path, {}).get("imports", [])
                if isinstance(file_rows.get(path, {}), dict)
                and isinstance(file_rows.get(path, {}).get("imports"), list)
                else []
            ),
            references=(
                file_rows.get(path, {}).get("references", [])
                if isinstance(file_rows.get(path, {}), dict)
                and isinstance(file_rows.get(path, {}).get("references"), list)
                else []
            ),
        )
        if not bool(signature.get("available", False)):
            continue
        sidecar[key] = signature

    return {key: sidecar[key] for key in sorted(sidecar)}


def count_available_robust_signatures(
    *,
    candidate_chunks: list[dict[str, Any]],
    sidecar: dict[str, dict[str, Any]] | None,
) -> int:
    chunks = candidate_chunks if isinstance(candidate_chunks, list) else []
    count = 0
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        inline_signature = (
            chunk.get("_robust_signature_lite")
            if isinstance(chunk.get("_robust_signature_lite"), dict)
            else chunk.get("robust_signature_summary")
            if isinstance(chunk.get("robust_signature_summary"), dict)
            else {}
        )
        if bool(inline_signature.get("available", False)):
            count += 1
            continue
        if not isinstance(sidecar, dict) or not sidecar:
            continue
        key = chunk_identity_key(chunk=chunk)
        if not key:
            continue
        signature = sidecar.get(key, {})
        if bool(signature.get("available", False)):
            count += 1
    return count


__all__ = [
    "ROBUST_SIGNATURE_ENTITY_VOCAB_LIMIT",
    "ROBUST_SIGNATURE_LITE_VERSION",
    "build_chunk_robust_signature_sidecar",
    "build_compatibility_domain",
    "build_robust_signature_lite",
    "chunk_identity_key",
    "count_available_robust_signatures",
    "extract_entity_vocab",
    "extract_shape_features",
    "summarize_robust_signature",
]
