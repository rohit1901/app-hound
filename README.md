# 🐶 app-hound

**Version 2.0** - Deterministic macOS artifact hunter with interactive TUI mode, comprehensive validation, and plan execution.

Scans well-known locations for application traces and produces rich CSV/JSON reports with deletion plans, shell scripts, and optional interactive artifact review.

## ✨ Key Features

- **Interactive TUI Mode** - Review and select artifacts for deletion with Rich-based interface
- **Deterministic Scanning** - Scans standard macOS locations (Applications, Application Support, Preferences, Containers, caches, logs, etc.)
- **Rich Metadata** - Artifact model with kind, scope, category, safety levels, size, timestamps, and removal instructions
- **Plan Execution** - Generate and execute deletion plans with built-in safety confirmations
- **Input Validation** - Comprehensive security checks for all user inputs
- **Exclusion Patterns** - Filter out paths you don't want to scan
- **Multiple Output Formats** - CSV, JSON reports, deletion plans, and executable shell scripts
- **Example Configs** - Ready-to-use configurations for Slack, Discord, Chrome, VS Code, and more

---

## 📦 Installation

### Using Poetry (recommended)

```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Clone repository
git clone https://github.com/rohit1901/app-hound.git
cd app-hound

# Install dependencies
poetry install

# Run app-hound
poetry run app-hound --help
```

---

## 🎯 Purpose

Uninstalling macOS apps cleanly requires identifying all related files (app bundles, support data, preferences, logs, caches, containers, saved state). app-hound scans predictable places and produces a structured set of artifacts so you can:

- **Audit** what exists and where
- **Decide** what's safe to remove (e.g., caches/logs) vs. what needs caution (e.g., preferences)
- **Generate** a deletion plan and an interactive shell script to clean up confidently
- **Review** artifacts in a beautiful TUI before making any changes

---

## ⚙️ Configuration

Configuration files are JSON and can be merged from multiple sources. By default, app-hound looks for `apps_config.json` in the input directory.

### Schema (per-app)

- `name` (string, required)
- `additional_locations` (array of strings, optional)
- `installation_path` (string or null, optional)
- `deep_home_search` (boolean, optional)
- `patterns` (array of strings, optional; supports glob patterns)
- `exclusions` (array of strings, optional; glob patterns to exclude)

### Example Configuration

```json
{
  "apps": [
    {
      "name": "Slack",
      "additional_locations": ["~/opt/slack-legacy"],
      "installation_path": "~/Downloads/Slack.pkg",
      "deep_home_search": false,
      "patterns": [
        "~/Library/**/Slack*",
        "/Library/Application Support/slack*"
      ],
      "exclusions": [
        "*/Cache/*",
        "*.log"
      ]
    },
    {
      "name": "PDF Expert"
    }
  ]
}
```

**Notes:**
- Environment variables and `~` are expanded in paths and patterns
- Multiple configuration files can be merged using `--input` with comma-separated paths
- Each config file must contain `{ "apps": [...] }`

---

## 🚀 Quick Start

### View version and help

```bash
poetry run app-hound --version
poetry run app-hound --help
```

### Use example configurations

```bash
# Scan Slack using example config
poetry run app-hound --input examples/slack.json --interactive

# Scan multiple apps
poetry run app-hound --input examples/multi-app.json --interactive
```

### Scan a single app

```bash
# Basic scan
poetry run app-hound --app "Slack"

# Interactive mode (recommended)
poetry run app-hound --app "Slack" --interactive

# With exclusions
poetry run app-hound --app "Chrome" --exclude "*/Cache/*" --exclude "*.log"
```

### Execute a deletion plan

```bash
# Generate plan first
poetry run app-hound --app "OldApp"

# Execute the plan (with confirmations)
poetry run app-hound --execute-plan ~/.app-hound/audit/plan.json
```

---

## 🎮 CLI Options

### Core Options

- `-v, --version` - Show detailed version information
- `-h, --help` - Show beautiful Rich-formatted help
- `-i, --input <path>` - Configuration file(s), comma-separated to merge
- `-a, --app <name>` - Scan a single app without config file
- `--interactive` - Enter interactive TUI mode for artifact review
- `--execute-plan <path>` - Execute deletion plan from JSON file

### Output Options

- `-o, --output <path>` - CSV report (default: `~/.app-hound/audit/audit.csv`)
- `--json-output <path>` - JSON artifact report (default: `~/.app-hound/audit/artifacts.json`)
- `--plan <path>` - Deletion plan JSON (default: `~/.app-hound/audit/plan.json`)
- `--plan-script <path>` - Shell script (default: `~/.app-hound/audit/delete.sh`)

### Scanning Options

- `--additional-location <path>` - Extra location to inspect (repeatable)
- `--pattern <glob>` - Glob pattern to match (repeatable)
- `--exclude <pattern>` - Exclude paths matching pattern (repeatable)
- `--deep-home-search` - Enable brute-force home directory search (slow)

### Installation Options

- `--installation-path <path>` - Installer to run before scanning
- `--run-installers` - Execute installers from config

### Display Options

- `--quiet` - Suppress console output (warnings/errors still show)
- `--no-progress` - Disable progress indicators
- Color customization: `--accent-color`, `--info-color`, `--success-color`, `--warning-color`, `--error-color`, `--highlight-color`, `--muted-color`, `--progress-bar-color`, `--progress-complete-color`, `--progress-description-color`

