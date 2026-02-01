# Refactoring Plan

### What app-hound currently does

- **CLI workflow** – `src/app_hound/main.py` sets up the entrypoint. It parses flags like `--input`, `--output`, `--app-name`, quiet/progress toggles, and optional color overrides. It ensures the audit directory exists, loads configuration (single app or merged `apps_config.json` files), delegates scanning, and saves a CSV report. All console styling flows through a shared `OutputManager`.

- **Configuration loading** – `finder.load_apps_from_json` / `load_apps_from_multiple_json` read JSON, validate the schema, and expand environment variables. The accepted schema is a list of `{ "name": ..., "additional_locations": [...] , "installation_path": ...? }`.

- **Scanning** – `finder.gather_app_entries` does the heavy lifting. It:
  1. Calls `find_all_matches_in_home` to recurse through the entire home directory and return any path whose basename contains the app name (case-insensitive).
  2. Appends any `additional_locations` from config.
  3. Emits themed console messages for each custom path.
  4. Iterates over every candidate path, verifying it still exists and recording a tuple `(app_name, absolute_path, is_dir, file_name-or-"none")` for each match whose basename still contains the app name.

  Notably, the helper `get_default_locations` enumerates the usual macOS directories (Application Support, Preferences, Containers, etc.) but is never called, so the scan relies on the “full home directory crawl + optional overrides” approach.

- **Installer support** – `finder.run_installer` expands and validates an optional `installation_path`, tries to run a `.pkg`, `.app`, generic executable, or prompts manual action for `.dmg`.

- **Output** – `write_audit_csv` writes the header `App Name, Base Path, Folder, File name` and appends the tuples from the scan. No deletion is offered; the CLI only reports what it finds.

- **Presentation layer** – `ui.OutputManager` wraps Rich, centralising palette management, quiet mode, progress bars, and emoji-flavoured messages.

### Gaps relative to the stated goal

- The “find everything” requirement is only partially met. Crawling the entire home folder by name match can overwhelm users with noisy results (e.g., unrelated files containing the app name) while still missing system-level artefacts outside `$HOME`. The unused `get_default_locations` hints at an intended deterministic scan that hasn’t been wired in.

- Results are flat tuples with no metadata about artifact type, removal safety, or dependencies. There’s no facility to selectively delete paths or even mark which ones are safe to remove.

- Responsibilities are tightly coupled: scanning is procedural and mixes filesystem logic, pattern heuristics, output, and progress reporting through global state (`output_manager`). Extending the tool to a richer interactive “select for removal” flow would be difficult in the current shape.

### Refactoring directions to realign with the goal

1. **Separate concerns into clearer layers**
   - Introduce a `Scanner` class (or module) that produces rich `Artifact` objects: `{app, path, scope(default/custom/home), kind(file/dir), writable, notes}` with no UI side effects.
   - Move all Rich/console interactions into dedicated presenter classes. Inject an `OutputPort` interface into the scanner so tests can run without monkeypatching globals.
   - Extract configuration schema/validation into its own module and relax `additional_locations` to be optional (currently the `TypeGuard` rejects entries that omit it, even though the README shows that usage).

2. **Replace the home-directory brute force with deterministic search targets**
   - Make `get_default_locations` the backbone: generate candidate directories/files up front (Applications, Application Support, Preferences, Containers, LaunchAgents, caches, logs, etc.).
   - Provide opt-in sweeping search such as “--deep-home-search” for users that want a slow exhaustive crawl.
   - De-duplicate candidate paths before hitting the filesystem to avoid redundant stats.

3. **Introduce a richer domain model for removal planning**
   - Define an `Artifact` dataclass that includes `path`, `category` (e.g., “app bundle”, “support data”, “preference plist”), `exists`, `size`, `last_modified`, and an optional `removal_strategy`.
   - Group artifacts per application and render them hierarchically in the CLI (or future UI).
   - Provide serialization to JSON in addition to CSV so a subsequent tool can drive selective deletion.

4. **Build a dedicated “selection/removal” pipeline**
   - Add a `--plan` mode that writes a JSON plan plus a shell script containing `rm` commands with prompts (or integrates directly with Python to remove after confirmation).
   - Offer interactive selection (maybe via textual/Rich prompt) so users can choose which artifacts to delete.
   - Encapsulate deletion in an `ArtifactRemover` service that handles permissions, dry-run, and error reporting.

5. **Improve configurability and extensibility**
   - Allow per-app rules: e.g., `{ "name": "Slack", "patterns": ["~/Library/Application Support/Slack", ...] }` to override generated heuristics.
   - Support plugin hooks so power users can write Python modules for bespoke detection logic per application.

6. **Testing & observability**
   - With the new domain classes, unit tests can assert on artifact collections without parsing console output.
   - Add snapshot tests for the reported CSV/JSON.
   - Consider injecting a virtual filesystem abstraction (e.g., pyfakefs) into the scanner to make end-to-end tests deterministic.

By modularising around `Scanner → Artifact → Plan/Report → Deletion`, you align the codebase with the broader ambition: reliably enumerate installation traces and hand users the ability to remove them confidently, while keeping the playful dog-themed UI as a thin presentation layer on top.

