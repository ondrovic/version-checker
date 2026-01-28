"""Command-line interface for version checker."""

import sys
from pathlib import Path

import click
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table

from .core.config import ConfigError, load_config
from .core.scraper import scrape_version_number
from .utils.auto_installer import AutoInstaller, PackageType, detect_package_type
from .utils.helpers import clear_screen

console = Console()


@click.group()
@click.version_option()
def cli() -> None:
    """Version Checker - Check for software updates and manage version cache."""
    pass


@cli.command(name="check")
@click.option(
    "--config",
    "-c",
    default=None,
    help="Path to configuration file (default: ~/.config/version-checker/config.yaml or platform equivalent)",
)
@click.option("--detailed", "-d", is_flag=True, help="Show detailed JSON output")
@click.option("--no-clear", is_flag=True, help="Don't clear screen before output")
@click.option("--selector", "-s", help="Override CSS selector for version element")
@click.option(
    "--auto-install",
    "-a",
    is_flag=True,
    default=False,
    help="Automatically download, install, and restart the application if an update is available",
)
@click.option(
    "--override",
    "-o",
    multiple=True,
    help="Hydra-style config overrides (e.g., timeout=20, site_url=https://example.com)",
)
def check(
    config: str | None,
    detailed: bool,
    no_clear: bool,
    selector: str | None,
    auto_install: bool,
    override: tuple[str, ...],
) -> None:
    """
    Version Checker - Check for software updates by comparing executable versions with web-scraped data.
    """

    if not no_clear:
        clear_screen()

    try:
        # Build Hydra overrides from CLI flags
        overrides = list(override)  # Start with explicit --override flags

        if detailed:
            overrides.append("detailed_info=true")
        if selector:
            overrides.append(f"css_selector={selector}")

        # Load configuration with Hydra
        config_data = load_config(config, overrides=overrides)

        # Merge auto_install from config with CLI flag (CLI flag overrides)
        auto_install_enabled = auto_install or config_data.get("auto_install", False)

        click.echo("Checking for updates...")

        # Check for updates
        result = scrape_version_number(config_data)

        if result:
            # Display section - handles both detailed and normal output
            if config_data.get("detailed_info", False):
                console.print_json(data=result)

            # Status message and auto-install section
            if result["needsUpdate"]:
                # Check if this is a fresh install
                is_fresh_install = result.get("freshInstall", False)

                # Display status message only for non-detailed mode
                if not config_data.get("detailed_info", False):
                    if is_fresh_install:
                        console.print(
                            f"[yellow]Application not found:[/yellow] "
                            f"Installing [green]{result['latestVersion']}[/green]"
                        )
                    else:
                        console.print(
                            f"[yellow]Update available:[/yellow] "
                            f"{result['installedVersion']} → "
                            f"[green]{result['latestVersion']}[/green]"
                        )

                # Auto-install section - runs regardless of detailed_info
                if auto_install_enabled:
                    if "downloadUrl" not in result:
                        console.print(
                            "[red]Error:[/red] Download URL not available for auto-install"
                        )
                        sys.exit(1)

                    # Define step descriptions based on whether it's a fresh install
                    # Get process name from config or derive from file_path
                    process_name = config_data.get("process_name") or Path(config_data["file_path"]).stem
                    auto_launch = config_data.get("auto_launch", False)

                    if is_fresh_install:
                        if auto_launch:
                            step_descriptions = [
                                "Download the latest version",
                                "Install to the configured location",
                                "Start the application",
                                "Clean up temporary files",
                            ]
                        else:
                            step_descriptions = [
                                "Download the latest version",
                                "Install to the configured location",
                                "Clean up temporary files",
                            ]
                    else:
                        if auto_launch:
                            step_descriptions = [
                                f"Stop any running {process_name} processes",
                                "Download the new version",
                                "Install to the configured location",
                                "Start the new version",
                                "Clean up temporary files",
                            ]
                        else:
                            step_descriptions = [
                                f"Stop any running {process_name} processes",
                                "Download the new version",
                                "Install to the configured location",
                                "Clean up temporary files",
                            ]

                    def create_display(step: int) -> Panel:
                        """Create the display for current step."""
                        header = (
                            f"[cyan]Download URL:[/cyan] {result['downloadUrl']}\n"
                        )

                        # Create steps table
                        steps_table = Table.grid(padding=(0, 2))
                        steps_table.add_column(
                            style="dim", justify="right", width=3
                        )
                        steps_table.add_column()

                        for i, desc in enumerate(step_descriptions, 1):
                            if i < step:
                                steps_table.add_row(
                                    f"{i}.", f"[green]✓[/green] {desc}"
                                )
                            elif i == step:
                                # Add spinner for current step
                                spinner = Spinner("dots", text=desc, style="cyan")
                                steps_table.add_row(f"{i}.", spinner)
                            else:
                                steps_table.add_row(f"{i}.", f"[dim]{desc}[/dim]")

                        panel_title = (
                            "[bold green]Fresh Install Progress[/bold green]"
                            if is_fresh_install
                            else "[bold green]Auto-Update Progress[/bold green]"
                        )
                        return Panel(
                            Group(header, steps_table),
                            title=panel_title,
                            border_style="green",
                            padding=(1, 2),
                        )

                    # Perform installation with live updates
                    with Live(
                        create_display(1), console=console, refresh_per_second=10
                    ) as live:
                        # Create installer instance with silent mode
                        installer = AutoInstaller(
                            config_data["file_path"],
                            result["downloadUrl"],
                            silent=True,
                            fresh_install=is_fresh_install,
                            auto_launch=auto_launch,
                            process_name=process_name,
                        )

                        # Manually run each step with UI updates
                        try:
                            current_step = 1

                            # Step 1: Kill process (skip for fresh install)
                            if not is_fresh_install:
                                live.update(create_display(current_step))
                                if not installer._kill_process():
                                    raise Exception(
                                        "Failed to stop running processes"
                                    )
                                current_step += 1

                            # Step N: Download (with spinner)
                            live.update(create_display(current_step))
                            if not installer._download():
                                raise Exception("Failed to download new version")
                            current_step += 1

                            # Step N+1: Extract
                            live.update(create_display(current_step))

                            # Check if package type requires sudo (needs interactive terminal)
                            needs_sudo = False
                            if installer.downloaded_file:
                                pkg_type = detect_package_type(installer.downloaded_file.name)
                                needs_sudo = pkg_type in (
                                    PackageType.DEB,
                                    PackageType.PACMAN,
                                    PackageType.RPM,
                                )

                            if needs_sudo:
                                # Stop Live display to allow sudo password prompt
                                live.stop()
                                console.print(
                                    f"\n[cyan]Installing {installer.downloaded_file.name}...[/cyan]"
                                )
                                if not installer._extract_and_overwrite():
                                    raise Exception("Failed to extract and install")
                                # Restart live display for remaining steps
                                live.start()
                            else:
                                if not installer._extract_and_overwrite():
                                    raise Exception("Failed to extract and install")
                            current_step += 1

                            # Step N+2: Start process (only if auto_launch is enabled)
                            if auto_launch:
                                live.update(create_display(current_step))
                                if not installer._start_process():
                                    raise Exception("Failed to start application")
                                current_step += 1

                            # Final step: Cleanup
                            live.update(create_display(current_step))
                            installer._cleanup()
                            current_step += 1

                            # Show completion
                            live.update(create_display(current_step))

                            success = True
                        except Exception as e:
                            console.print(
                                f"\n[bold red]✗[/bold red] Auto-install failed: {e}"
                            )
                            success = False

                    if success:
                        if is_fresh_install:
                            console.print(
                                "\n[bold green]✓[/bold green] Application installed successfully!"
                            )
                        else:
                            console.print(
                                "\n[bold green]✓[/bold green] Auto-update completed successfully!"
                            )
                    else:
                        if is_fresh_install:
                            console.print(
                                "\n[bold red]✗[/bold red] Installation failed. Please install manually."
                            )
                        else:
                            console.print(
                                "\n[bold red]✗[/bold red] Auto-update failed. Please update manually."
                            )
                        sys.exit(1)
                else:
                    # Display download URL if available and not auto-installing
                    if not config_data.get("detailed_info", False) and "downloadUrl" in result:
                        console.print(
                            f"[cyan]Download:[/cyan] {result['downloadUrl']}"
                        )
            else:
                # No update needed message - only for non-detailed mode
                if not config_data.get("detailed_info", False):
                    click.echo("You are using the latest version.")
        else:
            click.echo("Failed to check for updates. Please try again later.", err=True)
            sys.exit(1)

    except ConfigError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command(name="check-version")
