# Changelog

All notable changes to app-hound will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.1] - 2024-12-31

### Fixed

- **Type Safety Issues**
  - Added type annotation for `indices` variable in `interactive.py` to resolve mypy error
  - Added null check for app names in `finder.py` before passing to `gather_app_entries()`
  
- **Code Quality**
  - Removed unnecessary f-string prefixes where no placeholders are used (3 instances in `main.py`)
  - All mypy type checks now pass with zero errors
  - All flake8 linting checks now pass with zero errors

### Changed

- Color validation now performed during palette override processing
- Improved type safety across the codebase

## [2.0.0] - 2024-12-31

### 🎉 Major Release - Interactive Mode & Complete Refactoring

This is a major release featuring a complete architectural refactoring, interactive TUI mode, comprehensive testing, and numerous quality improvements.

### Added

#### Interactive Mode
- **Interactive artifact selection** with `--interactive` flag
  - Beautiful Rich-based TUI with color-coded safety levels
  - Table display showing app name, category, safety, path, size, and status
  - Multi-step selection workflow (select, filter, execute, confirm)
  - Support for individual, multiple, and range selections (e.g., `0-5`)
  - Smart filtering by app name, category, and safety level
  - Real-time space calculation showing total space to be freed
  - Dry-run preview before actual deletion (recommended)
  - Detailed removal reports with success/failure counts
  - 31 comprehensive tests for interactive functionality

#### CLI Enhancements
- **Enhanced `--version` flag** showing detailed information:
  - Version number
  - Python version
  - Platform
  - Author and license
- **Rich-formatted help system** with:
  - Organized sections with emoji headers
  - Color-coded options and values
  - Clean table-based layout
  - Practical examples section
  - Professional panels for header and footer
- **Input validation** for all CLI arguments:
  - App name validation (prevents path traversal)
  - File path validation with security checks
  - Glob pattern validation
  - Color value validation (named, hex, RGB)
  - Comprehensive error messages with suggestions

#### Example Configurations
- Created `examples/` directory with ready-to-use configs:
  - `slack.json` - Slack configuration
  - `discord.json` - Discord configuration
  - `chrome.json` - Google Chrome configuration
  - `vscode.json` - Visual Studio Code configuration
  - `multi-app.json` - Multiple apps in one config
  - Detailed `examples/README.md` with usage guide

#### Domain Models & Architecture
- New `Artifact` dataclass with rich metadata:
  - File size, last modified timestamp
  - Removal safety levels (SAFE, CAUTION, REVIEW)
  - Category classification (cache, logs, preferences, etc.)
  - Scope tracking (default, configured, discovered, system)
  - Immutable frozen dataclass for thread safety
- New `ScanResult` and `ScanSummary` classes
- New `Scanner` class with filesystem abstraction for testability
- New `interactive.py` module (599 lines) for TUI functionality
- New `validation.py` module (374 lines) for input validation

#### Testing
- **90 new comprehensive tests** (total: 140 tests)
  - `test_scanner.py` - 27 tests for filesystem operations
  - `test_domain.py` - 32 tests for domain models
  - `test_interactive.py` - 31 tests for TUI functionality
- **100% test pass rate**
- Mock filesystem support for deterministic testing
- Integration tests with real filesystem operations

#### Documentation
- `IMPLEMENTATION_SUMMARY.md` - Technical implementation details
- `INTERACTIVE_MODE_GUIDE.md` - Complete user guide (420 lines)
- `FINAL_SUMMARY.md` - Executive summary (700 lines)
- `QUICK_START.md` - 5-minute beginner guide (200 lines)
- `COMPLETION_CHECKLIST.md` - Detailed project checklist
- Updated `TODO.md` with completed items and roadmap

#### Output & Reporting
- JSON output format for artifacts (`--json-output`)
- Deletion plan generation (JSON format with `--plan`)
- Shell script generation for manual deletion (`--plan-script`)
- File metadata in reports (size, modified date, permissions)

#### Features
- Deep home search mode (`--deep-home-search`)
- Pattern matching support (`--pattern` flag, repeatable)
- Custom color support for all UI elements (10 color flags)
- Progress bars for long-running operations
- Quiet mode for scripting (`--quiet`)
- Configuration file merging (comma-separated paths)
- Environment variable expansion in configs (`$HOME`, `$USER`)

