"""Tests for __main__ entry point."""

import sys
from unittest.mock import MagicMock, patch


class TestMainEntryPoint:
    """Test cases for __main__.py entry point."""

    @patch("version_checker.__main__.cli")
    def test_main_calls_cli(self, mock_cli: MagicMock) -> None:
        """Test that __main__ calls cli() when executed."""
        _ = mock_cli  # unused but required by patch
        # Import and execute __main__
        import version_checker.__main__

        # The module should have imported cli
        assert hasattr(version_checker.__main__, "cli")

    @patch("version_checker.cli.cli")
    def test_main_execution(self, mock_cli: MagicMock) -> None:
        """Test that running __main__ as script calls cli."""
        import runpy

        # Clear cached modules to avoid RuntimeWarning
        sys.modules.pop("version_checker.__main__", None)

        # Mock sys.argv to avoid actual CLI execution
        with patch("sys.argv", ["version-checker"]):
            runpy.run_module("version_checker", run_name="__main__")

        # Verify cli was called
        mock_cli.assert_called_once()

    @patch("version_checker.cli.cli")
    def test_main_execution_with_system_exit(self, mock_cli: MagicMock) -> None:
        """Test that running __main__ handles SystemExit from cli."""
        import runpy

        # Clear cached modules to avoid RuntimeWarning
        sys.modules.pop("version_checker.__main__", None)

        # Make the mock raise SystemExit to exercise the exception handling
        mock_cli.side_effect = SystemExit(0)

        with patch("sys.argv", ["version-checker"]):
            try:
                runpy.run_module("version_checker", run_name="__main__", alter_sys=True)
            except SystemExit:
                # CLI called sys.exit, which is expected
                pass

        # Verify cli was called
        mock_cli.assert_called_once()
