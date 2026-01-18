# Version Checker

A Python tool to check for software updates by comparing installed executable versions with web-scraped latest versions.

## Features

- 🚀 **High Performance**: Optimized version reading with caching
- 🖥️ **Cross-Platform**: Works on Windows, macOS, and Linux
- ⚡ **Fast Windows Support**: Uses win32api when available for 5-10x faster version reading
- 💾 **Smart Caching**: Only re-reads versions when files are modified
- 🔧 **Configurable**: YAML-based configuration
- 🎯 **CLI Interface**: Easy-to-use command-line interface with rich formatting
- 🔄 **Auto-Install**: Automatically download, install, and restart applications
- 🎨 **Beautiful UI**: Rich terminal UI with spinners and progress indicators
- 📦 **Modern Python**: Built with uv, type hints, and best practices

## Installation

### Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/version-checker.git
cd version-checker

# Install uv if you haven't already
pip install uv

# Install dependencies and create virtual environment
uv sync

# Run the application
uv run version-checker --help
```

### Using pip

```bash
pip install version-checker
```

## Quick Start

1. **Create a configuration file:**
   ```bash
   version-checker check --create-example
   ```
   This creates an example configuration file at: `~/.config/version-checker/config.yaml.example`

2. **Copy and edit the configuration:**
   ```bash
   # Copy the example to config.yaml
   cp ~/.config/version-checker/config.yaml.example ~/.config/version-checker/config.yaml

   # Edit with your preferred editor
   nano ~/.config/version-checker/config.yaml
   ```

   Example configuration:
   ```yaml
   site_url: "https://example.com/software"
   base_download_url: "https://example.com/downloads/MyApp_"  # Base URL for downloads (optional)
   file_path: "/path/to/your/software.exe"
   css_selector: ".version-number"  # CSS selector for version element
   detailed_info: false
   timeout: 10
   ```

3. **Check for updates:**
   ```bash
   version-checker check
   ```

4. **Auto-install updates (optional):**
   ```bash
   version-checker check --auto-install
   ```

## Usage

### Command Overview

```bash
# Show all available commands
version-checker --help

# Show help for a specific command
version-checker check --help
```

**Available Commands:**
- `check` - Check for software updates
- `check-version` - Check version of any executable
- `config` - Display configuration file contents or path
- `cleanup-cache` - Clean up cached version data

### Check for Updates

```bash
# Check for updates using default config location (~/.config/version-checker/config.yaml)
version-checker check

# Use a specific config file
version-checker check --config /path/to/config.yaml

# Show detailed JSON output (with Rich syntax highlighting)
version-checker check --detailed

# Don't clear screen
version-checker check --no-clear

# Use custom CSS selector (override config file)
version-checker check --selector ".version-number"

# Override any config value using Hydra syntax
version-checker check --override timeout=30
version-checker check --override site_url=https://newsite.com
version-checker check -o timeout=20 -o detailed_info=true

# Auto-install updates (downloads, installs, and restarts the app)
version-checker check --auto-install
# or
version-checker check -a
```

### Auto-Install Feature

The `--auto-install` flag enables automatic installation of updates:

1. **Stops** any running instances of the application
2. **Downloads** the new version to ~/Downloads
3. **Extracts** and installs to the configured location
4. **Starts** the new version
5. **Cleans up** temporary files

**Example:**
```bash
# Check and auto-install if update is available
version-checker check --auto-install

# With custom config
version-checker check -c myapp.yaml --auto-install
```

**Features:**
- Beautiful terminal UI with live progress updates
- Animated spinners for each installation step
- Automatic process management (stop/start)
- Creates backup of old version (.exe.bak)
- Clean error handling and user feedback

### Check Executable Version

Check the version of a specific executable file:

```bash
# Check version of any executable
version-checker check-version /path/to/executable.exe

# Example
version-checker check-version "C:\Program Files\MyApp\myapp.exe"
```

### View Configuration

Display your current configuration with beautiful syntax highlighting:

```bash
# Show config file contents (with syntax highlighting)
version-checker config

# Show raw YAML without syntax highlighting
version-checker config --raw

# Show config file path and status
version-checker config --path

# View a specific config file
version-checker config --config /path/to/config.yaml

# Show path of a specific config file
version-checker config --path --config /path/to/config.yaml
```

The `config` command uses Rich formatting with:
- **Syntax highlighting** for YAML (default)
- **Line numbers** for easy reference
- **Bordered panel** with file path in subtitle

### Manage Cache

Clean up cached version information:

```bash
# Clean up cache (with confirmation prompt)
version-checker cleanup-cache

# Force cleanup without confirmation
version-checker cleanup-cache --force
```

The cache stores version information to speed up subsequent checks. Cache files are stored in `~/.version_checker_cache/`.

### Python API

```python
from version_checker import load_config, scrape_version_number

# Load configuration
config = load_config("config.yaml")

# Check for updates
result = scrape_version_number(config)

if result and result["needsUpdate"]:
    print(f"Update available: {result['installedVersion']} → {result['latestVersion']}")
