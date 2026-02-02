# 🐶 app-hound

Deterministic macOS artifact hunter that scans well-known locations for application traces and produces rich CSV/JSON reports. It optionally generates a safe deletion plan and a shell script for interactive cleanup.

app-hound focuses on:
- Deterministic scanning of standard macOS locations (Applications, Application Support, Preferences, Containers, caches, logs, etc.)
- A rich domain model (Artifact, ScanResult, ScanSummary) with metadata (kind, scope, category, exists, size, last modified, removal safety, notes)
- Clean CLI outputs (CSV/JSON) and optional deletion plan + shell script generation
- Opt-in deep home directory search for exhaustive matching
- Clear separation of concerns (Scanner, UI presenter, configuration loader, installer runner, removal planning)

---

## Installation

- Using Poetry (recommended):
  - Install Poetry: `curl -sSL https://install.python-poetry.org | python3 -`
  - Clone repository:
    - `git clone https://github.com/rohit1901/app-hound.git`
    - `cd app-hound`
  - Install dependencies:
    - `poetry install`

- Running:
  - `poetry run app-hound --help`

---

## Purpose

Uninstalling macOS apps cleanly requires identifying all related files (app bundles, support data, preferences, logs, caches, containers, saved state). app-hound scans predictable places and produces a structured set of artifacts so you can:
- Audit what exists and where
- Decide what’s safe to remove (e.g., caches/logs) vs. what needs caution (e.g., preferences)
- Generate a deletion plan and an interactive shell script to clean up confidently

---

## Configuration

Configuration files are JSON and can be merged from multiple sources. By default, app-hound looks for `apps_config.json` in the input directory.

Schema (per-app):
- `name` (string, required)
- `additional_locations` (array of strings, optional)
- `installation_path` (string or null, optional)
- `deep_home_search` (boolean, optional)
- `patterns` (array of strings, optional; supports glob patterns)

Example `apps_config.json`:
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
      ]
    },
    {
      "name": "PDF Expert"
    }
  ]
}
```

Notes:
- Environment variables and `~` are expanded in paths and patterns.
- Multiple configuration files can be merged using `--input` with comma-separated paths; each must contain `{ "apps": [...] }`.

---

## Quick Start

- Scan apps from a local configuration:
  - `poetry run app-hound --input ./`

- Scan a single app without a config file:
  - `poetry run app-hound --app "Slack"`

- Include JSON report of artifacts:
  - `poetry run app-hound --input ./` (JSON is written by default to `~/.app-hound/audit/artifacts.json`)

- Generate a deletion plan JSON and script:
  - `poetry run app-hound --input ./` (Plan JSON and script are written by default to `~/.app-hound/audit/plan.json` and `~/.app-hound/audit/delete.sh`)

---

## CLI Options

Core:
- `-i, --input <path>[,<path>...]`:
  - Directory containing `apps_config.json` or direct path(s) to configuration files. Comma-separated to merge multiple configs.
- `-o, --output <path>`:
  - Custom CSV report path. By default, app-hound writes to `~/.app-hound/audit/audit.csv`.
- `--json-output <path>`:
  - Custom JSON artifact report path (default: `~/.app-hound/audit/artifacts.json`).
- `--app, --app-name <name>`:
  - Scan a single application (no config file needed).
- `--additional-location <path>` (repeatable):
  - Extra location(s) to inspect when using `--app`.
- `--pattern <glob>` (repeatable):
  - Extra glob pattern(s) to evaluate (supports `**` recursive patterns).
- `--installation-path <path>`:
  - Installer path to execute before scanning (used with `--app`).

Scanning behavior:
- `--deep-home-search`:
  - Enable brute-force home directory matching in addition to deterministic locations (potentially slow, capped at 500 matches and reports truncation).

Installers:
- `--run-installers`:
  - Run installer commands when configuration entries provide an `installation_path` (supports `.pkg` via `installer`, `.dmg` with manual action prompt, `.app` via `open`, and executables).

Plans & deletion:
- `--plan <path>`:
  - Custom JSON deletion plan path (default: `~/.app-hound/audit/plan.json`). The plan is derived from artifacts (enabled entries default to SAFE artifacts that exist).
- `--plan-script <path>`:
  - Custom shell script path (default: `~/.app-hound/audit/delete.sh`). The script includes prompts and is marked executable by default.

Presentation:
- `--quiet`:
  - Suppress console output (warnings/errors still display).
- `--no-progress`:
  - Disable live progress indicators.
- Color customization:
  - `--accent-color`, `--info-color`, `--success-color`, `--warning-color`, `--error-color`, `--highlight-color`, `--muted-color`, `--progress-bar-color`, `--progress-complete-color`, `--progress-description-color`

---

## Reports

CSV (`--output`) includes:
- `App Name`
- `Artifact Path`
- `Kind` (file, directory, symlink, unknown)
- `Scope` (default, configured, discovered, system, unknown)
- `Category` (application, support, cache, preferences, logs, launch-agent, other)
- `Exists`
- `Writable`
- `Size (bytes)` (files only, non-symlinks)
- `Last Modified` (ISO 8601, UTC)
- `Removal Safety` (SAFE, CAUTION, REVIEW)
- `Notes`
- `Removal Instructions`

JSON (`--json-output`) captures the full artifact model:
- One entry per app with `generated_at`, `artifacts` (full metadata), and `errors` (non-fatal scan notes).

---

## Plans & Deletion

Deletion Plan (`--plan`):
- Built from the scan results with entries derived from artifacts.
- Enabled entries default to SAFE artifacts that currently exist (e.g., caches/logs). CAUTION/REVIEW entries are disabled by default.
- JSON structure includes fields such as:
  - `app_name`, `path`, `kind`, `category`, `scope`, `exists`, `writable`, `removal_safety`, `notes`, `removal_instructions`, `enabled`, `suggested_command`

Deletion Script (`--plan-script`):
- Portable bash script with:
  - Header (`#!/usr/bin/env bash`, `set -euo pipefail`)
  - Per-entry comments (notes/instructions)
  - Interactive prompt before each deletion
  - Commands use `rm -rf` for directories and `rm -f` for files/symlinks
