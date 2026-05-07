"""Configuration schema for version-checker using Hydra structured configs."""

from dataclasses import dataclass
from typing import Any, Optional

from hydra.core.config_store import ConfigStore


@dataclass
class VersionCheckerConfig:
    """
    Structured configuration for version-checker.

    Attributes:
        site_url: URL to scrape for the latest version.
        file_path: Path to the installed executable.
        css_selector: CSS selector to extract version from HTML.
        base_download_url: Base URL for constructing download URLs (optional).
        detailed_info: Show detailed JSON output (default: False).
        timeout: HTTP request timeout in seconds (default: 10).
        auto_launch: Auto-launch app after installation (default: False).
        process_name: Process name to kill before update (optional, defaults to file_path stem).
        install_method: Installation method to use when auto-installing (default: "download").
        install_script: Shell script to run when install_method is "script".
        version_timeout: Timeout for running version probes (default: 2).
        version_probes: Ordered list of probes to run for installed version detection.
    """

    # Required fields
    site_url: str
    file_path: str
    css_selector: str

    # Optional fields with defaults
    base_download_url: Optional[str] = None
    detailed_info: bool = False
    timeout: int = 10
    auto_launch: bool = False
    process_name: Optional[str] = None
    auto_install: bool = False
    update_type: str = "scrape"
    github_repo: Optional[str] = None
    version_pattern: Optional[str] = None
    default_package_type: Optional[str] = None

    install_method: str = "download"
    install_script: Optional[str] = None

    version_timeout: int = 2
    version_probes: Optional[list[dict[str, Any]]] = None


def register_configs() -> None:
    """Register structured configs with Hydra's ConfigStore."""
    cs = ConfigStore.instance()
    cs.store(name="base_config", node=VersionCheckerConfig)
