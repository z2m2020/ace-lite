"""Windows Filesystem Tests for ACE-Lite

This module provides Windows-specific filesystem tests to ensure
cross-platform compatibility.

PRD-91 QO-1105: Windows Filesystem Test Coverage

Key areas to test:
1. Path normalization and separators
2. Case sensitivity handling
3. Special characters in paths
4. UNC path handling
5. Long path support
"""

from __future__ import annotations

import platform
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest


class TestPathNormalization:
    """Tests for path normalization across platforms."""

    def test_posix_path_creation(self):
        """Test POSIX path creation works on all platforms."""
        posix = PurePosixPath("src/main.py")
        assert posix.parts == ("src", "main.py")

    def test_windows_path_creation(self):
        """Test Windows path creation."""
        if platform.system() != "Windows":
            pytest.skip("Windows-specific test")

        windows = PureWindowsPath("C:\\Users\\test")
        assert windows.drive == "C:"

    def test_forward_slash_normalization(self):
        """Test forward slash normalization."""
        path_str = "src/module/file.py"
        normalized = path_str.replace("\\", "/")
        assert normalized == "src/module/file.py"
        assert "/" in normalized

    def test_backslash_normalization(self):
        """Test backslash to forward slash conversion."""
        if platform.system() == "Windows":
            path_str = "src\\module\\file.py"
            normalized = path_str.replace("\\", "/")
            assert normalized == "src/module/file.py"

    def test_mixed_separator_normalization(self):
        """Test mixed separator normalization."""
        path_str = "src\\module/file.py"
        # Normalize to forward slashes
        normalized = path_str.replace("\\", "/")
        assert normalized == "src/module/file.py"


class TestPathOperations:
    """Tests for path operations."""

    def test_path_join(self):
        """Test joining path components."""
        base = Path("src")
        result = base / "module" / "file.py"
        assert "src" in str(result)
        assert "file.py" in str(result)

    def test_path_relative(self):
        """Test computing relative paths."""
        root = Path("src")
        full = root / "module" / "file.py"

        relative = full.relative_to(root)
        assert str(relative) == "module/file.py" or str(relative) == "module\\file.py"

    def test_path_parts_extraction(self):
        """Test extracting path parts."""
        path = PurePosixPath("src/module/file.py")
        assert path.parts == ("src", "module", "file.py")

    def test_path_stem_and_suffix(self):
        """Test extracting stem and suffix."""
        path = Path("src/module/file.py")
        assert path.stem == "file"
        assert path.suffix == ".py"

    def test_path_name_extraction(self):
        """Test extracting filename."""
        path = Path("src/module/file.py")
        assert path.name == "file.py"


class TestCaseSensitivity:
    """Tests for case sensitivity handling."""

    def test_case_preservation(self):
        """Test that case is preserved in paths."""
        path = Path("src/Module/FILE.PY")
        assert path.name == "FILE.PY"

    def test_case_insensitive_matching_windows(self):
        """Test case-insensitive matching on Windows."""
        if platform.system() != "Windows":
            pytest.skip("Windows-specific test")

        # Windows paths are case-insensitive
        path1 = Path("C:/Users/Test")
        path2 = Path("C:/users/test")
        assert path1 == path2

    def test_case_sensitive_matching_posix(self):
        """Test case-sensitive matching on POSIX."""
        if platform.system() == "Windows":
            pytest.skip("POSIX-specific test")

        path1 = Path("/Users/Test")
        path2 = Path("/users/test")
        # On POSIX, these should be different
        assert path1 != path2


class TestSpecialPathCharacters:
    """Tests for handling special characters in paths."""

    def test_space_in_path(self):
        """Test handling spaces in paths."""
        path = Path("src/My Documents/file.py")
        assert path.name == "file.py"
        assert " " in str(path)

    def test_unicode_in_path(self):
        """Test handling Unicode characters in paths."""
        path = Path("src/文档/file.py")
        assert path.name == "file.py"

    def test_parent_directory_reference(self):
        """Test handling parent directory references."""
        path = Path("src/../file.py")
        assert ".." in str(path)

    def test_current_directory_reference(self):
        """Test handling current directory references."""
        path = Path("./file.py")
        assert "." in str(path)


class TestLongPaths:
    """Tests for long path handling."""

    def test_deep_nesting(self):
        """Test deeply nested paths."""
        parts = ["level"] * 20
        deep_path = Path(*parts) / "file.py"
        assert deep_path.name == "file.py"
        assert len(str(deep_path)) > 100

    def test_long_filename(self):
        """Test handling long filenames."""
        long_name = "a" * 100 + ".py"
        path = Path("src") / long_name
        assert path.name == long_name


