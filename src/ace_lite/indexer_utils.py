"""Indexer Optimization Utilities

This module provides optimized utilities for the indexer module,
focusing on reducing redundant operations while maintaining
correctness and output ordering.

PRD-91 QO-1103: Indexer Hotspot Reduction

Key optimizations:
1. Pre-compiled .aceignore patterns using regex
2. Reduced Path.resolve() calls through caching
3. Optimized sorting with single-pass key extraction
4. Early filtering to avoid unnecessary processing
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Callable
from dataclasses import dataclass
from fnmatch import translate
from pathlib import Path, PurePosixPath
from typing import Any

# =============================================================================
# Compiled Pattern Cache
# =============================================================================


@dataclass(frozen=True, slots=True)
class CompiledPattern:
    """A pre-compiled pattern for efficient matching."""

    pattern: str
    is_negated: bool
    is_directory_only: bool
    is_path_pattern: bool
    regex: re.Pattern[str] | None = None
    name_pattern: str | None = None


def compile_aceignore_patterns(patterns: list[str]) -> list[CompiledPattern]:
    """Compile .aceignore patterns into efficient matchers.

    This converts fnmatch patterns to compiled regex patterns
    for faster matching during file scanning.

    Args:
        patterns: List of .aceignore patterns (may include !negation)

    Returns:
        List of CompiledPattern objects ready for matching
    """
    compiled: list[CompiledPattern] = []

    for raw_pattern in patterns:
        pattern = raw_pattern.strip()
        if not pattern or pattern.startswith("#"):
            continue

        is_negated = pattern.startswith("!")
        if is_negated:
            pattern = pattern[1:].strip()

        # Normalize slashes
        pattern = pattern.replace("\\", "/")

        # Check if it's a directory-only pattern
        is_directory_only = pattern.endswith("/")
        if is_directory_only:
            pattern = pattern.rstrip("/")

        if not pattern:
            continue

        # Check if it's a path pattern (contains /)
        is_path_pattern = "/" in pattern

        # Compile to regex if it's a path pattern
        regex = None
        name_pattern = None

        if is_path_pattern:
            # Convert fnmatch to regex
            fnmatch_pattern = translate(pattern)
            regex = re.compile(fnmatch_pattern)
        else:
            # For name patterns, store the raw pattern
            name_pattern = pattern

        compiled.append(
            CompiledPattern(
                pattern=pattern,
                is_negated=is_negated,
                is_directory_only=is_directory_only,
                is_path_pattern=is_path_pattern,
                regex=regex,
                name_pattern=name_pattern,
            )
        )

    return compiled


def match_compiled_patterns(
    relative_posix_path: str,
    patterns: list[CompiledPattern],
) -> bool:
    """Match a path against pre-compiled patterns.

    This implements gitignore-style matching where:
    - Negated patterns (!pattern) un-ignore matched paths
    - Last matching pattern wins

    Args:
        relative_posix_path: Normalized POSIX path relative to root
        patterns: Pre-compiled patterns from compile_aceignore_patterns

    Returns:
        True if the path should be ignored
    """
    ignored = False
    name = PurePosixPath(relative_posix_path).name
    parts = PurePosixPath(relative_posix_path).parts

    for compiled in patterns:
        matched = False

        if compiled.is_path_pattern and compiled.regex:
            # For path patterns, check full path match
            matched = bool(compiled.regex.fullmatch(relative_posix_path))
            # Also check if path starts with directory pattern
            if not matched and compiled.is_directory_only:
                # Check if this is a subdirectory of the pattern
                for i in range(len(parts)):
                    partial_path = "/".join(parts[:i + 1])
                    if compiled.regex.fullmatch(partial_path):
                        matched = True
                        break
        elif compiled.name_pattern:
            # For name patterns, match against filename
            matched = fnmatch.fnmatchcase(name, compiled.name_pattern)
            # Also check if directory name matches
            if not matched and compiled.is_directory_only:
                matched = any(
                    fnmatch.fnmatchcase(part, compiled.name_pattern)
                    for part in parts[:-1]
                )

        if matched:
            ignored = not compiled.is_negated

    return ignored


# =============================================================================
# Path Resolution Caching
# =============================================================================


class PathResolutionCache:
    """Cache for Path.resolve() results to avoid redundant calls."""

    def __init__(self):
        self._cache: dict[Path, Path] = {}
        self._relative_cache: dict[tuple[Path, Path], str] = {}

    def resolve(self, path: Path) -> Path:
        """Get resolved path with caching."""
        if path not in self._cache:
            self._cache[path] = path.resolve()
        return self._cache[path]

    def relative_to(
        self,
        path: Path,
        root: Path,
    ) -> str | None:
        """Get path relative to root with caching."""
        key = (path, root)
        if key not in self._relative_cache:
            try:
                self._relative_cache[key] = path.relative_to(root).as_posix()
            except ValueError:
                return None
        return self._relative_cache[key]

    def clear(self) -> None:
        """Clear all caches."""
        self._cache.clear()
        self._relative_cache.clear()


# =============================================================================
# Sorting Utilities
# =============================================================================


def extract_sort_key(path: Path, root: Path) -> str:
    """Extract sort key for a path relative to root.

    This is optimized to be called once per path during sorting,
    avoiding repeated PurePosixPath construction.
    """
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def sorted_paths(
    paths: list[Path],
    *,
    root: Path,
    key_func: Callable[[Path], Any] | None = None,
) -> list[Path]:
    """Sort paths with optimized key extraction.

    Uses extract_sort_key to compute keys in a single pass,
    which is more efficient than the lambda approach.

    Args:
        paths: List of paths to sort
        root: Root path for computing relative paths
        key_func: Optional custom key function (overrides default)

    Returns:
        Sorted list of paths
    """
    if not paths:
        return []

    if key_func is None:
        def key_func(path: Path) -> Any:
            return extract_sort_key(path, root)

    return sorted(paths, key=key_func)


# =============================================================================
# Filter Utilities
# =============================================================================


def should_process_file(
    path: Path,
    *,
    suffixes: set[str],
    excluded_dirs: set[str],
    root: Path,
    relative_path: str | None = None,
) -> tuple[bool, str | None]:
    """Determine if a file should be processed.

    This consolidates multiple checks into a single function
    to avoid repeated path computations.

    Returns:
        Tuple of (should_process, relative_path)
    """
    # Get relative path if not provided
    if relative_path is None:
        try:
            relative_path = path.relative_to(root).as_posix()
        except ValueError:
            return False, None

    # Check suffix
    if path.suffix.lower() not in suffixes:
        return False, None

    # Check if in excluded directory
    # Use PurePosixPath to get directory parts regardless of OS
    posix_parts = PurePosixPath(relative_path).parts[:-1]  # Exclude filename
    if any(part in excluded_dirs for part in posix_parts):
        return False, None

    return True, relative_path


# =============================================================================
# Normalization Utilities
# =============================================================================


def normalize_aceignore_pattern(pattern: str) -> str:
    """Normalize a single .aceignore pattern.

    - Strips whitespace
    - Normalizes slashes to forward slashes
    - Removes leading ./
    - Removes leading /
    """
    pattern = pattern.strip()
    if not pattern:
        return ""

    # Normalize slashes
    pattern = pattern.replace("\\", "/")

    # Remove leading ./
    while pattern.startswith("./"):
        pattern = pattern[2:]

    # Remove leading /
    if pattern.startswith("/"):
        pattern = pattern[1:]

    return pattern


def normalize_aceignore_patterns(patterns: list[str]) -> list[str]:
    """Normalize a list of .aceignore patterns.

    This consolidates duplicates and applies normalization
    to all patterns.
    """
    normalized: list[str] = []
    seen: set[str] = set()

    for pattern in patterns:
        normalized_pattern = normalize_aceignore_pattern(pattern)
        if normalized_pattern and normalized_pattern not in seen:
            seen.add(normalized_pattern)
            normalized.append(normalized_pattern)

    return normalized


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "CompiledPattern",
    "PathResolutionCache",
    "compile_aceignore_patterns",
    "extract_sort_key",
    "match_compiled_patterns",
    "normalize_aceignore_pattern",
    "normalize_aceignore_patterns",
    "should_process_file",
    "sorted_paths",
]
