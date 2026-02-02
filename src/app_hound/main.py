from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

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
from app_hound.removal import DeletionPlan, write_shell_script
from app_hound.scanner import Scanner
from app_hound.ui import OutputManager

APP_HOUND_HOME = Path.home() / ".app-hound"
AUDIT_DIR = APP_HOUND_HOME / "audit"
DEFAULT_CSV = AUDIT_DIR / "audit.csv"


@dataclass(frozen=True)
class ParsedArgs:
    argv: argparse.Namespace

    @property
    def csv_output_path(self) -> Path:
        return Path(self.argv.output).expanduser()

    @property
    def json_output_path(self) -> Path | None:
        json_path = self.argv.json_output
        return Path(json_path).expanduser() if json_path else None

    @property
    def plan_output_path(self) -> Path | None:
        plan_path = self.argv.plan
        return Path(plan_path).expanduser() if plan_path else None

    @property
    def plan_script_output_path(self) -> Path | None:
        plan_script_path = getattr(self.argv, "plan_script", None)
        return Path(plan_script_path).expanduser() if plan_script_path else None

    @property
    def palette_overrides(self) -> dict[str, str]:
        names = (
            "accent_color",
            "info_color",
            "success_color",
            "warning_color",
            "error_color",
            "highlight_color",
            "muted_color",
            "progress_bar_color",
            "progress_complete_color",
            "progress_description_color",
        )
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
        return {key: value for key, value in mapping.items() if value}


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


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="app-hound",
        formatter_class=argparse.RawTextHelpFormatter,
        description="🐶 app-hound — deterministic macOS artifact hunter",
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
        "--additional-location",
        action="append",
        dest="additional_locations",
        default=[],
        metavar="PATH",
        help="Extra location to inspect when using --app (repeatable).",
    )
    parser.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        default=[],
        metavar="GLOB",
        help="Additional glob pattern(s) to evaluate when using --app (repeatable).",
    )
    parser.add_argument(
        "--installation-path",
        type=str,
        default=None,
        help="Installer path to execute before scanning (only used with --app).",
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
        candidate = Path(raw).expanduser()
        if candidate.is_file():
            config_paths.append(candidate)
        else:
            config_paths.append(default_config_path(candidate))

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
    additional_locations = tuple(
        Path(path).expanduser() for path in args.argv.additional_locations
    )
    patterns = tuple(pattern for pattern in args.argv.patterns)
    installation_path = (
        Path(args.argv.installation_path).expanduser()
        if args.argv.installation_path
        else None
    )

    return AppConfiguration(
        name=args.argv.app.strip(),
        additional_locations=additional_locations,
        installation_path=installation_path,
        patterns=patterns,
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

    ensure_directories_exist(AUDIT_DIR, args.csv_output_path.parent)
    if args.json_output_path:
        ensure_directories_exist(args.json_output_path.parent)
    if args.plan_output_path:
        ensure_directories_exist(args.plan_output_path.parent)

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

    with manager.status(f"Compiling reports → {args.csv_output_path}"):
        write_csv_report(results, args.csv_output_path, manager)
        # Always write the artifact JSON report to the default location (or custom if provided)
        write_json_report(
            results, args.json_output_path, manager=manager, label="artifact report"
        )
        # Always build and write the deletion plan JSON and shell script
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
