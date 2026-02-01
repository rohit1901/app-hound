import argparse
import csv
from pathlib import Path
from typing import Any

from app_hound.finder import (
    configure_output_manager,
    gather_app_entries,
    get_output_manager,
    load_apps_from_json,
    load_apps_from_multiple_json,
    run_installer,
)
from app_hound.types import AppConfigEntry, AppsConfig

APP_HOUND_HOME = Path.home() / ".app-hound"
APP_CONFIG_NAME = "apps_config.json"
AUDIT_DIR = APP_HOUND_HOME / "audit"


def parse_arguments():
    """
    Parse command-line arguments for input and output file locations.

    Returns:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        prog="app-hound",
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "\033[1;36m╭──────────────────────────────────────────────╮\033[0m\n"
            "\033[1;36m│ 🐶  app-hound: Snout & About Audit Parade!   │\033[0m\n"
            "\033[1;36m╰──────────────────────────────────────────────╯\033[0m\n"
            "  \033[1;33m•\033[0m Fetch top-level pawprints without clutter.\n"
            "  \033[1;33m•\033[0m Sweep away stubborn leftovers with confidence.\n"
            "  \033[1;33m•\033[0m Spotlight a VIP app with --app-name or bring the whole pack.\n"
        ),
        epilog=(
            "\033[1;35mPro tip:\033[0m Pair with \033[1m--output\033[0m to stash reports in your favorite den.\n"
            "Give app-hound a pat with ⭐️ if it keeps your Mac tidy!"
        ),
    )
    sniff_group = parser.add_argument_group(
        "\033[1;34mTrail Options\033[0m",
        description="Tune the trek with colorful toggles:",
    )
    _ = sniff_group.add_argument(
        "-i",
        "--input",
        type=str,
        help="🎒 Config den for apps_config.json (default: current den). Multiple paths can be specified as a comma-separated list.",
        default=str(Path.cwd()),
    )
    _ = sniff_group.add_argument(
        "-o",
        "--output",
        type=str,
        default=str(AUDIT_DIR / "audit.csv"),
        help="🗂️  Drop spot for the sparkling audit.csv (default: ~/.app-hound/audit/audit.csv)",
    )
    _ = sniff_group.add_argument(
        "-a",
        "--app",
        "--app-name",
        type=str,
        default=None,
        help="🎯 Name a single VIP app for a focused sniff instead of using apps_config.json",
    )
    _ = sniff_group.add_argument(
        "--quiet",
        action="store_true",
        help="🤫 Suppress console output for scripting flows (critical errors still appear).",
    )
    _ = sniff_group.add_argument(
        "--no-progress",
        action="store_true",
        help="🚫 Disable live progress indicators for environments where they are undesirable.",
    )
    color_group = parser.add_argument_group(
        "\033[1;32mColor Customization\033[0m",
        description="Tailor app-hound's palette with Rich style strings (e.g., 'bold blue'):",
    )
    color_group.add_argument(
        "--accent-color",
        type=str,
        help="Set the accent color used for banners and rules.",
    )
    color_group.add_argument(
        "--info-color",
        type=str,
        help="Set the informational message color.",
    )
    color_group.add_argument(
        "--success-color",
        type=str,
        help="Set the success message color.",
    )
    color_group.add_argument(
        "--warning-color",
        type=str,
        help="Set the warning message color.",
    )
    color_group.add_argument(
        "--error-color",
        type=str,
        help="Set the error message color.",
    )
    color_group.add_argument(
        "--highlight-color",
        type=str,
        help="Set the highlight color used for emphasized text.",
    )
    color_group.add_argument(
        "--muted-color",
        type=str,
        help="Set the muted/secondary text color.",
    )
    return parser.parse_args()


def ensure_directories_exist(*directories: Path):
    """
    Ensure the provided directories exist.

    Args:
        *directories (Path): Directory paths to create if missing.
    """
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def validate_config_path(config_path: Path, *, output: Any | None = None):
    """
    Validate the existence of the apps config JSON file.

    Args:
        config_path (Path): The path to apps_config.json.
        output (Any | None): Optional console manager for styled output.

    Raises:
        SystemExit: If the config file is not found.
    """
    if not config_path.exists():
        missing_msg = f"🐶 app-hound couldn't find {APP_CONFIG_NAME} at {config_path}."
        hint_msg = "Make sure your config file is in your project root directory!"
        if output is not None:
            output.error(missing_msg, emoji="🐶", force=True)
            output.warning(hint_msg, emoji="🐶", force=True)
        else:
            print(missing_msg)
            print(f"{hint_msg}\n")
        exit(1)


def validate_config_paths(config_paths: list[Path], *, output: Any | None = None):
    """
    Validate the existence of the apps config JSON files.

    Args:
        config_paths (list[Path]): List of paths to apps_config.json files.
        output (Any | None): Optional console manager for styled output.

    Raises:
        SystemExit: If any config file is not found.
    """
    missing_paths = [path for path in config_paths if not path.exists()]
    if missing_paths:
        header = f"🐶 app-hound couldn't find {APP_CONFIG_NAME} in the following config files:"
        footer = "Make sure your config files exist!"
        if output is not None:
            output.error(header, emoji="🐶", force=True)
            for path in missing_paths:
                output.warning(f"  - {path}", emoji="🐶", force=True)
            output.warning(footer, emoji="🐶", force=True)
        else:
            print(header)
            for path in missing_paths:
                print(f"  - {path}")
            print(f"{footer}\n")
        exit(1)


def process_app_entries(
    app: AppConfigEntry, *, output: Any | None = None
) -> list[tuple[str, str, bool, str]]:
    """
    Install app (if installation_path exists), then gather and return app folders/files.

    Args:
        app (dict): App configuration dictionary.
        output (Any | None): Optional console manager for styled output.

    Returns:
        list: List of found files/folders for this app.
    """
    manager = output or get_output_manager()
    name = app.get("name")
    additional_locations = app.get("additional_locations", [])
    installer: Any | None = app.get("installation_path")  # pyright: ignore[reportExplicitAny]

    if installer and isinstance(installer, str):
        _ = run_installer(installer, output=manager)

    files_found = gather_app_entries(name, additional_locations, output=manager)
    return files_found


def collect_audit_results(
    apps: AppsConfig, *, output: Any | None = None
) -> list[tuple[str, str, bool, str]]:
    """
    Collect audit results from a list of apps.

    Args:
        apps (list): List of apps.
        output (Any | None): Optional console manager for styled output.

    Returns:
        list: Combined list of app entries for audit.
    """
    manager = output or get_output_manager()
    all_results: list[tuple[str, str, bool, str]] = []
    app_configs = apps["apps"]
    iterable = manager.track(
        app_configs,
        "Sniffing audit targets",
        total=len(app_configs) if app_configs else None,
        transient=True,
    )
    for app in iterable:
        all_results.extend(process_app_entries(app, output=manager))
    return all_results


def write_audit_csv(
    results: list[tuple[str, str, bool, str]],
    output_csv: Path,
    *,
    output: Any | None = None,
):
    """
    Write audit results to a CSV file.

    Args:
        results (list): Audit results to write.
        output_csv (Path): Output CSV file path.
        output (Any | None): Optional console manager for styled output.
    """
    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["App Name", "Base Path", "Folder", "File name"])
        writer.writerows(results)
    if output is not None:
        styled_path = output.stylize(str(output_csv), palette_key="highlight")
        output.success(
            f"app-hound saved your audit report to {styled_path}.",
            emoji="🐶",
        )
    else:
        print(
            f"\n🐶 app-hound says: Audit report saved to {output_csv}. Time for a treat!\n"
        )


def main():
    """
    Main entry point for app-hound: parses args, validates config, collects results, writes audit report.
    """
    args: argparse.Namespace = parse_arguments()
    output_path = Path(args.output)  # pyright: ignore[reportAny]
    raw_app = args.app
    app_name = raw_app.strip() if isinstance(raw_app, str) else None

    palette_overrides = {
        "accent": getattr(args, "accent_color", None),
        "info": getattr(args, "info_color", None),
        "success": getattr(args, "success_color", None),
        "warning": getattr(args, "warning_color", None),
        "error": getattr(args, "error_color", None),
        "highlight": getattr(args, "highlight_color", None),
        "muted": getattr(args, "muted_color", None),
    }
    palette_overrides = {
        key: value for key, value in palette_overrides.items() if value
    }

    manager = configure_output_manager(
        quiet=args.quiet,
        show_progress=not args.no_progress,
        palette_overrides=palette_overrides or None,
    )

    ensure_directories_exist(AUDIT_DIR, output_path.parent)

    manager.highlight(
        "app-hound is on the trail, ready to fetch audit results!",
        emoji="🐶",
    )
    if app_name:
        styled_app = manager.stylize(app_name, palette_key="highlight")
        manager.info(f"app-hound will sniff exclusively for {styled_app}.", emoji="🐶")
        single_app: AppConfigEntry = {"name": app_name, "additional_locations": []}
        apps: AppsConfig = {"apps": [single_app]}
    else:
        raw_inputs = [segment.strip() for segment in args.input.split(",")]
        config_dirs = [Path(segment or ".") for segment in raw_inputs]
        config_files = [config_dir / APP_CONFIG_NAME for config_dir in config_dirs]
        validate_config_paths(config_files, output=manager)
        if len(config_files) == 1:
            apps = load_apps_from_json(str(config_files[0]))
        else:
            apps = load_apps_from_multiple_json([str(path) for path in config_files])

    all_results = collect_audit_results(apps, output=manager)

    styled_output_path = manager.stylize(str(output_path), palette_key="highlight")
    with manager.status(f"Compiling fetch report → {styled_output_path}"):
        write_audit_csv(all_results, output_path, output=manager)

    manager.finalize(
        f"app-hound says: Audit Complete! Report saved to {styled_output_path}"
    )


if __name__ == "__main__":
    main()
