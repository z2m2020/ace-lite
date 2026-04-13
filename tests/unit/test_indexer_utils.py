"""Unit tests for indexer_utils module.

Tests verify the optimization utilities for the indexer module (QO-1103).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ace_lite.indexer_utils import (
    CompiledPattern,
    PathResolutionCache,
    compile_aceignore_patterns,
    extract_sort_key,
    match_compiled_patterns,
    normalize_aceignore_pattern,
    normalize_aceignore_patterns,
    should_process_file,
    sorted_paths,
)


class TestNormalizeAceignorePattern:
    """Tests for .aceignore pattern normalization."""

    def test_strip_whitespace(self):
        """Test whitespace stripping."""
        assert normalize_aceignore_pattern("  test  ") == "test"
        assert normalize_aceignore_pattern("\ttest\n") == "test"

    def test_normalize_slashes(self):
        """Test slash normalization."""
        assert normalize_aceignore_pattern("path\\to\\file") == "path/to/file"
        assert normalize_aceignore_pattern("path/to/file") == "path/to/file"

    def test_remove_leading_dotslash(self):
        """Test leading ./ removal."""
        assert normalize_aceignore_pattern("./path/to/file") == "path/to/file"
        assert normalize_aceignore_pattern("./file.py") == "file.py"

    def test_remove_leading_slash(self):
        """Test leading / removal."""
        assert normalize_aceignore_pattern("/path/to/file") == "path/to/file"

    def test_empty_pattern(self):
        """Test empty pattern."""
        assert normalize_aceignore_pattern("") == ""
        assert normalize_aceignore_pattern("   ") == ""


class TestNormalizeAceignorePatterns:
    """Tests for normalizing pattern lists."""

    def test_normalize_multiple(self):
        """Test normalizing multiple patterns."""
        patterns = ["  test1  ", "test2", "  test3  "]
        normalized = normalize_aceignore_patterns(patterns)

        assert normalized == ["test1", "test2", "test3"]

    def test_remove_duplicates(self):
        """Test duplicate removal."""
        patterns = ["test", "test", "other"]
        normalized = normalize_aceignore_patterns(patterns)

        assert len(normalized) == 2
        assert "test" in normalized
        assert "other" in normalized


class TestCompileAceignorePatterns:
    """Tests for compiling .aceignore patterns."""

    def test_simple_pattern(self):
        """Test simple filename pattern."""
        patterns = compile_aceignore_patterns(["*.pyc"])
        assert len(patterns) == 1
        assert patterns[0].name_pattern == "*.pyc"
        assert patterns[0].is_negated is False
        assert patterns[0].is_path_pattern is False

    def test_negated_pattern(self):
        """Test negated pattern."""
        patterns = compile_aceignore_patterns(["!test.py"])
        assert len(patterns) == 1
        assert patterns[0].is_negated is True

    def test_directory_pattern(self):
        """Test directory-only pattern."""
        patterns = compile_aceignore_patterns(["dir/"])
        assert len(patterns) == 1
        assert patterns[0].is_directory_only is True

    def test_path_pattern(self):
        """Test path pattern with /."""
        patterns = compile_aceignore_patterns(["path/to/file.py"])
        assert len(patterns) == 1
        assert patterns[0].is_path_pattern is True
        assert patterns[0].regex is not None

    def test_ignore_comments(self):
        """Test ignoring comments."""
        patterns = compile_aceignore_patterns(["# comment", "*.pyc", "  # another"])
        assert len(patterns) == 1

    def test_empty_patterns(self):
        """Test with empty list."""
        patterns = compile_aceignore_patterns([])
        assert patterns == []


class TestMatchCompiledPatterns:
    """Tests for matching paths against compiled patterns."""

    def test_simple_match(self):
        """Test simple filename matching."""
        patterns = compile_aceignore_patterns(["*.pyc"])
        assert match_compiled_patterns("test.pyc", patterns) is True
        assert match_compiled_patterns("test.py", patterns) is False

    def test_negated_match(self):
        """Test negated pattern matching.

        Note: Pattern order matters - the last matching pattern wins.
        To keep important.py visible: ["*.py", "!important.py"]
        """
        # Order: normal pattern first, then negated
        patterns = compile_aceignore_patterns(["*.py", "!important.py"])
        assert len(patterns) == 2

        # *.py matches but !important.py negates it
        assert match_compiled_patterns("important.py", patterns) is False
        assert match_compiled_patterns("other.py", patterns) is True

    def test_path_pattern_match(self):
        """Test path pattern matching."""
        patterns = compile_aceignore_patterns(["src/*.py"])
        assert match_compiled_patterns("src/main.py", patterns) is True
        assert match_compiled_patterns("lib/main.py", patterns) is False

    def test_directory_pattern_match(self):
        """Test directory-only pattern."""
        patterns = compile_aceignore_patterns(["node_modules/"])
        assert match_compiled_patterns("node_modules/package", patterns) is True
        assert match_compiled_patterns("node_modules/package/file.js", patterns) is True


class TestPathResolutionCache:
    """Tests for PathResolutionCache."""

    def test_resolve_caching(self):
        """Test that resolve results are cached."""
        cache = PathResolutionCache()
        path = Path("test.py")

        resolved1 = cache.resolve(path)
        resolved2 = cache.resolve(path)

        assert resolved1 == resolved2
        assert resolved1 is resolved2  # Same object

    def test_relative_to_caching(self):
        """Test that relative_to results are cached."""
        cache = PathResolutionCache()
        path = Path("test/subdir/file.py").resolve()
        root = Path("test").resolve()

        rel1 = cache.relative_to(path, root)
        rel2 = cache.relative_to(path, root)

        assert rel1 == rel2
        assert rel1 is rel2  # Same object

    def test_relative_to_invalid(self):
        """Test relative_to with path not under root."""
        cache = PathResolutionCache()
        path = Path("other/file.py").resolve()
        root = Path("test").resolve()

        result = cache.relative_to(path, root)
        assert result is None

    def test_clear(self):
        """Test cache clearing."""
        cache = PathResolutionCache()
        path = Path("test.py")
        cache.resolve(path)

        cache.clear()

        # After clear, should recompute
        resolved = cache.resolve(path)
        assert resolved is not None


class TestExtractSortKey:
    """Tests for sort key extraction."""

    def test_basic_extraction(self, tmp_path):
        """Test basic sort key extraction."""
        root = tmp_path / "project"
        root.mkdir()

        file1 = root / "b.py"
        file2 = root / "a.py"

        key1 = extract_sort_key(file1, root)
        key2 = extract_sort_key(file2, root)

        assert key1 == "b.py"
        assert key2 == "a.py"

    def test_nested_paths(self, tmp_path):
        """Test extraction with nested paths."""
        root = tmp_path / "project"
        root.mkdir()

        dir1 = root / "src"
        dir1.mkdir()

        file1 = dir1 / "b.py"
        file2 = dir1 / "a.py"

        key1 = extract_sort_key(file1, root)
        key2 = extract_sort_key(file2, root)

        assert key1 == "src/b.py"
        assert key2 == "src/a.py"

    def test_invalid_relative(self, tmp_path):
        """Test with path not under root."""
        root = tmp_path / "project"
        other = tmp_path / "other"

        key = extract_sort_key(other / "file.py", root)
        # Falls back to string representation
        assert key is not None


class TestSortedPaths:
    """Tests for sorted_paths utility."""

    def test_basic_sorting(self, tmp_path):
        """Test basic path sorting."""
        root = tmp_path / "project"
        root.mkdir()

        paths = [
            root / "z.py",
            root / "a.py",
            root / "m.py",
        ]

        sorted_paths_list = sorted_paths(paths, root=root)

        assert sorted_paths_list[0].name == "a.py"
        assert sorted_paths_list[1].name == "m.py"
        assert sorted_paths_list[2].name == "z.py"

    def test_nested_sorting(self, tmp_path):
        """Test sorting with nested paths."""
        root = tmp_path / "project"
        root.mkdir()
        (root / "sub").mkdir()

        paths = [
            root / "sub/b.py",
            root / "a.py",
            root / "sub/a.py",
        ]

        sorted_paths_list = sorted_paths(paths, root=root)

        assert sorted_paths_list[0].name == "a.py"
        assert sorted_paths_list[1].name == "a.py"
        assert sorted_paths_list[2].name == "b.py"

    def test_empty_list(self, tmp_path):
        """Test with empty list."""
        result = sorted_paths([], root=tmp_path)
        assert result == []

    def test_custom_key(self, tmp_path):
        """Test with custom key function."""
        root = tmp_path / "project"
        root.mkdir()

        paths = [root / "a.py", root / "B.py", root / "c.py"]

        # Case-insensitive sort
        result = sorted_paths(
            paths,
            root=root,
            key_func=lambda p: p.name.lower(),
        )

        assert result[0].name == "a.py"
        assert result[1].name == "B.py"
        assert result[2].name == "c.py"


class TestShouldProcessFile:
    """Tests for should_process_file utility."""

    def test_suffix_match(self, tmp_path):
        """Test suffix matching."""
        root = tmp_path
        file_path = root / "test.py"

        should_process, rel_path = should_process_file(
            file_path,
            suffixes={".py"},
            excluded_dirs=set(),
            root=root,
        )

        assert should_process is True
        assert rel_path == "test.py"

    def test_suffix_no_match(self, tmp_path):
        """Test non-matching suffix."""
        root = tmp_path
        file_path = root / "test.txt"

        should_process, _ = should_process_file(
            file_path,
            suffixes={".py"},
            excluded_dirs=set(),
            root=root,
        )

        assert should_process is False

    def test_excluded_directory(self, tmp_path):
        """Test excluded directory check."""
        root = tmp_path
        (root / "node_modules").mkdir()

        file_path = root / "node_modules" / "test.js"

        should_process, _ = should_process_file(
            file_path,
            suffixes={".js"},
            excluded_dirs={"node_modules"},
            root=root,
        )

        assert should_process is False


class TestCompiledPattern:
    """Tests for CompiledPattern dataclass."""

    def test_frozen(self):
        """Test that CompiledPattern is frozen."""
        pattern = CompiledPattern(
            pattern="test.py",
            is_negated=False,
            is_directory_only=False,
            is_path_pattern=False,
        )

        with pytest.raises(AttributeError):
            pattern.pattern = "other.py"  # type: ignore

    def test_immutable(self):
        """Test that CompiledPattern attributes cannot be changed."""
        pattern = CompiledPattern(
            pattern="test.py",
            is_negated=False,
            is_directory_only=False,
            is_path_pattern=False,
        )

        # All attributes should be immutable due to frozen=True
        with pytest.raises((AttributeError, TypeError)):
            pattern.is_negated = True  # type: ignore

    def test_has_expected_fields(self):
        """Test that all expected fields are present."""
        pattern = CompiledPattern(
            pattern="test.py",
            is_negated=True,
            is_directory_only=True,
            is_path_pattern=True,
            regex=None,
            name_pattern="*.py",
        )

        assert pattern.pattern == "test.py"
        assert pattern.is_negated is True
        assert pattern.is_directory_only is True
        assert pattern.is_path_pattern is True
        assert pattern.regex is None
        assert pattern.name_pattern == "*.py"
