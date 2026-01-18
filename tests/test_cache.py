"""Tests for caching utilities."""

import json
import time
from pathlib import Path
from unittest.mock import patch


from version_checker.utils.cache import VersionCache


class TestVersionCache:
    """Test cases for VersionCache class."""

    def test_cache_init_default(self):
        """Test VersionCache initialization with defaults."""
        cache = VersionCache()

        assert cache.cache_suffix == ".version_cache"
        assert cache.cache_dir == Path.home() / ".version_checker_cache"
        assert cache.cache_dir.exists()

    def test_cache_init_custom_suffix(self):
        """Test VersionCache initialization with custom suffix."""
        cache = VersionCache(cache_suffix=".custom_cache")

        assert cache.cache_suffix == ".custom_cache"

    def test_cache_dir_creation(self, temp_dir, monkeypatch):
        """Test that cache directory is created if it doesn't exist."""
        cache_dir = temp_dir / "test_cache"

        with patch("pathlib.Path.home", return_value=temp_dir):
            cache = VersionCache()
            # Override cache_dir for testing
            cache.cache_dir = cache_dir
            cache.cache_dir.mkdir(exist_ok=True)

            assert cache_dir.exists()
            assert cache_dir.is_dir()

    def test_get_cache_path(self, temp_dir):
        """Test getting cache path for a file."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        file_path = "/path/to/software.exe"
        cache_path = cache.get_cache_path(file_path)

        assert cache_path.parent == temp_dir
        assert cache_path.name.endswith(".version_cache")
        # Should be a hash of the file path
        assert len(cache_path.stem) == 32  # MD5 hash length

    def test_get_cache_path_consistent(self, temp_dir):
        """Test that same file path always gives same cache path."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        file_path = "/path/to/software.exe"
        cache_path1 = cache.get_cache_path(file_path)
        cache_path2 = cache.get_cache_path(file_path)

        assert cache_path1 == cache_path2

    def test_get_cache_path_different_files(self, temp_dir):
        """Test that different file paths give different cache paths."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        file_path1 = "/path/to/software1.exe"
        file_path2 = "/path/to/software2.exe"

        cache_path1 = cache.get_cache_path(file_path1)
        cache_path2 = cache.get_cache_path(file_path2)

        assert cache_path1 != cache_path2

    def test_save_and_load_cache(self, temp_dir, mock_exe_file):
        """Test saving and loading cache data."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        version = "1.2.3"
        cache.save_cache(mock_exe_file, version)

        # Load the cache
        cache_data = cache.load_cache(mock_exe_file)

        assert cache_data is not None
        assert cache_data["version"] == version
        assert "mtime" in cache_data
        assert cache_data["original_path"] == mock_exe_file

    def test_load_cache_nonexistent(self, temp_dir):
        """Test loading cache for non-existent cache file."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        cache_data = cache.load_cache("/nonexistent/file.exe")

        assert cache_data is None

    def test_load_cache_invalid_json(self, temp_dir):
        """Test loading cache with invalid JSON."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        file_path = "/path/to/software.exe"
        cache_path = cache.get_cache_path(file_path)

        # Write invalid JSON
        cache_path.write_text("invalid json {")

        cache_data = cache.load_cache(file_path)

        assert cache_data is None

    def test_load_cache_non_dict(self, temp_dir):
        """Test loading cache that doesn't contain a dict."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        file_path = "/path/to/software.exe"
        cache_path = cache.get_cache_path(file_path)

        # Write a list instead of dict
        cache_path.write_text(json.dumps(["not", "a", "dict"]))

        cache_data = cache.load_cache(file_path)

        assert cache_data is None

    def test_is_cache_valid_fresh(self, temp_dir, mock_exe_file):
        """Test cache validity for fresh cache."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        cache.save_cache(mock_exe_file, "1.0.0")

        assert cache.is_cache_valid(mock_exe_file) is True

    def test_is_cache_valid_nonexistent(self, temp_dir):
        """Test cache validity for non-existent cache."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        assert cache.is_cache_valid("/nonexistent/file.exe") is False

    def test_is_cache_valid_modified_file(self, temp_dir, mock_exe_file):
        """Test cache validity when file has been modified."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        # Save cache
        cache.save_cache(mock_exe_file, "1.0.0")

        # Modify the file
        time.sleep(0.1)  # Ensure mtime changes
        Path(mock_exe_file).write_bytes(b"Modified content")

        # Cache should be invalid now
        assert cache.is_cache_valid(mock_exe_file) is False

    def test_is_cache_valid_corrupted_cache(self, temp_dir, mock_exe_file):
        """Test cache validity with corrupted cache file."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        # Create corrupted cache
        cache_path = cache.get_cache_path(mock_exe_file)
        cache_path.write_text("corrupted")

        assert cache.is_cache_valid(mock_exe_file) is False

    def test_get_cached_version_valid(self, temp_dir, mock_exe_file):
        """Test getting cached version when cache is valid."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        version = "2.3.4"
        cache.save_cache(mock_exe_file, version)

        cached_version = cache.get_cached_version(mock_exe_file)

        assert cached_version == version

    def test_get_cached_version_invalid(self, temp_dir, mock_exe_file):
        """Test getting cached version when cache is invalid."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        # Save cache
        cache.save_cache(mock_exe_file, "1.0.0")

        # Modify file to invalidate cache
        time.sleep(0.1)
        Path(mock_exe_file).write_bytes(b"Modified")

        cached_version = cache.get_cached_version(mock_exe_file)

        assert cached_version is None

    def test_get_cached_version_nonexistent(self, temp_dir):
        """Test getting cached version for non-existent cache."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        cached_version = cache.get_cached_version("/nonexistent/file.exe")

        assert cached_version is None

    def test_save_cache_error_handling(self, temp_dir):
        """Test save_cache error handling."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        # Try to save cache for non-existent file (should handle gracefully)
        with patch("builtins.print") as mock_print:
            cache.save_cache("/nonexistent/file.exe", "1.0.0")
            # Should print warning but not raise exception
            mock_print.assert_called()

    def test_cleanup_orphaned_caches(self, temp_dir, mock_exe_file):
        """Test cleaning up orphaned cache files."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        # Create cache for existing file
        cache.save_cache(mock_exe_file, "1.0.0")

        # Create cache for non-existent file
        nonexistent_file = "/path/to/nonexistent.exe"
        cache_path = cache.get_cache_path(nonexistent_file)
        cache_path.write_text(json.dumps({"version": "1.0.0", "mtime": 0}))

        # Cleanup orphaned caches
        with patch("builtins.print") as mock_print:
            cache.cleanup_orphaned_caches([mock_exe_file, nonexistent_file])

            # Should have cleaned up the orphaned cache
            assert not cache_path.exists()
            mock_print.assert_called()

    def test_cleanup_orphaned_caches_error_handling(self, temp_dir):
        """Test cleanup_orphaned_caches error handling."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        # Try to cleanup with invalid path
        with patch("builtins.print") as mock_print:
            cache.cleanup_orphaned_caches(["/invalid/path.exe"])
            # Should handle errors gracefully
            # May or may not print depending on implementation

    def test_clear_all_caches(self, temp_dir, mock_exe_file):
        """Test clearing all cache files."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        # Create multiple cache files
        cache.save_cache(mock_exe_file, "1.0.0")
        cache.save_cache("/another/file.exe", "2.0.0")

        # Clear all caches
        with patch("builtins.print") as mock_print:
            cache.clear_all_caches()

            # All cache files should be deleted
            cache_files = list(cache.cache_dir.glob(f"*{cache.cache_suffix}"))
            assert len(cache_files) == 0
            mock_print.assert_called()

    def test_clear_all_caches_empty_dir(self, temp_dir):
        """Test clearing all caches when directory is empty."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        with patch("builtins.print") as mock_print:
            cache.clear_all_caches()
            mock_print.assert_called()

    def test_clear_all_caches_error_handling(self, temp_dir):
        """Test clear_all_caches error handling."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        # Create a cache file
        cache_path = cache.cache_dir / "test.version_cache"
        cache_path.write_text("test")

        # Make it read-only to cause deletion error
        with patch("pathlib.Path.unlink", side_effect=PermissionError("Access denied")):
            with patch("builtins.print") as mock_print:
                cache.clear_all_caches()
                # Should print warning
                mock_print.assert_called()

    def test_cache_data_structure(self, temp_dir, mock_exe_file):
        """Test that cache data has correct structure."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        version = "3.2.1"
        cache.save_cache(mock_exe_file, version)

        cache_path = cache.get_cache_path(mock_exe_file)
        with open(cache_path, "r") as f:
            cache_data = json.load(f)

        assert "version" in cache_data
        assert "mtime" in cache_data
        assert "original_path" in cache_data
        assert cache_data["version"] == version
        assert cache_data["original_path"] == mock_exe_file
        assert isinstance(cache_data["mtime"], (int, float))

    def test_multiple_cache_instances(self, temp_dir, mock_exe_file):
        """Test that multiple cache instances work correctly."""
        cache1 = VersionCache()
        cache1.cache_dir = temp_dir

        cache2 = VersionCache()
        cache2.cache_dir = temp_dir

        # Save with cache1
        cache1.save_cache(mock_exe_file, "1.0.0")

        # Load with cache2
        cached_version = cache2.get_cached_version(mock_exe_file)

        assert cached_version == "1.0.0"

    def test_cache_with_special_characters_in_path(self, temp_dir):
        """Test caching with special characters in file path."""
        cache = VersionCache()
        cache.cache_dir = temp_dir

        # File path with special characters
        file_path = "/path/to/my software (v2.0) [x64].exe"

        # Should handle special characters in path
        cache_path = cache.get_cache_path(file_path)
        assert cache_path.parent == temp_dir
        assert cache_path.name.endswith(".version_cache")
