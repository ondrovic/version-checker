"""Utility helper functions."""

import os
import platform
from pathlib import Path


def clear_screen() -> None:
    """Clear the terminal screen."""
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")


def format_version(version: str) -> str:
    """Format version string consistently."""
    if not version:
        return "Unknown"

    # Add 'v' prefix if not present
    return version if version.startswith("v") else f"v{version}"


def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def get_platform_info() -> dict:
    """Get platform information."""
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }


def get_config_dir() -> Path:
    """
    Get the configuration directory path for version-checker.

    Returns config directory following XDG Base Directory specification:
    - All platforms: ~/.config/version-checker

    Note: XDG_CONFIG_HOME environment variable can override the default.

    Creates the directory if it doesn't exist.

    Returns:
        Path object pointing to the config directory.
    """
    # Use XDG_CONFIG_HOME if set, otherwise use ~/.config
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        config_base = Path(xdg_config)
    else:
        config_base = Path.home() / ".config"

    config_dir = config_base / "version-checker"

    # Create directory if it doesn't exist
    config_dir.mkdir(parents=True, exist_ok=True)

    return config_dir


def get_default_config_path() -> Path:
    """
    Get the default config.yaml file path.

    Returns:
        Path object pointing to the default config.yaml location.
    """
    return get_config_dir() / "config.yaml"
