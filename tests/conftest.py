"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "site_url": "https://example.com/software",
        "file_path": "/path/to/software.exe",
        "css_selector": ".version-number",
        "detailed_info": False,
        "timeout": 10,
    }


@pytest.fixture
def mock_exe_file(temp_dir):
    """Create a mock executable file for testing."""
    exe_path = temp_dir / "test.exe"
    exe_path.write_bytes(b"Mock executable content")
    return str(exe_path)
