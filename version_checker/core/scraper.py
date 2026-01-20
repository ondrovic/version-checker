"""Web scraping functionality for version checking."""

from datetime import datetime
from typing import Any, Dict, Optional, Union

import requests
from bs4 import BeautifulSoup
from omegaconf import DictConfig
from packaging.version import parse

from ..utils.platform_utils import build_download_url
from .version_reader import get_exe_version


class VersionScraper:
    """Handles web scraping and version comparison."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def scrape_version_number(
        self, config: Union[Dict[str, Any], DictConfig]
    ) -> Optional[Dict[str, Any]]:
        """
        Main function to scrape and compare versions.

        Args:
            config: Configuration dictionary or DictConfig containing site_url, file_path, etc.

        Returns:
            Dictionary with version comparison results or None if failed.
        """
        from pathlib import Path

        site_url = config["site_url"]
        installed_exe_path = config["file_path"]
        timeout = config.get("timeout", self.timeout)
        base_download_url = config.get("base_download_url")

        # Check if the executable exists
        exe_path = Path(installed_exe_path).expanduser()
        executable_exists = exe_path.exists()

        # Get installed version if executable exists
        current_installed_version = None
        if executable_exists:
            installed_version_raw = get_exe_version(installed_exe_path)
            if not installed_version_raw:
                print("Warning: Could not read installed version")
                return None
            current_installed_version = installed_version_raw

        # Scrape latest version
        css_selector = config.get("css_selector")
        latest_version = self._scrape_latest_version(site_url, timeout, css_selector)
        if not latest_version:
            print("Warning: Could not scrape latest version")
            return None

        # If executable doesn't exist, mark as needing fresh install
        if not executable_exists:
            result = {
                "installedVersion": "Not installed",
                "latestVersion": latest_version,
                "timestamp": datetime.now().isoformat(),
                "needsUpdate": True,
                "freshInstall": True,
            }
        else:
            # Compare versions (current_installed_version is guaranteed to be str here)
            assert current_installed_version is not None
            needs_update = self._compare_versions(
                current_installed_version, latest_version
            )

            result = {
                "installedVersion": current_installed_version,
                "latestVersion": latest_version,
                "timestamp": datetime.now().isoformat(),
                "needsUpdate": needs_update,
                "freshInstall": False,
            }

        # Build and include download URL if update is needed or fresh install
        if (
            result["needsUpdate"] or result.get("freshInstall", False)
        ) and base_download_url:
            download_url = build_download_url(base_download_url, latest_version)
            result["downloadUrl"] = download_url

        return result

    def _scrape_latest_version(
        self, site_url: str, timeout: int, css_selector: Optional[str] = None
    ) -> Optional[str]:
        """
        Scrape the latest version from the website.

        Args:
            site_url: URL to scrape.
            timeout: Request timeout in seconds.
            css_selector: Custom CSS selector for version element. If None, uses default.

        Returns:
            Latest version string or None if failed.
        """
        try:
            response = requests.get(site_url, timeout=timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Use custom CSS selector if provided, otherwise use default
            if css_selector:
                element = soup.select_one(css_selector)
            else:
                # Default selector - this should be made configurable in the future
                element = soup.select_one(
                    "body > nav > div > div > div.hidden.flex-1.items-center.justify-center.md\\:flex > a:nth-child(6)"
                )

            return element.text.strip() if element else None

        except Exception as e:
            print(f"Error during scraping: {e}")
            return None

    def _compare_versions(self, installed: str, latest: str) -> bool:
        """
        Compare version strings to determine if update is needed.

        Args:
            installed: Installed version string.
            latest: Latest version string.

        Returns:
            True if update is needed, False otherwise.
        """
        if not installed or not latest:
            return False

        try:
            # Remove 'v' prefix if present
            installed_clean = installed.lstrip("v")
            latest_clean = latest.lstrip("v")

            return parse(latest_clean) > parse(installed_clean)
        except Exception as e:
            print(f"Error comparing versions: {e}")
            return False


# Convenience function for backward compatibility
def scrape_version_number(
    config: Union[Dict[str, Any], DictConfig],
) -> Optional[Dict[str, Any]]:
    """
    Scrape and compare versions (backward compatibility function).

    Args:
        config: Configuration dictionary or DictConfig.

    Returns:
        Version comparison results or None if failed.
    """
    scraper = VersionScraper()
    return scraper.scrape_version_number(config)
