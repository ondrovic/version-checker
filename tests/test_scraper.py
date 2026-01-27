"""Tests for scraper functionality."""

from unittest.mock import MagicMock, patch

from version_checker.core.scraper import VersionScraper, scrape_version_number


class TestVersionScraper:
    """Test cases for VersionScraper class."""

    def test_scraper_init(self):
        """Test VersionScraper initialization."""
        scraper = VersionScraper()
        assert scraper.timeout == 10

        scraper_custom = VersionScraper(timeout=30)
        assert scraper_custom.timeout == 30

    def test_compare_versions(self):
        """Test version comparison logic."""
        scraper = VersionScraper()

        # Test normal version comparison
        assert scraper._compare_versions("v1.0.0", "v1.0.1") is True
        assert scraper._compare_versions("v1.0.1", "v1.0.0") is False
        assert scraper._compare_versions("v1.0.0", "v1.0.0") is False

        # Test with 'v' prefix handling
        assert scraper._compare_versions("1.0.0", "v1.0.1") is True
        assert scraper._compare_versions("v1.0.0", "1.0.1") is True

        # Test edge cases
        assert scraper._compare_versions(None, "v1.0.0") is False
        assert scraper._compare_versions("v1.0.0", None) is False
        assert scraper._compare_versions("", "v1.0.0") is False

    @patch("version_checker.core.scraper.requests")
    def test_scrape_latest_version_success(self, mock_requests):
        """Test successful version scraping."""
        # Mock response
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <body>
                <nav>
                    <div>
                        <div>
                            <div class="hidden flex-1 items-center justify-center md:flex">
                                <a>Link 1</a>
                                <a>Link 2</a>
                                <a>Link 3</a>
                                <a>Link 4</a>
                                <a>Link 5</a>
                                <a>v2.1.0</a>
                            </div>
                        </div>
                    </div>
                </nav>
            </body>
        </html>
        """
        mock_requests.get.return_value = mock_response

        scraper = VersionScraper()
        version = scraper._scrape_latest_version("https://example.com", 10)

        assert version == "v2.1.0"
        mock_requests.get.assert_called_once_with("https://example.com", timeout=10)

    @patch("version_checker.core.scraper.requests")
    def test_scrape_latest_version_custom_selector(self, mock_requests):
        """Test version scraping with custom CSS selector."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <body>
                <div class="version-info">v3.2.1</div>
            </body>
        </html>
        """
        mock_requests.get.return_value = mock_response

        scraper = VersionScraper()
        version = scraper._scrape_latest_version(
            "https://example.com", 10, ".version-info"
        )

        assert version == "v3.2.1"

    @patch("version_checker.core.scraper.requests")
    def test_scrape_latest_version_not_found(self, mock_requests):
        """Test version scraping when element not found."""
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>No version info</p></body></html>"
        mock_requests.get.return_value = mock_response

        scraper = VersionScraper()
        version = scraper._scrape_latest_version("https://example.com", 10)

        assert version is None

    @patch("version_checker.core.scraper.requests")
    def test_scrape_latest_version_request_error(self, mock_requests):
        """Test version scraping with request error."""
        mock_requests.get.side_effect = Exception("Network error")

        scraper = VersionScraper()
        version = scraper._scrape_latest_version("https://example.com", 10)

        assert version is None

    @patch("pathlib.Path.exists")
    @patch("version_checker.core.scraper.get_exe_version")
    @patch("version_checker.core.scraper.VersionScraper._scrape_latest_version")
    def test_scrape_version_number_success(
        self, mock_scrape, mock_get_version, mock_exists, sample_config
    ):
        """Test complete version checking process."""
        # Mock Path.exists() to return True so file existence check passes
        mock_exists.return_value = True

        mock_get_version.return_value = "1.0.0"
        mock_scrape.return_value = "v1.0.1"

        scraper = VersionScraper()
        result = scraper.scrape_version_number(sample_config)

        assert result is not None
        assert (
            result["installedVersion"] == "1.0.0"
        )  # Returns as-is from get_exe_version
        assert result["latestVersion"] == "v1.0.1"
        assert result["needsUpdate"] is True
        assert result["freshInstall"] is False
        assert "timestamp" in result

    @patch("pathlib.Path.exists")
    @patch("version_checker.core.scraper.get_exe_version")
    def test_scrape_version_number_no_installed_version(
        self, mock_get_version, mock_exists, sample_config
    ):
        """Test when installed version cannot be read but file exists."""
        # Mock Path.exists() to return True (file exists)
        mock_exists.return_value = True

        # But version reading fails
        mock_get_version.return_value = None

        scraper = VersionScraper()
        result = scraper.scrape_version_number(sample_config)

        assert result is None

    @patch("pathlib.Path.exists")
    @patch("version_checker.core.scraper.VersionScraper._scrape_latest_version")
    def test_scrape_version_number_fresh_install(
        self, mock_scrape, mock_exists, sample_config
    ):
        """Test when executable doesn't exist (fresh install)."""
        # Mock Path.exists() to return False (file doesn't exist)
        mock_exists.return_value = False
        mock_scrape.return_value = "v1.0.1"

        scraper = VersionScraper()
        result = scraper.scrape_version_number(sample_config)

        assert result is not None
        assert result["installedVersion"] == "Not installed"
        assert result["latestVersion"] == "v1.0.1"
        assert result["needsUpdate"] is True
        assert result["freshInstall"] is True

    @patch("pathlib.Path.exists")
    @patch("version_checker.core.scraper.VersionScraper._scrape_latest_version")
    def test_scrape_version_number_fresh_install_with_download_url(
        self, mock_scrape, mock_exists, sample_config
    ):
        """Test fresh install with download URL."""
        mock_exists.return_value = False
        mock_scrape.return_value = "v1.0.1"

        # Add base_download_url to config
        config_with_url = sample_config.copy()
        config_with_url["base_download_url"] = "https://example.com/downloads/App_"

        scraper = VersionScraper()
        result = scraper.scrape_version_number(config_with_url)

        assert result is not None
        assert result["freshInstall"] is True
        assert "downloadUrl" in result

    @patch("pathlib.Path.exists")
    @patch("version_checker.core.version_reader.get_exe_version")
    @patch("version_checker.core.scraper.VersionScraper._scrape_latest_version")
    def test_scrape_version_number_no_latest_version(
        self, mock_scrape, mock_get_version, mock_exists, sample_config
    ):
        """Test when latest version cannot be scraped."""
        mock_exists.return_value = True
        mock_get_version.return_value = "1.0.0"
        mock_scrape.return_value = None

        scraper = VersionScraper()
        result = scraper.scrape_version_number(sample_config)

        assert result is None

    @patch("pathlib.Path.exists")
    @patch("version_checker.core.scraper.get_exe_version")
    @patch("version_checker.core.scraper.VersionScraper._scrape_latest_version")
    def test_scrape_version_number_with_download_url(
        self, mock_scrape, mock_get_version, mock_exists, sample_config
    ):
        """Test version checking with download URL generation."""
        mock_exists.return_value = True
        mock_get_version.return_value = "1.0.0"
        mock_scrape.return_value = "v1.0.1"

        # Add base_download_url to config
        config_with_url = sample_config.copy()
        config_with_url["base_download_url"] = "https://example.com/downloads/App_"

        scraper = VersionScraper()
        result = scraper.scrape_version_number(config_with_url)

        assert result is not None
        assert result["needsUpdate"] is True
        assert "downloadUrl" in result
        assert "example.com" in result["downloadUrl"]

    def test_scrape_version_number_function(self, sample_config):
        """Test the convenience function."""
        with patch("version_checker.core.scraper.VersionScraper") as mock_scraper_class:
            mock_scraper = MagicMock()
            mock_scraper_class.return_value = mock_scraper
            mock_scraper.scrape_version_number.return_value = {"test": "result"}

            result = scrape_version_number(sample_config)

            assert result == {"test": "result"}
            mock_scraper.scrape_version_number.assert_called_once_with(sample_config)


