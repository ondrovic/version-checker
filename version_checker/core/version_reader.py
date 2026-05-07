"""Version reading functionality for executables with efficient caching."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Sequence

import pefile

# Try to import win32api for faster Windows version reading
_has_win32api: bool = False
_win32api_module: Any = None

try:
    import win32api as _win32api_import  # pragma: no cover

    _win32api_module = _win32api_import  # pragma: no cover
    _has_win32api = True  # pragma: no cover
except ImportError:
    pass


def has_win32api() -> bool:  # pragma: no cover
    """Check if win32api is available."""
    return _has_win32api


def get_win32api() -> Any:
    """Get the win32api module if available."""
    return _win32api_module


class VersionReader:
    """Handles reading version information from executables with efficient caching."""

    def __init__(
        self,
        use_cache: bool = True,
        cache_dir: Optional[Path] = None,  # pyright: ignore[reportUnusedParameter]
    ):
        """
        Initialize VersionReader with optional caching.

        Args:
            use_cache: Whether to enable caching (default: True)
            cache_dir: Custom cache directory (ignored, kept for backward compatibility)
        """
        self.use_cache = use_cache
        # Cache files are now stored next to executables, so no central cache directory needed

    def get_version(self, file_path: str) -> Optional[str]:
        """
        Get version from executable with efficient caching.

        Args:
            file_path: Path to the executable file.

        Returns:
            Version string or None if not found.
        """
        if not self.use_cache:
            return self._get_version_direct(file_path)

        # Try cache first
        cached_version = self._get_cached_version(file_path)
        if cached_version is not None:
            return cached_version

        # Get version and cache it
        version = self._get_version_direct(file_path)
        if version:
            self._save_cached_version(file_path, version)

        return version

    def get_version_from_probes(
        self,
        file_path: str,
        *,
        version_probes: Sequence[dict[str, Any]],
        version_timeout: int = 2,
    ) -> Optional[str]:
        """
        Attempt to get installed version by running CLI probes.

        Each probe runs the binary at file_path with probe["args"] and extracts
        the version from combined stdout+stderr using probe["regex"].

        Args:
            file_path: Path to installed executable.
            version_probes: Ordered list of probe dicts with keys:
                - "args": list[str]
                - "regex": str with ONE capture group
            version_timeout: Timeout in seconds for each probe.

        Returns:
            Extracted version string or None if probes fail.
        """
        binary_path = str(Path(file_path).expanduser())
        if not Path(binary_path).exists():
            return None

        for probe in version_probes:
            args = probe.get("args")
            regex = probe.get("regex")
            if not isinstance(args, Sequence) or isinstance(args, (str, bytes)):
                continue
            if not isinstance(regex, str) or not regex.strip():
                continue

            version = self._run_probe_and_extract(
                binary_path=binary_path,
                args=[str(a) for a in args],
                pattern=regex,
                timeout_seconds=version_timeout,
            )
            if version:
                return version

        return None

    def _get_version_direct(self, file_path: str) -> Optional[str]:
        """
        Get version directly without caching.

        Args:
            file_path: Path to the executable file.

        Returns:
            Version string or None if not found.
        """
        # Use Linux-specific detection on Linux systems
        if platform.system() == "Linux":
            return self._get_linux_version(file_path)

        # Windows: Use the _get_file_properties method
        file_properties = self._get_file_properties(file_path)

        # Check if we got an error or valid properties
        if "Error" not in file_properties:
            # Try ProductVersion first, then FileVersion as fallback
            version = file_properties.get("ProductVersion") or file_properties.get(
                "FileVersion"
            )
            if version and version != "N/A" and isinstance(version, str):
                return str(version)

        # Fallback to old method if _get_file_properties fails
        return self._read_version_fallback(file_path)

    def _run_probe_and_extract(
        self,
        *,
        binary_path: str,
        args: list[str],
        pattern: str,
        timeout_seconds: int,
    ) -> Optional[str]:
        """
        Run a version probe and extract a version string.

        Notes:
        - Parses stdout+stderr (some CLIs write version to stderr).
        - Requires exactly one capture group in the regex.
        """
        try:
            regex = re.compile(pattern)
        except re.error:
            return None

        if regex.groups != 1:
            return None

        try:
            completed = subprocess.run(
                [binary_path, *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        match = regex.search(output)
        if not match:
            return None
        extracted = match.group(1).strip()
        return extracted or None

    def _get_file_properties(self, file_path: str) -> dict[str, Any]:
        """
        Get comprehensive file properties using win32api (Windows only).

        Args:
            file_path: Path to the executable file.

        Returns:
            Dictionary containing file properties or error information.
        """
        win32api = get_win32api()
        if not has_win32api() or platform.system() != "Windows" or win32api is None:
            return {"Error": "win32api not available or not on Windows"}

        try:
            # Get fixed file info
            info = win32api.GetFileVersionInfo(file_path, "\\")
            ms: int = info["FileVersionMS"]
            ls: int = info["FileVersionLS"]
            file_version = f"{win32api.HIWORD(ms)}.{win32api.LOWORD(ms)}.{win32api.HIWORD(ls)}.{win32api.LOWORD(ls)}"

            # Get string file info
            translation: list[tuple[int, int]] = win32api.GetFileVersionInfo(
                file_path, "\\VarFileInfo\\Translation"
            )
            if not translation or len(translation) == 0:
                return {"Error": "No translation info available"}
            lang, codepage = translation[0]
            string_file_info: dict[str, str] = {}

            str_info_keys = [
                "CompanyName",
                "FileDescription",
                "FileVersion",
                "ProductName",
                "ProductVersion",
                "LegalCopyright",
            ]

            for key in str_info_keys:
                try:
                    string_file_info[key] = win32api.GetFileVersionInfo(
                        file_path, f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\{key}"
                    )
                except Exception:
                    string_file_info[key] = "N/A"

            return {"FileVersion": file_version, **string_file_info}
        except Exception as e:
            return {"Error": str(e)}

    def _read_version_fallback(self, file_path: str) -> Optional[str]:
        """
        Fallback version reading method using pefile.

        Args:
            file_path: Path to the executable file.

        Returns:
            Version string or None if not found.
        """
        try:
            # Use fast_load to speed up PE parsing
            pe = pefile.PE(file_path, fast_load=True)

            try:
                if hasattr(pe, "VS_VERSIONINFO"):
                    for file_info in pe.FileInfo:
                        for entry in file_info:
                            if hasattr(entry, "StringTable"):
                                for string_table in entry.StringTable:
                                    for key, value in string_table.entries.items():
                                        if key.decode() == "ProductVersion":
                                            return str(value.decode())
                return None
            finally:
                pe.close()  # Always clean up resources

        except Exception as e:
            print(f"Pefile error: {e}")
            return None

    def _resolve_binary(self, app: str) -> Optional[str]:
        """
        Resolve an app name to its binary path using shutil.which().

        Args:
            app: Application name or path.

        Returns:
            Resolved binary path or None if not found.
        """
        return shutil.which(app)

    def _version_from_dpkg(self, package_name: str) -> Optional[str]:
        """
        Get version from dpkg package manager (Linux only).

        Args:
            package_name: Name of the package to query.

        Returns:
            Version string with 'v' prefix or None if not found.
        """
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f=${Version}", package_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            version = result.stdout.strip()
            return f"v{version}" if version else None
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _version_from_pacman(self, package_name: str) -> Optional[str]:
        """
        Get version from pacman package manager (Arch Linux).

        Args:
            package_name: Name of the package to query.

        Returns:
            Version string with 'v' prefix or None if not found.
        """
        try:
            result = subprocess.run(
                ["pacman", "-Q", package_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            # Output format: "heroic 2.19.0-1"
            parts = result.stdout.strip().split()
            if len(parts) >= 2:
                version = parts[1]
                # Remove package release suffix (e.g., "-1" from "2.19.0-1")
                version = version.rsplit("-", 1)[0] if "-" in version else version
                return f"v{version}" if version else None
            return None
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _extract_main_version_from_binary(self, file_path: str) -> Optional[str]:
        """
        Extract main.version from a binary using `strings` command.

        This is useful for Go binaries that embed version info via ldflags.
        Example match: -X main.version=v0.24.0

        Args:
            file_path: Path to the binary file.

        Returns:
            Version string (e.g., 'v0.24.0') or None if not found.
        """
        try:
            result = subprocess.run(
                ["strings", file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

        pattern = re.compile(r"main\.version=([^\s\"']+)")

        for line in result.stdout.splitlines():
            if "main.version" in line:
                match = pattern.search(line)
                if match:
                    return match.group(1)

        return None

    def _get_linux_version(self, file_path: str) -> Optional[str]:
        """
        Get version on Linux systems.

        Tries package managers (dpkg, pacman) first, then falls back to
        extracting main.version from binary.

        Args:
            file_path: Path to executable or app name.

        Returns:
            Version string or None if not found.
        """
        path = Path(file_path).expanduser()
        resolved_path = str(path)

        # Get app name for package manager queries
        app_name = path.name if path.parent != Path(".") else file_path

        # If it's an explicit file path that exists
        if path.is_file() and os.access(resolved_path, os.X_OK):
            # Try extracting version from binary first
            version = self._extract_main_version_from_binary(resolved_path)
            if version:
                return version

            # Try package managers using the binary name
            version = self._version_from_dpkg(app_name)
            if version:
                return version

            version = self._version_from_pacman(app_name)
            if version:
                return version

            return None

        # Otherwise treat as app name and try package managers

        # Try dpkg first (Debian/Ubuntu)
        version = self._version_from_dpkg(app_name)
        if version:
            return version

        # Try pacman (Arch Linux)
        version = self._version_from_pacman(app_name)
        if version:
            return version

        # Try to resolve binary and extract version
        binary_path = self._resolve_binary(app_name)
        if binary_path:
            version = self._extract_main_version_from_binary(binary_path)
            if version:
                return version

        return None

    def _get_cache_dir(self) -> Path:
        """
        Get the cache directory for version information.

        Returns:
            Path to the cache directory (~/.cache/version-checker/).
        """
        # Use XDG_CACHE_HOME if set, otherwise ~/.cache
        xdg_cache = os.environ.get("XDG_CACHE_HOME")
        if xdg_cache:
            cache_base = Path(xdg_cache)
        else:
            cache_base = Path.home() / ".cache"

        cache_dir = cache_base / "version-checker"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _get_cache_path(self, file_path: str) -> Path:
        """
        Get the cache file path for a given executable.

        Args:
            file_path: Path to the executable file.

        Returns:
            Path to the cache file in the user's cache directory.
        """
        import hashlib

        # Get the resolved path and create a unique cache filename
        exec_path = Path(file_path).expanduser().resolve()

        # Use hash of full path to avoid filename collisions
        path_hash = hashlib.md5(str(exec_path).encode()).hexdigest()[:12]
        cache_filename = f"{exec_path.name}_{path_hash}.json"

        return self._get_cache_dir() / cache_filename

    def _get_cached_version(self, file_path: str) -> Optional[str]:
        """
        Get cached version if valid.

        Args:
            file_path: Path to the executable file.

        Returns:
            Cached version string or None if not valid.
        """
        try:
            cache_path = self._get_cache_path(file_path)

            if not cache_path.exists():
                return None

            # Check if file has been modified since cache was created
            resolved_path = str(Path(file_path).expanduser())
            file_mtime = os.path.getmtime(resolved_path)

            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # Validate cache
            if cache_data.get("mtime") != file_mtime:
                return None

            version = cache_data.get("version")
            return str(version) if version else None

        except Exception:
            return None

    def _save_cached_version(self, file_path: str, version: str) -> None:
        """
        Save version to cache.

        Args:
            file_path: Path to the executable file.
            version: Version string to cache.
        """
        try:
            cache_path = self._get_cache_path(file_path)
            resolved_path = str(Path(file_path).expanduser())
            file_mtime = os.path.getmtime(resolved_path)

            cache_data = {
                "version": version,
                "mtime": file_mtime,
                "original_path": resolved_path,
            }

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2)

        except Exception as e:
            # Don't fail the whole operation if caching fails
            print(f"Warning: Could not save cache: {e}")

    def clear_cache(self) -> None:
        """Clear all cache files from the cache directory."""
        try:
            cache_dir = self._get_cache_dir()
            count = 0
            for cache_file in cache_dir.glob("*.json"):
                cache_file.unlink()
                count += 1
            print(f"Cleared {count} cache file(s) from {cache_dir}")
        except Exception as e:
            print(f"Warning: Could not clear cache: {e}")

    def clear_cache_for_file(self, file_path: str) -> None:
        """
        Clear cache for a specific executable file.

        Args:
            file_path: Path to the executable file.
        """
        try:
            cache_path = self._get_cache_path(file_path)
            if cache_path.exists():
                cache_path.unlink()
                print(f"Cleared cache: {cache_path}")
        except Exception as e:
            print(f"Warning: Could not clear cache for {file_path}: {e}")

    def cleanup_orphaned_caches(self, file_paths: list[str]) -> None:
        """
        Clean up cache files for executables that no longer exist.

        Args:
            file_paths: List of known executable paths.
        """
        for file_path in file_paths:
            try:
                # Check if executable still exists
                if not Path(file_path).exists():
                    # Executable doesn't exist, remove its cache
                    cache_path = self._get_cache_path(file_path)
                    if cache_path.exists():
                        cache_path.unlink()
                        print(f"Cleaned up orphaned cache: {cache_path}")
            except Exception as e:
                print(f"Warning: Could not check cache for {file_path}: {e}")


# Global instance with caching enabled
_default_reader = VersionReader(use_cache=True)


@lru_cache(maxsize=128)
def get_exe_version(file_path: str) -> Optional[str]:
    """
    Get executable version with caching (backward compatibility function).

    Args:
        file_path: Path to executable file.

    Returns:
        Version string or None if not found.
    """
    return _default_reader.get_version(file_path)


def get_exe_version_no_cache(file_path: str) -> Optional[str]:
    """
    Get executable version without caching.

    Args:
        file_path: Path to executable file.

    Returns:
        Version string or None if not found.
    """
    reader = VersionReader(use_cache=False)
    return reader.get_version(file_path)


def clear_version_cache() -> None:
    """Clear the global version cache."""
    _default_reader.clear_cache()


def cleanup_orphaned_caches(file_paths: list[str]) -> None:
    """
    Clean up orphaned cache files.

    Args:
        file_paths: List of known executable paths.
    """
    _default_reader.cleanup_orphaned_caches(file_paths)
