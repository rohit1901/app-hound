from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app_hound.configuration import (
    AppConfiguration,
    AppsConfiguration,
    ConfigurationError,
    default_config_path,
    load_configuration,
    load_multiple_configurations,
)
from app_hound.domain import (
    Artifact,
    ScanResult,
    ScanSummary,
    summarize_all,
)
from app_hound.installer import InstallerRunner, InstallerStatus
from app_hound.interactive import run_interactive_mode
from app_hound.removal import DeletionPlan, write_shell_script
from app_hound.scanner import Scanner
from app_hound.ui import OutputManager
from app_hound.validation import (
    ValidationError,
    validate_app_name,
    validate_color,
    validate_file_path,
    validate_glob_pattern,
)

APP_HOUND_HOME = Path.home() / ".app-hound"
AUDIT_DIR = APP_HOUND_HOME / "audit"
DEFAULT_CSV = AUDIT_DIR / "audit.csv"

# Version information
VERSION = "2.0.1"
PYTHON_VERSION = (
    f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
)


@dataclass(frozen=True)
class ParsedArgs:
    argv: argparse.Namespace

    @property
    def csv_output_path(self) -> Path:
        return Path(self.argv.output).expanduser()

    @property
    def json_output_path(self) -> Path:
        return Path(self.argv.json_output).expanduser()

    @property
    def plan_output_path(self) -> Path:
        return Path(self.argv.plan).expanduser()

    @property
    def plan_script_output_path(self) -> Path:
        return Path(self.argv.plan_script).expanduser()

    @property
    def palette_overrides(self) -> dict[str, str]:
        mapping = {
            "accent": self.argv.accent_color,
            "info": self.argv.info_color,
            "success": self.argv.success_color,
            "warning": self.argv.warning_color,
            "error": self.argv.error_color,
            "highlight": self.argv.highlight_color,
            "muted": self.argv.muted_color,
            "progress_bar": self.argv.progress_bar_color,
            "progress_complete": self.argv.progress_complete_color,
            "progress_description": self.argv.progress_description_color,
        }
        # Validate colors before returning
        validated = {}
        for key, value in mapping.items():
            if value:
                try:
                    validated_color = validate_color(value, allow_none=True)
                    if validated_color:
                        validated[key] = validated_color
                except ValidationError as exc:
                    # Log warning but don't fail - just skip invalid color
                    print(f"Warning: Invalid {key}: {exc}", file=sys.stderr)
        return validated


class OutputManagerFeedback:
    """Adapter between InstallerRunner feedback protocol and OutputManager."""

    def __init__(self, manager: OutputManager) -> None:
        self._manager = manager

    def highlight(self, message: str) -> None:
        self._manager.highlight(message, emoji="🐶")

    def info(self, message: str) -> None:
        self._manager.info(message, emoji="🐶")

    def warning(self, message: str) -> None:
        self._manager.warning(message, emoji="🐶")

    def error(self, message: str) -> None:
        self._manager.error(message, emoji="🐶", force=True)


