"""Web scraping functionality for version checking."""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import requests
from bs4 import BeautifulSoup
from omegaconf import DictConfig
from packaging.version import parse

from ..utils.platform_utils import build_download_url, find_best_asset
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

        timeout = config.get("timeout", self.timeout)

        # Check update type - use GitHub API or traditional scraping
        update_type = config.get("update_type", "scrape")

        if update_type == "github":
            return self._scrape_github_version(config)

        # For scrape provider, get required fields
        site_url = config["site_url"]
        installed_exe_path = config["file_path"]
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

    def _fetch_github_release(self, repo: str, timeout: int) -> Optional[Dict[str, Any]]:
        """
        Fetch the latest release from GitHub API.

        Args:
            repo: Repository in format "owner/repo".
            timeout: Request timeout in seconds.

        Returns:
            JSON response dictionary or None if failed.
        """
        try:
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            headers = {
                "User-Agent": "version-checker/1.0",
                "Accept": "application/vnd.github+json"
            }
            response = requests.get(url, headers=headers, timeout=timeout)

            if response.status_code == 404:
                print(f"Repository not found or has no releases: {repo}")
                return None
            elif response.status_code == 403:
                print("GitHub API rate limit exceeded. Try again later.")
                return None

            response.raise_for_status()
            return response.json()

        except Exception as e:
            print(f"Error fetching GitHub release: {e}")
            return None

    def _extract_version_from_tag(self, tag_name: str, pattern: Optional[str]) -> str:
        """
        Extract version from tag name using optional regex pattern.

        Args:
            tag_name: Git tag name (e.g., "v1.2.3" or "release-1.2.3").
            pattern: Optional regex pattern with one capture group for version.

        Returns:
            Extracted version string.
        """
        if not pattern:
            return tag_name.lstrip("v")

        try:
            match = re.search(pattern, tag_name)
            if match:
                return match.group(1)
        except Exception as e:
            print(f"Error extracting version with pattern '{pattern}': {e}")

        # Fallback to simple stripping
        return tag_name.lstrip("v")

    def _find_matching_asset(
        self, assets: List[Dict], package_type: Optional[str]
    ) -> Optional[str]:
        """
        Find the best matching asset for the current platform.

        Args:
            assets: List of asset dictionaries from GitHub API.
            package_type: Optional file extension to prefer (e.g., ".zip", ".tar.gz").

        Returns:
            Download URL of best matching asset or None if no match found.
        """
        best_asset = find_best_asset(assets, package_type)
        if best_asset:
            return best_asset.get("browser_download_url")
        return None

    def _display_available_assets(self, assets: List[Dict]) -> None:
        """
        Display list of available assets when no platform match is found.

        Args:
            assets: List of asset dictionaries from GitHub API.
        """
        print("No matching asset found for your platform. Available assets:")
        for asset in assets:
            print(f"  - {asset.get('name', 'unknown')}")

    def _scrape_github_version(self, config: Union[Dict[str, Any], DictConfig]) -> Optional[Dict[str, Any]]:
        """
        Scrape version from GitHub releases API.

        Args:
            config: Configuration dictionary or DictConfig containing github_repo, file_path, etc.

        Returns:
            Dictionary with version comparison results or None if failed.
        """
        from pathlib import Path

        github_repo = config.get("github_repo")
        if not github_repo:
            print("Error: github_repo not specified in config")
            return None

        installed_exe_path = config["file_path"]
        timeout = config.get("timeout", self.timeout)
        version_pattern = config.get("version_pattern")
        default_package_type = config.get("default_package_type")

        # Fetch latest release from GitHub
        release_data = self._fetch_github_release(github_repo, timeout)
        if not release_data:
            return None

        # Extract version from tag name
        tag_name = release_data.get("tag_name", "")
        latest_version = self._extract_version_from_tag(tag_name, version_pattern)

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
            # Compare versions
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

        # Find matching asset and include download URL if update is needed
        if result["needsUpdate"] or result.get("freshInstall", False):
            assets = release_data.get("assets", [])
            if assets:
                download_url = self._find_matching_asset(assets, default_package_type)
                if download_url:
                    result["downloadUrl"] = download_url
                else:
                    self._display_available_assets(assets)

        return result


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
