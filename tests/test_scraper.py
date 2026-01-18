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
