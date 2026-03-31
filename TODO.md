# app-hound TODO List

This file outlines potential improvements and features for the `app-hound` project.

## ✅ Completed Refactoring (v2.0)
- [x] Domain models (Artifact, ScanResult, ScanSummary)
- [x] Scanner class with filesystem abstraction
- [x] Configuration module with flexible schema
- [x] Support for multiple configuration files
- [x] Environment variable support in configuration (e.g., `$HOME`, `$USER`)
- [x] JSON output format for artifacts and plans
- [x] Include metadata in reports (file size, last modified date, permissions)
- [x] Plan generation (JSON and shell script)
- [x] Deletion pipeline (ArtifactRemover, DeletionPlan)
- [x] Deep home search mode (--deep-home-search)
- [x] Pattern matching support (--pattern)
- [x] Progress bars for long-running operations
- [x] Color customization for console output
- [x] Quiet mode to suppress console output for scripting
- [x] Interactive mode for reviewing and selecting artifacts for deletion

## 🚀 High Priority - Next Up

### Interactive Mode for Artifact Selection ✅
- [x] Add `--interactive` flag for TUI-based artifact review
- [x] Allow users to check/uncheck artifacts for deletion
- [x] Show total space to be freed
- [x] Provide filtering/search within selection UI
- [x] Execute deletions with confirmation
- [x] Support selection by app name, category, and safety level
- [x] Support range selection (e.g., 0-5)
- [x] Dry-run mode before actual deletion
- [x] Rich table display with color-coded safety levels
- [x] Created comprehensive test suite (31 tests)

### Plan Execution ✅
- [x] Add `--execute-plan <plan.json>` command to run saved plans
- [x] Integrated dry-run in execution workflow (prompted automatically)
- [ ] Add `--backup-before-remove` option

### Logging and Debugging
- [ ] Add structured logging support (e.g., structlog)
- [ ] Add `--log-level` flag (DEBUG, INFO, WARNING, ERROR)
- [ ] Add `--log-file` option to write logs to file
- [ ] Improve error messages with actionable suggestions

## 📋 Search and Filtering Improvements
- [x] Support exclusion patterns to ignore specific paths (--exclude)
- [ ] Enable regex-based matching for application names and paths
- [ ] Add bundle ID detection for more accurate app matching

## 📊 Output and Reporting Enhancements
- [ ] Support XML output format
- [ ] Support Markdown output format
- [ ] Add summary report with statistics per app
- [ ] Add `--format` flag to choose output format

## 🧪 Testing and Validation Enhancements
- [ ] Add integration tests for real-world scenarios with pyfakefs
- [ ] Test edge cases (missing directories, permission issues, large-scale audits)
- [ ] Add snapshot tests for CSV/JSON output
- [ ] Measure and optimize performance for large directories
- [ ] Add unit tests for interactive mode

## 📚 Documentation and Examples
- [ ] Create ARCHITECTURE.md documenting the refactored design
- [ ] Create a comprehensive user guide with examples
- [ ] Generate and publish API documentation
- [x] Provide example configuration files for common apps (Slack, Chrome, VSCode, etc.)
- [ ] Add migration guide for v1.x to v2.0
- [ ] Document removal plan workflow

## 🛡️ Error Handling Improvements
- [x] Ensure graceful degradation for inaccessible paths (basic implementation)
- [ ] Enhance error messages with suggestions and next steps
- [ ] Add retry logic for transient filesystem errors

## 🌐 Cross-Platform Support (Future)
- [ ] Extend functionality to support Linux
- [ ] Extend functionality to support Windows
- [ ] Abstract platform-specific default locations

## 👥 Community and Contribution
- [ ] Add CONTRIBUTING.md with guidelines
- [ ] Create issue templates for bug reports and feature requests
- [ ] Add pull request template
- [ ] Create CODE_OF_CONDUCT.md

## ⚡ Performance Optimizations
- [ ] Use parallel processing for filesystem scans (concurrent.futures)
- [ ] Cache scan results with intelligent invalidation
- [ ] Optimize path deduplication algorithm
- [ ] Add benchmarking suite

## 🔒 Security Enhancements
- [x] Secure path handling with expanduser/expandvars
- [x] Add input validation for all CLI arguments
- [x] Add safety checks before executing removal commands
- [x] Implement permission verification before deletion

## 🖥️ GUI Development (Future)
- [ ] Evaluate GUI frameworks (e.g., Textual for TUI, PyQt for GUI)
- [ ] Design mockups for interactive mode
- [ ] Implement basic GUI for artifact review and deletion

## 🔄 CI/CD Setup
- [ ] Set up GitHub Actions for automated testing
- [ ] Add pre-commit hooks for linting and formatting
- [ ] Automate the release process for new versions
- [ ] Add automated changelog generation
- [ ] Set up code coverage reporting

## 🌍 Localization (Future)
- [ ] Add i18n support framework
- [ ] Translate UI messages to common languages

## 🔧 Miscellaneous
- [x] Create CHANGELOG.md with v2.0 release notes
- [ ] Review and update dependencies regularly
- [x] Add --version flag enhancement (show detailed version info)
- [ ] Add plugin system for custom artifact detectors
- [ ] Support custom removal strategies per app in config

---

## 📝 Notes on Implementation Order

**Immediate Next Steps (Sprint 1):**
1. Fix any remaining errors in codebase ✅
2. Update TODO.md to reflect completed work ✅
3. Write tests for current functionality ✅
4. Implement Interactive Mode for Artifact Selection ✅

**Recent Completions (Sprint 2):**
1. Enhanced --version flag ✅
2. Example configuration files (5 apps) ✅
3. Input validation and security ✅
4. CHANGELOG.md ✅
5. --exclude patterns ✅
6. --execute-plan command ✅

**Short Term (Sprint 3):**
1. Logging and debugging improvements
2. Enhanced error messages
3. Integration tests with pyfakefs
4. Performance optimizations

**Medium Term:**
1. Additional output formats (XML, Markdown)
2. Performance optimizations
3. Documentation and examples
4. CI/CD setup
