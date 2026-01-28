"""Tests for configuration management with Hydra."""

import tempfile
from pathlib import Path

import pytest
from omegaconf import DictConfig

from unittest.mock import patch

from version_checker.core.config import (
    ConfigError,
    get_config_as_dict,
    load_config,
    select_config_file,
)
from version_checker.utils.helpers import get_config_dir


class TestConfigLoading:
    """Test cases for Hydra configuration loading."""

    @pytest.fixture
    def sample_config_file(self, temp_dir):
        """Create a sample config file for testing."""
        config_content = """
site_url: "https://example.com/software"
file_path: "/path/to/software.exe"
css_selector: ".version-number"
detailed_info: false
timeout: 10
base_download_url: "https://example.com/downloads/"
"""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(config_content)
        return config_file

    @pytest.fixture
    def minimal_config_file(self, temp_dir):
        """Create a minimal config file with only required fields."""
        config_content = """
site_url: "https://example.com/software"
file_path: "/path/to/software.exe"
css_selector: ".version-number"
"""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(config_content)
        return config_file

    def test_load_config_success(self, sample_config_file):
        """Test successful configuration loading."""
        cfg = load_config(str(sample_config_file))

        assert isinstance(cfg, DictConfig)
        assert cfg.site_url == "https://example.com/software"
        assert cfg.file_path == "/path/to/software.exe"
        assert cfg.css_selector == ".version-number"
        assert cfg.detailed_info is False
        assert cfg.timeout == 10
        assert cfg.base_download_url == "https://example.com/downloads/"

    def test_load_config_with_defaults(self, minimal_config_file):
        """Test that defaults are applied for optional fields."""
        cfg = load_config(str(minimal_config_file))

        assert cfg.site_url == "https://example.com/software"
        assert cfg.file_path == "/path/to/software.exe"
        assert cfg.css_selector == ".version-number"
        # Check defaults
        assert cfg.detailed_info is False
        assert cfg.timeout == 10
        assert cfg.base_download_url is None
        assert cfg.auto_install is False

    def test_load_config_with_overrides(self, sample_config_file):
        """Test configuration loading with Hydra overrides."""
        cfg = load_config(
            str(sample_config_file),
            overrides=["timeout=20", "detailed_info=true"],
        )

        assert cfg.timeout == 20
        assert cfg.detailed_info is True
        # Original values should remain
        assert cfg.site_url == "https://example.com/software"

    def test_load_config_override_all_fields(self, sample_config_file):
        """Test overriding multiple fields including required ones."""
        cfg = load_config(
            str(sample_config_file),
            overrides=[
                "site_url=https://newsite.com",
                "file_path=/new/path.exe",
                "css_selector='.new-selector'",  # Quote selector to handle special chars
                "timeout=30",
            ],
        )

        assert cfg.site_url == "https://newsite.com"
        assert cfg.file_path == "/new/path.exe"
        assert cfg.css_selector == ".new-selector"
        assert cfg.timeout == 30

    def test_load_config_missing_file(self):
        """Test error when config file doesn't exist."""
        with pytest.raises(ConfigError) as exc_info:
            load_config("/nonexistent/path/config.yaml")

        assert "not found" in str(exc_info.value).lower()

    def test_load_config_missing_required_field(self, temp_dir):
        """Test error when required field is missing."""
        incomplete_config = temp_dir / "config.yaml"
        incomplete_config.write_text("site_url: 'https://example.com'\n")

        with pytest.raises(ConfigError) as exc_info:
            load_config(str(incomplete_config))

        assert "missing required field" in str(exc_info.value).lower()

    def test_load_config_dict_compatibility(self, sample_config_file):
        """Test that DictConfig is dict-compatible."""
        cfg = load_config(str(sample_config_file))

        # Test dict-style access
        assert cfg["site_url"] == "https://example.com/software"
        assert cfg["file_path"] == "/path/to/software.exe"

        # Test .get() method
        assert cfg.get("timeout") == 10
        assert cfg.get("nonexistent_key", "default") == "default"

        # Test membership
        assert "site_url" in cfg
        assert "nonexistent_key" not in cfg

    def test_get_config_as_dict(self, sample_config_file):
        """Test conversion of DictConfig to regular dict."""
        cfg = load_config(str(sample_config_file))
        config_dict = get_config_as_dict(cfg)

        assert isinstance(config_dict, dict)
        assert config_dict["site_url"] == "https://example.com/software"
        assert config_dict["timeout"] == 10

    def test_load_config_invalid_yaml(self, temp_dir):
        """Test error handling for invalid YAML syntax."""
        invalid_config = temp_dir / "config.yaml"
        invalid_config.write_text("site_url: [invalid: yaml: syntax")

        with pytest.raises(ConfigError):
            load_config(str(invalid_config))

    def test_load_config_type_override(self, sample_config_file):
        """Test that type conversions work in overrides."""
        cfg = load_config(
            str(sample_config_file),
            overrides=["timeout=15", "detailed_info=false"],
        )

        assert isinstance(cfg.timeout, int)
        assert isinstance(cfg.detailed_info, bool)

    def test_config_dir_creation(self):
        """Test that config directory is created if it doesn't exist."""
        config_dir = get_config_dir()
        assert config_dir.exists()
        assert config_dir.is_dir()

    def test_multiple_load_calls(self, sample_config_file):
        """Test that multiple load_config calls work correctly."""
        # First load
        cfg1 = load_config(str(sample_config_file))
        assert cfg1.timeout == 10

        # Second load with overrides
        cfg2 = load_config(str(sample_config_file), overrides=["timeout=20"])
        assert cfg2.timeout == 20

        # Third load without overrides should reset
        cfg3 = load_config(str(sample_config_file))
        assert cfg3.timeout == 10


