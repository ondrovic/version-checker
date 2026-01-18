"""Platform detection utilities for building OS-specific download URLs."""

import platform
from typing import Tuple


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
    else:
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
