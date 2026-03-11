from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_FUNCTION_KINDS = {"function", "method", "async_function"}
_CLASS_KINDS = {"class", "type"}


@dataclass(frozen=True, slots=True)
class CodeTag:
    name: str
    kind: str
    signature: str
    start_line: int
    end_line: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "signature": self.signature,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


def extract_code_tags(
    entry: dict[str, Any] | None,
    *,
    max_tags: int = 24,
) -> list[dict[str, Any]]:
    if not isinstance(entry, dict):
        return []

    raw_symbols: list[dict[str, Any]] = []
    for source_key, fallback_kind in (
        ("symbols", None),
        ("classes", "class"),
        ("functions", "function"),
    ):
        source = entry.get(source_key)
        if not isinstance(source, list):
            continue
        for item in source:
            if not isinstance(item, dict):
                continue
            candidate = dict(item)
            if fallback_kind and not str(candidate.get("kind") or "").strip():
                candidate["kind"] = fallback_kind
            raw_symbols.append(candidate)

    dedup: dict[tuple[str, str, int, int], CodeTag] = {}
    for symbol in raw_symbols:
        normalized = _normalize_symbol(symbol)
        if normalized is None:
            continue
        key = (
            normalized.kind,
            normalized.name,
            normalized.start_line,
            normalized.end_line,
        )
        if key not in dedup:
            dedup[key] = normalized

    ordered = sorted(
        dedup.values(),
        key=lambda item: (
            int(item.start_line),
            int(item.end_line),
            str(item.name),
            str(item.kind),
        ),
    )

    limited = ordered[: max(0, int(max_tags))]
    return [item.to_dict() for item in limited]


def _normalize_symbol(symbol: dict[str, Any]) -> CodeTag | None:
    raw_name = str(symbol.get("qualified_name") or symbol.get("name") or "").strip()
    if not raw_name:
        return None

    raw_kind = str(symbol.get("kind") or "").strip().lower()
    kind = raw_kind or "symbol"

    start_line = _to_positive_int(symbol.get("lineno"), default=1)
    end_line = _to_positive_int(symbol.get("end_lineno"), default=start_line)
    if end_line < start_line:
        end_line = start_line

    signature = _build_signature(name=raw_name, kind=kind)
    return CodeTag(
        name=raw_name,
        kind=kind,
        signature=signature,
        start_line=start_line,
        end_line=end_line,
    )


def _to_positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return max(1, int(default))
    return parsed if parsed > 0 else max(1, int(default))


def _build_signature(*, name: str, kind: str) -> str:
    label = str(name).strip()
    if not label:
        return ""
    if kind in _FUNCTION_KINDS:
        return f"def {label}(...)"
    if kind in _CLASS_KINDS:
        return f"class {label}"
    return f"{kind} {label}"


__all__ = ["CodeTag", "extract_code_tags"]
