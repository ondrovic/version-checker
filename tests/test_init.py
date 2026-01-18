"""Tests for version_checker package initialization."""

import version_checker


class TestPackageInit:
    """Test cases for package __init__.py."""

    def test_version_attribute(self):
        """Test that __version__ is defined."""
        assert hasattr(version_checker, "__version__")
        assert isinstance(version_checker.__version__, str)
        assert version_checker.__version__ == "0.1.0"

    def test_author_attribute(self):
        """Test that __author__ is defined."""
        assert hasattr(version_checker, "__author__")
        assert isinstance(version_checker.__author__, str)

    def test_email_attribute(self):
        """Test that __email__ is defined."""
        assert hasattr(version_checker, "__email__")
        assert isinstance(version_checker.__email__, str)

    def test_all_exports(self):
        """Test that __all__ contains expected exports."""
        assert hasattr(version_checker, "__all__")
        expected_exports = ["scrape_version_number", "get_exe_version", "load_config"]
        assert set(version_checker.__all__) == set(expected_exports)

    def test_exported_functions_accessible(self):
        """Test that exported functions are accessible."""
        assert hasattr(version_checker, "scrape_version_number")
        assert hasattr(version_checker, "get_exe_version")
        assert hasattr(version_checker, "load_config")

    def test_scrape_version_number_import(self):
        """Test that scrape_version_number can be imported."""
        from version_checker import scrape_version_number

        assert callable(scrape_version_number)

    def test_get_exe_version_import(self):
        """Test that get_exe_version can be imported."""
        from version_checker import get_exe_version

        assert callable(get_exe_version)

    def test_load_config_import(self):
        """Test that load_config can be imported."""
        from version_checker import load_config

        assert callable(load_config)
