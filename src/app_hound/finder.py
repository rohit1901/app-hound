import csv
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

from app_hound.types import AppsConfig, is_apps_config

console = Console()


def run_installer(installer_path: str) -> int:
    """
    Attempts to execute the provided installer.

    Args:
        installer_path (str): Path to the installer on the local machine.

    Returns:
        int: Status code (0=success, 1=not found, 2=manual action for .dmg).
    """
    path = Path(installer_path).expanduser()
    if not path.exists():
        console.print(f"🐶 [red]app-hound can't sniff out the installer: {path}[/red]")
        return 1
    console.print(
        f"🐶 [bold yellow]app-hound is launching installer: {path}[/bold yellow]"
    )
    if path.suffix == ".pkg":
        return subprocess.call(["sudo", "installer", "-pkg", str(path), "-target", "/"])
    elif path.suffix == ".dmg":
        console.print(
            "[cyan]🐶 app-hound says: Please manually mount the DMG and run the contained app.[/cyan]"
        )
        return 2
    elif path.is_dir() and path.name.endswith(".app"):
        return subprocess.call(["open", str(path)])
    else:
        return subprocess.call([str(path)])


def expand_env_vars(data: Any) -> Any:
    """
    Recursively expands environment variables in strings and lists of strings.

    Args:
        data (Any): The data to process.
    Returns:
        Any: Data with environment variables expanded.
    """
    if isinstance(data, str):
        return os.path.expandvars(data)
    elif isinstance(data, list):
        return [expand_env_vars(item) for item in data]
    elif isinstance(data, dict):
        return {key: expand_env_vars(value) for key, value in data.items()}
    else:
        return data


def load_apps_from_json(json_path: str) -> AppsConfig:
    """
    Loads app definitions from a JSON configuration file.

    Args:
        json_path (str): Path to the config file.
    Returns:
        List[Dict]: List of apps.
    """
    with open(json_path, "r") as f:
        raw_data: Any = json.load(f)  # pyright: ignore[reportExplicitAny, reportAny]

        if not is_apps_config(raw_data):
            raise ValueError("Invalid apps configuration")

        config: AppsConfig = raw_data
        if not config.get("apps"):
            raise ValueError("Invalid apps configuration")

        # Expand environment variables in the configuration
        config = expand_env_vars(config)

        return config


def load_apps_from_multiple_json(json_paths: list[str]) -> AppsConfig:
    """
    Loads app definitions from multiple JSON configuration files and merges them.

    Args:
        json_paths (list[str]): List of paths to config files.
    Returns:
        AppsConfig: Merged configuration.
    """
    merged_config: AppsConfig = {"apps": []}

    for json_path in json_paths:
        config = load_apps_from_json(json_path)
        merged_config["apps"].extend(config["apps"])

    return merged_config


def get_default_locations(app_name: str) -> list[str]:
    """
    Returns default macOS locations where app data is commonly stored.
    """
    user_home = str(Path.home())
    return [
        f"/Applications/{app_name}.app",
        f"{user_home}/Library/Application Support/{app_name}",
        f"{user_home}/Library/Preferences/com.{app_name}.plist",
        f"{user_home}/Library/Caches/com.{app_name}",
        f"{user_home}/Library/Containers/com.{app_name}",
        f"/Library/Application Support/{app_name}",
        f"{user_home}/Library/Logs",
    ]


def find_all_matches_in_home(app_name: str) -> list[str]:
    """
    Recursively searches the current user's home directory for any file or folder whose
    name contains the app name (case-insensitive).

    Args:
        app_name (str): Name of the app.

    Returns:
        List[str]: List of full paths to matched files/folders.
    """
    user_home = Path.home()
    pattern = re.compile(re.escape(app_name), re.IGNORECASE)
    matches: list[str] = []
    for path in user_home.rglob("*"):
        # Only match actual file/folder names
        if pattern.search(path.name):
            matches.append(str(path))
    return matches


def gather_app_entries(
    app_name: str, additional_locations: list[str] | None = None
) -> list[tuple[str, str, bool, str]]:
    """
    Searches default macOS and additional locations for top-level folders/files
    whose name contains the app name. Playful 'app-hound' themed console messages.
    Only found paths go into audit data.

    Returns:
        List[Tuple[str, str, bool, str]]: (app_name, base path, is_folder(bool), file/folder name or 'none')
    """
    search_paths = find_all_matches_in_home(app_name)
    if additional_locations:
        search_paths.extend(additional_locations)
    pattern = re.compile(re.escape(app_name.lower()), re.IGNORECASE)

    entries: list[tuple[str, str, bool, str]] = []
    if additional_locations:
        console.rule(
            f"[bold magenta]🐶 app-hound sniffs extra spots for '{app_name}'![/bold magenta]"
        )
        for _, add_path in enumerate(additional_locations, 1):
            path = Path(add_path).expanduser()
            status = "found" if path.exists() else "not found"
            msg = (
                f"🐶 app-hound checks custom path: [bold yellow]{path}[/bold yellow]... "
                f"{'[green]Bingo! Found![/green]' if status == 'found' else '[red]No scent detected![/red]'}"
            )

            console.print(msg)
    # Auditing only found matches
    for raw_path in search_paths:
        path = Path(raw_path).expanduser()
        if path.exists():
            top_name = path.name
            if pattern.search(top_name.lower()):
                if path.is_dir():
                    console.print(
                        f"🐶 [bold green]app-hound sniffs: '{path}' (folder exists). Ready to fetch all traces![/bold green]"
                    )
                    entries.append((app_name, str(path), True, "none"))
                else:
                    console.print(
                        f"🐶 [bold blue]app-hound fetches: '{path}' (file exists).[/bold blue]"
                    )
                    entries.append((app_name, str(path), False, top_name))
    return entries


def export_multiple_apps_files(
    apps_config: AppsConfig,
    csv_filepath: str,
    verbose: bool = True,
) -> None:
    """
    Exports all top-level folders and files related to all apps in config to a CSV.
    Args:
        apps_config (List[Dict]): Apps to process.
        csv_filepath (str): Output CSV file path.
        verbose (bool): Print section headers for each app audit.

    Writes columns: App Name, Base Path, Folder, File name
    """
    all_entries: list[tuple[str, str, bool, str]] = []
    for app in apps_config["apps"]:
        name: str | None = app.get("name")
        additional_locations = app.get("additional_locations", [])
        if verbose:
            console.rule(
                f"[bold magenta]🐶 app-hound is sniffing for '{name}'![/bold magenta]"
            )
        entries = gather_app_entries(name, additional_locations)
        all_entries.extend(entries)
    with open(csv_filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["App Name", "Base Path", "Folder", "File name"])
        writer.writerows(all_entries)
    console.rule("[bold green]🐶 app-hound says: Audit Complete!", style="green")
