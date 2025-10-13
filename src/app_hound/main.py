from pathlib import Path
from app_hound.finder import (
    run_installer,
    load_apps_from_json,
    gather_app_entries,
)
import csv

APP_CONFIG_PATH = Path(__file__).parents[2] / "apps_config.json"
AUDIT_DIR = Path(__file__).parents[2] / "audit"


def process_app_entries(app: dict) -> list:
    """
    Installs the app if installation_path is set, then gathers and lists all top-level app folders/files.
    """
    name = app.get("name")
    additional_locations = app.get("additional_locations", [])
    installer = app.get("installation_path")
    if installer:
        run_installer(installer)
    files_found = gather_app_entries(name, additional_locations)
    return files_found


def main():
    if not APP_CONFIG_PATH.exists():
        print(f"🐶 app-hound couldn't find apps_config.json at {APP_CONFIG_PATH}.")
        print("Make sure your config file is in your project root directory!\n")
        exit(1)
    print("\n🐶 app-hound is on the trail, ready to fetch audit results!\n")
    apps = load_apps_from_json(str(APP_CONFIG_PATH))
    all_results = []
    for app in apps:
        all_results.extend(process_app_entries(app))
    # Ensure audit directory exists
    AUDIT_DIR.mkdir(exist_ok=True)
    output_csv = input(
        "Enter the output CSV filename (default: audit/audit.csv): "
    ).strip()
    if not output_csv:
        output_csv = AUDIT_DIR / "audit.csv"
    else:
        output_csv = (
            AUDIT_DIR / output_csv
            if not str(output_csv).startswith(str(AUDIT_DIR))
            else Path(output_csv)
        )
    print(f"\n🐶 app-hound is compiling your fetch report ({output_csv})...\n")
    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["App Name", "Base Path", "Folder", "File name"])
        writer.writerows(all_results)
    print(
        f"\n🐶 app-hound says: Audit report saved to {output_csv}. Time for a treat!\n"
    )


if __name__ == "__main__":
    main()