def show_version() -> None:
    """Display detailed version information."""
    console = Console()

    version_panel = Panel(
        f"[bold cyan]🐶 app-hound[/bold cyan] version [bold green]{VERSION}[/bold green]\n\n"
        + f"[dim]Python:[/dim] {PYTHON_VERSION}\n"
        + f"[dim]Platform:[/dim] {sys.platform}\n"
        + "[dim]Author:[/dim] Rohit Khanduri\n"
        + "[dim]License:[/dim] MIT",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(version_panel)


def show_custom_help() -> None:
    """Display custom Rich-formatted help message."""
    console = Console()

    # Header
    header = Panel(
        "[bold cyan]🐶 app-hound[/bold cyan] — [cyan]deterministic macOS artifact hunter[/cyan]\n\n"
        + "[dim]A powerful utility to discover, review, and remove application artifacts on macOS.[/dim]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(header)
    console.print()

    # Usage section
    console.print("[bold yellow]📋 USAGE[/bold yellow]")
    usage_table = Table(show_header=False, box=None, padding=(0, 1))
    usage_table.add_column(style="dim cyan", width=50)
    usage_table.add_row("  app-hound [OPTIONS]")
    usage_table.add_row("  app-hound -a APP_NAME [OPTIONS]")
    usage_table.add_row("  app-hound --input CONFIG_FILE [OPTIONS]")
    console.print(usage_table)
    console.print()

    # Core Options
    console.print("[bold yellow]🎯 CORE OPTIONS[/bold yellow]")
    core_table = Table(show_header=False, box=None, padding=(0, 1))
    core_table.add_column("Option", style="green bold", width=28, no_wrap=True)
    core_table.add_column("Description", style="white")
    core_table.add_row(
        "  -h, --help",
        "Show this help message and exit",
    )
    core_table.add_row(
        "  -a, --app, --app-name APP",
        "Scan a single application without a configuration file",
    )
    core_table.add_row(
        "  -i, --input PATH",
        "Directory with apps_config.json or config file path(s)\n[dim](comma-separated list supported)[/dim]",
    )
    core_table.add_row(
        "  --interactive",
        "[bold cyan]Enter interactive TUI mode[/bold cyan] to review and select artifacts",
    )
    core_table.add_row(
        "  --execute-plan PATH",
        "[bold yellow]Execute deletion plan[/bold yellow] from JSON file",
    )
    console.print(core_table)
    console.print()

    # Output Options
    console.print("[bold yellow]📊 OUTPUT OPTIONS[/bold yellow]")
    output_table = Table(show_header=False, box=None, padding=(0, 1))
    output_table.add_column("Option", style="green bold", width=22, no_wrap=True)
    output_table.add_column("Description", style="white")
    output_table.add_row(
        "  -o, --output PATH",
        "Custom CSV report path\n[dim]Default: ~/.app-hound/audit/audit.csv[/dim]",
    )
    output_table.add_row(
        "  --json-output PATH",
        "JSON report path with full artifact model\n[dim]Default: ~/.app-hound/audit/artifacts.json[/dim]",
    )
    output_table.add_row(
        "  --plan PATH",
        "Plan file (JSON) with removal metadata\n[dim]Default: ~/.app-hound/audit/plan.json[/dim]",
    )
    output_table.add_row(
        "  --plan-script PATH",
        "Shell script with rm commands from plan\n[dim]Default: ~/.app-hound/audit/delete.sh[/dim]",
    )
    console.print(output_table)
    console.print()

    # Scanning Options
    console.print("[bold yellow]🔍 SCANNING OPTIONS[/bold yellow]")
    scan_table = Table(show_header=False, box=None, padding=(0, 1))
    scan_table.add_column("Option", style="green bold", width=26, no_wrap=True)
    scan_table.add_column("Description", style="white")
    scan_table.add_row(
        "  --additional-location",
        "Extra location to inspect with -a [dim](repeatable)[/dim]",
    )
    scan_table.add_row(
        "  --pattern GLOB",
        "Additional glob pattern(s) with -a [dim](repeatable)[/dim]",
    )
    scan_table.add_row(
        "  --exclude PATTERN",
        "Exclude paths matching pattern [dim](repeatable)[/dim]",
    )
    scan_table.add_row(
        "  --deep-home-search",
        "Enable brute-force home directory search\n[dim](slower but more thorough)[/dim]",
    )
    console.print(scan_table)
    console.print()

    # Installation Options
    console.print("[bold yellow]⚙️  INSTALLATION OPTIONS[/bold yellow]")
    install_table = Table(show_header=False, box=None, padding=(0, 1))
    install_table.add_column("Option", style="green bold", width=24, no_wrap=True)
    install_table.add_column("Description", style="white")
    install_table.add_row(
        "  --installation-path",
        "Installer path to execute before scanning\n[dim](only used with -a)[/dim]",
    )
    install_table.add_row(
        "  --run-installers",
        "Execute installer commands from configuration",
    )
    console.print(install_table)
    console.print()

    # Display Options
    console.print("[bold yellow]🎨 DISPLAY OPTIONS[/bold yellow]")
    display_table = Table(show_header=False, box=None, padding=(0, 1))
    display_table.add_column("Option", style="green bold", width=18, no_wrap=True)
    display_table.add_column("Description", style="white")
    display_table.add_row(
        "  --quiet",
        "Suppress console output (warnings/errors still show)",
    )
    display_table.add_row(
        "  --no-progress",
        "Disable live progress indicators",
    )
    console.print(display_table)
    console.print()

    # Color Customization
    console.print("[bold yellow]🌈 COLOR CUSTOMIZATION[/bold yellow]")
    color_table = Table(show_header=False, box=None, padding=(0, 1))
    color_table.add_column("Option", style="green bold", width=32, no_wrap=True)
    color_table.add_column("Description", style="white")
    color_table.add_row("  --accent-color", "Override accent color")
    color_table.add_row("  --info-color", "Override info message color")
    color_table.add_row("  --success-color", "Override success message color")
    color_table.add_row("  --warning-color", "Override warning message color")
    color_table.add_row("  --error-color", "Override error message color")
    color_table.add_row("  --highlight-color", "Override highlight color")
    color_table.add_row("  --muted-color", "Override muted text color")
    color_table.add_row("  --progress-bar-color", "Override progress bar color")
    color_table.add_row(
        "  --progress-complete-color", "Override progress complete color"
    )
    color_table.add_row(
        "  --progress-description-color", "Override progress description color"
    )
    console.print(color_table)
    console.print()

    # Examples section
    console.print("[bold yellow]💡 EXAMPLES[/bold yellow]")
    console.print()
    console.print("  [dim]Scan single app:[/dim]")
    console.print('    [cyan]app-hound -a "Slack"[/cyan]')
    console.print()
    console.print("  [dim]Interactive mode:[/dim]")
    console.print('    [cyan]app-hound -a "Discord" --interactive[/cyan]')
    console.print()
    console.print("  [dim]From config file:[/dim]")
    console.print("    [cyan]app-hound --input ./apps_config.json[/cyan]")
    console.print()
    console.print("  [dim]Deep search:[/dim]")
    console.print('    [cyan]app-hound -a "TestApp" --deep-home-search[/cyan]')
    console.print()
    console.print("  [dim]Custom output:[/dim]")
    console.print(
        '    [cyan]app-hound -a "Chrome" -o ~/Desktop/chrome-audit.csv[/cyan]'
    )
    console.print()
    console.print(
        "  [dim italic]Note: -a, --app, and --app-name are interchangeable[/dim italic]"
    )
    console.print()

    # Footer
    footer = Panel(
        "[dim]For more information, visit: [cyan]https://github.com/rohit1901/app-hound[/cyan][/dim]",
        border_style="dim",
        padding=(0, 2),
    )
    console.print(footer)


def parse_arguments() -> argparse.Namespace:
    # Check if version is requested and show version
    if "--version" in sys.argv or "-v" in sys.argv:
        show_version()
        sys.exit(0)

    # Check if help is requested and show custom help
    if "-h" in sys.argv or "--help" in sys.argv:
        show_custom_help()
        sys.exit(0)

    parser = argparse.ArgumentParser(
        prog="app-hound",
        add_help=False,  # Disable default help to use custom
        formatter_class=argparse.RawTextHelpFormatter,
        description="🐶 app-hound — deterministic macOS artifact hunter",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="Show version information and exit",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=str(Path.cwd()),
        help=(
            "Directory containing apps_config.json or direct path(s) to configuration files. "
            "Multiple entries can be provided as a comma-separated list."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=str(DEFAULT_CSV),
        help="Custom CSV report path. By default, reports are written to ~/.app-hound/audit/audit.csv.",
    )
    parser.add_argument(
        "--json-output",
        type=str,
        default=str(AUDIT_DIR / "artifacts.json"),
        help="JSON report path capturing the full artifact model (default: ~/.app-hound/audit/artifacts.json).",
    )
    parser.add_argument(
        "--plan",
        type=str,
        default=str(AUDIT_DIR / "plan.json"),
        help="Plan file (JSON) capturing removal metadata derived from artifacts (default: ~/.app-hound/audit/plan.json).",
    )
    parser.add_argument(
        "--plan-script",
        type=str,
        default=str(AUDIT_DIR / "delete.sh"),
        help="Shell script of rm commands derived from the plan (default: ~/.app-hound/audit/delete.sh).",
    )
    parser.add_argument(
        "-a",
        "--app",
        "--app-name",
        type=str,
        default=None,
        help="Scan a single application without a configuration file.",
    )
    parser.add_argument(
        "--execute-plan",
        type=str,
        default=None,
        metavar="PATH",
        help="Execute deletion plan from a JSON file (skips scanning).",
    )
    parser.add_argument(
        "--additional-location",
        action="append",
        dest="additional_locations",
        default=[],
        metavar="PATH",
        help="Extra location to inspect when using -a (repeatable).",
    )
    parser.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        default=[],
        metavar="GLOB",
        help="Additional glob pattern(s) to evaluate when using -a (repeatable).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        dest="exclusions",
        default=[],
        metavar="PATTERN",
        help="Exclude paths matching pattern when using -a (repeatable).",
    )
    parser.add_argument(
        "--installation-path",
        type=str,
        default=None,
        help="Installer path to execute before scanning (only used with -a).",
    )
    parser.add_argument(
        "--deep-home-search",
        action="store_true",
        help="Enable brute-force home directory matching in addition to deterministic locations.",
    )
    parser.add_argument(
        "--run-installers",
        action="store_true",
        help="Execute installer commands when configuration entries provide an installation_path.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Enter interactive mode to review and select artifacts for deletion.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console output (warnings and errors still display).",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable live progress indicators.",
    )

    color_group = parser.add_argument_group("Color Customisation")
    color_group.add_argument("--accent-color", type=str)
    color_group.add_argument("--info-color", type=str)
    color_group.add_argument("--success-color", type=str)
    color_group.add_argument("--warning-color", type=str)
    color_group.add_argument("--error-color", type=str)
    color_group.add_argument("--highlight-color", type=str)
    color_group.add_argument("--muted-color", type=str)
    color_group.add_argument("--progress-bar-color", type=str)
    color_group.add_argument("--progress-complete-color", type=str)
    color_group.add_argument("--progress-description-color", type=str)

    return parser.parse_args()


def ensure_directories_exist(*directories: Path) -> None:
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def load_app_configurations(
    args: ParsedArgs, manager: OutputManager
) -> AppsConfiguration:
    if args.argv.app:
        app_config = build_single_app_configuration(args)
        return AppsConfiguration(apps=(app_config,))

    raw_inputs = [
        segment.strip() for segment in args.argv.input.split(",") if segment.strip()
    ]
    if not raw_inputs:
        raise ConfigurationError("No configuration paths provided via --input.")

    config_paths: list[Path] = []
    for raw in raw_inputs:
        try:
            candidate = validate_file_path(raw, must_exist=False)
            if candidate is None:
                continue
            if candidate.is_file():
                config_paths.append(candidate)
            else:
                config_paths.append(default_config_path(candidate))
        except ValidationError as exc:
            raise ConfigurationError(f"Invalid input path '{raw}': {exc}") from exc

    missing = [path for path in config_paths if not path.exists()]
    if missing:
        lines = "\n  - ".join(str(path) for path in missing)
        raise ConfigurationError(
            f"app-hound could not locate configuration file(s):\n  - {lines}"
        )

    if len(config_paths) == 1:
        return load_configuration(config_paths[0])
    return load_multiple_configurations(config_paths)


def build_single_app_configuration(args: ParsedArgs) -> AppConfiguration:
    # Validate app name
    try:
        app_name = validate_app_name(args.argv.app)
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid application name: {exc}") from exc

    # Validate additional locations
    validated_locations = []
    for path in args.argv.additional_locations:
        try:
            validated_path = validate_file_path(path, must_exist=False)
            if validated_path:
                validated_locations.append(validated_path)
        except ValidationError as exc:
            raise ConfigurationError(f"Invalid location '{path}': {exc}") from exc

    # Validate patterns
    validated_patterns = []
    for pattern in args.argv.patterns:
        try:
            validated_pattern = validate_glob_pattern(pattern)
            validated_patterns.append(validated_pattern)
        except ValidationError as exc:
            raise ConfigurationError(f"Invalid pattern '{pattern}': {exc}") from exc

    # Validate exclusions
    validated_exclusions = []
    for exclusion in args.argv.exclusions:
        try:
            validated_exclusion = validate_glob_pattern(exclusion)
            validated_exclusions.append(validated_exclusion)
        except ValidationError as exc:
            raise ConfigurationError(f"Invalid exclusion '{exclusion}': {exc}") from exc

    # Validate installation path
    installation_path = None
    if args.argv.installation_path:
        try:
            installation_path = validate_file_path(
                args.argv.installation_path, must_exist=False
            )
        except ValidationError as exc:
            raise ConfigurationError(f"Invalid installation path: {exc}") from exc

    return AppConfiguration(
        name=app_name,
        additional_locations=tuple(validated_locations),
        installation_path=installation_path,
        patterns=tuple(validated_patterns),
        exclusions=tuple(validated_exclusions),
        deep_home_search=args.argv.deep_home_search,
    )


def execute_installers_if_requested(
    apps: Sequence[AppConfiguration],
    *,
    manager: OutputManager,
    run_installers: bool,
) -> None:
    if not run_installers:
        return

    feedback = OutputManagerFeedback(manager)
    runner = InstallerRunner()
    for app in apps:
        if not app.installation_path:
            continue
        outcome = runner.run(app.installation_path, feedback=feedback)
        if outcome.status == InstallerStatus.ERROR:
            manager.warning(
                f"Installer for {app.name} exited with code {outcome.exit_code}. Continuing.",
                emoji="🐶",
            )
        elif outcome.status == InstallerStatus.NOT_FOUND:
            manager.warning(
                f"Installer for {app.name} was not found at {outcome.path}.",
                emoji="🐶",
            )
        elif outcome.status == InstallerStatus.MANUAL_ACTION_REQUIRED:
            manager.info(
                outcome.message or f"Manual action required for {outcome.path}",
                emoji="🐶",
            )


def perform_scans(
    apps_configuration: AppsConfiguration,
    *,
    manager: OutputManager,
    deep_home_search_default: bool,
) -> list[ScanResult]:
    scanner = Scanner(deep_home_search_default=deep_home_search_default)
    results: list[ScanResult] = []
    apps = list(apps_configuration.apps)

    iterable = manager.track(
        apps,
        "Sniffing application artifacts",
        total=len(apps) if apps else None,
        transient=True,
    )

    for app_config in iterable:
        manager.rule(f"🐶 Tracking pawprints for {app_config.name}")
        result = scanner.scan(app_config)
        emit_scan_summary(app_config.name, result, manager)
        results.append(result)

    return results


def emit_scan_summary(
    app_name: str, result: ScanResult, manager: OutputManager
) -> None:
    summary = ScanSummary.from_result(result)
    manager.info(
        (
            f"{app_name}: {summary.existing_artifacts}/{summary.total_artifacts} artifacts exist; "
            f"{summary.removable_artifacts} marked safe/caution for removal."
        ),
        emoji="🐶",
    )
    if result.errors:
        for message in result.errors:
            manager.warning(f"{app_name} — {message}", emoji="🐶")


def write_csv_report(
    results: Iterable[ScanResult], output_path: Path, manager: OutputManager
) -> None:
    ensure_directories_exist(output_path.parent)
    rows = build_csv_rows(results)
    headers = [
        "App Name",
        "Artifact Path",
        "Kind",
        "Scope",
        "Category",
        "Exists",
        "Writable",
        "Size (bytes)",
        "Last Modified",
        "Removal Safety",
        "Notes",
        "Removal Instructions",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    styled = manager.stylize(str(output_path), palette_key="highlight")
    manager.success(f"Wrote CSV report to {styled}", emoji="🐶")


def build_csv_rows(results: Iterable[ScanResult]) -> list[list[str]]:
    rows: list[list[str]] = []
    for result in results:
        for artifact in result.artifacts:
            rows.append(
                [
                    result.app_name,
                    str(artifact.path),
                    artifact.kind.value,
                    artifact.scope.value,
                    artifact.category.value,
                    str(artifact.exists),
                    str(artifact.writable) if artifact.writable is not None else "",
                    str(artifact.size_bytes) if artifact.size_bytes is not None else "",
                    artifact.last_modified.isoformat()
                    if artifact.last_modified
                    else "",
                    artifact.removal_safety.value,
                    " | ".join(artifact.notes),
                    " | ".join(artifact.removal_instructions),
                ]
            )
    return rows


def write_json_report(
    results: Iterable[ScanResult],
    output_path: Path,
    *,
    manager: OutputManager,
    label: str,
) -> None:
    ensure_directories_exist(output_path.parent)
    payload = [serialise_scan_result(result) for result in results]
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    styled = manager.stylize(str(output_path), palette_key="highlight")
    manager.success(f"Wrote {label} JSON to {styled}", emoji="🐶")


def serialise_scan_result(result: ScanResult) -> dict[str, object]:
    return {
        "app_name": result.app_name,
        "generated_at": result.generated_at.isoformat(),
        "artifacts": [serialise_artifact(artifact) for artifact in result.artifacts],
        "errors": list(result.errors),
    }


def serialise_artifact(artifact: Artifact) -> dict[str, object]:
    return {
        "app_name": artifact.app_name,
        "path": str(artifact.path),
        "kind": artifact.kind.value,
        "scope": artifact.scope.value,
        "category": artifact.category.value,
        "removal_safety": artifact.removal_safety.value,
        "exists": artifact.exists,
        "writable": artifact.writable,
        "size_bytes": artifact.size_bytes,
        "last_modified": artifact.last_modified.isoformat()
        if artifact.last_modified
        else None,
        "notes": list(artifact.notes),
        "removal_instructions": list(artifact.removal_instructions),
    }


def display_overall_summary(
    results: Sequence[ScanResult], manager: OutputManager
) -> None:
    if not results:
        manager.info("No artifacts were discovered.", emoji="🐶")
        return

    summaries = summarize_all(results)
    total_artifacts = sum(summary.total_artifacts for summary in summaries)
    total_existing = sum(summary.existing_artifacts for summary in summaries)
    total_removable = sum(summary.removable_artifacts for summary in summaries)
    message = (
        f"Summary: {total_existing}/{total_artifacts} artifacts currently exist; "
        f"{total_removable} flagged safe or caution for removal."
    )
    manager.highlight(message, emoji="🐶")


def main() -> None:
    args_ns = parse_arguments()
    args = ParsedArgs(args_ns)

    manager = OutputManager(
        quiet=args_ns.quiet,
        show_progress=not args_ns.no_progress,
    )
    if args.palette_overrides:
        manager.update_palette(**args.palette_overrides)

    ensure_directories_exist(
        AUDIT_DIR,
        args.csv_output_path.parent,
        args.json_output_path.parent,
        args.plan_output_path.parent,
    )

    # Handle --execute-plan mode
    if args_ns.execute_plan:
        from rich.prompt import Confirm

        from app_hound.interactive import ConsoleAdapter
        from app_hound.removal import ArtifactRemover

        try:
            plan_path = validate_file_path(args_ns.execute_plan, must_exist=True)
            if plan_path is None:
                manager.error("Plan file path is required", emoji="🐶", force=True)
                raise SystemExit(1)

            manager.highlight(f"Loading deletion plan from {plan_path}", emoji="🐶")
            plan = DeletionPlan.from_file(plan_path)

            enabled = plan.enabled_entries()
            if not enabled:
                manager.warning(
                    "No enabled entries in plan. Nothing to delete.", emoji="🐶"
                )
                raise SystemExit(0)

            manager.info(
                f"Plan contains {len(enabled)} enabled entries for deletion", emoji="📋"
            )

            # Ask for confirmation
            console = Console()

            if not Confirm.ask(
                "[bold yellow]⚠️  Execute deletion plan?[/bold yellow]", default=False
            ):
                manager.info("Execution cancelled.", emoji="🐶")
                raise SystemExit(0)

            # Offer dry-run
            dry_run = Confirm.ask(
                "[yellow]Perform dry run first?[/yellow]", default=True
            )

            # Create remover with console adapter
            console_adapter = ConsoleAdapter(console)
            remover = ArtifactRemover(output=console_adapter)

            if dry_run:
                console.print()
                console.print(
                    "[bold yellow]🔍 Dry Run - No files will be deleted[/bold yellow]"
                )
                console.print()
                report = remover.remove(enabled, dry_run=True)
                console.print()
                console.print(f"[green]✓ Would delete:[/green] {len(report.succeeded)}")
                console.print(f"[red]✗ Would fail:[/red] {len(report.failed)}")
                console.print()

                if not Confirm.ask(
                    "[bold red]Proceed with actual deletion?[/bold red]",
                    default=False,
                ):
                    manager.info("Execution cancelled.", emoji="🐶")
                    raise SystemExit(0)

            # Actual deletion
            console.print()
            console.print("[bold red]🗑️  Deleting files...[/bold red]")
            console.print()
            report = remover.remove(enabled, dry_run=False, prompt=False)

            # Show results
            console.print()
            console.print("[bold]Results:[/bold]")
            console.print(f"[green]✓ Deleted:[/green] {len(report.succeeded)}")
            console.print(f"[red]✗ Failed:[/red] {len(report.failed)}")
            console.print(f"[yellow]⊘ Skipped:[/yellow] {len(report.skipped)}")

            if report.failed:
                console.print()
                console.print("[bold red]Failed items:[/bold red]")
                for entry, error in report.failed:
                    console.print(f"  [red]✗[/red] {entry.path}")
                    console.print(f"    [dim]{error}[/dim]")

            manager.finalize("app-hound says: Deletion complete! 🦴")
            raise SystemExit(0)

        except FileNotFoundError as exc:
            manager.error(str(exc), emoji="🐶", force=True)
            raise SystemExit(1)
        except ValueError as exc:
            manager.error(f"Invalid plan file: {exc}", emoji="🐶", force=True)
            raise SystemExit(1)
        except Exception as exc:
            manager.error(f"Error executing plan: {exc}", emoji="🐶", force=True)
            raise SystemExit(1)

    manager.highlight("app-hound is on the trail!", emoji="🐶")

    try:
        apps_configuration = load_app_configurations(args, manager)
    except ConfigurationError as exc:
        manager.error(str(exc), emoji="🐶", force=True)
        raise SystemExit(1) from exc

    if not apps_configuration.apps:
        manager.warning(
            "No applications defined; nothing to scan.", emoji="🐶", force=True
        )
        raise SystemExit(0)

    execute_installers_if_requested(
        apps_configuration.apps,
        manager=manager,
        run_installers=args_ns.run_installers,
    )

    results = perform_scans(
        apps_configuration,
        manager=manager,
        deep_home_search_default=args_ns.deep_home_search,
    )

    # If interactive mode is enabled, enter TUI for artifact selection
    if args_ns.interactive:
        manager.finalize("Entering interactive mode... 🎯")
        console = Console()
        removal_report = run_interactive_mode(results, console)

        if removal_report:
            manager.highlight(
                "Interactive session complete: "
                + f"{len(removal_report.succeeded)} deleted, "
                + f"{len(removal_report.failed)} failed, "
                + f"{len(removal_report.skipped)} skipped",
                emoji="✓",
            )
        else:
            manager.info("Interactive session cancelled.", emoji="🐶")

        # Still write reports even in interactive mode
        manager.info("Writing reports...", emoji="📝")

    with manager.status(f"Compiling reports → {args.csv_output_path}"):
        write_csv_report(results, args.csv_output_path, manager)

        # Write artifact JSON report
        write_json_report(
            results, args.json_output_path, manager=manager, label="artifact report"
        )

        # Build and write the deletion plan JSON and shell script
        plan = DeletionPlan.from_scan_results(results)

        ensure_directories_exist(args.plan_output_path.parent)
        with args.plan_output_path.open("w", encoding="utf-8") as handle:
            handle.write(plan.to_json(indent=2))
        styled_plan = manager.stylize(
            str(args.plan_output_path), palette_key="highlight"
        )
        manager.success(f"Wrote plan JSON to {styled_plan}", emoji="🐶")

        ensure_directories_exist(args.plan_script_output_path.parent)
        script_path = write_shell_script(
            plan,
            args.plan_script_output_path,
            only_enabled=True,
            prompt_each=True,
            executable=True,
        )
        styled_script = manager.stylize(str(script_path), palette_key="highlight")
        manager.success(f"Wrote deletion script to {styled_script}", emoji="🐶")

    display_overall_summary(results, manager)
    manager.finalize("app-hound says: Fetch complete! 🦴")


if __name__ == "__main__":
    main()