---

## 📊 Reports

### CSV Report

Columns include:
- App Name
- Artifact Path
- Kind (file, directory, symlink, unknown)
- Scope (default, configured, discovered, system, unknown)
- Category (application, support, cache, preferences, logs, launch-agent, other)
- Exists
- Writable
- Size (bytes) - files only, non-symlinks
- Last Modified (ISO 8601, UTC)
- Removal Safety (SAFE, CAUTION, REVIEW)
- Notes
- Removal Instructions

### JSON Report

Captures the full artifact model with:
- One entry per app
- `generated_at` timestamp
- `artifacts` array with full metadata
- `errors` array with non-fatal scan notes

### Deletion Plan

JSON structure with enabled/disabled entries:
- `app_name`, `path`, `kind`, `category`, `scope`
- `exists`, `writable`, `removal_safety`
- `notes`, `removal_instructions`
- `enabled` (defaults to SAFE artifacts only)
- `suggested_command`

### Shell Script

Portable bash script with:
- Header (`#!/usr/bin/env bash`, `set -euo pipefail`)
- Per-entry comments (notes/instructions)
- Interactive prompts before each deletion
- Safe commands (`rm -rf` for directories, `rm -f` for files)
- Marked executable automatically

---

## 💡 Examples

### Interactive workflow (recommended)

```bash
# Scan and review interactively
poetry run app-hound --app "Slack" --interactive

# In the TUI:
# - Press 'f' → '4' to filter safe items only
# - Press 'x' to execute deletion
# - Confirm with dry-run, then actual deletion
```

### Using example configs

```bash
# Single app with full features
poetry run app-hound --input examples/slack.json --interactive

# Multiple apps at once
poetry run app-hound --input examples/multi-app.json --interactive
```

### Advanced scanning

```bash
# With exclusions
poetry run app-hound --app "Chrome" \
  --exclude "*/Cache/*" \
  --exclude "*.log" \
  --interactive

# Deep search with patterns
poetry run app-hound --app "VSCode" \
  --pattern "~/.vscode*" \
  --deep-home-search \
  --output ~/Desktop/vscode-audit.csv
```

### Plan execution

```bash
# Generate plan first
poetry run app-hound --app "OldApp"

# Review plan JSON
cat ~/.app-hound/audit/plan.json

# Execute with confirmations
poetry run app-hound --execute-plan ~/.app-hound/audit/plan.json
```

### Merging configurations

```bash
poetry run app-hound --input ~/configs/slack.json,~/configs/pdf.json
```

---

## 🛡️ Safety Notes

- **Review CAUTION/REVIEW entries** before enabling deletion
- **Use interactive mode** to review before deleting
- **Run dry-run first** (automatically offered in `--execute-plan`)
- **Create backups** (Time Machine) before major cleanups
- **Read the notes** - safety levels are color-coded (green/yellow/red)

---

## 🏗️ Development

### Structure

```
src/app_hound/
├── main.py           # CLI wiring, argument parsing, orchestration
├── scanner.py        # Deterministic artifact discovery
├── domain.py         # Artifact model, enums, serialization
├── configuration.py  # Config loading/merging
├── installer.py      # Installer runner
├── ui.py            # OutputManager, Rich presentation
├── removal.py        # Plan building, deletion execution
├── interactive.py    # Interactive TUI mode
├── validation.py     # Input validation and security
└── finder.py         # Legacy (superseded by scanner.py)
```

### Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app_hound --cov-report=html

# Test structure includes:
# - Unit tests for Scanner (with mock filesystem)
# - Domain model tests (140 total tests)
# - Interactive mode tests
# - Integration tests
```

### Contributing

PRs welcome for:
- Plugin hooks
- Per-app rule extensions
- Interactive selection enhancements
- Expanded location detection
- Cross-platform support

Keep the UI friendly and scanning deterministic!

---

## 🎉 What's New in v2.0

- ✨ **Interactive Mode** - Rich TUI for artifact selection and deletion
- 🚀 **Plan Execution** - `--execute-plan` command with multi-step confirmation
- 🛡️ **Input Validation** - Comprehensive security checks for all inputs
- 🚫 **Exclusion Patterns** - `--exclude` flag to filter unwanted paths
- 📋 **Example Configs** - 5 ready-to-use configs in `examples/` directory
- 💎 **Enhanced Help** - Beautiful Rich-formatted `--help` output
- 📌 **Detailed Version** - `--version` shows Python, platform, author
- 🧪 **140 Tests** - Comprehensive test suite with 100% pass rate
- ✅ **Zero Errors** - Complete type safety and validation

See `CHANGELOG.md` for full release notes.

---

## 📚 Documentation

- `QUICK_START.md` - 5-minute beginner guide
- `INTERACTIVE_MODE_GUIDE.md` - Complete interactive mode tutorial
- `examples/README.md` - Example configuration guide
- `CHANGELOG.md` - Version 2.0 release notes
- `TODO.md` - Roadmap and future features
- `IMPLEMENTATION_SUMMARY.md` - Technical details

---

## 📄 License

MIT

---

## 🐾 About

A friendly dog-themed tool for Mac users and admins. app-hound helps you audit and clean application traces with confidence—sniff, fetch, and wag your way to a tidy system! 🐶🦴