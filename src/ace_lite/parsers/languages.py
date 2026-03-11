from __future__ import annotations

from pathlib import Path

DEFAULT_LANGUAGE_PROFILE: tuple[str, ...] = (
    "python",
    "typescript",
    "tsx",
    "javascript",
    "go",
    "rust",
    "java",
    "c",
    "cpp",
    "c_sharp",
    "ruby",
    "php",
    "solidity",
    "markdown",
)

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
    ".cs": "c_sharp",
    ".rb": "ruby",
    ".php": "php",
    ".sol": "solidity",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".sh": "bash",
    ".bash": "bash",
    ".lua": "lua",
    ".md": "markdown",
}


def parse_language_csv(raw_languages: str | None) -> list[str] | None:
    if raw_languages is None:
        return None
    values = [token.strip().lower() for token in raw_languages.split(",") if token.strip()]
    if not values:
        return None
    return values


def normalize_languages(languages: list[str] | tuple[str, ...] | set[str] | None) -> tuple[str, ...]:
    if languages is None:
        return DEFAULT_LANGUAGE_PROFILE

    normalized: list[str] = []
    for language in languages:
        value = str(language).strip().lower()
        if value in {"c++", "cplusplus"}:
            value = "cpp"
        elif value in {"c#", "csharp"}:
            value = "c_sharp"
        elif value in {"js"}:
            value = "javascript"
        elif value in {"ts"}:
            value = "typescript"
        elif value in {"golang"}:
            value = "go"
        if value and value not in normalized:
            normalized.append(value)

    if "typescript" in normalized and "tsx" not in normalized:
        normalized.insert(normalized.index("typescript") + 1, "tsx")
    if "tsx" in normalized and "typescript" not in normalized:
        normalized.insert(normalized.index("tsx") + 1, "typescript")

    if not normalized:
        return DEFAULT_LANGUAGE_PROFILE

    return tuple(normalized)


def supported_extensions(languages: tuple[str, ...]) -> set[str]:
    return {suffix for suffix, language in EXTENSION_TO_LANGUAGE.items() if language in set(languages)}


def detect_language(file_path: Path) -> str | None:
    return EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())


def module_name(relative_path: Path, language: str) -> str:
    if language == "python":
        parts = list(relative_path.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            return "__init__"
        return ".".join(parts)

    return relative_path.with_suffix("").as_posix().replace("/", ".")


__all__ = [
    "DEFAULT_LANGUAGE_PROFILE",
    "EXTENSION_TO_LANGUAGE",
    "detect_language",
    "module_name",
    "normalize_languages",
    "parse_language_csv",
    "supported_extensions",
]
