"""Configuration management for version checker using Hydra."""

from pathlib import Path
from typing import Any, List, Optional

from hydra import compose, initialize_config_dir
from hydra.core.global_hydra import GlobalHydra
from omegaconf import DictConfig, OmegaConf

from version_checker.utils.helpers import get_config_dir, get_default_config_path


class ConfigError(Exception):
    """Raised when there's an error with configuration."""

    pass


def load_config(
    config_path: Optional[str] = None, overrides: Optional[List[str]] = None
) -> DictConfig:
    """
    Load configuration using Hydra.

    Args:
        config_path: Path to config file. If None, uses default location in
                    ~/.config/version-checker (or platform equivalent).
        overrides: List of Hydra override strings (e.g., ["timeout=20", "detailed_info=true"]).

    Returns:
        DictConfig containing configuration data.

    Raises:
        ConfigError: If config file is not found or invalid.
    """
    if overrides is None:
        overrides = []

    # Determine config directory
    if config_path is None:
        # Use default config location
        config_dir = get_config_dir()
        config_file = get_default_config_path()
    else:
        # Use provided path
        config_file = Path(config_path)
        if not config_file.exists():
            raise ConfigError(f"Configuration file not found: {config_path}")
        config_dir = config_file.parent

    # Ensure config directory exists
    config_dir.mkdir(parents=True, exist_ok=True)

    # Check if config file exists
    if not config_file.exists():
        raise ConfigError(
            f"Configuration file not found: {config_file}\n"
            f"Run 'version-checker --create-example' to create a sample configuration file."
        )

    try:
        # Clear any existing Hydra instance
        GlobalHydra.instance().clear()

        # Initialize Hydra with the config directory
        with initialize_config_dir(
            config_dir=str(config_dir.absolute()), version_base=None
        ):
            # Compose configuration with overrides
            cfg = compose(config_name=config_file.stem, overrides=overrides)

            # Validate required fields
            required_fields = ["site_url", "file_path", "css_selector"]
            for field in required_fields:
                if field not in cfg or cfg[field] is None:
                    raise ConfigError(f"Missing required field in config: {field}")

            # Set defaults for optional fields (if not present) using OmegaConf.merge
            defaults = {
                "detailed_info": False,
                "timeout": 10,
                "base_download_url": None,
            }

            # Only add missing defaults
            for key, value in defaults.items():
                if key not in cfg:
                    OmegaConf.set_struct(cfg, False)  # Temporarily disable struct mode
                    cfg[key] = value
                    OmegaConf.set_struct(cfg, True)  # Re-enable struct mode

            return cfg

    except Exception as e:
        if isinstance(e, ConfigError):
            raise
        raise ConfigError(f"Error loading config: {e}")


def create_example_config(path: Optional[str] = None) -> None:
    """
    Create an example configuration file.

    Args:
        path: Optional path for the example file. If None, creates in default location.
    """
    example_config_content = """# Version Checker Configuration File
# Copy this file to config.yaml and customize for your needs

# Required: URL to scrape for the latest version
site_url: "https://example.com/software"

# Required: Base URL for downloading the latest version
# The architecture and OS will be automatically detected and appended
# Example: "https://cos.olived.app/d/OlivedPro_" will become
#          "https://cos.olived.app/d/OlivedPro_0.23.4_windows_x64.zip"
base_download_url: "https://example.com/downloads/Software_"

# Required: Path to the installed executable
file_path: "C:/Program Files/Software/software.exe"

# Optional: Show detailed JSON output (default: false)
detailed_info: false

# Optional: HTTP request timeout in seconds (default: 10)
timeout: 10

# Optional: Custom CSS selector for the version element on the webpage
# If not specified, uses the default selector
css_selector: "body > nav > div > div > div.hidden.flex-1.items-center.justify-center.md\\\\:flex > a:nth-child(6)"

# Examples of other CSS selectors you might use:
# css_selector: ".version-number"
# css_selector: "#latest-version"
# css_selector: "[data-version]"
# css_selector: "h1.release-title"
# css_selector: ".download-link:first-child"

# Future options (not yet implemented):
# version_regex: "v?(\\\\d+\\\\.\\\\d+\\\\.\\\\d+)"  # Custom regex to extract version
# user_agent: "Mozilla/5.0..."  # Custom user agent string
"""

    if path is None:
        # Create in default location
        config_dir = get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        target_path = config_dir / "config.yaml.example"
    else:
        target_path = Path(path)

    with open(target_path, "w", encoding="utf-8") as file:
        file.write(example_config_content)

    print(f"Example configuration created at: {target_path}")


def get_config_as_dict(cfg: DictConfig) -> dict[str, Any]:
    """
    Convert DictConfig to a regular Python dictionary.

    Args:
        cfg: Hydra DictConfig object.

    Returns:
        Dictionary representation of the config.
    """
    result = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(result, dict):
        raise ValueError("Expected dict from OmegaConf.to_container")
    return result  # type: ignore[return-value]
