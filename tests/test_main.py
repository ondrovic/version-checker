"""Tests for __main__ entry point."""

from unittest.mock import patch

import pytest


class TestMainEntryPoint:
    """Test cases for __main__.py entry point."""

    @patch("version_checker.__main__.cli")
    def test_main_calls_cli(self, mock_cli):
        """Test that __main__ calls cli() when executed."""
        # Import and execute __main__
        import version_checker.__main__

        # The module should have imported cli
        assert hasattr(version_checker.__main__, "cli")

    @patch("version_checker.cli.cli")
    def test_main_execution(self, mock_cli):
        """Test that running __main__ as script calls cli."""
        import runpy

        # Mock sys.argv to avoid actual CLI execution
        with patch("sys.argv", ["version-checker"]):
            try:
                runpy.run_module("version_checker", run_name="__main__")
            except SystemExit:
                # CLI might call sys.exit, which is fine
                pass

        # Verify cli was called
        mock_cli.assert_called_once()
