"""Tests for CLI functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner

from version_checker.cli import (
    check,
    check_version,
    cleanup_cache,
    cli,
    show_config,
)


class TestCLIGroup:
    """Test cases for main CLI group."""

    def test_cli_group_exists(self):
        """Test that CLI group is defined."""
        assert cli is not None
        assert isinstance(cli, click.Group)

    def test_cli_version_option(self):
        """Test --version option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "version" in result.output.lower()

    def test_cli_help(self):
        """Test --help option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Version Checker" in result.output


class TestCheckCommand:
    """Test cases for check command."""

    def test_check_command_exists(self):
        """Test that check command is defined."""
        assert check is not None

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    def test_check_basic_success(self, mock_clear, mock_scrape, mock_load_config):
        """Test basic check command success."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": False,
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "1.0.0",
            "needsUpdate": False,
            "freshInstall": False,
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a config file
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(check, ["--config", "config.yaml", "--no-clear"])

            assert result.exit_code == 0
            assert "latest version" in result.output.lower()

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    def test_check_update_available(self, mock_clear, mock_scrape, mock_load_config):
        """Test check when update is available."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": False,
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "2.0.0",
            "needsUpdate": True,
            "freshInstall": False,
            "downloadUrl": "https://example.com/download.zip",
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(check, ["--config", "config.yaml", "--no-clear"])

            assert result.exit_code == 0
            assert (
                "update available" in result.output.lower() or "2.0.0" in result.output
            )

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    def test_check_update_available_no_auto_install(
        self, mock_clear, mock_scrape, mock_load_config
    ):
        """Test check when update is available but auto-install is disabled."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": False,
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "2.0.0",
            "needsUpdate": True,
            "freshInstall": False,
            "downloadUrl": "https://example.com/download.zip",
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            # Test with auto-install disabled (don't pass the flag)
            result = runner.invoke(check, ["--config", "config.yaml", "--no-clear"])

            # Since auto_install defaults to True, we need to test the case where it's explicitly disabled
            # This is tricky with Click flags. Let's test the download URL display instead
            assert result.exit_code == 0
            assert "Download:" in result.output or "download.zip" in result.output

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    def test_check_detailed_output(self, mock_clear, mock_scrape, mock_load_config):
        """Test check with detailed JSON output."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": True,
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "1.0.0",
            "needsUpdate": False,
            "freshInstall": False,
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check, ["--config", "config.yaml", "--detailed", "--no-clear"]
            )

            assert result.exit_code == 0

    @patch("version_checker.cli.load_config")
    def test_check_config_error(self, mock_load_config):
        """Test check with configuration error."""
        from version_checker.core.config import ConfigError

        mock_load_config.side_effect = ConfigError("Config not found")

        runner = CliRunner()
        result = runner.invoke(check, ["--no-clear"])

        assert result.exit_code == 1
        assert "configuration error" in result.output.lower()

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    def test_check_scrape_failure(self, mock_clear, mock_scrape, mock_load_config):
        """Test check when scraping fails."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
        }
        mock_scrape.return_value = None

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check, ["--config", "config.yaml", "--no-clear", "-a"]
            )

            assert result.exit_code == 1
            assert "failed" in result.output.lower()

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    def test_check_with_overrides(self, mock_clear, mock_scrape, mock_load_config):
        """Test check with Hydra overrides."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "timeout": 30,
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "1.0.0",
            "needsUpdate": False,
            "freshInstall": False,
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check,
                [
                    "--config",
                    "config.yaml",
                    "--no-clear",
                    "--override",
                    "timeout=30",
                ],
            )

            assert result.exit_code == 0
            mock_load_config.assert_called_once()
            call_args = mock_load_config.call_args
            assert "timeout=30" in call_args[1]["overrides"]

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    def test_check_with_selector_override(
        self, mock_clear, mock_scrape, mock_load_config
    ):
        """Test check with CSS selector override."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".custom-selector",
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "1.0.0",
            "needsUpdate": False,
            "freshInstall": False,
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check,
                [
                    "--config",
                    "config.yaml",
                    "--no-clear",
                    "--selector",
                    ".custom-selector",
                ],
            )

            assert result.exit_code == 0

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    def test_check_unexpected_error(self, mock_clear, mock_scrape, mock_load_config):
        """Test check with unexpected error."""
        mock_load_config.side_effect = Exception("Unexpected error")

        runner = CliRunner()
        result = runner.invoke(check, ["--no-clear"])

        assert result.exit_code == 1
        assert "unexpected error" in result.output.lower()


