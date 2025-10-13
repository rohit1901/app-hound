import json
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple
import csv
from rich.console import Console

console = Console()


def run_installer(installer_path: str) -> int:
    """
    Attempts to execute the provided installer.

    Args:
        installer_path (str): Path to the installer on the local machine.

    Returns:
        int: Status code (0=success, 1=not found, 2=manual action for .dmg).
              .pkg: Executes via 'installer' command with sudo.
              .dmg: Prompts user for manual mounting (cannot automate fully).
              .app: Executes via 'open'.
              If file is missing, returns 1.
    """
    path = Path(installer_path).expanduser()
    if not path.exists():
        console.print(f"[red]Installer not found: {path}[/red]")
        return 1
    console.print(f"[bold yellow]Running installer: {path}[/bold yellow]")
    if path.suffix == ".pkg":
        # User must confirm; sudo prompt!
        return subprocess.call(["sudo", "installer", "-pkg", str(path), "-target", "/"])
    elif path.suffix == ".dmg":
        console.print(
            "[cyan]Please manually mount the DMG and run the contained app.[/cyan]"
        )
        return 2
    elif path.is_dir() and path.name.endswith(".app"):
        return subprocess.call(["open", str(path)])
    else:
        return subprocess.call([str(path)])


def load_apps_from_json(json_path: str) -> List[Dict]:
    """
    Loads app definitions from a JSON configuration file.

    Args:
        json_path (str): Path to the config file (typically app_config.json).

    Returns:
        List[Dict]: List of apps with 'name', 'paths', and optionally 'installation_path'.
    """
    with open(json_path, "r") as f:
        config = json.load(f)
    return config.get("apps", [])


def gather_app_entries(app_name: str, paths: List[str]) -> List[Tuple[str, str]]:
    """
    For a given application, checks all configured paths relevant to the
    currently logged-in user and /Applications, recording details about their
    existence and contents.

    Only audits:
        - paths starting with "~/" (current user home)
        - paths starting with "/Applications"
        - paths starting with the full home dir path

    Args:
        app_name (str): Name of the application (e.g., "PDF Expert").
        paths (List[str]): List of possible install/support locations (strings).

    Returns:
        List[Tuple[str, str]]: Each tuple is (base path, file or status).
    """
    user_home = str(Path.home())
    allowed_prefixes = [user_home, "/Applications"]
    entries = []

    for raw_path in paths:
        path = Path(raw_path).expanduser()
        expanded = str(path)
        # Only paths for this user and top-level Applications
        if not any(
            expanded.startswith(prefix) for prefix in allowed_prefixes
        ) and not raw_path.startswith("~"):
            continue

        if not path.exists():
            entries.append((str(path), "not found"))
            console.print(f"[red]{app_name}: {path} (not found)[/red]")
        elif path.is_dir():
            files = [str(p) for p in path.rglob("*") if p.is_file()]
            if files:
                for f in files:
                    entries.append((str(path), f))
                    console.print(f"[green]{app_name}: {f}[/green]")
            else:
                entries.append((str(path), "(empty)"))
                console.print(f"[yellow]{app_name}: {path} (empty)[/yellow]")
        else:
            entries.append((str(path), "file exists"))
            console.print(f"[blue]{app_name}: {path} (file exists)[/blue]")
    return entries


def export_multiple_apps_files(
    apps_config: List[Dict], csv_filepath: str, verbose: bool = True
) -> None:
    """
    Exports all files related to all apps in config to a CSV.

    Args:
        apps_config (List[Dict]): Apps to process (with 'name', 'paths', optional installer).
        csv_filepath (str): Output CSV file path.
        verbose (bool): If True, prints section headers for each app audit.
    """
    all_entries = []
    for app in apps_config:
        name = app.get("name")
        paths = app.get("paths", [])
        if verbose:
            console.rule(f"[bold magenta]Auditing {name}")
        entries = gather_app_entries(name, paths)
        all_entries.extend([(name, base, file) for base, file in entries])
    with open(csv_filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["App Name", "Base Path", "File"])
        writer.writerows(all_entries)
    console.rule("[bold green]Audit Complete", style="green")
