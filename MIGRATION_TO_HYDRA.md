# Migration Guide: Moving to Hydra Configuration

Version-checker v0.4.0 introduces Hydra for configuration management. This provides more powerful and flexible configuration options while maintaining backward compatibility.

## What Changed

### Configuration File Location

**Before (v0.3.x and earlier):**
- Config file: `./config.yaml` (in the current directory)

**After (v0.4.0+):**
- **All platforms**: `~/.config/version-checker/config.yaml`

This follows the XDG Base Directory specification for consistent cross-platform config management.

### New Features

1. **Unified config directory** - `~/.config/version-checker` on all platforms (follows XDG specification)
2. **Command-line overrides** - Override any config value without editing files
3. **Type-safe configuration** - Better validation and error messages
4. **Hydra integration** - Access to Hydra's powerful features

## Migration Steps

### Quick Migration (Recommended)

1. **Create new config location:**
   ```bash
   version-checker check --create-example
   ```

2. **Copy your existing config.yaml:**
   ```bash
   cp config.yaml ~/.config/version-checker/config.yaml
   ```

3. **Test the new setup:**
   ```bash
   version-checker check --no-clear
   ```

That's it! Your existing config.yaml will work without any changes.

### Alternative: Keep Using Custom Location

If you prefer to keep your config in a custom location:

```bash
version-checker check --config /path/to/your/config.yaml
```

## Configuration Format

No changes required! Your existing config.yaml format remains the same:

```yaml
site_url: "https://example.com/software"
file_path: "/path/to/software.exe"
css_selector: ".version-number"
base_download_url: "https://example.com/downloads/MyApp_"
detailed_info: false
timeout: 10
```

## New Capabilities

### Command-Line Overrides

Override any config value without editing files:

```bash
# Override timeout
version-checker check --override timeout=30

# Override multiple values
version-checker check -o timeout=20 -o detailed_info=true

# Override site URL (useful for testing)
version-checker check -o site_url=https://newsite.com

# Quote values with special characters
version-checker check -o "css_selector='.my-version-class'"
```

### Use Cases for Overrides

1. **Testing different sites:**
   ```bash
   version-checker check -o site_url=https://test-site.com
   ```

2. **Temporary detailed output:**
   ```bash
   version-checker check -o detailed_info=true
   ```

3. **Adjust timeout for slow networks:**
   ```bash
   version-checker check -o timeout=60
   ```

4. **CI/CD pipelines with dynamic config:**
   ```bash
   version-checker check -o site_url=$SITE_URL -o file_path=$EXE_PATH
   ```

## Backward Compatibility

### What Still Works

- ✅ Existing config.yaml format (no changes needed)
- ✅ All CLI flags (`--detailed`, `--selector`, etc.)
- ✅ Custom config paths (`--config /path/to/config.yaml`)
- ✅ Python API (`load_config()`, `scrape_version_number()`)
- ✅ Dict-style config access in code

### What Changed

- 📁 Default config location moved to `~/.config/version-checker` (all platforms, XDG spec)
- ➕ New `--override/-o` flag for dynamic config changes
- 🔧 Config loaded via Hydra (but remains dict-compatible)

## Troubleshooting

### "Configuration file not found" Error

**Problem:** Version-checker can't find your config file.

**Solution 1 - Use default location:**
```bash
# Create example config
version-checker check --create-example

# Copy your existing config to the new location
cp config.yaml ~/.config/version-checker/config.yaml
```

**Solution 2 - Specify custom path:**
```bash
version-checker check --config /path/to/your/config.yaml
```

### Config Directory Location

To find where version-checker looks for configs:

**All platforms:**
```bash
echo ~/.config/version-checker/config.yaml
```

**Note:** On Windows, `~` expands to `C:\Users\YourUsername`

### Testing Your Setup

```bash
# Check that config loads correctly
version-checker check --no-clear --detailed

# Verify override functionality works
version-checker check --no-clear -o timeout=5
```

## Python API Changes

### Before

```python
from version_checker.core.config import load_config

config = load_config("config.yaml")  # Returns dict
```

### After

```python
from version_checker.core.config import load_config

# Still works! Returns DictConfig (dict-compatible)
config = load_config("config.yaml")

# New: With overrides
config = load_config("config.yaml", overrides=["timeout=20"])

# New: Use default location
config = load_config()  # Uses ~/.config/version-checker/config.yaml

# Access values (both styles work)
url = config["site_url"]  # Dict-style
url = config.site_url     # Attribute-style (new)
```

DictConfig is fully compatible with dict operations:
- `config["key"]` - dict access
- `config.get("key", default)` - get with default
- `"key" in config` - membership test
- `config.items()` - iteration

## Benefits of Hydra

1. **Better error messages** - Clear indication of what's wrong
2. **Type validation** - Catches configuration errors early
3. **Override flexibility** - Test different configs without file edits
4. **Composability** - Future: Support for config groups and composition
5. **OS integration** - Configs stored in proper OS-specific locations

## Need Help?

- 📚 **Hydra docs**: https://hydra.cc/docs/intro/
- 🐛 **Report issues**: https://github.com/yourusername/version-checker/issues
- 💬 **Questions**: Open a GitHub discussion

## Summary

**TL;DR:**
1. Your existing config.yaml works without changes
2. Copy it to the new OS-specific location, OR use `--config` flag
3. Enjoy new override capabilities with `--override` flag
4. Everything is backward compatible