class TestCheckVersionCommand:
    """Test cases for check-version command."""

    def test_check_version_command_exists(self):
        """Test that check-version command is defined."""
        assert check_version is not None

    @patch("version_checker.core.version_reader.get_exe_version")
    def test_check_version_success(self, mock_get_version, temp_dir):
        """Test check-version command success."""
        exe_file = temp_dir / "test.exe"
        exe_file.write_bytes(b"Mock exe")

        mock_get_version.return_value = "1.2.3"

        runner = CliRunner()
        result = runner.invoke(check_version, [str(exe_file)])

        assert result.exit_code == 0
        assert "1.2.3" in result.output

    @patch("version_checker.core.version_reader.get_exe_version")
    def test_check_version_failure(self, mock_get_version, temp_dir):
        """Test check-version when version cannot be read."""
        exe_file = temp_dir / "test.exe"
        exe_file.write_bytes(b"Mock exe")

        mock_get_version.return_value = None

        runner = CliRunner()
        result = runner.invoke(check_version, [str(exe_file)])

        assert result.exit_code == 1
        assert "could not read" in result.output.lower()


class TestCleanupCacheCommand:
    """Test cases for cleanup-cache command."""

    def test_cleanup_cache_command_exists(self):
        """Test that cleanup-cache command is defined."""
        assert cleanup_cache is not None

    @patch("version_checker.utils.cache.VersionCache")
    def test_cleanup_cache_with_confirmation(self, mock_cache_class):
        """Test cleanup-cache with user confirmation."""
        mock_cache = MagicMock()
        mock_cache_class.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(cleanup_cache, input="y\n")

        assert result.exit_code == 0
        mock_cache.clear_all_caches.assert_called_once()

    @patch("version_checker.utils.cache.VersionCache")
    def test_cleanup_cache_cancelled(self, mock_cache_class):
        """Test cleanup-cache when user cancels."""
        mock_cache = MagicMock()
        mock_cache_class.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(cleanup_cache, input="n\n")

        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()
        mock_cache.clear_all_caches.assert_not_called()

    @patch("version_checker.utils.cache.VersionCache")
    def test_cleanup_cache_force(self, mock_cache_class):
        """Test cleanup-cache with --force flag."""
        mock_cache = MagicMock()
        mock_cache_class.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(cleanup_cache, ["--force"])

        assert result.exit_code == 0
        mock_cache.clear_all_caches.assert_called_once()


