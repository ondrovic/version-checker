"""Tests for helper utility functions."""

from pathlib import Path
from unittest.mock import patch


from version_checker.utils.helpers import (
    clear_screen,
    format_version,
    get_config_dir,
    get_default_config_path,
    get_platform_info,
    is_windows,
)


class TestClearScreen:
    """Test cases for clear_screen function."""

    @patch("platform.system")
    @patch("os.system")
    def test_clear_screen_windows(self, mock_os_system, mock_platform_system):
        """Test clear_screen on Windows."""
        mock_platform_system.return_value = "Windows"

        clear_screen()

        mock_os_system.assert_called_once_with("cls")

    @patch("platform.system")
    @patch("os.system")
    def test_clear_screen_unix(self, mock_os_system, mock_platform_system):
        """Test clear_screen on Unix-like systems."""
        mock_platform_system.return_value = "Linux"

        clear_screen()

        mock_os_system.assert_called_once_with("clear")

    @patch("platform.system")
    @patch("os.system")
    def test_clear_screen_mac(self, mock_os_system, mock_platform_system):
        """Test clear_screen on macOS."""
        mock_platform_system.return_value = "Darwin"

        clear_screen()

        mock_os_system.assert_called_once_with("clear")


class TestFormatVersion:
    """Test cases for format_version function."""

    def test_format_version_with_v_prefix(self):
        """Test formatting version that already has 'v' prefix."""
        assert format_version("v1.0.0") == "v1.0.0"
        assert format_version("v2.3.4") == "v2.3.4"

    def test_format_version_without_v_prefix(self):
        """Test formatting version without 'v' prefix."""
        assert format_version("1.0.0") == "v1.0.0"
        assert format_version("2.3.4") == "v2.3.4"

    def test_format_version_empty_string(self):
        """Test formatting empty version string."""
        assert format_version("") == "Unknown"

    def test_format_version_none(self):
        """Test formatting None version."""
        assert format_version(None) == "Unknown"

    def test_format_version_complex(self):
        """Test formatting complex version strings."""
        assert format_version("1.0.0-beta") == "v1.0.0-beta"
        assert format_version("v1.0.0-beta") == "v1.0.0-beta"


class TestIsWindows:
    """Test cases for is_windows function."""

    @patch("platform.system")
    def test_is_windows_true(self, mock_platform_system):
        """Test is_windows returns True on Windows."""
        mock_platform_system.return_value = "Windows"

        assert is_windows() is True

    @patch("platform.system")
    def test_is_windows_false_linux(self, mock_platform_system):
        """Test is_windows returns False on Linux."""
        mock_platform_system.return_value = "Linux"

        assert is_windows() is False

    @patch("platform.system")
    def test_is_windows_false_mac(self, mock_platform_system):
        """Test is_windows returns False on macOS."""
        mock_platform_system.return_value = "Darwin"

        assert is_windows() is False


class TestGetPlatformInfo:
    """Test cases for get_platform_info function."""

    def test_get_platform_info_returns_dict(self):
        """Test that get_platform_info returns a dictionary."""
        info = get_platform_info()

        assert isinstance(info, dict)

    def test_get_platform_info_has_required_keys(self):
        """Test that platform info contains all required keys."""
        info = get_platform_info()

        required_keys = ["system", "release", "version", "machine", "processor"]
        for key in required_keys:
            assert key in info

    def test_get_platform_info_values_are_strings(self):
        """Test that all platform info values are strings."""
        info = get_platform_info()

        for value in info.values():
            assert isinstance(value, str)

    @patch("platform.system")
    @patch("platform.release")
    @patch("platform.version")
    @patch("platform.machine")
    @patch("platform.processor")
    def test_get_platform_info_mocked(
        self,
        mock_processor,
        mock_machine,
        mock_version,
        mock_release,
        mock_system,
    ):
        """Test get_platform_info with mocked platform functions."""
        mock_system.return_value = "TestOS"
        mock_release.return_value = "1.0"
        mock_version.return_value = "1.0.0"
        mock_machine.return_value = "x86_64"
        mock_processor.return_value = "TestProcessor"

        info = get_platform_info()

        assert info["system"] == "TestOS"
        assert info["release"] == "1.0"
        assert info["version"] == "1.0.0"
        assert info["machine"] == "x86_64"
        assert info["processor"] == "TestProcessor"


class TestGetConfigDir:
    """Test cases for get_config_dir function."""

    def test_get_config_dir_returns_path(self):
        """Test that get_config_dir returns a Path object."""
        config_dir = get_config_dir()

        assert isinstance(config_dir, Path)

    def test_get_config_dir_creates_directory(self, temp_dir, monkeypatch):
        """Test that get_config_dir creates the directory if it doesn't exist."""
        # Set up a temporary config directory
        test_config_dir = temp_dir / ".config" / "version-checker"

        # Mock Path.home() to return temp_dir
        monkeypatch.setenv("XDG_CONFIG_HOME", "")
        with patch("pathlib.Path.home", return_value=temp_dir):
            config_dir = get_config_dir()

            assert config_dir.exists()
            assert config_dir.is_dir()

    def test_get_config_dir_with_xdg_config_home(self, temp_dir, monkeypatch):
        """Test get_config_dir respects XDG_CONFIG_HOME environment variable."""
        xdg_config = temp_dir / "custom_config"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))

        config_dir = get_config_dir()

        assert config_dir == xdg_config / "version-checker"
        assert config_dir.exists()

    def test_get_config_dir_without_xdg_config_home(self, temp_dir, monkeypatch):
        """Test get_config_dir uses ~/.config when XDG_CONFIG_HOME is not set."""
        # Unset XDG_CONFIG_HOME
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        with patch("pathlib.Path.home", return_value=temp_dir):
            config_dir = get_config_dir()

            assert config_dir == temp_dir / ".config" / "version-checker"

    def test_get_config_dir_idempotent(self):
        """Test that calling get_config_dir multiple times returns same path."""
        config_dir1 = get_config_dir()
        config_dir2 = get_config_dir()

        assert config_dir1 == config_dir2


class TestGetDefaultConfigPath:
    """Test cases for get_default_config_path function."""

    def test_get_default_config_path_returns_path(self):
        """Test that get_default_config_path returns a Path object."""
        config_path = get_default_config_path()

        assert isinstance(config_path, Path)

    def test_get_default_config_path_ends_with_config_yaml(self):
        """Test that default config path ends with config.yaml."""
        config_path = get_default_config_path()

        assert config_path.name == "config.yaml"

    def test_get_default_config_path_in_config_dir(self, temp_dir, monkeypatch):
        """Test that default config path is in the config directory."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        with patch("pathlib.Path.home", return_value=temp_dir):
            config_path = get_default_config_path()
            config_dir = get_config_dir()

            assert config_path.parent == config_dir

    def test_get_default_config_path_with_xdg(self, temp_dir, monkeypatch):
        """Test default config path with XDG_CONFIG_HOME set."""
        xdg_config = temp_dir / "custom_config"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))

        config_path = get_default_config_path()

        expected_path = xdg_config / "version-checker" / "config.yaml"
        assert config_path == expected_path