- Marked executable automatically

Programmatic deletion (optional):
- The removal pipeline provides an `ArtifactRemover` that can execute deletions using Python filesystem operations with options for dry-run, prompt, force, and stop-on-error. It returns a `RemovalReport` with successes, failures, and skips.
- To use it in your own scripts, import from `app_hound.removal` and plug in `app_hound.ui.OutputConsoleAdapter` for consistent console messages.

Safety notes:
- Review CAUTION/REVIEW entries before enabling deletion.
- The script prompts for confirmation; leave prompts enabled unless you fully trust the plan.
- Consider running with a dry-run first (script inspection or programmatic dry-run).

---

## Examples

- Single app scan with extra hints and a plan:
  - `poetry run app-hound --app "Slack" --additional-location "~/opt/slack-legacy" --pattern "~/Library/**/Slack*" --output ~/.app-hound/audit/audit.csv --json-output ~/.app-hound/audit/artifacts.json --plan ~/.app-hound/audit/plan.json --plan-script ~/.app-hound/audit/delete.sh`

- Merging multiple configurations:
  - `poetry run app-hound --input ~/configs/slack.json,~/configs/pdf.json --output ~/.app-hound/audit/audit.csv`

- Deep home search (opt-in; potentially noisy/slow):
  - `poetry run app-hound --app "Visual Studio Code" --deep-home-search --output ~/.app-hound/audit/audit.csv`

---

## Development Notes

Structure:
- `src/app_hound/`:
  - `main.py`: CLI wiring, argument parsing, installer execution, scan orchestration, reports, plan/script generation
  - `scanner.py`: deterministic artifact discovery with filesystem abstraction, deep-home search optional
  - `domain.py`: artifact model, scan result/summary, enums, serialization helpers
  - `configuration.py`: config dataclasses, loading/merging, environment/path expansion
  - `installer.py`: installer runner with feedback protocol and status outcomes
  - `ui.py`: OutputManager presentation, progress, palette customization, adapter for removal console
  - `removal.py`: plan building, shell script writing, ArtifactRemover and RemovalReport
  - Legacy: `finder.py` (older procedural approach) is present for reference but superseded by `scanner.py`

Testing (suggested):
- Unit tests around `Scanner` (using a virtual/pyfakefs filesystem)
- Snapshot tests for artifact JSON and CSV output
- Tests for `DeletionPlan` and `write_shell_script`
- Installer runner tests with a stubbed command runner

Contributions:
- PRs welcomed for plugin hooks, per-app rule extensions, interactive selection UI, and expanded locations.
- Keep the UI friendly and the scanning deterministic.

---

## License

MIT

---

## About

A friendly dog-themed tool for Mac users and admins. app-hound helps you audit and clean application traces with confidence—sniff, fetch, and wag your way to a tidy system!
