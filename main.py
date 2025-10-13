from pathlib import Path
from app_hound.finder import (
    run_installer,
    load_apps_from_json,
    gather_app_entries,
    export_multiple_apps_files,
)
import csv

APP_CONFIG_PATH = (
    Path(__file__).parent / "apps_config.json"
)  # Static config, root-level


def process_app_entries(app: dict) -> list:
    """
    Installs the app if installation_path is set, then gathers and lists all file entries for the current user only.

    Args:
        app (dict): App configuration dict with 'name', 'paths', optionally 'installation_path'.

    Returns:
        list: List of tuples (name, base, file) to be exported to CSV.
    """
    name = app.get("name")
    paths = app.get("paths", [])
    installer = app.get("installation_path")
    # Only run installer if property exists and is a local path
    if installer:
        run_installer(installer)
    files_found = gather_app_entries(name, paths)
    return [(name, base, file) for base, file in files_found]


def main():
    """
    Entry point for app-hound.
    Loads config, processes each app (install & audit), and exports the full audit to CSV.
    """
    apps = load_apps_from_json(str(APP_CONFIG_PATH))
    all_results = []
    for app in apps:
        all_results.extend(process_app_entries(app))
    output_csv = input("Enter the output CSV filename (e.g., audit.csv): ").strip()
    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["App Name", "Base Path", "File"])
        writer.writerows(all_results)
    print(f"Audit report saved to {output_csv}")


if __name__ == "__main__":
    main()