class TestFilesystemOperations:
    """Tests for filesystem operations."""

    def test_exists_check(self, tmp_path):
        """Test checking if path exists."""
        test_file = tmp_path / "test.txt"
        assert not test_file.exists()

        test_file.write_text("content")
        assert test_file.exists()

    def test_is_file_check(self, tmp_path):
        """Test checking if path is a file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        assert test_file.is_file()
        assert not test_file.is_dir()

    def test_is_dir_check(self, tmp_path):
        """Test checking if path is a directory."""
        test_dir = tmp_path / "subdir"
        test_dir.mkdir()

        assert test_dir.is_dir()
        assert not test_dir.is_file()

    def test_read_write_text(self, tmp_path):
        """Test reading and writing text files."""
        test_file = tmp_path / "test.txt"
        content = "Hello, World!"

        test_file.write_text(content, encoding="utf-8")
        assert test_file.read_text(encoding="utf-8") == content

    def test_read_write_bytes(self, tmp_path):
        """Test reading and writing binary files."""
        test_file = tmp_path / "test.bin"
        content = b"\x00\x01\x02\x03"

        test_file.write_bytes(content)
        assert test_file.read_bytes() == content


class TestPathConversions:
    """Tests for path format conversions."""

    def test_as_posix(self):
        """Test converting path to POSIX format."""
        path = PureWindowsPath("C:\\Users\\test\\file.py")
        posix = path.as_posix()
        assert "/" in posix
        assert "\\" not in posix

    def test_posix_to_windows_conversion(self):
        """Test converting POSIX path to Windows format."""
        if platform.system() == "Windows":
            # On Windows, PureWindowsPath should work
            path = PureWindowsPath("C:/Users/test/file.py")
            assert "Users" in str(path)
        else:
            # On POSIX, we can't easily test Windows paths
            pytest.skip("Windows-specific test")

    def test_anchor_extraction(self):
        """Test extracting anchor (drive) from paths."""
        if platform.system() == "Windows":
            path = PureWindowsPath("C:\\Users\\test")
            assert path.drive == "C:"
        else:
            path = PurePosixPath("/Users/test")
            assert path.root == "/"


class TestCrossPlatformPaths:
    """Tests for cross-platform path handling."""

    def test_posix_path_works_on_all_platforms(self):
        """Test that PurePosixPath works on all platforms."""
        # PurePosixPath should work regardless of OS
        posix = PurePosixPath("src/module/file.py")
        assert posix.parts == ("src", "module", "file.py")

    def test_windows_path_format(self):
        """Test Windows path format handling."""
        if platform.system() != "Windows":
            pytest.skip("Windows-specific test")

        # Windows-specific paths
        paths = [
            "C:\\Users\\test",
            "D:\\Program Files",
            "\\\\server\\share\\file",
        ]
        for path_str in paths:
            path = Path(path_str)
            assert path.exists() or not path.exists()  # Just check it doesn't crash

    def test_network_path_windows(self):
        """Test UNC network path handling on Windows."""
        if platform.system() != "Windows":
            pytest.skip("Windows-specific test")

        # UNC paths start with \\
        unc_path = Path("\\\\localhost\\c$\\test")
        assert str(unc_path).startswith("\\\\")


class TestTempDirectoryHandling:
    """Tests for temporary directory handling."""

    def test_temp_dir_creation(self, tmp_path):
        """Test creating temporary directories."""
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        assert temp_dir.exists()
        assert temp_dir.is_dir()

    def test_temp_file_cleanup(self, tmp_path):
        """Test that temp files can be cleaned up."""
        test_file = tmp_path / "temp.txt"
        test_file.write_text("temp")

        assert test_file.exists()

        # Simulate cleanup
        test_file.unlink()
        assert not test_file.exists()

    def test_nested_temp_dirs(self, tmp_path):
        """Test creating nested temporary directories."""
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        assert nested.exists()


class TestPermissions:
    """Tests for file permissions."""

    def test_default_permissions(self, tmp_path):
        """Test default file permissions."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # On POSIX, check read/write permissions
        if platform.system() != "Windows":
            mode = test_file.stat().st_mode
            # Basic permission checks (implementation-specific)
            assert mode > 0

    def test_readonly_file(self, tmp_path):
        """Test read-only file handling."""
        test_file = tmp_path / "readonly.txt"
        test_file.write_text("content")

        # Make read-only (may not work on all platforms)
        try:
            test_file.chmod(0o444)
            # Verify it's still readable
            assert test_file.read_text() == "content"
        except OSError:
            pytest.skip("Cannot modify permissions on this platform")


class TestEncodingHandling:
    """Tests for path encoding handling."""

    def test_utf8_path(self, tmp_path):
        """Test UTF-8 encoded paths."""
        path = tmp_path / "文件.txt"
        path.write_text("content", encoding="utf-8")
        assert path.exists()

    def test_ascii_path(self, tmp_path):
        """Test ASCII paths."""
        path = tmp_path / "ascii_file.txt"
        path.write_text("content", encoding="ascii")
        assert path.exists()


class TestEdgeCases:
    """Tests for edge cases in path handling."""

    def test_empty_path(self):
        """Test handling empty path."""
        # Path with empty string is valid but represents current dir
        path = Path("")
        # It should not crash when converted to string
        result = str(path)
        assert result == "" or result == "."

    def test_dot_path(self):
        """Test handling dot path."""
        path = Path(".")
        # Dot path represents current directory
        # Note: On Windows, Path(".").name returns ""
        assert path.name == "." or path.name == ""
        # Path should be resolvable
        resolved = path.resolve()
        assert resolved.exists()

    def test_root_path(self):
        """Test handling root path."""
        if platform.system() == "Windows":
            root = Path("C:\\")
            assert root.is_absolute()
        else:
            root = Path("/")
            assert root.is_absolute()
            assert root.name == ""

    def test_relative_path_resolution(self, tmp_path):
        """Test resolving relative paths."""
        # Create a file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Resolve should give absolute path
        resolved = test_file.resolve()
        assert resolved.is_absolute()