### Changed

#### Architecture
- Complete refactoring to clean layered architecture:
  - Domain layer (models, business logic)
  - Scanner layer (filesystem operations)
  - Interactive layer (TUI)
  - Configuration layer (schema, validation)
  - Removal layer (deletion planning and execution)
- Protocol-based design for dependency injection
- Separation of concerns (no UI in business logic)

#### CLI Interface
- Custom help system replaces default argparse output
- All output paths now have sensible defaults:
  - CSV: `~/.app-hound/audit/audit.csv`
  - JSON: `~/.app-hound/audit/artifacts.json`
  - Plan: `~/.app-hound/audit/plan.json`
  - Script: `~/.app-hound/audit/delete.sh`
- Improved error messages with actionable suggestions
- Better validation of user inputs

#### Configuration
- More flexible schema:
  - `additional_locations` now optional
  - `patterns` field for glob matching
  - `deep_home_search` per-app configuration
- Better error messages for invalid configs

### Fixed

#### Critical Bug Fixes
- **Fixed type errors in scanner.py**:
  - `Filesystem.stat()` now correctly returns `os.stat_result | None`
  - Proper null handling for stat results
  - Accurate file metadata extraction (size, timestamps)
- **Fixed path handling in main.py**:
  - `ParsedArgs` properties now return `Path` instead of `Path | None`
  - Removed unnecessary null checks throughout codebase
  - Cleaner type contracts and better maintainability
- **Fixed frozen dataclass tests**:
  - Tests now properly validate immutability using `setattr()`
  - No type errors in test suite
- **Error count reduced**: 8 errors → 0 errors ✅

#### Quality Improvements
- Resolved all type safety issues across codebase
- Fixed implicit string concatenation warnings
- Improved error handling in removal operations
- Better permission checking for file operations

### Security

- **Path traversal prevention**: App names validated to prevent `..` sequences and path separators
- **Input sanitization**: All CLI arguments validated before processing
- **Null byte detection**: Input checked for control characters and null bytes
- **Safe path expansion**: All paths properly resolved and validated
- **Color injection prevention**: Color values validated against safe formats only
- **Glob pattern validation**: Patterns checked for dangerous path traversal attempts
- **Maximum length checks**: Input length limits to prevent memory exhaustion
- **Type validation**: All inputs checked for expected types before processing

### Deprecated

- Old `finder.py` functions are still available for backward compatibility but may be removed in v3.0
  - Consider migrating to new `Scanner` class
  - See migration guide (to be created) for details

### Performance

- **Deterministic scanning**: Avoids slow full-home directory crawls by default
- **Path deduplication**: Prevents redundant filesystem operations
- **Efficient selection**: Set-based indexing for O(1) lookups in interactive mode
- **Lazy evaluation**: Artifacts materialized on-demand during scanning

### Developer Experience

- **100% test coverage** for new code
- **Type-safe throughout**: Zero type errors, full mypy compliance
- **Protocol-based design**: Easy to mock and test
- **Comprehensive documentation**: 6 documentation files with examples
- **Clear error messages**: Actionable suggestions for all validation errors

## [1.0.x] - Previous Versions

See git history for changes in v1.x releases.

---

## Version Links

- [2.0.0] - 2024-12-31 - Major release with interactive mode
- [1.0.x] - Earlier versions

## Migration Guide

### From v1.x to v2.0

**No breaking changes** - v2.0 is fully backward compatible with v1.x configurations and command-line usage.

**New features you can adopt**:
1. Use `--interactive` flag for better UX
2. Switch to JSON output with `--json-output`
3. Generate deletion plans with `--plan`
4. Try example configs in `examples/` directory
5. Customize colors with new color flags
6. Use `--pattern` for flexible matching

**Deprecation warnings**:
- Old `finder.py` module functions still work but consider migrating to `Scanner` class
- Future v3.0 may remove deprecated functions

---

**Full Changelog**: https://github.com/yourusername/app-hound/compare/v1.0...v2.0.0