class TestConfigCompatibility:
    """Test backward compatibility with old config system."""

    @pytest.fixture
    def legacy_style_config(self, temp_dir):
        """Create a config file in legacy format."""
        config_content = """# Legacy config format
site_url: "https://legacy.com/app"
file_path: "C:/Program Files/App/app.exe"
css_selector: "body > nav > div > a:nth-child(6)"
detailed_info: false
timeout: 10
"""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(config_content)
        return config_file

    def test_legacy_config_loads(self, legacy_style_config):
        """Test that legacy config format still works."""
        cfg = load_config(str(legacy_style_config))

        assert cfg.site_url == "https://legacy.com/app"
        assert cfg.file_path == "C:/Program Files/App/app.exe"
        assert cfg.detailed_info is False

    def test_config_dict_style_access(self, legacy_style_config):
        """Test that old dict-style access still works."""
        cfg = load_config(str(legacy_style_config))

        # Old code used dict-style access
        assert cfg["site_url"] == "https://legacy.com/app"
        assert cfg["file_path"] == "C:/Program Files/App/app.exe"
        assert cfg.get("timeout", 10) == 10
        assert cfg.get("base_download_url") is None


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_required_site_url(self, temp_dir):
        """Test that site_url is required."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("file_path: '/path/to/exe'\ncss_selector: '.version'\n")

        with pytest.raises(ConfigError) as exc_info:
            load_config(str(config_file))

        assert "site_url" in str(exc_info.value).lower()

    def test_validate_required_file_path(self, temp_dir):
        """Test that file_path is required."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            "site_url: 'https://example.com'\ncss_selector: '.version'\n"
        )

        with pytest.raises(ConfigError) as exc_info:
            load_config(str(config_file))

        assert "file_path" in str(exc_info.value).lower()

    def test_validate_required_css_selector(self, temp_dir):
        """Test that css_selector is required."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            "site_url: 'https://example.com'\nfile_path: '/path/to/exe'\n"
        )

        with pytest.raises(ConfigError) as exc_info:
            load_config(str(config_file))

        assert "css_selector" in str(exc_info.value).lower()

    def test_validate_github_provider_missing_repo(self, temp_dir):
        """Test that github_repo is required for github provider."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            "update_type: github\nfile_path: '/path/to/exe'\n"
        )

        with pytest.raises(ConfigError) as exc_info:
            load_config(str(config_file))

        assert "github_repo" in str(exc_info.value).lower()

    def test_validate_github_provider_with_repo(self, temp_dir):
        """Test that github provider works with github_repo specified."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            "update_type: github\nfile_path: '/path/to/exe'\ngithub_repo: 'owner/repo'\n"
        )

        cfg = load_config(str(config_file))

        assert cfg.update_type == "github"
        assert cfg.github_repo == "owner/repo"

    def test_validate_invalid_update_type(self, temp_dir):
        """Test error for invalid update_type."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            "update_type: invalid\nfile_path: '/path/to/exe'\n"
        )

        with pytest.raises(ConfigError) as exc_info:
            load_config(str(config_file))

        assert "invalid update_type" in str(exc_info.value).lower()