```

## Configuration

Configuration is managed using [Hydra](https://hydra.cc/), providing powerful configuration management features.

### Configuration File Location

By default, version-checker looks for `config.yaml` in:
- **All platforms**: `~/.config/version-checker/config.yaml`

This follows the XDG Base Directory specification. You can override the base directory with the `XDG_CONFIG_HOME` environment variable, or specify a custom config file with the `--config` flag.

### Configuration Options

The `config.yaml` file supports the following options:

```yaml
# Required fields
site_url: "https://example.com/software"  # URL to scrape for latest version
file_path: "/path/to/software.exe"        # Path to installed executable
css_selector: ".version-number"           # CSS selector for version element on webpage

# Optional fields
base_download_url: "https://example.com/downloads/MyApp_"  # Base URL for downloads (enables auto-install)
detailed_info: false    # Show detailed JSON output
timeout: 10            # HTTP request timeout in seconds
```

### Hydra Configuration Overrides

Version-checker uses Hydra for configuration management, allowing you to override any config value from the command line:

```bash
# Override timeout value
version-checker check --override timeout=30

# Override multiple values
version-checker check -o timeout=20 -o detailed_info=true

# Override site URL
version-checker check -o site_url=https://newsite.com

# Values with special characters should be quoted
version-checker check -o "css_selector='.my-version-class'"
```

This is especially useful for:
- Testing different configurations without editing files
- Automating checks for multiple applications
- CI/CD pipelines with dynamic configuration

### Download URL Construction

When `base_download_url` is provided, the tool automatically constructs download URLs based on your platform:

- **Format**: `{base_download_url}{version}_{os}_{arch}.zip`
- **Example**: `https://example.com/MyApp_1.2.3_windows_x64.zip`

**Supported Platforms:**
- Windows: `windows_x64`, `windows_x86`, `windows_arm64`
- macOS: `darwin_x64`, `darwin_arm64`
- Linux: `linux_x64`, `linux_x86`, `linux_arm64`

## Development

### Setup Development Environment

```bash
# Clone and setup
git clone https://github.com/yourusername/version-checker.git
cd version-checker

# Install uv
pip install uv

# Install all dependencies including dev dependencies
uv sync

# Install pre-commit hooks
uv run pre-commit install
```

### Running Tests

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=version_checker

# Run specific test
uv run pytest tests/test_version_reader.py
```

### Code Quality

```bash
# Format code
uv run black version_checker tests

# Sort imports
uv run isort version_checker tests

# Lint code
uv run flake8 version_checker tests

# Type checking
uv run mypy version_checker

# Or use ruff for faster linting
uv run ruff check version_checker tests
```

## Performance

- **First run**: Similar to original (needs to read version)
- **Subsequent runs**: 90%+ faster (uses cached version)
- **Windows with pywin32**: 5-10x faster version reading
- **File updates**: Automatically detects and re-reads when executable changes

## Requirements

- Python 3.10+
- Dependencies (installed automatically):
  - `requests` - HTTP requests
  - `beautifulsoup4` - HTML parsing
  - `pyyaml` - YAML configuration
  - `hydra-core` - Configuration management
  - `click` - CLI framework
  - `rich` - Terminal UI
  - `pefile` - Windows executable version reading
  - `psutil` - Process management (for auto-install)
  - `packaging` - Version comparison
- Windows-specific:
  - `pywin32` - Optional, for faster version reading

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and ensure code quality
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

### v0.4.0
- **Migrated to Hydra for configuration management**
  - More powerful and flexible configuration system
  - Command-line overrides with `--override` flag
  - Unified config location: `~/.config/version-checker` (all platforms, following XDG specification)
- **Enhanced configuration features**
  - Type-safe configuration with structured configs
  - Better error messages and validation
  - Support for Hydra-style overrides: `timeout=20`, `detailed_info=true`, etc.
- **Improved CLI**
  - New `--override/-o` flag for dynamic config changes
  - New `config` command to view configuration with Rich syntax highlighting
  - `--raw` flag for plain text config output
  - Rich syntax-highlighted JSON output for `--detailed` flag
  - Better help documentation with config location info
- **Comprehensive test suite** for configuration management
- **Backward compatible** with existing config.yaml files

### v0.3.0
- Restructured CLI with subcommands for better organization
- Added `check` command for checking updates
- Added `check-version` command to check any executable version
- Added `cleanup-cache` command to manage cached version data
- Improved CLI help documentation
- Updated all commands to use consistent naming conventions

### v0.2.0
- Added auto-install feature with `--auto-install` flag
- Rich terminal UI with spinners and live progress
- Automatic download URL construction based on platform
- Process management (stop/start applications)
- Beautiful panel-based installation progress display
- Added `psutil` and `rich` dependencies

### v0.1.0
- Initial release
- Optimized version reading with caching
- Cross-platform support
- CLI interface
- Poetry-based project structure

## Example

Here's what the auto-install looks like in action:

```
Checking for updates...
Update available: 1.0.0 → 1.1.0

╭────────────── Auto-Install Progress ───────────────╮
│ Download URL: https://example.com/MyApp_1.1.0...   │
│                                                    │
│ 1. ✓ Stop any running <AppName> processes          │
│ 2. ⠋ Download the new version                      │ 
│ 3.   Extract and install to the configured...      │
│ 4.   Start the new version                         │
│ 5.   Clean up temporary files                      │
╰────────────────────────────────────────────────────╯

✓ Auto-install completed successfully!
```