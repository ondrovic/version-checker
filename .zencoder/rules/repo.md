---
description: Repository Information Overview
alwaysApply: true
---

# version-checker Information

## Summary
A Python-based command-line tool designed to check for software updates by comparing the version of an installed executable with the latest version scraped from a website. It features smart caching, high-performance version reading (especially on Windows), and an auto-install capability.

## Structure
- `version_checker/`: Main application source code.
  - `core/`: Core logic for scraping and version comparison.
  - `utils/`: Utility functions including platform-specific helpers.
  - `cli.py`: Command-line interface definition using Click.
- `tests/`: Comprehensive test suite using Pytest.
- `config.yaml.example`: Template for user configuration.
- `pyproject.toml`: Project metadata, dependencies, and tool configurations.
- `uv.lock`: Locked dependency versions for reproducible builds.

## Language & Runtime
**Language**: Python  
**Version**: >=3.10  
**Build System**: Hatchling  
**Package Manager**: uv (recommended), pip

## Dependencies
**Main Dependencies**:
- `requests`: HTTP requests for web scraping.
- `pyyaml`: YAML configuration parsing.
- `beautifulsoup4`: HTML parsing for version scraping.
- `pefile`: Windows executable version reading.
- `packaging`: Version comparison logic.
- `pywin32`: Faster version reading on Windows (platform-specific).
- `click`: CLI framework.
- `psutil`: Process management for auto-installation.
- `rich`: Enhanced terminal UI and formatting.
- `hydra-core`: Configuration management.

**Development Dependencies**:
- `pytest`, `pytest-cov`: Testing and coverage.
- `black`, `isort`, `flake8`, `ruff`: Linting and formatting.
- `mypy`: Static type checking.
- `pre-commit`: Git hooks management.

## Build & Installation
```bash
# Using uv (Recommended)
uv sync

# Using pip
pip install .
```

## Testing
**Framework**: pytest  
**Test Location**: `tests/`  
**Naming Convention**: `test_*.py`  
**Configuration**: `pyproject.toml` (`[tool.pytest.ini_options]`)

**Run Command**:
```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=version_checker
```

## Main Files & Resources
- **Entry Points**: 
  - `version-checker` (mapped to `version_checker.cli:cli`)
  - `vcheck` (alias)
- **Configuration**: 
  - Default: `~/.config/version-checker/config.yaml`
  - Example: `config.yaml.example`
- **Cache**: 
  - Located in `~/.version_checker_cache/`
