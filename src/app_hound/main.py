from pathlib import Path
import argparse
import csv

from app_hound.finder import (
    run_installer,
    load_apps_from_json,
    gather_app_entries,
)

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
        description="🐶 app-hound fetches top-level app files and folders for audit!"
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        help="Location of apps_config.json (default: project root)",
        default=str(Path.cwd()),
        required=True,
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=str(AUDIT_DIR / "audit.csv"),
        help="Location of output audit.csv (default: ~/.app-hound/audit/audit.csv in project root)",
    )
    return parser.parse_args()


def ensure_directories_exist(audit_dir: Path):
    """
    Ensure the audit directory exists.

    Args:
        audit_dir (Path): The audit directory path.
    """
    audit_dir.mkdir(parents=True, exist_ok=True)


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


def process_app_entries(app: dict) -> list:
    """
    Install app (if installation_path exists), then gather and return app folders/files.

    Args:
        app (dict): App configuration dictionary.

    Returns:
        list: List of found files/folders for this app.
    """
    name = app.get("name")
    additional_locations = app.get("additional_locations", [])
    installer = app.get("installation_path")

    if installer:
        run_installer(installer)

    files_found = gather_app_entries(name, additional_locations)
    return files_found


def collect_audit_results(apps: list) -> list:
    """
    Collect audit results from a list of apps.

    Args:
        apps (list): List of apps.

    Returns:
        list: Combined list of app entries for audit.
    """
    all_results = []
    for app in apps:
        all_results.extend(process_app_entries(app))
    return all_results


def write_audit_csv(results: list, output_csv: Path):
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
    args = parse_arguments()
    input_path = Path(args.input) / APP_CONFIG_NAME
    output_path = Path(args.output)

    ensure_directories_exist(AUDIT_DIR)
    validate_config_path(input_path)

    print("\n🐶 app-hound is on the trail, ready to fetch audit results!\n")

    apps = load_apps_from_json(str(input_path))
    all_results = collect_audit_results(apps)

    print(f"\n🐶 app-hound is compiling your fetch report ({output_path})...\n")
    write_audit_csv(all_results, output_path)


if __name__ == "__main__":
    main()
