"""Caching utilities for version information."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, cast


class VersionCache:
    """Handles caching of version information."""

    def __init__(self, cache_suffix: str = ".version_cache"):
        self.cache_suffix = cache_suffix
        # Create cache directory in user's home directory
        self.cache_dir = Path.home() / ".version_checker_cache"
        self.cache_dir.mkdir(exist_ok=True)

    def get_cache_path(self, file_path: str) -> Path:
        """Get the cache file path for a given executable."""
        # Create a hash of the file path to use as cache filename
        # This avoids issues with special characters and long paths
        file_hash = hashlib.md5(file_path.encode()).hexdigest()
        return self.cache_dir / f"{file_hash}{self.cache_suffix}"

    def is_cache_valid(self, file_path: str) -> bool:
        """Check if cache is valid (exists and file hasn't been modified)."""
        try:
            cache_path = self.get_cache_path(file_path)

            if not cache_path.exists():
                return False

            file_mtime = os.path.getmtime(file_path)
            cache_data = self.load_cache(file_path)

            if cache_data is None:
                return False

            return cache_data.get("mtime") == file_mtime
        except Exception:
            return False

    def load_cache(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Load cache data for a file."""
        try:
            cache_path = self.get_cache_path(file_path)

            if not cache_path.exists():
                return None

            with open(cache_path, "r", encoding="utf-8") as f:
                data: object = json.load(f)
                # Ensure we return a dict or None
                if isinstance(data, dict):
                    return cast(Dict[str, Any], data)
                return None
        except Exception:
            return None

    def save_cache(self, file_path: str, version: str) -> None:
        """Save version to cache."""
        try:
            cache_path = self.get_cache_path(file_path)
            file_mtime = os.path.getmtime(file_path)

            cache_data = {
                "version": version,
                "mtime": file_mtime,
                "original_path": file_path,  # Store original path for debugging
            }

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            # Don't fail the whole operation if caching fails
            print(f"Warning: Could not save cache: {e}")

    def get_cached_version(self, file_path: str) -> Optional[str]:
        """Get cached version if valid."""
        if self.is_cache_valid(file_path):
            cache_data = self.load_cache(file_path)
            return cache_data.get("version") if cache_data else None
        return None

    def cleanup_orphaned_caches(self, file_paths: list[str]) -> None:
        """Clean up cache files for executables that no longer exist."""
        for file_path in file_paths:
            cache_path = self.get_cache_path(file_path)

            if cache_path.exists() and not Path(file_path).exists():
                try:
                    cache_path.unlink()
                    print(f"Cleaned up orphaned cache: {cache_path}")
                except Exception as e:
                    print(f"Warning: Could not clean up {cache_path}: {e}")

    def clear_all_caches(self) -> None:
        """Clear all cache files."""
        try:
            for cache_file in self.cache_dir.glob(f"*{self.cache_suffix}"):
                cache_file.unlink()
            print(f"Cleared all caches from: {self.cache_dir}")
        except Exception as e:
            print(f"Warning: Could not clear caches: {e}")
