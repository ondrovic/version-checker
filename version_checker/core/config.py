"""Configuration management for version checker using Hydra."""

import sys
import time
from pathlib import Path
from typing import Any, List, Optional

import questionary
from hydra import compose, initialize_config_dir
from hydra.core.global_hydra import GlobalHydra
from omegaconf import DictConfig, OmegaConf
from questionary import Style
from rich.console import Console

from version_checker.utils.helpers import (
    clear_screen,
    find_yaml_configs,
    get_config_dir,
    get_default_config_path,
)

console = Console()

# Custom style for questionary to match rich aesthetics
MENU_STYLE = Style(
    [
        ("qmark", "fg:yellow bold"),
        ("question", "fg:yellow bold"),
        ("answer", "fg:green bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
        ("instruction", "fg:gray"),
    ]
)


class ConfigError(Exception):
    """Raised when there's an error with configuration."""

    pass


def select_config_file(yaml_files: list[Path]) -> Optional[Path]:
    """
    Prompt user to select a configuration file from available options.

    Uses arrow keys for navigation.

    Args:
        yaml_files: List of available YAML config file paths.

    Returns:
        Selected Path, or None if user cancels.
    """
    if not yaml_files:
        return None

    # Build choices for questionary
    choices = [file_path.name for file_path in yaml_files]
    choices.append("Cancel")

    console.print()
    console.print("[dim]config.yaml not found[/dim]")
    console.print()

    try:
        answer = questionary.select(
            "Select configuration file:",
            choices=choices,
            style=MENU_STYLE,
            instruction="(Use arrow keys)",
            pointer="❯",
        ).ask()

        if answer is None or answer == "Cancel":
            console.print("[dim]Cancelled[/dim]")
            sys.exit(0)

        # Find the selected file
        selected = next(f for f in yaml_files if f.name == answer)
        console.print(f"\n[green]✓[/green] Using: [bold]{selected.name}[/bold]")
        time.sleep(0.5)  # Brief pause to show selection
        clear_screen()
        return selected

    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled[/dim]")
        sys.exit(0)


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

        # If default config doesn't exist, check for other YAML files
        if not config_file.exists():
            available_configs = find_yaml_configs()
            if available_configs:
                selected = select_config_file(available_configs)
                if selected is None:
                    raise ConfigError("No configuration file selected.")
                config_file = selected
                config_dir = config_file.parent
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

            # Validate required fields - file_path is always required
            if "file_path" not in cfg or cfg["file_path"] is None:
                raise ConfigError("Missing required field in config: file_path")

            # Get update_type (defaults to "scrape" for backward compatibility)
            update_type = cfg.get("update_type", "scrape")

            # Validate provider-specific required fields
            if update_type == "scrape":
                for field in ["site_url", "css_selector"]:
                    if field not in cfg or cfg[field] is None:
                        raise ConfigError(f"Missing required field for scrape provider: {field}")
            elif update_type == "github":
                if "github_repo" not in cfg or cfg["github_repo"] is None:
                    raise ConfigError("Missing required field for github provider: github_repo")
            else:
                raise ConfigError(f"Invalid update_type: {update_type}. Must be 'scrape' or 'github'")

            # Set defaults for optional fields (if not present) using OmegaConf.merge
            defaults = {
                "detailed_info": False,
                "timeout": 10,
                "base_download_url": None,
                "update_type": "scrape",
                "github_repo": None,
                "version_pattern": None,
                "default_package_type": None,
                "site_url": None,
                "css_selector": None,
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