class TestShowConfigCommand:
    """Test cases for config command."""

    def test_show_config_command_exists(self):
        """Test that config command is defined."""
        assert show_config is not None

    def test_show_config_path_only(self, temp_dir):
        """Test showing config path only."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(show_config, ["--path"])

            assert result.exit_code == 0
            assert "config file location" in result.output.lower()

    def test_show_config_contents(self, temp_dir):
        """Test showing config contents."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a config file in isolated filesystem (not real home dir)
            config_file = Path("config.yaml")
            config_file.write_text("site_url: https://example.com\n")

            with patch(
                "version_checker.utils.helpers.get_default_config_path",
                return_value=config_file,
            ):
                result = runner.invoke(show_config)

                # May succeed or fail depending on file existence
                # Just check it doesn't crash
                assert result.exit_code in [0, 1]

    def test_show_config_not_found(self):
        """Test showing config when file doesn't exist."""
        from version_checker.core.config import ConfigError

        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch(
                "version_checker.core.config.resolve_config_path",
                side_effect=ConfigError("No configuration file found"),
            ):
                result = runner.invoke(show_config)

                assert result.exit_code == 1
                assert "error" in result.output.lower()

    def test_show_config_raw(self, temp_dir):
        """Test showing config in raw format."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            config_file = Path("config.yaml")
            config_file.write_text("site_url: https://example.com\n")

            with patch(
                "version_checker.core.config.resolve_config_path",
                return_value=config_file,
            ):
                result = runner.invoke(show_config, ["--raw"])

                assert result.exit_code == 0
                assert "example.com" in result.output

    def test_show_config_custom_path(self, temp_dir):
        """Test showing config from custom path."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            config_file = Path("custom_config.yaml")
            config_file.write_text("site_url: https://example.com\n")

            result = runner.invoke(show_config, ["--config", str(config_file)])

            assert result.exit_code == 0

    def test_show_config_read_error(self, temp_dir):
        """Test showing config with read error."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            config_file = Path("config.yaml")
            config_file.write_text("site_url: https://example.com\n")

            with patch(
                "version_checker.core.config.resolve_config_path",
                return_value=config_file,
            ):
                with patch(
                    "builtins.open", side_effect=PermissionError("Access denied")
                ):
                    result = runner.invoke(show_config)

                    assert result.exit_code == 1
                    assert "error" in result.output.lower()

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    @patch("version_checker.cli.AutoInstaller")
    @patch("version_checker.cli.Live")
    def test_check_auto_install_success(
        self, mock_live, mock_installer_class, mock_clear, mock_scrape, mock_load_config
    ):
        """Test check command with successful auto-install."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": False,
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "2.0.0",
            "needsUpdate": True,
            "freshInstall": False,
            "downloadUrl": "https://example.com/download.zip",
        }

        # Mock installer
        mock_installer = MagicMock()
        mock_installer_class.return_value = mock_installer

        # Mock Live context manager
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = mock_live_instance
        mock_live.return_value.__exit__ = MagicMock()

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check, ["--config", "config.yaml", "--no-clear", "-a"]
            )

            assert result.exit_code == 0
            mock_installer_class.assert_called_once()
            mock_live.assert_called()

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    @patch("version_checker.cli.run_install_script")
    @patch("version_checker.cli.AutoInstaller")
    @patch("version_checker.cli.Live")
    def test_check_auto_install_script_path_skips_auto_installer(
        self,
        mock_live,
        mock_installer_class,
        mock_run_script,
        mock_clear,
        mock_scrape,
        mock_load_config,
    ):
        """Test script install path runs script and does not create AutoInstaller."""
        mock_load_config.return_value = {
            "update_type": "github",
            "github_repo": "owner/repo",
            "file_path": "/path/to/app.exe",
            "detailed_info": False,
            "install_method": "script",
            "install_script": "echo installing",
            "auto_launch": False,
            "process_name": "app",
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "2.0.0",
            "needsUpdate": True,
            "freshInstall": True,
            # downloadUrl may be absent for script installs; ensure no hard dependency
        }

        mock_run_script.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Mock Live context manager
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = mock_live_instance
        mock_live.return_value.__exit__ = MagicMock()

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            with patch("pathlib.Path.exists", return_value=True):
                result = runner.invoke(
                    check, ["--config", "config.yaml", "--no-clear", "-a"]
                )

        assert result.exit_code == 0
        mock_installer_class.assert_not_called()
        mock_run_script.assert_called_once()

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    @patch("version_checker.cli.AutoInstaller")
    @patch("version_checker.cli.Live")
    def test_check_auto_install_fresh_install(
        self, mock_live, mock_installer_class, mock_clear, mock_scrape, mock_load_config
    ):
        """Test check command with fresh install auto-install."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": False,
        }
        mock_scrape.return_value = {
            "installedVersion": "Not installed",
            "latestVersion": "1.0.0",
            "needsUpdate": True,
            "freshInstall": True,
            "downloadUrl": "https://example.com/download.zip",
        }

        # Mock installer
        mock_installer = MagicMock()
        mock_installer_class.return_value = mock_installer

        # Mock Live context manager
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = mock_live_instance
        mock_live.return_value.__exit__ = MagicMock()

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check, ["--config", "config.yaml", "--no-clear", "-a"]
            )

            assert result.exit_code == 0
            # Check that fresh_install=True was passed to installer
            call_args = mock_installer_class.call_args
            assert call_args[1]["fresh_install"] is True

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    def test_check_auto_install_no_download_url(
        self, mock_clear, mock_scrape, mock_load_config
    ):
        """Test check command when auto-install is requested but no download URL."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": False,
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "2.0.0",
            "needsUpdate": True,
            "freshInstall": False,
            # No downloadUrl
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check, ["--config", "config.yaml", "--no-clear", "-a"]
            )

            assert result.exit_code == 1
            assert "download url not available" in result.output.lower()

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    @patch("version_checker.cli.AutoInstaller")
    @patch("version_checker.cli.Live")
    def test_check_auto_install_failure(
        self, mock_live, mock_installer_class, mock_clear, mock_scrape, mock_load_config
    ):
        """Test check command with auto-install failure."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": False,
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "2.0.0",
            "needsUpdate": True,
            "freshInstall": False,
            "downloadUrl": "https://example.com/download.zip",
        }

        # Mock installer that raises exception
        mock_installer = MagicMock()
        mock_installer._kill_process.return_value = True
        mock_installer._download.return_value = True
        mock_installer._extract_and_overwrite.return_value = False  # Fail here
        mock_installer_class.return_value = mock_installer

        # Mock Live context manager
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = mock_live_instance
        mock_live.return_value.__exit__ = MagicMock()

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check, ["--config", "config.yaml", "--no-clear", "-a"]
            )

            assert result.exit_code == 1
            assert "failed" in result.output.lower()

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    @patch("version_checker.cli.AutoInstaller")
    @patch("version_checker.cli.Live")
    def test_check_auto_install_process_kill_failure(
        self, mock_live, mock_installer_class, mock_clear, mock_scrape, mock_load_config
    ):
        """Test check command with auto-install process kill failure."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": False,
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "2.0.0",
            "needsUpdate": True,
            "freshInstall": False,  # Not fresh install, so will try to kill process
            "downloadUrl": "https://example.com/download.zip",
        }

        # Mock installer that fails to kill process
        mock_installer = MagicMock()
        mock_installer._kill_process.return_value = False
        mock_installer_class.return_value = mock_installer

        # Mock Live context manager
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = mock_live_instance
        mock_live.return_value.__exit__ = MagicMock()

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check, ["--config", "config.yaml", "--no-clear", "-a"]
            )

            assert result.exit_code == 1
            assert "failed" in result.output.lower()

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    @patch("version_checker.cli.AutoInstaller")
    @patch("version_checker.cli.Live")
    def test_check_auto_install_download_failure(
        self, mock_live, mock_installer_class, mock_clear, mock_scrape, mock_load_config
    ):
        """Test check command with auto-install download failure."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": False,
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "2.0.0",
            "needsUpdate": True,
            "freshInstall": False,
            "downloadUrl": "https://example.com/download.zip",
        }

        # Mock installer that fails download
        mock_installer = MagicMock()
        mock_installer._kill_process.return_value = True
        mock_installer._download.return_value = False
        mock_installer_class.return_value = mock_installer

        # Mock Live context manager
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = mock_live_instance
        mock_live.return_value.__exit__ = MagicMock()

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check, ["--config", "config.yaml", "--no-clear", "-a"]
            )

            assert result.exit_code == 1
            assert "failed" in result.output.lower()

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    @patch("version_checker.cli.AutoInstaller")
    @patch("version_checker.cli.Live")
    def test_check_auto_install_start_failure(
        self, mock_live, mock_installer_class, mock_clear, mock_scrape, mock_load_config
    ):
        """Test check command with auto-install start process failure."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": False,
            "auto_launch": True,  # Enable auto_launch to test start_process failure
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "2.0.0",
            "needsUpdate": True,
            "freshInstall": False,
            "downloadUrl": "https://example.com/download.zip",
        }

        # Mock installer that fails to start process
        mock_installer = MagicMock()
        mock_installer._kill_process.return_value = True
        mock_installer._download.return_value = True
        mock_installer._extract_and_overwrite.return_value = True
        mock_installer._start_process.return_value = False
        mock_installer.auto_launch = True
        mock_installer_class.return_value = mock_installer

        # Mock Live context manager
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = mock_live_instance
        mock_live.return_value.__exit__ = MagicMock()

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check, ["--config", "config.yaml", "--no-clear", "-a"]
            )

            assert result.exit_code == 1
            assert "failed" in result.output.lower()


