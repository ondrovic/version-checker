"""Tests for platform detection utilities."""

from unittest.mock import patch

import pytest

from version_checker.utils.platform_utils import (
    build_download_url,
    get_platform_display_name,
    get_platform_info,
)


class TestGetPlatformInfo:
    """Test cases for get_platform_info function."""

    @patch("platform.system")
    @patch("platform.machine")
    def test_windows_x64(self, mock_machine, mock_system):
        """Test platform detection for Windows x64."""
        mock_system.return_value = "Windows"
        mock_machine.return_value = "AMD64"

        os_name, arch = get_platform_info()

        assert os_name == "windows"
        assert arch == "x64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_windows_x86_64(self, mock_machine, mock_system):
        """Test platform detection for Windows x86_64."""
        mock_system.return_value = "Windows"
        mock_machine.return_value = "x86_64"

        os_name, arch = get_platform_info()

        assert os_name == "windows"
        assert arch == "x64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_windows_arm64(self, mock_machine, mock_system):
        """Test platform detection for Windows ARM64."""
        mock_system.return_value = "Windows"
        mock_machine.return_value = "arm64"

        os_name, arch = get_platform_info()

        assert os_name == "windows"
        assert arch == "arm64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_windows_aarch64(self, mock_machine, mock_system):
        """Test platform detection for Windows aarch64."""
        mock_system.return_value = "Windows"
        mock_machine.return_value = "aarch64"

        os_name, arch = get_platform_info()

        assert os_name == "windows"
        assert arch == "arm64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_windows_unknown_arch(self, mock_machine, mock_system):
        """Test platform detection for Windows with unknown architecture."""
        mock_system.return_value = "Windows"
        mock_machine.return_value = "unknown"

        os_name, arch = get_platform_info()

        assert os_name == "windows"
        assert arch == "x64"  # Default to x64

    @patch("platform.system")
    @patch("platform.machine")
    def test_mac_arm64(self, mock_machine, mock_system):
        """Test platform detection for macOS ARM64."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"

        os_name, arch = get_platform_info()

        assert os_name == "mac"
        assert arch == "arm64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_mac_aarch64(self, mock_machine, mock_system):
        """Test platform detection for macOS aarch64."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "aarch64"

        os_name, arch = get_platform_info()

        assert os_name == "mac"
        assert arch == "arm64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_mac_intel(self, mock_machine, mock_system):
        """Test platform detection for macOS Intel."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "x86_64"

        os_name, arch = get_platform_info()

        assert os_name == "mac"
        assert arch == "intel"

    @patch("platform.system")
    @patch("platform.machine")
    def test_mac_amd64(self, mock_machine, mock_system):
        """Test platform detection for macOS AMD64."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "amd64"

        os_name, arch = get_platform_info()

        assert os_name == "mac"
        assert arch == "intel"

    @patch("platform.system")
    @patch("platform.machine")
    def test_mac_unknown_arch(self, mock_machine, mock_system):
        """Test platform detection for macOS with unknown architecture."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "unknown"

        os_name, arch = get_platform_info()

        assert os_name == "mac"
        assert arch == "arm64"  # Default to arm64 for newer Macs

    @patch("platform.system")
    @patch("platform.machine")
    def test_linux_amd64(self, mock_machine, mock_system):
        """Test platform detection for Linux AMD64."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"

        os_name, arch = get_platform_info()

        assert os_name == "linux"
        assert arch == "amd64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_linux_x86_64(self, mock_machine, mock_system):
        """Test platform detection for Linux x86_64."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "amd64"

        os_name, arch = get_platform_info()

        assert os_name == "linux"
        assert arch == "amd64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_linux_arm64(self, mock_machine, mock_system):
        """Test platform detection for Linux ARM64."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "arm64"

        os_name, arch = get_platform_info()

        assert os_name == "linux"
        assert arch == "arm64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_linux_aarch64(self, mock_machine, mock_system):
        """Test platform detection for Linux aarch64."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "aarch64"

        os_name, arch = get_platform_info()

        assert os_name == "linux"
        assert arch == "arm64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_linux_unknown_arch(self, mock_machine, mock_system):
        """Test platform detection for Linux with unknown architecture."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "unknown"

        os_name, arch = get_platform_info()

        assert os_name == "linux"
        assert arch == "amd64"  # Default to amd64

    @patch("platform.system")
    @patch("platform.machine")
    def test_unknown_os(self, mock_machine, mock_system):
        """Test platform detection for unknown OS."""
        mock_system.return_value = "UnknownOS"
        mock_machine.return_value = "x86_64"

        os_name, arch = get_platform_info()

        assert os_name == "linux"  # Default to linux
        assert arch == "amd64"


