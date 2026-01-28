"""Tests for configuration schema."""

from dataclasses import fields

import pytest

from version_checker.core.config_schema import VersionCheckerConfig, register_configs


class TestVersionCheckerConfig:
    """Test cases for VersionCheckerConfig dataclass."""

    def test_config_is_dataclass(self):
        """Test that VersionCheckerConfig is a dataclass."""
        assert hasattr(VersionCheckerConfig, "__dataclass_fields__")

    def test_required_fields(self):
        """Test that required fields are defined."""
        config = VersionCheckerConfig(
            site_url="https://example.com",
            file_path="/path/to/exe",
            css_selector=".version",
        )

        assert config.site_url == "https://example.com"
        assert config.file_path == "/path/to/exe"
        assert config.css_selector == ".version"

    def test_optional_fields_defaults(self):
        """Test that optional fields have correct defaults."""
        config = VersionCheckerConfig(
            site_url="https://example.com",
            file_path="/path/to/exe",
            css_selector=".version",
        )

        assert config.base_download_url is None
        assert config.detailed_info is False
        assert config.timeout == 10

    def test_optional_fields_custom_values(self):
        """Test that optional fields can be set to custom values."""
        config = VersionCheckerConfig(
            site_url="https://example.com",
            file_path="/path/to/exe",
            css_selector=".version",
            base_download_url="https://downloads.example.com/",
            detailed_info=True,
            timeout=30,
        )

        assert config.base_download_url == "https://downloads.example.com/"
        assert config.detailed_info is True
        assert config.timeout == 30

    def test_all_fields_present(self):
        """Test that all expected fields are present."""
        field_names = {f.name for f in fields(VersionCheckerConfig)}
        expected_fields = {
            "site_url",
            "file_path",
            "css_selector",
            "base_download_url",
            "detailed_info",
            "timeout",
            "auto_launch",
            "process_name",
        }

        assert field_names == expected_fields

    def test_field_types(self):
        """Test that fields have correct type annotations."""
        config_fields = {f.name: f.type for f in fields(VersionCheckerConfig)}

        assert config_fields["site_url"] == str
        assert config_fields["file_path"] == str
        assert config_fields["css_selector"] == str
        assert config_fields["detailed_info"] == bool
        assert config_fields["timeout"] == int

    def test_register_configs(self):
        """Test that register_configs runs without error."""
        # This should not raise any exceptions
        register_configs()

    def test_config_instantiation_missing_required(self):
        """Test that missing required fields raises TypeError."""
        with pytest.raises(TypeError):
            VersionCheckerConfig()  # Missing all required fields

        with pytest.raises(TypeError):
            VersionCheckerConfig(
                site_url="https://example.com"
            )  # Missing file_path and css_selector

        with pytest.raises(TypeError):
            VersionCheckerConfig(
                site_url="https://example.com", file_path="/path/to/exe"
            )  # Missing css_selector

    def test_config_modification(self):
        """Test that config fields can be modified after creation."""
        config = VersionCheckerConfig(
            site_url="https://example.com",
            file_path="/path/to/exe",
            css_selector=".version",
        )

        # Modify fields
        config.timeout = 20
        config.detailed_info = True
        config.base_download_url = "https://new-url.com/"

        assert config.timeout == 20
        assert config.detailed_info is True
        assert config.base_download_url == "https://new-url.com/"

    def test_config_with_none_values(self):
        """Test config with explicit None values for optional fields."""
        config = VersionCheckerConfig(
            site_url="https://example.com",
            file_path="/path/to/exe",
            css_selector=".version",
            base_download_url=None,
        )

        assert config.base_download_url is None

    def test_config_equality(self):
        """Test that two configs with same values are equal."""
        config1 = VersionCheckerConfig(
            site_url="https://example.com",
            file_path="/path/to/exe",
            css_selector=".version",
        )

        config2 = VersionCheckerConfig(
            site_url="https://example.com",
            file_path="/path/to/exe",
            css_selector=".version",
        )

        assert config1 == config2

    def test_config_inequality(self):
        """Test that configs with different values are not equal."""
        config1 = VersionCheckerConfig(
            site_url="https://example.com",
            file_path="/path/to/exe",
            css_selector=".version",
        )

        config2 = VersionCheckerConfig(
            site_url="https://different.com",
            file_path="/path/to/exe",
            css_selector=".version",
        )

        assert config1 != config2
