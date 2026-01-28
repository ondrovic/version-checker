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


def resolve_config_path(config_path: Optional[str] = None) -> Path:
    """
    Resolve the configuration file path with auto-selection support.

    If no config_path is provided and the default config.yaml doesn't exist,
    prompts the user to select from available YAML configs in the config directory.

    Args:
        config_path: Optional explicit path to config file.

    Returns:
        Path to the resolved configuration file.

    Raises:
        ConfigError: If no configuration file is found or selected.
    """
    if config_path is not None:
        # Use provided path
        resolved = Path(config_path)
        if not resolved.exists():
            raise ConfigError(f"Configuration file not found: {config_path}")
        return resolved

    # Use default config location
    config_file = get_default_config_path()

    # If default config doesn't exist, check for other YAML files
    if not config_file.exists():
        available_configs = find_yaml_configs()
        if available_configs:
            selected = select_config_file(available_configs)
            if selected is None:  # pragma: no cover
                raise ConfigError("No configuration file selected.")
            return selected
        else:
            raise ConfigError(
                f"No configuration file found. Expected: {config_file}"
            )

    return config_file


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

    # Resolve config file path (handles auto-selection if needed)
    config_file = resolve_config_path(config_path)
    config_dir = config_file.parent

    # Ensure config directory exists
    config_dir.mkdir(parents=True, exist_ok=True)

    # Check if config file exists
    if not config_file.exists():
        raise ConfigError(f"Configuration file not found: {config_file}")

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
                "auto_install": False,
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