class TestBuildDownloadUrl:
    """Test cases for build_download_url function."""

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_build_url_windows_x64(self, mock_get_platform):
        """Test building download URL for Windows x64."""
        mock_get_platform.return_value = ("windows", "x64")

        url = build_download_url(
            "https://cos.olived.app/d/OlivedPro_", "0.23.4", "OlivedPro"
        )

        assert url == "https://cos.olived.app/d/OlivedPro_0.23.4_windows_x64.zip"

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_build_url_mac_arm64(self, mock_get_platform):
        """Test building download URL for macOS ARM64."""
        mock_get_platform.return_value = ("mac", "arm64")

        url = build_download_url(
            "https://cos.olived.app/d/OlivedPro_", "0.23.4", "OlivedPro"
        )

        assert url == "https://cos.olived.app/d/OlivedPro_0.23.4_mac_arm64.zip"

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_build_url_linux_amd64(self, mock_get_platform):
        """Test building download URL for Linux AMD64."""
        mock_get_platform.return_value = ("linux", "amd64")

        url = build_download_url(
            "https://cos.olived.app/d/OlivedPro_", "0.23.4", "OlivedPro"
        )

        assert url == "https://cos.olived.app/d/OlivedPro_0.23.4_linux_amd64.zip"

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_build_url_version_with_v_prefix(self, mock_get_platform):
        """Test building URL with version that has 'v' prefix."""
        mock_get_platform.return_value = ("windows", "x64")

        url = build_download_url(
            "https://cos.olived.app/d/OlivedPro_", "v0.23.4", "OlivedPro"
        )

        # Should strip 'v' prefix
        assert url == "https://cos.olived.app/d/OlivedPro_0.23.4_windows_x64.zip"

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_build_url_base_without_trailing_slash(self, mock_get_platform):
        """Test building URL when base URL doesn't end with app name."""
        mock_get_platform.return_value = ("windows", "x64")

        url = build_download_url("https://example.com/downloads", "0.23.4", "MyApp")

        assert url == "https://example.com/downloads/MyApp_0.23.4_windows_x64.zip"

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_build_url_base_with_trailing_slash(self, mock_get_platform):
        """Test building URL when base URL ends with slash."""
        mock_get_platform.return_value = ("windows", "x64")

        url = build_download_url("https://example.com/downloads/", "0.23.4", "MyApp")

        assert url == "https://example.com/downloads/MyApp_0.23.4_windows_x64.zip"

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_build_url_base_already_has_app_name(self, mock_get_platform):
        """Test building URL when base URL already ends with app name."""
        mock_get_platform.return_value = ("windows", "x64")

        url = build_download_url(
            "https://example.com/downloads/MyApp_", "0.23.4", "MyApp"
        )

        assert url == "https://example.com/downloads/MyApp_0.23.4_windows_x64.zip"

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_build_url_different_app_name(self, mock_get_platform):
        """Test building URL with different app name."""
        mock_get_platform.return_value = ("mac", "intel")

        url = build_download_url(
            "https://example.com/d/CustomApp_", "1.0.0", "CustomApp"
        )

        assert url == "https://example.com/d/CustomApp_1.0.0_mac_intel.zip"

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_build_url_complex_version(self, mock_get_platform):
        """Test building URL with complex version string."""
        mock_get_platform.return_value = ("linux", "arm64")

        url = build_download_url("https://example.com/d/App_", "v2.1.0-beta.1", "App")

        assert url == "https://example.com/d/App_2.1.0-beta.1_linux_arm64.zip"


class TestGetPlatformDisplayName:
    """Test cases for get_platform_display_name function."""

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_display_name_windows_x64(self, mock_get_platform):
        """Test display name for Windows x64."""
        mock_get_platform.return_value = ("windows", "x64")

        display_name = get_platform_display_name()

        assert display_name == "Windows X64"

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_display_name_mac_arm64(self, mock_get_platform):
        """Test display name for macOS ARM64."""
        mock_get_platform.return_value = ("mac", "arm64")

        display_name = get_platform_display_name()

        assert display_name == "macOS ARM64"

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_display_name_mac_intel(self, mock_get_platform):
        """Test display name for macOS Intel."""
        mock_get_platform.return_value = ("mac", "intel")

        display_name = get_platform_display_name()

        assert display_name == "macOS INTEL"

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_display_name_linux_amd64(self, mock_get_platform):
        """Test display name for Linux AMD64."""
        mock_get_platform.return_value = ("linux", "amd64")

        display_name = get_platform_display_name()

        assert display_name == "Linux AMD64"

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_display_name_linux_arm64(self, mock_get_platform):
        """Test display name for Linux ARM64."""
        mock_get_platform.return_value = ("linux", "arm64")

        display_name = get_platform_display_name()

        assert display_name == "Linux ARM64"

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_display_name_windows_arm64(self, mock_get_platform):
        """Test display name for Windows ARM64."""
        mock_get_platform.return_value = ("windows", "arm64")

        display_name = get_platform_display_name()

        assert display_name == "Windows ARM64"

    @patch("version_checker.utils.platform_utils.get_platform_info")
    def test_display_name_unknown_os(self, mock_get_platform):
        """Test display name for unknown OS."""
        mock_get_platform.return_value = ("unknownos", "x64")

        display_name = get_platform_display_name()

        assert display_name == "Unknownos X64"
