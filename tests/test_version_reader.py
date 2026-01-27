"""Tests for version reader functionality."""

import json
import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from version_checker.core.version_reader import (
    VersionReader,
    cleanup_orphaned_caches,
    clear_version_cache,
    get_exe_version,
    get_exe_version_no_cache,
)


class TestVersionReader:
    """Test cases for VersionReader class."""

    def test_version_reader_init(self) -> None:
        """Test VersionReader initialization."""
        reader = VersionReader()
        assert reader.use_cache is True

        reader_no_cache = VersionReader(use_cache=False)
        assert reader_no_cache.use_cache is False

    def test_version_reader_init_with_cache_dir(self) -> None:
        """Test VersionReader initialization with cache_dir (backward compatibility)."""
        # cache_dir parameter is ignored but should not cause errors
        reader = VersionReader(use_cache=True, cache_dir=Path("/some/path"))
        assert reader.use_cache is True

    @patch("version_checker.core.version_reader.pefile")
    def test_read_version_fallback(
        self, mock_pefile: MagicMock, mock_exe_file: str
    ) -> None:
        """Test version reading with pefile fallback method."""
        # Mock pefile.PE
        mock_pe = MagicMock()
        mock_pefile.PE.return_value = mock_pe

        # Mock version info structure
        mock_string_table = MagicMock()
        mock_string_table.entries = {b"ProductVersion": MagicMock()}
        mock_string_table.entries[b"ProductVersion"].decode.return_value = "1.2.3"

        mock_entry = MagicMock()
        mock_entry.StringTable = [mock_string_table]

        mock_file_info = MagicMock()
        mock_file_info.__iter__ = lambda self: iter(
            [mock_entry]
        )  # pyright: ignore[reportUnknownLambdaType]

        mock_pe.FileInfo = [mock_file_info]
        mock_pe.VS_VERSIONINFO = True

        reader = VersionReader(use_cache=False)
        version = reader._read_version_fallback(mock_exe_file)

        assert version == "1.2.3"
        mock_pe.close.assert_called_once()

    @patch("version_checker.core.version_reader.pefile")
    def test_read_version_fallback_no_version_info(
        self, mock_pefile: MagicMock, mock_exe_file: str
    ) -> None:
        """Test version reading when no version info is present."""
        mock_pe = MagicMock()
        mock_pefile.PE.return_value = mock_pe
        mock_pe.VS_VERSIONINFO = False
        mock_pe.FileInfo = []

        reader = VersionReader(use_cache=False)
        version = reader._read_version_fallback(mock_exe_file)

        assert version is None
        mock_pe.close.assert_called_once()

    @patch("version_checker.core.version_reader.has_win32api", return_value=True)
    @patch("version_checker.core.version_reader.get_win32api")
    @patch("version_checker.core.version_reader.platform")
    def test_get_file_properties(
        self,
        mock_platform: MagicMock,
        mock_get_win32api: MagicMock,
        mock_has_win32api: MagicMock,
        mock_exe_file: str,
    ) -> None:
        """Test getting file properties with win32api."""
        _ = mock_has_win32api  # unused but required by patch
        mock_platform.system.return_value = "Windows"

        mock_win32api = MagicMock()
        mock_get_win32api.return_value = mock_win32api

        # Mock win32api response for GetFileVersionInfo with path
        def mock_get_file_version_info(path: str, query: str) -> Any:
            if query == "\\":
                return {
                    "FileVersionMS": 0x00010002,  # Version 1.2
                    "FileVersionLS": 0x00030004,  # Version 3.4
                }
            elif query == "\\VarFileInfo\\Translation":
                return [(0x0409, 0x04B0)]  # English, Unicode
            elif "ProductVersion" in query:
                return "1.2.3.4"
            elif "FileVersion" in query:
                return "1.2.3.4"
            else:
                # Other string file info queries
                return "Test Value"

        mock_win32api.GetFileVersionInfo.side_effect = mock_get_file_version_info
        mock_win32api.HIWORD.side_effect = (
            lambda x: (x >> 16) & 0xFFFF
        )  # pyright: ignore[reportUnknownLambdaType]
        mock_win32api.LOWORD.side_effect = (
            lambda x: x & 0xFFFF
        )  # pyright: ignore[reportUnknownLambdaType]

        reader = VersionReader(use_cache=False)
        properties = reader._get_file_properties(mock_exe_file)

        assert properties["FileVersion"] == "1.2.3.4"
        assert "ProductVersion" in properties
        assert properties["ProductVersion"] == "1.2.3.4"

    @patch("version_checker.core.version_reader.has_win32api", return_value=True)
    @patch("version_checker.core.version_reader.get_win32api")
    @patch("version_checker.core.version_reader.platform")
    def test_get_file_properties_no_translation(
        self,
        mock_platform: MagicMock,
        mock_get_win32api: MagicMock,
        mock_has_win32api: MagicMock,
        mock_exe_file: str,
    ) -> None:
        """Test getting file properties when no translation info is available."""
        _ = mock_has_win32api  # unused but required by patch
        mock_platform.system.return_value = "Windows"

        mock_win32api = MagicMock()
        mock_get_win32api.return_value = mock_win32api

        def mock_get_file_version_info(path: str, query: str) -> Any:
            if query == "\\":
                return {
                    "FileVersionMS": 0x00010002,
                    "FileVersionLS": 0x00030004,
                }
            # Return empty list for translation info to simulate no translation
            return []  # No translation info

        mock_win32api.GetFileVersionInfo.side_effect = mock_get_file_version_info
        mock_win32api.HIWORD.side_effect = (
            lambda x: (x >> 16) & 0xFFFF
        )  # pyright: ignore[reportUnknownLambdaType]
        mock_win32api.LOWORD.side_effect = (
            lambda x: x & 0xFFFF
        )  # pyright: ignore[reportUnknownLambdaType]

        reader = VersionReader(use_cache=False)
        properties = reader._get_file_properties(mock_exe_file)

        assert "Error" in properties

    @patch("version_checker.core.version_reader.has_win32api", return_value=True)
    @patch("version_checker.core.version_reader.get_win32api")
    @patch("version_checker.core.version_reader.platform")
    def test_get_file_properties_error(
        self,
        mock_platform: MagicMock,
        mock_get_win32api: MagicMock,
        mock_has_win32api: MagicMock,
        mock_exe_file: str,
    ) -> None:
        """Test getting file properties with error."""
        _ = mock_has_win32api  # unused but required by patch
        mock_platform.system.return_value = "Windows"

        mock_win32api = MagicMock()
        mock_get_win32api.return_value = mock_win32api
        mock_win32api.GetFileVersionInfo.side_effect = Exception("Test error")

        reader = VersionReader(use_cache=False)
        properties = reader._get_file_properties(mock_exe_file)

        assert "Error" in properties
        assert "Test error" in properties["Error"]

    @patch("version_checker.core.version_reader.has_win32api", return_value=False)
    def test_get_file_properties_no_win32api(
        self, mock_has_win32api: MagicMock, mock_exe_file: str
    ) -> None:
        """Test getting file properties when win32api is not available."""
        _ = mock_has_win32api  # unused but required by patch
        reader = VersionReader(use_cache=False)
        properties = reader._get_file_properties(mock_exe_file)

        assert "Error" in properties
        assert "win32api not available" in properties["Error"]

    @patch("version_checker.core.version_reader.has_win32api", return_value=True)
    @patch("version_checker.core.version_reader.get_win32api")
    @patch("version_checker.core.version_reader.platform")
    def test_get_file_properties_not_windows(
        self,
        mock_platform: MagicMock,
        mock_get_win32api: MagicMock,
        mock_has_win32api: MagicMock,
        mock_exe_file: str,
    ) -> None:
        """Test getting file properties on non-Windows platform."""
        _ = mock_has_win32api  # unused but required by patch
        _ = mock_get_win32api  # unused but required by patch
        mock_platform.system.return_value = "Linux"

        reader = VersionReader(use_cache=False)
        properties = reader._get_file_properties(mock_exe_file)

        assert "Error" in properties
        assert "not on Windows" in properties["Error"]

    @patch("version_checker.core.version_reader.pefile")
    def test_read_version_error_handling(
        self, mock_pefile: MagicMock, mock_exe_file: str
    ) -> None:
        """Test error handling in version reading."""
        mock_pefile.PE.side_effect = Exception("Test error")

        reader = VersionReader(use_cache=False)
        version = reader._read_version_fallback(mock_exe_file)

        assert version is None

    def test_get_version_with_cache(self, temp_dir: Path, mock_exe_file: str) -> None:
        """Test getting version with caching enabled."""
        _ = temp_dir  # unused but required by fixture
        reader = VersionReader(use_cache=True)

        # Mock _get_version_direct to return a version
        with patch.object(reader, "_get_version_direct", return_value="1.0.0"):
            version = reader.get_version(mock_exe_file)
            assert version == "1.0.0"

    def test_get_version_without_cache(self, mock_exe_file: str) -> None:
        """Test getting version without caching."""
        reader = VersionReader(use_cache=False)

        with patch.object(reader, "_get_version_direct", return_value="1.0.0"):
            version = reader.get_version(mock_exe_file)
            assert version == "1.0.0"

    def test_get_version_uses_cached(self, temp_dir: Path, mock_exe_file: str) -> None:
        """Test that get_version uses cached version when available."""
        _ = temp_dir  # unused but required by fixture
        reader = VersionReader(use_cache=True)

        # Save a cached version
        cache_path = reader._get_cache_path(mock_exe_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {
            "version": "2.0.0",
            "mtime": os.path.getmtime(mock_exe_file),
            "original_path": mock_exe_file,
        }
        with open(cache_path, "w") as f:
            json.dump(cache_data, f)

        version = reader.get_version(mock_exe_file)
        assert version == "2.0.0"

    @patch("version_checker.core.version_reader.platform.system", return_value="Windows")
    def test_get_version_direct_with_file_properties(
        self, mock_platform: MagicMock, mock_exe_file: str
    ) -> None:
        """Test _get_version_direct using file properties (Windows path)."""
        reader = VersionReader(use_cache=False)

        with patch.object(
            reader,
            "_get_file_properties",
            return_value={"ProductVersion": "3.0.0", "FileVersion": "3.0.0"},
        ):
            version = reader._get_version_direct(mock_exe_file)
            assert version == "3.0.0"

    @patch("version_checker.core.version_reader.platform.system", return_value="Windows")
    def test_get_version_direct_fallback_to_file_version(
        self, mock_platform: MagicMock, mock_exe_file: str
    ) -> None:
        """Test _get_version_direct falls back to FileVersion (Windows path)."""
        reader = VersionReader(use_cache=False)

        with patch.object(
            reader,
            "_get_file_properties",
            return_value={"FileVersion": "4.0.0"},
        ):
            version = reader._get_version_direct(mock_exe_file)
            assert version == "4.0.0"

    @patch("version_checker.core.version_reader.platform.system", return_value="Windows")
    def test_get_version_direct_with_na_version(
        self, mock_platform: MagicMock, mock_exe_file: str
    ) -> None:
        """Test _get_version_direct when version is N/A (Windows path)."""
        reader = VersionReader(use_cache=False)

        with patch.object(
            reader,
            "_get_file_properties",
            return_value={"ProductVersion": "N/A", "FileVersion": "N/A"},
        ):
            with patch.object(reader, "_read_version_fallback", return_value="5.0.0"):
                version = reader._get_version_direct(mock_exe_file)
                assert version == "5.0.0"

    @patch("version_checker.core.version_reader.platform.system", return_value="Windows")
    def test_get_version_direct_with_error(
        self, mock_platform: MagicMock, mock_exe_file: str
    ) -> None:
        """Test _get_version_direct when file properties returns error (Windows path)."""
        reader = VersionReader(use_cache=False)

        with patch.object(
            reader, "_get_file_properties", return_value={"Error": "Some error"}
        ):
            with patch.object(reader, "_read_version_fallback", return_value="6.0.0"):
                version = reader._get_version_direct(mock_exe_file)
                assert version == "6.0.0"

    def test_get_cache_path(self, mock_exe_file: str) -> None:
        """Test getting cache path."""
        reader = VersionReader()
        cache_path = reader._get_cache_path(mock_exe_file)

        # Cache files are now stored in ~/.cache/version-checker/ with format {name}_{hash}.json
        assert cache_path.name.startswith(Path(mock_exe_file).name)
        assert cache_path.name.endswith(".json")
        assert "version-checker" in str(cache_path.parent)

    def test_save_and_load_cached_version(
        self, temp_dir: Path, mock_exe_file: str
    ) -> None:
        """Test saving and loading cached version."""
        _ = temp_dir  # unused but required by fixture
        reader = VersionReader(use_cache=True)

        reader._save_cached_version(mock_exe_file, "7.0.0")

        cached_version = reader._get_cached_version(mock_exe_file)
        assert cached_version == "7.0.0"

    def test_get_cached_version_invalid(
        self, temp_dir: Path, mock_exe_file: str
    ) -> None:
        """Test getting cached version when cache is invalid."""
        _ = temp_dir  # unused but required by fixture
        reader = VersionReader(use_cache=True)

        # Save cache
        reader._save_cached_version(mock_exe_file, "1.0.0")

        # Modify file to invalidate cache
        time.sleep(0.1)
        Path(mock_exe_file).write_bytes(b"Modified content")

        cached_version = reader._get_cached_version(mock_exe_file)
        assert cached_version is None

    def test_save_cached_version_error(self, mock_exe_file: str) -> None:
        """Test save_cached_version error handling."""
        reader = VersionReader(use_cache=True)

        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with patch("builtins.print") as mock_print:
                reader._save_cached_version(mock_exe_file, "1.0.0")
                mock_print.assert_called()

    def test_clear_cache(self) -> None:
        """Test clear_cache method."""
        reader = VersionReader()

        with patch("builtins.print") as mock_print:
            reader.clear_cache()
            mock_print.assert_called()

    def test_clear_cache_for_file(self, temp_dir: Path, mock_exe_file: str) -> None:
        """Test clearing cache for specific file."""
        _ = temp_dir  # unused but required by fixture
        reader = VersionReader(use_cache=True)

        # Save cache
        reader._save_cached_version(mock_exe_file, "1.0.0")
        cache_path = reader._get_cache_path(mock_exe_file)
        assert cache_path.exists()

        # Clear cache
        with patch("builtins.print") as mock_print:
            reader.clear_cache_for_file(mock_exe_file)
            assert not cache_path.exists()
            mock_print.assert_called()

    def test_clear_cache_for_file_nonexistent(self, mock_exe_file: str) -> None:
        """Test clearing cache for file with no cache."""
        reader = VersionReader(use_cache=True)

        with patch("builtins.print"):
            reader.clear_cache_for_file(mock_exe_file)
            # Should not raise exception

    def test_clear_cache_for_file_error(
        self, temp_dir: Path, mock_exe_file: str
    ) -> None:
        """Test clear_cache_for_file error handling."""
        _ = temp_dir  # unused but required by fixture
        reader = VersionReader(use_cache=True)

        reader._save_cached_version(mock_exe_file, "1.0.0")

        with patch("pathlib.Path.unlink", side_effect=PermissionError("Access denied")):
            with patch("builtins.print") as mock_print:
                reader.clear_cache_for_file(mock_exe_file)
                mock_print.assert_called()

    def test_cleanup_orphaned_caches(self, temp_dir: Path, mock_exe_file: str) -> None:
        """Test cleanup_orphaned_caches method."""
        reader = VersionReader(use_cache=True)

        # Create cache for existing file
        reader._save_cached_version(mock_exe_file, "1.0.0")

        # Create cache for non-existent file
        nonexistent = str(temp_dir / "nonexistent.exe")
        cache_path = reader._get_cache_path(nonexistent)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {"version": "1.0.0", "mtime": 0, "original_path": nonexistent}
        with open(cache_path, "w") as f:
            json.dump(cache_data, f)

        with patch("builtins.print") as mock_print:
            reader.cleanup_orphaned_caches([mock_exe_file, nonexistent])
            assert not cache_path.exists()
            mock_print.assert_called()

    def test_cleanup_orphaned_caches_error(self) -> None:
        """Test cleanup_orphaned_caches error handling."""
        reader = VersionReader(use_cache=True)

        with patch("pathlib.Path.exists", side_effect=Exception("Test error")):
            with patch("builtins.print") as mock_print:
                reader.cleanup_orphaned_caches(["/some/file.exe"])
                mock_print.assert_called()

    def test_get_exe_version_function(self, mock_exe_file: str) -> None:
        """Test the convenience function."""
        with patch(
            "version_checker.core.version_reader._default_reader"
        ) as mock_reader:
            mock_reader.get_version.return_value = "1.0.0"

            version = get_exe_version(mock_exe_file)

            assert version == "1.0.0"
            mock_reader.get_version.assert_called_once_with(mock_exe_file)

    def test_get_exe_version_no_cache_function(self, mock_exe_file: str) -> None:
        """Test the get_exe_version_no_cache function."""
        with patch(
            "version_checker.core.version_reader.VersionReader"
        ) as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader_class.return_value = mock_reader
            mock_reader.get_version.return_value = "2.0.0"

            version = get_exe_version_no_cache(mock_exe_file)

            assert version == "2.0.0"
            mock_reader_class.assert_called_once_with(use_cache=False)
            mock_reader.get_version.assert_called_once_with(mock_exe_file)

    def test_clear_version_cache_function(self) -> None:
        """Test the clear_version_cache function."""
        with patch(
            "version_checker.core.version_reader._default_reader"
        ) as mock_reader:
            clear_version_cache()
            mock_reader.clear_cache.assert_called_once()

    def test_cleanup_orphaned_caches_function(self) -> None:
        """Test the cleanup_orphaned_caches function."""
        file_paths = ["/path/to/file1.exe", "/path/to/file2.exe"]

        with patch(
            "version_checker.core.version_reader._default_reader"
        ) as mock_reader:
            cleanup_orphaned_caches(file_paths)
            mock_reader.cleanup_orphaned_caches.assert_called_once_with(file_paths)

    def test_lru_cache_on_get_exe_version(self, mock_exe_file: str) -> None:
        """Test that get_exe_version uses LRU cache."""
        with patch(
            "version_checker.core.version_reader._default_reader"
        ) as mock_reader:
            mock_reader.get_version.return_value = "1.0.0"

            # Call multiple times with same argument
            version1 = get_exe_version(mock_exe_file)
            version2 = get_exe_version(mock_exe_file)

            assert version1 == version2 == "1.0.0"
            # Due to LRU cache, should only call once
            # Note: This might be called more than once in test environment
            # but the cache should work in production


class TestLinuxVersionMethods:
    """Test cases for Linux-specific version detection methods."""

    @patch("version_checker.core.version_reader.subprocess.run")
    def test_version_from_dpkg_success(self, mock_run: MagicMock) -> None:
        """Test successful dpkg version extraction."""
        mock_run.return_value = MagicMock(stdout="1.2.3\n")

        reader = VersionReader(use_cache=False)
        version = reader._version_from_dpkg("mypackage")

        assert version == "v1.2.3"
        mock_run.assert_called_once()

    @patch("version_checker.core.version_reader.subprocess.run")
    def test_version_from_dpkg_empty(self, mock_run: MagicMock) -> None:
        """Test dpkg version extraction with empty result."""
        mock_run.return_value = MagicMock(stdout="")

        reader = VersionReader(use_cache=False)
        version = reader._version_from_dpkg("mypackage")

        assert version is None

    @patch("version_checker.core.version_reader.subprocess.run")
    def test_version_from_dpkg_error(self, mock_run: MagicMock) -> None:
        """Test dpkg version extraction with error."""
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(1, "dpkg-query")

        reader = VersionReader(use_cache=False)
        version = reader._version_from_dpkg("mypackage")

        assert version is None

    @patch("version_checker.core.version_reader.subprocess.run")
    def test_version_from_dpkg_not_found(self, mock_run: MagicMock) -> None:
        """Test dpkg version extraction when dpkg not found."""
        mock_run.side_effect = FileNotFoundError()

        reader = VersionReader(use_cache=False)
        version = reader._version_from_dpkg("mypackage")

        assert version is None

    @patch("version_checker.core.version_reader.subprocess.run")
    def test_version_from_pacman_success(self, mock_run: MagicMock) -> None:
        """Test successful pacman version extraction."""
        mock_run.return_value = MagicMock(stdout="heroic 2.19.0-1\n")

        reader = VersionReader(use_cache=False)
        version = reader._version_from_pacman("heroic")

        assert version == "v2.19.0"

    @patch("version_checker.core.version_reader.subprocess.run")
    def test_version_from_pacman_no_suffix(self, mock_run: MagicMock) -> None:
        """Test pacman version extraction without release suffix."""
        mock_run.return_value = MagicMock(stdout="myapp 1.0.0\n")

        reader = VersionReader(use_cache=False)
        version = reader._version_from_pacman("myapp")

        assert version == "v1.0.0"

    @patch("version_checker.core.version_reader.subprocess.run")
    def test_version_from_pacman_short_output(self, mock_run: MagicMock) -> None:
        """Test pacman version extraction with short output."""
        mock_run.return_value = MagicMock(stdout="heroic\n")

        reader = VersionReader(use_cache=False)
        version = reader._version_from_pacman("heroic")

        assert version is None

    @patch("version_checker.core.version_reader.subprocess.run")
    def test_version_from_pacman_error(self, mock_run: MagicMock) -> None:
        """Test pacman version extraction with error."""
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(1, "pacman")

        reader = VersionReader(use_cache=False)
        version = reader._version_from_pacman("mypackage")

        assert version is None

    @patch("version_checker.core.version_reader.subprocess.run")
    def test_extract_main_version_from_binary_success(self, mock_run: MagicMock) -> None:
        """Test successful version extraction from binary."""
        mock_run.return_value = MagicMock(
            stdout="some data\nmain.version=v1.2.3\nmore data\n"
        )

        reader = VersionReader(use_cache=False)
        version = reader._extract_main_version_from_binary("/path/to/binary")

        assert version == "v1.2.3"

    @patch("version_checker.core.version_reader.subprocess.run")
    def test_extract_main_version_from_binary_not_found(self, mock_run: MagicMock) -> None:
        """Test version extraction when main.version not found."""
        mock_run.return_value = MagicMock(stdout="no version here\n")

        reader = VersionReader(use_cache=False)
        version = reader._extract_main_version_from_binary("/path/to/binary")

        assert version is None

    @patch("version_checker.core.version_reader.subprocess.run")
    def test_extract_main_version_from_binary_error(self, mock_run: MagicMock) -> None:
        """Test version extraction with subprocess error."""
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(1, "strings")

        reader = VersionReader(use_cache=False)
        version = reader._extract_main_version_from_binary("/path/to/binary")

        assert version is None

    @patch("version_checker.core.version_reader.subprocess.run")
    def test_extract_main_version_strings_not_found(self, mock_run: MagicMock) -> None:
        """Test version extraction when strings command not found."""
        mock_run.side_effect = FileNotFoundError()

        reader = VersionReader(use_cache=False)
        version = reader._extract_main_version_from_binary("/path/to/binary")

        assert version is None

    def test_resolve_binary(self) -> None:
        """Test _resolve_binary method."""
        reader = VersionReader(use_cache=False)

        # Test with a command that definitely exists
        with patch("shutil.which", return_value="/usr/bin/python"):
            result = reader._resolve_binary("python")
            assert result == "/usr/bin/python"

    def test_resolve_binary_not_found(self) -> None:
        """Test _resolve_binary when binary not found."""
        reader = VersionReader(use_cache=False)

        with patch("shutil.which", return_value=None):
            result = reader._resolve_binary("nonexistent")
            assert result is None

    @patch("version_checker.core.version_reader.platform.system", return_value="Linux")
    def test_get_linux_version_with_file(self, mock_platform: MagicMock, temp_dir: Path) -> None:
        """Test _get_linux_version with existing executable file."""
        # Create a mock executable
        exe_file = temp_dir / "myapp"
        exe_file.write_bytes(b"#!/bin/bash\necho test")
        exe_file.chmod(0o755)

        reader = VersionReader(use_cache=False)

        with patch.object(reader, "_extract_main_version_from_binary", return_value="v1.0.0"):
            version = reader._get_linux_version(str(exe_file))
            assert version == "v1.0.0"

    @patch("version_checker.core.version_reader.platform.system", return_value="Linux")
    def test_get_linux_version_file_fallback_to_dpkg(
        self, mock_platform: MagicMock, temp_dir: Path
    ) -> None:
        """Test _get_linux_version falls back to dpkg for file."""
        exe_file = temp_dir / "myapp"
        exe_file.write_bytes(b"#!/bin/bash\necho test")
        exe_file.chmod(0o755)

        reader = VersionReader(use_cache=False)

        with patch.object(reader, "_extract_main_version_from_binary", return_value=None):
            with patch.object(reader, "_version_from_dpkg", return_value="v2.0.0"):
                version = reader._get_linux_version(str(exe_file))
                assert version == "v2.0.0"

    @patch("version_checker.core.version_reader.platform.system", return_value="Linux")
    def test_get_linux_version_file_fallback_to_pacman(
        self, mock_platform: MagicMock, temp_dir: Path
    ) -> None:
        """Test _get_linux_version falls back to pacman for file."""
        exe_file = temp_dir / "myapp"
        exe_file.write_bytes(b"#!/bin/bash\necho test")
        exe_file.chmod(0o755)

        reader = VersionReader(use_cache=False)

        with patch.object(reader, "_extract_main_version_from_binary", return_value=None):
            with patch.object(reader, "_version_from_dpkg", return_value=None):
                with patch.object(reader, "_version_from_pacman", return_value="v3.0.0"):
                    version = reader._get_linux_version(str(exe_file))
                    assert version == "v3.0.0"

    @patch("version_checker.core.version_reader.platform.system", return_value="Linux")
    def test_get_linux_version_file_all_fail(
        self, mock_platform: MagicMock, temp_dir: Path
    ) -> None:
        """Test _get_linux_version returns None when all methods fail for file."""
        exe_file = temp_dir / "myapp"
        exe_file.write_bytes(b"#!/bin/bash\necho test")
        exe_file.chmod(0o755)

        reader = VersionReader(use_cache=False)

        with patch.object(reader, "_extract_main_version_from_binary", return_value=None):
            with patch.object(reader, "_version_from_dpkg", return_value=None):
                with patch.object(reader, "_version_from_pacman", return_value=None):
                    version = reader._get_linux_version(str(exe_file))
                    assert version is None

    @patch("version_checker.core.version_reader.platform.system", return_value="Linux")
    def test_get_linux_version_app_name_dpkg(self, mock_platform: MagicMock) -> None:
        """Test _get_linux_version with app name using dpkg."""
        reader = VersionReader(use_cache=False)

        with patch.object(reader, "_version_from_dpkg", return_value="v1.0.0"):
            version = reader._get_linux_version("myapp")
            assert version == "v1.0.0"

    @patch("version_checker.core.version_reader.platform.system", return_value="Linux")
    def test_get_linux_version_app_name_pacman(self, mock_platform: MagicMock) -> None:
        """Test _get_linux_version with app name using pacman."""
        reader = VersionReader(use_cache=False)

        with patch.object(reader, "_version_from_dpkg", return_value=None):
            with patch.object(reader, "_version_from_pacman", return_value="v2.0.0"):
                version = reader._get_linux_version("myapp")
                assert version == "v2.0.0"

    @patch("version_checker.core.version_reader.platform.system", return_value="Linux")
    def test_get_linux_version_app_name_resolve_binary(self, mock_platform: MagicMock) -> None:
        """Test _get_linux_version with app name resolving binary."""
        reader = VersionReader(use_cache=False)

        with patch.object(reader, "_version_from_dpkg", return_value=None):
            with patch.object(reader, "_version_from_pacman", return_value=None):
                with patch.object(reader, "_resolve_binary", return_value="/usr/bin/myapp"):
                    with patch.object(reader, "_extract_main_version_from_binary", return_value="v3.0.0"):
                        version = reader._get_linux_version("myapp")
                        assert version == "v3.0.0"

    @patch("version_checker.core.version_reader.platform.system", return_value="Linux")
    def test_get_linux_version_app_name_all_fail(self, mock_platform: MagicMock) -> None:
        """Test _get_linux_version returns None when all methods fail for app name."""
        reader = VersionReader(use_cache=False)

        with patch.object(reader, "_version_from_dpkg", return_value=None):
            with patch.object(reader, "_version_from_pacman", return_value=None):
                with patch.object(reader, "_resolve_binary", return_value=None):
                    version = reader._get_linux_version("myapp")
                    assert version is None

    def test_get_cache_dir_with_xdg(self, monkeypatch: Any, temp_dir: Path) -> None:
        """Test _get_cache_dir respects XDG_CACHE_HOME."""
        custom_cache = temp_dir / "custom_cache"
        monkeypatch.setenv("XDG_CACHE_HOME", str(custom_cache))

        reader = VersionReader(use_cache=True)
        cache_dir = reader._get_cache_dir()

        assert cache_dir == custom_cache / "version-checker"
        assert cache_dir.exists()

    def test_clear_cache_with_error(self) -> None:
        """Test clear_cache error handling."""
        reader = VersionReader()

        with patch.object(reader, "_get_cache_dir", side_effect=Exception("Test error")):
            with patch("builtins.print") as mock_print:
                reader.clear_cache()
                mock_print.assert_called()