class TestSelectConfigFile:
    """Test cases for config file selection functionality."""

    def test_select_config_file_empty_list(self):
        """Test select_config_file returns None for empty list."""
        result = select_config_file([])

        assert result is None

    def test_select_config_file_valid_selection(self, temp_dir):
        """Test select_config_file with valid user selection."""
        file1 = temp_dir / "app1.yaml"
        file2 = temp_dir / "app2.yaml"
        file1.touch()
        file2.touch()

        with patch("version_checker.core.config.questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = "app1.yaml"
            result = select_config_file([file1, file2])

        assert result == file1

    def test_select_config_file_second_option(self, temp_dir):
        """Test select_config_file selecting second option."""
        file1 = temp_dir / "app1.yaml"
        file2 = temp_dir / "app2.yaml"
        file1.touch()
        file2.touch()

        with patch("version_checker.core.config.questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = "app2.yaml"
            result = select_config_file([file1, file2])

        assert result == file2

    def test_select_config_file_cancel(self, temp_dir):
        """Test select_config_file exits cleanly when user cancels."""
        file1 = temp_dir / "app1.yaml"
        file1.touch()

        with patch("version_checker.core.config.questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = "Cancel"
            with pytest.raises(SystemExit) as exc_info:
                select_config_file([file1])

        assert exc_info.value.code == 0

    def test_select_config_file_keyboard_interrupt(self, temp_dir):
        """Test select_config_file exits cleanly on keyboard interrupt."""
        file1 = temp_dir / "app1.yaml"
        file1.touch()

        with patch("version_checker.core.config.questionary.select") as mock_select:
            mock_select.return_value.ask.side_effect = KeyboardInterrupt
            with pytest.raises(SystemExit) as exc_info:
                select_config_file([file1])

        assert exc_info.value.code == 0

    def test_select_config_file_eof_error(self, temp_dir):
        """Test select_config_file exits cleanly on EOF error."""
        file1 = temp_dir / "app1.yaml"
        file1.touch()

        with patch("version_checker.core.config.questionary.select") as mock_select:
            mock_select.return_value.ask.side_effect = EOFError
            with pytest.raises(SystemExit) as exc_info:
                select_config_file([file1])

        assert exc_info.value.code == 0

    def test_select_config_file_none_response(self, temp_dir):
        """Test select_config_file exits cleanly on None response (Ctrl+C)."""
        file1 = temp_dir / "app1.yaml"
        file1.touch()

        with patch("version_checker.core.config.questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = None
            with pytest.raises(SystemExit) as exc_info:
                select_config_file([file1])

        assert exc_info.value.code == 0


class TestConfigFallbackSelection:
    """Test cases for config fallback selection when default is missing."""

    def test_load_config_uses_selected_file(self, temp_dir, monkeypatch):
        """Test load_config uses user-selected config when default missing."""
        config_dir = temp_dir / "version-checker"
        config_dir.mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(temp_dir))

        # Create an alternative config (not config.yaml)
        alt_config = config_dir / "myapp.yaml"
        alt_config.write_text(
            "site_url: 'https://alt.com'\n"
            "file_path: '/alt/path'\n"
            "css_selector: '.alt'\n"
        )

        with patch("version_checker.core.config.questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = "myapp.yaml"
            cfg = load_config(None)

        assert cfg.site_url == "https://alt.com"

    def test_load_config_cancel_selection_exits_cleanly(self, temp_dir, monkeypatch):
        """Test load_config exits cleanly when user cancels selection."""
        config_dir = temp_dir / "version-checker"
        config_dir.mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(temp_dir))

        # Create an alternative config
        alt_config = config_dir / "myapp.yaml"
        alt_config.touch()

        with patch("version_checker.core.config.questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = "Cancel"
            with pytest.raises(SystemExit) as exc_info:
                load_config(None)

        assert exc_info.value.code == 0


class TestResolveConfigPath:
    """Test cases for resolve_config_path function."""

    def test_resolve_config_path_default_exists(self, temp_dir, monkeypatch):
        """Test resolve_config_path when default config exists."""
        from version_checker.core.config import resolve_config_path

        config_dir = temp_dir / "version-checker"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.yaml"
        config_file.write_text("file_path: /test\n")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(temp_dir))

        result = resolve_config_path(None)

        assert result == config_file

    def test_resolve_config_path_no_configs_available(self, temp_dir, monkeypatch):
        """Test resolve_config_path when no configs available."""
        from version_checker.core.config import ConfigError, resolve_config_path

        config_dir = temp_dir / "version-checker"
        config_dir.mkdir(parents=True)
        # Don't create any config files
        monkeypatch.setenv("XDG_CONFIG_HOME", str(temp_dir))

        with pytest.raises(ConfigError) as exc_info:
            resolve_config_path(None)

        assert "no configuration file found" in str(exc_info.value).lower()


class TestLoadConfigEdgeCases:
    """Test edge cases for load_config function."""

    def test_load_config_file_exists_after_resolve(self, temp_dir):
        """Test load_config when file exists after resolution."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            "site_url: 'https://example.com'\n"
            "file_path: '/path/to/exe'\n"
            "css_selector: '.version'\n"
        )

        cfg = load_config(str(config_file))

        assert cfg.file_path == "/path/to/exe"

    def test_load_config_file_deleted_after_resolve(self, temp_dir):
        """Test load_config when file is deleted after resolve_config_path."""
        from version_checker.core.config import ConfigError

        config_file = temp_dir / "config.yaml"
        config_file.write_text("file_path: '/path/to/exe'\n")

        # Mock resolve_config_path to return the path, then delete the file
        with patch("version_checker.core.config.resolve_config_path") as mock_resolve:
            mock_resolve.return_value = config_file
            # Delete the file after resolve returns but before load checks
            config_file.unlink()

            with pytest.raises(ConfigError) as exc_info:
                load_config(str(config_file))

            assert "not found" in str(exc_info.value).lower()
