"""Version Checker - A tool to check for software updates."""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .core.config import load_config
from .core.scraper import scrape_version_number
from .core.version_reader import get_exe_version

__all__ = ["scrape_version_number", "get_exe_version", "load_config"]
