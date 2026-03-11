from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SymbolEntry:
    name: str
    qualified_name: str
    kind: str
    lineno: int
    end_lineno: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "qualified_name": self.qualified_name,
            "kind": self.kind,
            "lineno": self.lineno,
            "end_lineno": self.end_lineno,
        }


@dataclass(slots=True)
class ImportEntry:
    module: str | None
    name: str | None = None
    alias: str | None = None
    lineno: int = 1
    type: str = "import"
    level: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
            "module": self.module,
            "name": self.name,
            "alias": self.alias,
            "lineno": self.lineno,
        }
        if self.level is not None:
            payload["level"] = self.level
        return payload


@dataclass(slots=True)
class ReferenceEntry:
    name: str
    qualified_name: str | None = None
    lineno: int = 1
    kind: str = 'reference'

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'name': self.name,
            'lineno': self.lineno,
            'kind': self.kind,
        }
        if self.qualified_name is not None:
            payload['qualified_name'] = self.qualified_name
        return payload


@dataclass(slots=True)
class ParseResult:
    language: str
    module: str
    sha256: str
    mtime_ns: int = 0
    size_bytes: int = 0
    generated: bool = False
    symbols: list[SymbolEntry] = field(default_factory=list)
    imports: list[ImportEntry] = field(default_factory=list)
    references: list[ReferenceEntry] = field(default_factory=list)
    parse_error: str | None = None

    def to_index_entry(self, *, path: str) -> dict[str, Any]:
        symbols = [symbol.to_dict() for symbol in self.symbols]
        imports = [item.to_dict() for item in self.imports]
        references = [item.to_dict() for item in self.references]

        classes = [
            {
                "name": symbol.name,
                "qualified_name": symbol.qualified_name,
                "lineno": symbol.lineno,
                "end_lineno": symbol.end_lineno,
            }
            for symbol in self.symbols
            if symbol.kind in {"class", "type"}
        ]

        functions = [
            {
                "name": symbol.name,
                "qualified_name": symbol.qualified_name,
                "lineno": symbol.lineno,
                "end_lineno": symbol.end_lineno,
                "is_async": symbol.kind == "async_function",
            }
            for symbol in self.symbols
            if symbol.kind in {"function", "async_function", "method"}
        ]

        entry: dict[str, Any] = {
            "path": path,
            "language": self.language,
            "module": self.module,
            "sha256": self.sha256,
            "mtime_ns": max(0, int(self.mtime_ns)),
            "size_bytes": max(0, int(self.size_bytes)),
            "generated": bool(self.generated),
            "symbols": symbols,
            "imports": imports,
            "classes": classes,
            "functions": functions,
        }
        if self.parse_error:
            entry["parse_error"] = self.parse_error
        entry['references'] = references
        return entry


__all__ = ["ImportEntry", "ParseResult", "ReferenceEntry", "SymbolEntry"]

