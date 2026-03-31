# 🐶 App-Hound Example Configurations

This directory contains example configuration files for popular macOS applications. Use these as templates or run them directly to scan for artifacts.

## 📋 Available Examples

| File | App | Description |
|------|-----|-------------|
| `slack.json` | Slack | Team communication app |
| `discord.json` | Discord | Voice, video, and text chat |
| `chrome.json` | Google Chrome | Web browser |
| `vscode.json` | Visual Studio Code | Code editor |
| `multi-app.json` | Multiple Apps | Scan 7 apps at once |

## 🚀 Quick Usage

### Scan a Single App

```bash
# Using an example config
app-hound --input examples/slack.json

# Interactive mode (recommended)
app-hound --input examples/slack.json --interactive
```

### Scan Multiple Apps

```bash
# Scan all apps in multi-app.json
app-hound --input examples/multi-app.json --interactive
```

## 📝 Customizing Examples

### 1. Copy and Modify

```bash
# Copy an example
cp examples/slack.json my-apps.json

# Edit with your preferences
# Then run
app-hound --input my-apps.json --interactive
```

### 2. Add Your Own Apps

```json
{
  "apps": [
    {
      "name": "YourApp",
      "additional_locations": [
        "~/Library/Application Support/YourApp",
        "~/Library/Caches/com.company.yourapp"
      ],
      "patterns": [
        "~/Library/Preferences/*yourapp*"
      ],
      "deep_home_search": false
    }
  ]
}
```

## 🔍 Configuration Options

### Basic Structure

```json
{
  "apps": [
    {
      "name": "AppName",                    // Required: Application name
      "additional_locations": [],           // Optional: Specific paths to check
      "patterns": [],                       // Optional: Glob patterns
      "deep_home_search": false,            // Optional: Enable deep search
      "installation_path": ""               // Optional: Installer to run first
    }
  ]
}
```

### Field Descriptions

- **`name`** (required): The application name to search for
- **`additional_locations`** (optional): Specific paths to inspect
- **`patterns`** (optional): Glob patterns for additional matching
- **`deep_home_search`** (optional): Enable brute-force home directory search (slower)
- **`installation_path`** (optional): Path to installer to run before scanning

## 💡 Tips

### Finding App Locations

Common macOS locations for app artifacts:

```
/Applications/AppName.app                           # Application bundle
~/Library/Application Support/AppName               # App data
~/Library/Caches/com.company.appname               # Cache files
~/Library/Preferences/com.company.appname.plist    # Preferences
~/Library/Logs/AppName                             # Log files
~/Library/Saved Application State/...              # Saved state
~/Library/WebKit/com.company.appname               # WebKit data
~/Library/Containers/com.company.appname           # Sandboxed data
~/Library/LaunchAgents/com.company.appname.plist   # Launch agents
```

### Environment Variables

Use environment variables in paths:

```json
{
  "additional_locations": [
    "$HOME/Library/Application Support/MyApp",
    "${HOME}/.myapp"
  ]
}
```

### Patterns

Use glob patterns for flexible matching:

```json
{
  "patterns": [
    "~/Library/Preferences/*appname*",     // Match any file containing "appname"
    "~/Library/Caches/*/appname",          // Match in any subdirectory
    "~/Library/Application Support/App*"   // Match App prefix
  ]
}
```

## 🎯 Common Workflows

### Complete Uninstall

```bash
# 1. Scan the app
app-hound --input examples/slack.json --interactive

# 2. In interactive mode:
#    - Press 'a' to select all
#    - Press 'x' to execute
#    - Confirm deletion
```

### Cache Cleanup Only

```bash
# 1. Scan the app
app-hound --input examples/chrome.json --interactive

# 2. In interactive mode:
#    - Press 'f' for filters
#    - Select '4' for safe items only
#    - Press 'x' to execute
```

### Multiple Apps Cleanup

```bash
# 1. Scan all apps
app-hound --input examples/multi-app.json --interactive

# 2. In interactive mode:
#    - Press 'f' for filters
#    - Select '1' to filter by app
#    - Choose which app to clean
#    - Select items and execute
```

## 📚 Creating Your Own Examples

### Step 1: Identify App Bundle ID

```bash
# Find the bundle ID
osascript -e 'id of app "AppName"'
```

### Step 2: Find Common Locations

```bash
# Search for app artifacts
find ~/Library -iname "*appname*" -o -iname "*bundleid*"
```

### Step 3: Create Config

```json
{
  "apps": [
    {
      "name": "MyApp",
      "additional_locations": [
        "~/Library/Application Support/MyApp",
        "~/Library/Caches/com.company.myapp",
        "~/Library/Preferences/com.company.myapp.plist"
      ]
    }
  ]
}
```

### Step 4: Test

```bash
# Dry run first
app-hound --input my-app.json --interactive

# Review what's found
# Only delete if satisfied
```

## 🛡️ Safety Notes

- **Review before deleting**: Always use `--interactive` mode
- **Start with safe items**: Filter for caches and logs first
- **Backup important data**: Create a Time Machine backup
- **Test with dry-run**: Always preview before actual deletion
- **Read the notes**: Pay attention to safety levels (green/yellow/red)

## 🤝 Contributing

Found a better config for an app? Have examples for other popular apps?

1. Create a new `.json` file in this directory
2. Follow the naming convention: `appname.json`
3. Test it thoroughly
4. Submit a pull request!

## 📖 More Information

- **Full documentation**: See main README.md
- **Interactive mode guide**: See INTERACTIVE_MODE_GUIDE.md
- **Quick start**: See QUICK_START.md

---

**Happy hunting! 🐶🦴**