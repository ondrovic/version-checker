"""Configuration management for version checker using Hydra."""

import sys
import time
from pathlib import Path
from typing import Any, List, Optional, Sequence

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

# Version probe allowlist (kept small on purpose for safety).
# Extend intentionally as needed.
_ALLOWED_VERSION_PROBE_ARGS: set[str] = {
    "--version",
    "-V",
    "-v",
    "version",
}

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
                "auto_launch": False,
                "process_name": None,
                "install_method": "download",
                "install_script": None,
                "version_probes": None,
                "version_timeout": 2,
            }

            # Only add missing defaults
            for key, value in defaults.items():
                if key not in cfg:
                    OmegaConf.set_struct(cfg, False)  # Temporarily disable struct mode
                    cfg[key] = value
                    OmegaConf.set_struct(cfg, True)  # Re-enable struct mode

            # Validate install settings
            install_method = cfg.get("install_method", "download")
            if install_method not in ("download", "script"):
                raise ConfigError(
                    "Invalid install_method: "
                    f"{install_method}. Must be 'download' or 'script'"
                )
            if install_method == "script":
                install_script = cfg.get("install_script")
                if not install_script or not isinstance(install_script, str):
                    raise ConfigError(
                        "install_method is 'script' but install_script is missing"
                    )

            # Validate version probe settings (optional)
            version_timeout = cfg.get("version_timeout", 2)
            if not isinstance(version_timeout, int) or version_timeout <= 0:
                raise ConfigError("version_timeout must be a positive integer")

            version_probes = cfg.get("version_probes")
            if version_probes is not None:
                if not isinstance(version_probes, Sequence):
                    raise ConfigError("version_probes must be a list of probe objects")

                for i, probe in enumerate(version_probes):
                    if isinstance(probe, DictConfig):
                        probe = OmegaConf.to_container(probe, resolve=True)
                    if not isinstance(probe, dict):
                        raise ConfigError(f"version_probes[{i}] must be a mapping")

                    args = probe.get("args")
                    regex = probe.get("regex")

                    if not isinstance(args, Sequence) or isinstance(args, (str, bytes)):
                        raise ConfigError(f"version_probes[{i}].args must be a list of strings")
                    if not args:
                        raise ConfigError(f"version_probes[{i}].args must not be empty")
                    for arg in args:
                        if not isinstance(arg, str) or not arg.strip():
                            raise ConfigError(
                                f"version_probes[{i}].args entries must be non-empty strings"
                            )
                        # enforce allowlist for safety / determinism
                        if arg not in _ALLOWED_VERSION_PROBE_ARGS:
                            raise ConfigError(
                                f"version_probes[{i}].args contains disallowed token: {arg!r}"
                            )

                    if not isinstance(regex, str) or not regex.strip():
                        raise ConfigError(f"version_probes[{i}].regex must be a non-empty string")

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
