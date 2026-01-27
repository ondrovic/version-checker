"""Platform detection utilities for building OS-specific download URLs."""

import platform
from typing import Any, Dict, List, Optional, Tuple


def get_platform_info() -> Tuple[str, str]:
    """
    Detect the current operating system and architecture.

    Returns:
        Tuple of (os_name, architecture) strings formatted for download URLs.
        Examples: ('windows', 'x64'), ('mac', 'arm64'), ('linux', 'amd64')
    """
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Determine OS name
    if system == "windows":
        os_name = "windows"
    elif system == "darwin":
        os_name = "mac"
    elif system == "linux":
        os_name = "linux"
    else:
        # Default to linux for unknown systems
        os_name = "linux"

    # Determine architecture
    if os_name == "windows":
        if machine in ("amd64", "x86_64"):
            arch = "x64"
        elif machine in ("arm64", "aarch64"):
            arch = "arm64"
        else:
            # Default to x64 for unknown Windows architectures
            arch = "x64"

    elif os_name == "mac":
        if machine in ("arm64", "aarch64"):
            arch = "arm64"
        elif machine in ("x86_64", "amd64"):
            arch = "intel"
        else:
            # Default to arm64 for unknown Mac architectures (newer Macs)
            arch = "arm64"

    elif os_name == "linux":
        if machine in ("x86_64", "amd64"):
            arch = "amd64"
        elif machine in ("arm64", "aarch64"):
            arch = "arm64"
        else:
            # Default to amd64 for unknown Linux architectures
            arch = "amd64"
    else:  # pragma: no cover
        # Default architecture for unknown OS
        arch = "amd64"

    return os_name, arch


def build_download_url(base_url: str, version: str, app_name: str = "OlivedPro") -> str:
    """
    Build a platform-specific download URL.

    Args:
        base_url: Base URL for downloads (e.g., "https://cos.olived.app/d/OlivedPro_")
        version: Version string (without 'v' prefix, e.g., "0.23.4")
        app_name: Application name (default: "OlivedPro")

    Returns:
        Complete download URL for the current platform.
        Example: "https://cos.olived.app/d/OlivedPro_0.23.4_windows_x64.zip"
    """
    # Remove 'v' prefix if present
    clean_version = version.lstrip("v")

    # Get platform info
    os_name, arch = get_platform_info()

    # Build the URL
    # Pattern: {base_url}{version}_{os}_{arch}.zip
    # Example: https://cos.olived.app/d/OlivedPro_0.23.4_windows_x64.zip

    # If base_url doesn't end with app_name_, add it
    if not base_url.endswith(f"{app_name}_"):
        if not base_url.endswith("/"):
            base_url += "/"
        base_url += f"{app_name}_"

    download_url = f"{base_url}{clean_version}_{os_name}_{arch}.zip"

    return download_url


def get_platform_display_name() -> str:
    """
    Get a human-readable platform name.

    Returns:
        Platform display name (e.g., "Windows x64", "macOS ARM64", "Linux AMD64")
    """
    os_name, arch = get_platform_info()

    os_display = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}.get(
        os_name, os_name.capitalize()
    )

    arch_display = arch.upper()

    return f"{os_display} {arch_display}"


def get_platform_patterns() -> List[str]:
    """
    Return list of patterns to search for in GitHub asset names for current platform.

    Returns:
        List of platform-specific patterns to match in asset filenames.
    """
    os_name, arch = get_platform_info()

    patterns: List[str] = []

    if os_name == "linux":
        if arch == "amd64":
            patterns = [
                "linux_amd64", "linux-amd64", "Linux_x86_64", "linux-x86_64",
                "linux_x86_64", "x86_64-unknown-linux", "x86_64-linux",
                "linux64", "Linux_amd64", "Linux-amd64"
            ]
        elif arch == "arm64":
            patterns = [
                "linux_arm64", "linux-arm64", "Linux_aarch64", "linux-aarch64",
                "linux_aarch64", "aarch64-unknown-linux", "aarch64-linux",
                "Linux_arm64", "Linux-arm64"
            ]
    elif os_name == "mac":
        if arch == "arm64":
            patterns = [
                "darwin_arm64", "darwin-arm64", "macos_arm64", "macos-arm64",
                "Darwin_arm64", "macOS_arm64", "apple-darwin", "aarch64-apple-darwin",
                "macos_aarch64", "darwin_aarch64"
            ]
        elif arch == "intel":
            patterns = [
                "darwin_amd64", "darwin-amd64", "macos_x86_64", "macos-x86_64",
                "Darwin_x86_64", "macOS_x86_64", "x86_64-apple-darwin",
                "darwin_x86_64", "macos_amd64"
            ]
    elif os_name == "windows":
        if arch == "x64":
            patterns = [
                "windows_x64", "windows-x64", "windows_amd64", "windows-amd64",
                "win64", "Windows_x86_64", "windows_x86_64", "win-x64",
                "Windows_amd64", "Windows-x64"
            ]
        elif arch == "arm64":
            patterns = [
                "windows_arm64", "windows-arm64", "Windows_arm64", "win-arm64"
            ]

    return patterns


def match_asset_to_platform(asset_name: str, package_type: Optional[str] = None) -> int:
    """
    Score how well an asset matches the current platform.

    Args:
        asset_name: Name of the asset file.
        package_type: Optional file extension to prefer (e.g., ".tar.gz", ".zip").

    Returns:
        Score indicating match quality. Higher is better, 0 means no match.
    """
    patterns = get_platform_patterns()
    asset_lower = asset_name.lower()

    score = 0

    # Check if any platform pattern matches (case-insensitive)
    for pattern in patterns:
        if pattern.lower() in asset_lower:
            score = 10
            break

    # If no platform match, return 0
    if score == 0:
        return 0

    # Bonus for matching package type
    if package_type and asset_name.endswith(package_type):
        score += 5

    return score


def find_best_asset(
    assets: List[Dict[str, Any]], package_type: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Find the best matching asset for the current platform.

    Args:
        assets: List of asset dictionaries from GitHub API.
            Each dict should have "name" and "browser_download_url" keys.
        package_type: Optional file extension to prefer (e.g., ".tar.gz", ".zip").

    Returns:
        Best matching asset dictionary or None if no match found.
    """
    if not assets:
        return None

    best_asset: Optional[Dict[str, Any]] = None
    best_score = 0

    for asset in assets:
        name = asset.get("name", "")
        score = match_asset_to_platform(name, package_type)

        if score > best_score:
            best_score = score
            best_asset = asset

    return best_asset