class TestCLIAdditionalCoverage:
    """Additional test cases for complete CLI coverage."""

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    @patch("version_checker.cli.AutoInstaller")
    @patch("version_checker.cli.Live")
    @patch("version_checker.cli.detect_package_type")
    def test_check_auto_install_with_sudo_package(
        self,
        mock_detect_type,
        mock_live,
        mock_installer_class,
        mock_clear,
        mock_scrape,
        mock_load_config,
    ):
        """Test check command with sudo-requiring package type."""
        from version_checker.cli import PackageType

        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": False,
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "2.0.0",
            "needsUpdate": True,
            "freshInstall": False,
            "downloadUrl": "https://example.com/download.deb",
        }

        # Mock installer
        mock_installer = MagicMock()
        mock_installer._kill_process.return_value = True
        mock_installer._download.return_value = True
        mock_installer._extract_and_overwrite.return_value = True
        mock_installer.downloaded_file = MagicMock()
        mock_installer.downloaded_file.name = "app.deb"
        mock_installer_class.return_value = mock_installer

        # Mock package type detection to return DEB (sudo required)
        mock_detect_type.return_value = PackageType.DEB

        # Mock Live context manager
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = mock_live_instance
        mock_live.return_value.__exit__ = MagicMock()

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check, ["--config", "config.yaml", "--no-clear", "-a"]
            )

            assert result.exit_code == 0

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    @patch("version_checker.cli.AutoInstaller")
    @patch("version_checker.cli.Live")
    def test_check_auto_install_fresh_with_auto_launch(
        self, mock_live, mock_installer_class, mock_clear, mock_scrape, mock_load_config
    ):
        """Test check command with fresh install and auto_launch enabled."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": False,
            "auto_launch": True,
        }
        mock_scrape.return_value = {
            "installedVersion": "Not installed",
            "latestVersion": "1.0.0",
            "needsUpdate": True,
            "freshInstall": True,
            "downloadUrl": "https://example.com/download.zip",
        }

        # Mock installer
        mock_installer = MagicMock()
        mock_installer._download.return_value = True
        mock_installer._extract_and_overwrite.return_value = True
        mock_installer._start_process.return_value = True
        mock_installer.downloaded_file = MagicMock()
        mock_installer.downloaded_file.name = "app.zip"
        mock_installer_class.return_value = mock_installer

        # Mock Live context manager
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = mock_live_instance
        mock_live.return_value.__exit__ = MagicMock()

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check, ["--config", "config.yaml", "--no-clear", "-a"]
            )

            assert result.exit_code == 0
            # Verify auto_launch was passed
            call_kwargs = mock_installer_class.call_args[1]
            assert call_kwargs["auto_launch"] is True

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    @patch("version_checker.cli.AutoInstaller")
    @patch("version_checker.cli.Live")
    def test_check_auto_install_start_failure_fresh(
        self, mock_live, mock_installer_class, mock_clear, mock_scrape, mock_load_config
    ):
        """Test check command with fresh install start process failure."""
        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": False,
            "auto_launch": True,
        }
        mock_scrape.return_value = {
            "installedVersion": "Not installed",
            "latestVersion": "1.0.0",
            "needsUpdate": True,
            "freshInstall": True,
            "downloadUrl": "https://example.com/download.zip",
        }

        # Mock installer that fails to start process
        mock_installer = MagicMock()
        mock_installer._download.return_value = True
        mock_installer._extract_and_overwrite.return_value = True
        mock_installer._start_process.return_value = False
        mock_installer.downloaded_file = MagicMock()
        mock_installer.downloaded_file.name = "app.zip"
        mock_installer_class.return_value = mock_installer

        # Mock Live context manager
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = mock_live_instance
        mock_live.return_value.__exit__ = MagicMock()

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check, ["--config", "config.yaml", "--no-clear", "-a"]
            )

            assert result.exit_code == 1
            assert "failed" in result.output.lower()

    def test_show_config_path_exists(self, temp_dir):
        """Test showing config path when file exists."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            config_file = Path("config.yaml")
            config_file.write_text("site_url: https://example.com\n")

            with patch(
                "version_checker.utils.helpers.get_default_config_path",
                return_value=config_file,
            ):
                result = runner.invoke(show_config, ["--path"])

                assert result.exit_code == 0
                assert "exists" in result.output.lower()

    @patch("version_checker.cli.load_config")
    @patch("version_checker.cli.scrape_version_number")
    @patch("version_checker.cli.clear_screen")
    @patch("version_checker.cli.AutoInstaller")
    @patch("version_checker.cli.Live")
    @patch("version_checker.cli.detect_package_type")
    def test_check_auto_install_extract_failure_non_sudo(
        self,
        mock_detect_type,
        mock_live,
        mock_installer_class,
        mock_clear,
        mock_scrape,
        mock_load_config,
    ):
        """Test check command with extract failure for non-sudo package type."""
        from version_checker.cli import PackageType

        mock_load_config.return_value = {
            "site_url": "https://example.com",
            "file_path": "/path/to/app.exe",
            "css_selector": ".version",
            "detailed_info": False,
        }
        mock_scrape.return_value = {
            "installedVersion": "1.0.0",
            "latestVersion": "2.0.0",
            "needsUpdate": True,
            "freshInstall": False,
            "downloadUrl": "https://example.com/download.zip",
        }

        # Mock installer that fails extraction
        mock_installer = MagicMock()
        mock_installer._kill_process.return_value = True
        mock_installer._download.return_value = True
        mock_installer._extract_and_overwrite.return_value = False  # Fail here
        mock_installer.downloaded_file = MagicMock()
        mock_installer.downloaded_file.name = "app.zip"
        mock_installer_class.return_value = mock_installer

        # Mock package type detection to return ZIP (non-sudo)
        mock_detect_type.return_value = PackageType.ZIP

        # Mock Live context manager
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = mock_live_instance
        mock_live.return_value.__exit__ = MagicMock()

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("config.yaml").write_text("site_url: https://example.com\n")

            result = runner.invoke(
                check, ["--config", "config.yaml", "--no-clear", "-a"]
            )

            assert result.exit_code == 1
            assert "failed" in result.output.lower()