@click.argument("executable_path", type=click.Path(exists=True))
def check_version(executable_path: str) -> None:
    """Check the version of a specific executable file."""
    from .core.version_reader import get_exe_version

    version = get_exe_version(executable_path)
    if version:
        click.echo(f"Version: {version}")
    else:
        click.echo("Could not read version from executable", err=True)
        sys.exit(1)


@cli.command(name="cleanup-cache")
@click.option("--force", is_flag=True, help="Force cleanup even if files exist")
def cleanup_cache(force: bool) -> None:
    """Clean up all cache files."""
    from .utils.cache import VersionCache

    cache = VersionCache()

    if not force:
        if not click.confirm(
            f"This will delete all cached version information from {cache.cache_dir}. Continue?"
        ):
            click.echo("Cache cleanup cancelled.")
            return

    cache.clear_all_caches()
    click.echo("Cache cleanup completed.")


@cli.command(name="config")
@click.option(
    "--path", is_flag=True, help="Show the config file path instead of contents"
)
@click.option(
    "--config",
    "-c",
    default=None,
    help="Path to configuration file (default: ~/.config/version-checker/config.yaml)",
)
@click.option("--raw", is_flag=True, help="Show raw YAML without syntax highlighting")
def show_config(path: bool, config: str | None, raw: bool) -> None:
    """Display the current configuration file contents or path."""
    from pathlib import Path

    from rich.panel import Panel
    from rich.syntax import Syntax

    from .core.config import ConfigError, resolve_config_path
    from .utils.helpers import get_default_config_path

    # Show path only (just show default location, no auto-selection)
    if path:
        config_file = Path(config) if config else get_default_config_path()
        console.print(f"[bold cyan]Config file location:[/bold cyan] {config_file}")
        if config_file.exists():
            console.print("[green]Status: [EXISTS][/green]")
        else:
            console.print("[red]Status: [NOT FOUND][/red]")
        return

    # Resolve config file with auto-selection support
    try:
        config_file = resolve_config_path(config)
    except ConfigError as e:
        console.print(f"[red]Configuration error:[/red] {e}", style="bold")
        sys.exit(1)

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            contents = f.read()

        # Show with or without syntax highlighting
        if raw:
            # Plain output
            click.echo(f"Configuration file: {config_file}")
            click.echo("=" * 60)
            click.echo(contents)
            click.echo("=" * 60)
        else:
            # Rich syntax-highlighted output
            syntax = Syntax(contents, "yaml", theme="monokai", line_numbers=True)
            panel = Panel(
                syntax,
                title="[bold cyan]Configuration File[/bold cyan]",
                subtitle=f"[dim]{config_file}[/dim]",
                border_style="cyan",
            )
            console.print(panel)
    except Exception as e:
        console.print(f"[red]Error reading config file:[/red] {e}", style="bold")
        sys.exit(1)


if __name__ == "__main__":
    cli()