class TestGitHubProvider:
    """Test cases for GitHub provider functionality."""

    @patch("version_checker.core.scraper.requests")
    def test_fetch_github_release_success(self, mock_requests):
        """Test successful GitHub release fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tag_name": "v1.0.0", "assets": []}
        mock_requests.get.return_value = mock_response

        scraper = VersionScraper()
        result = scraper._fetch_github_release("owner/repo", 10)

        assert result == {"tag_name": "v1.0.0", "assets": []}
        mock_requests.get.assert_called_once()

    @patch("version_checker.core.scraper.requests")
    def test_fetch_github_release_404(self, mock_requests):
        """Test GitHub release fetch with 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_requests.get.return_value = mock_response

        scraper = VersionScraper()
        result = scraper._fetch_github_release("owner/repo", 10)

        assert result is None

    @patch("version_checker.core.scraper.requests")
    def test_fetch_github_release_403(self, mock_requests):
        """Test GitHub release fetch with 403 rate limit."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_requests.get.return_value = mock_response

        scraper = VersionScraper()
        result = scraper._fetch_github_release("owner/repo", 10)

        assert result is None

    @patch("version_checker.core.scraper.requests")
    def test_fetch_github_release_exception(self, mock_requests):
        """Test GitHub release fetch with exception."""
        mock_requests.get.side_effect = Exception("Network error")

        scraper = VersionScraper()
        result = scraper._fetch_github_release("owner/repo", 10)

        assert result is None

    def test_extract_version_from_tag_no_pattern(self):
        """Test version extraction without pattern."""
        scraper = VersionScraper()

        assert scraper._extract_version_from_tag("v1.0.0", None) == "1.0.0"
        assert scraper._extract_version_from_tag("1.0.0", None) == "1.0.0"

    def test_extract_version_from_tag_with_pattern(self):
        """Test version extraction with regex pattern."""
        scraper = VersionScraper()

        result = scraper._extract_version_from_tag("release-1.2.3", r"release-(\d+\.\d+\.\d+)")
        assert result == "1.2.3"

    def test_extract_version_from_tag_pattern_no_match(self):
        """Test version extraction when pattern doesn't match."""
        scraper = VersionScraper()

        result = scraper._extract_version_from_tag("v1.0.0", r"release-(\d+)")
        assert result == "1.0.0"  # Falls back to lstrip

    def test_extract_version_from_tag_invalid_pattern(self):
        """Test version extraction with invalid pattern."""
        scraper = VersionScraper()

        result = scraper._extract_version_from_tag("v1.0.0", r"[invalid")
        assert result == "1.0.0"  # Falls back to lstrip

    @patch("version_checker.core.scraper.find_best_asset")
    def test_find_matching_asset_found(self, mock_find_best):
        """Test finding matching asset."""
        mock_find_best.return_value = {"browser_download_url": "https://example.com/file.zip"}

        scraper = VersionScraper()
        result = scraper._find_matching_asset([{"name": "file.zip"}], ".zip")

        assert result == "https://example.com/file.zip"

    @patch("version_checker.core.scraper.find_best_asset")
    def test_find_matching_asset_not_found(self, mock_find_best):
        """Test finding matching asset when none match."""
        mock_find_best.return_value = None

        scraper = VersionScraper()
        result = scraper._find_matching_asset([{"name": "file.zip"}], ".zip")

        assert result is None

    def test_display_available_assets(self, capsys):
        """Test displaying available assets."""
        scraper = VersionScraper()
        assets = [{"name": "file1.zip"}, {"name": "file2.tar.gz"}]

        scraper._display_available_assets(assets)

        captured = capsys.readouterr()
        assert "file1.zip" in captured.out
        assert "file2.tar.gz" in captured.out

    @patch("pathlib.Path.exists")
    @patch("version_checker.core.scraper.get_exe_version")
    @patch("version_checker.core.scraper.VersionScraper._fetch_github_release")
    def test_scrape_github_version_success(self, mock_fetch, mock_get_version, mock_exists):
        """Test successful GitHub version scraping."""
        mock_exists.return_value = True
        mock_get_version.return_value = "1.0.0"
        mock_fetch.return_value = {
            "tag_name": "v1.0.1",
            "assets": [{"name": "app_linux_amd64.tar.gz", "browser_download_url": "https://example.com/file.tar.gz"}]
        }

        config = {
            "update_type": "github",
            "github_repo": "owner/repo",
            "file_path": "/path/to/exe",
            "timeout": 10,
        }

        scraper = VersionScraper()
        result = scraper.scrape_version_number(config)

        assert result is not None
        assert result["latestVersion"] == "1.0.1"
        assert result["installedVersion"] == "1.0.0"
        assert result["needsUpdate"] is True

    @patch("pathlib.Path.exists")
    @patch("version_checker.core.scraper.VersionScraper._fetch_github_release")
    def test_scrape_github_version_fresh_install(self, mock_fetch, mock_exists):
        """Test GitHub version scraping for fresh install."""
        mock_exists.return_value = False
        mock_fetch.return_value = {
            "tag_name": "v1.0.0",
            "assets": []
        }

        config = {
            "update_type": "github",
            "github_repo": "owner/repo",
            "file_path": "/path/to/exe",
        }

        scraper = VersionScraper()
        result = scraper.scrape_version_number(config)

        assert result is not None
        assert result["freshInstall"] is True
        assert result["installedVersion"] == "Not installed"

    def test_scrape_github_version_missing_repo(self):
        """Test GitHub version scraping with missing repo."""
        config = {
            "update_type": "github",
            "file_path": "/path/to/exe",
        }

        scraper = VersionScraper()
        result = scraper.scrape_version_number(config)

        assert result is None

    @patch("version_checker.core.scraper.VersionScraper._fetch_github_release")
    def test_scrape_github_version_fetch_failed(self, mock_fetch):
        """Test GitHub version scraping when fetch fails."""
        mock_fetch.return_value = None

        config = {
            "update_type": "github",
            "github_repo": "owner/repo",
            "file_path": "/path/to/exe",
        }

        scraper = VersionScraper()
        result = scraper.scrape_version_number(config)

        assert result is None

    @patch("pathlib.Path.exists")
    @patch("version_checker.core.scraper.get_exe_version")
    @patch("version_checker.core.scraper.VersionScraper._fetch_github_release")
    def test_scrape_github_version_no_installed_version(self, mock_fetch, mock_get_version, mock_exists):
        """Test GitHub scraping when installed version can't be read."""
        mock_exists.return_value = True
        mock_get_version.return_value = None
        mock_fetch.return_value = {"tag_name": "v1.0.0", "assets": []}

        config = {
            "update_type": "github",
            "github_repo": "owner/repo",
            "file_path": "/path/to/exe",
        }

        scraper = VersionScraper()
        result = scraper.scrape_version_number(config)

        assert result is None

    @patch("pathlib.Path.exists")
    @patch("version_checker.core.scraper.get_exe_version")
    @patch("version_checker.core.scraper.VersionScraper._fetch_github_release")
    @patch("version_checker.core.scraper.VersionScraper._find_matching_asset")
    @patch("version_checker.core.scraper.VersionScraper._display_available_assets")
    def test_scrape_github_version_no_matching_asset(
        self, mock_display, mock_find, mock_fetch, mock_get_version, mock_exists
    ):
        """Test GitHub scraping with no matching asset shows available assets."""
        mock_exists.return_value = True
        mock_get_version.return_value = "0.9.0"
        mock_fetch.return_value = {
            "tag_name": "v1.0.0",
            "assets": [{"name": "other.zip"}]
        }
        mock_find.return_value = None

        config = {
            "update_type": "github",
            "github_repo": "owner/repo",
            "file_path": "/path/to/exe",
        }

        scraper = VersionScraper()
        result = scraper.scrape_version_number(config)

        assert result is not None
        mock_display.assert_called_once()

    @patch("pathlib.Path.exists")
    @patch("version_checker.core.scraper.get_exe_version")
    @patch("version_checker.core.scraper.VersionScraper._fetch_github_release")
    @patch("version_checker.core.scraper.VersionScraper._find_matching_asset")
    def test_scrape_github_version_with_download_url(
        self, mock_find, mock_fetch, mock_get_version, mock_exists
    ):
        """Test GitHub scraping includes download URL when found."""
        mock_exists.return_value = True
        mock_get_version.return_value = "0.9.0"
        mock_fetch.return_value = {
            "tag_name": "v1.0.0",
            "assets": [{"name": "app.zip"}]
        }
        mock_find.return_value = "https://example.com/app.zip"

        config = {
            "update_type": "github",
            "github_repo": "owner/repo",
            "file_path": "/path/to/exe",
        }

        scraper = VersionScraper()
        result = scraper.scrape_version_number(config)

        assert result is not None
        assert result["downloadUrl"] == "https://example.com/app.zip"

    @patch("pathlib.Path.exists")
    @patch("version_checker.core.scraper.get_exe_version")
    @patch("version_checker.core.scraper.VersionScraper._fetch_github_release")
    def test_scrape_github_version_with_version_pattern(
        self, mock_fetch, mock_get_version, mock_exists
    ):
        """Test GitHub scraping with custom version pattern."""
        mock_exists.return_value = True
        mock_get_version.return_value = "1.0.0"
        mock_fetch.return_value = {
            "tag_name": "release-2.0.0",
            "assets": []
        }

        config = {
            "update_type": "github",
            "github_repo": "owner/repo",
            "file_path": "/path/to/exe",
            "version_pattern": r"release-(\d+\.\d+\.\d+)",
        }

        scraper = VersionScraper()
        result = scraper.scrape_version_number(config)

        assert result is not None
        assert result["latestVersion"] == "2.0.0"
