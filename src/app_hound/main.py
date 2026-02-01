import argparse
import csv
from pathlib import Path
from typing import Any

from app_hound.finder import (
    gather_app_entries,
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
        type=str,
        default=None,
        help="🎯 Name a single VIP app for a focused sniff instead of using apps_config.json",
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


def validate_config_path(config_path: Path):
    """
    Validate the existence of the apps config JSON file.

    Args:
        config_path (Path): The path to apps_config.json.

    Raises:
        SystemExit: If the config file is not found.
    """
    if not config_path.exists():
        print(f"🐶 app-hound couldn't find {APP_CONFIG_NAME} at {config_path}.")
        print("Make sure your config file is in your project root directory!\n")
        exit(1)


def validate_config_paths(config_paths: list[Path]):
    """
    Validate the existence of the apps config JSON files.

    Args:
        config_paths (list[Path]): List of paths to apps_config.json files.

    Raises:
        SystemExit: If any config file is not found.
    """
    missing_paths = [path for path in config_paths if not path.exists()]
    if missing_paths:
        print(
            f"🐶 app-hound couldn't find {APP_CONFIG_NAME} in the following config files:"
        )
        for path in missing_paths:
            print(f"  - {path}")
        print("Make sure your config files exist!\n")
        exit(1)


def process_app_entries(app: AppConfigEntry) -> list[tuple[str, str, bool, str]]:
    """
    Install app (if installation_path exists), then gather and return app folders/files.

    Args:
        app (dict): App configuration dictionary.

    Returns:
        list: List of found files/folders for this app.
    """
    name = app.get("name")
    additional_locations = app.get("additional_locations", [])
    installer: Any | None = app.get("installation_path")  # pyright: ignore[reportExplicitAny]

    if installer and isinstance(installer, str):
        _ = run_installer(installer)

    files_found = gather_app_entries(name, additional_locations)
    return files_found


def collect_audit_results(apps: AppsConfig) -> list[tuple[str, str, bool, str]]:
    """
    Collect audit results from a list of apps.

    Args:
        apps (list): List of apps.

    Returns:
        list: Combined list of app entries for audit.
    """
    all_results: list[tuple[str, str, bool, str]] = []
    for app in apps["apps"]:
        all_results.extend(process_app_entries(app))
    return all_results


def write_audit_csv(results: list[tuple[str, str, bool, str]], output_csv: Path):
    """
    Write audit results to a CSV file.

    Args:
        results (list): Audit results to write.
        output_csv (Path): Output CSV file path.
    """
    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["App Name", "Base Path", "Folder", "File name"])
        writer.writerows(results)
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

    ensure_directories_exist(AUDIT_DIR, output_path.parent)

    print("\n🐶 app-hound is on the trail, ready to fetch audit results!\n")
    if app_name:
        print(f"🐶 app-hound will sniff exclusively for '{app_name}'.\n")
        single_app: AppConfigEntry = {"name": app_name, "additional_locations": []}
        apps: AppsConfig = {"apps": [single_app]}
    else:
        raw_inputs = [segment.strip() for segment in args.input.split(",")]
        config_dirs = [Path(segment or ".") for segment in raw_inputs]
        config_files = [config_dir / APP_CONFIG_NAME for config_dir in config_dirs]
        validate_config_paths(config_files)
        if len(config_files) == 1:
            apps = load_apps_from_json(str(config_files[0]))
        else:
            apps = load_apps_from_multiple_json([str(path) for path in config_files])
    all_results = collect_audit_results(apps)

    print(f"\n🐶 app-hound is compiling your fetch report ({output_path})...\n")
    write_audit_csv(all_results, output_path)


if __name__ == "__main__":
    main()
