import csv
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from app_hound.types import AppsConfig, is_apps_config
from app_hound.ui import ColorPalette, OutputManager

output_manager = OutputManager()


def get_output_manager() -> OutputManager:
    return output_manager


def configure_output_manager(
    *,
    quiet: bool | None = None,
    show_progress: bool | None = None,
    palette: ColorPalette | None = None,
    palette_overrides: dict[str, str] | None = None,
) -> OutputManager:
    if quiet is not None:
        output_manager.set_quiet(quiet)
    if show_progress is not None:
        output_manager.set_show_progress(show_progress)
    if palette is not None:
        output_manager.set_palette(palette)
    if palette_overrides:
        output_manager.update_palette(**palette_overrides)
    return output_manager


def run_installer(installer_path: str, *, output: OutputManager | None = None) -> int:
    """
    Attempts to execute the provided installer.

    Args:
        installer_path (str): Path to the installer on the local machine.
        output (OutputManager | None): Optional output manager for user feedback.

    Returns:
        int: Status code (0=success, 1=not found, 2=manual action for .dmg).
    """
    manager = output or output_manager
    path = Path(installer_path).expanduser()
    path_str = str(path)
    styled_path = manager.stylize(path_str, palette_key="highlight")
    if not path.exists():
        manager.error(
            f"app-hound can't sniff out the installer: {styled_path}",
            emoji="🐶",
            force=True,
        )
        return 1
    manager.highlight(
        f"app-hound is launching installer: {styled_path}",
        emoji="🐶",
    )
    if path.suffix == ".pkg":
        return subprocess.call(["sudo", "installer", "-pkg", str(path), "-target", "/"])
    elif path.suffix == ".dmg":
        manager.info(
            f"app-hound says: Please manually mount the DMG and run the contained app from {styled_path}.",
            emoji="🐶",
            force=True,
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
    home = Path.home()
    home_str = str(home)
    normalized = re.sub(r"[^A-Za-z0-9]+", "", app_name)
    spaced_lower = app_name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", spaced_lower).strip("-")
    compact = normalized.lower() if normalized else spaced_lower.replace(" ", "")

    def unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            cleaned = value.strip()
            if cleaned and cleaned not in seen:
                ordered.append(cleaned)
                seen.add(cleaned)
        return ordered

    name_candidates = unique(
        [
            app_name,
            spaced_lower,
            app_name.replace(" ", ""),
            spaced_lower.replace(" ", ""),
            app_name.replace(" ", "-"),
            spaced_lower.replace(" ", "-"),
            slug.replace("-", ""),
            slug,
            compact,
        ]
    )

    bundle_candidates = unique(
        [
            compact,
            slug.replace("-", "."),
            f"com.{compact}" if compact else "",
        ]
        + [candidate for candidate in name_candidates if candidate.startswith("com.")]
        + [
            f"com.{candidate}"
            for candidate in name_candidates
            if candidate and not candidate.startswith("com.")
        ]
    )

    if not bundle_candidates:
        bundle_candidates = [compact] if compact else name_candidates

    locations: list[str] = []
    seen_paths: set[str] = set()

    def add(path: str) -> None:
        if path and path not in seen_paths:
            locations.append(path)
            seen_paths.add(path)

    for install_target in [
        f"/Applications/{app_name}.app",
        f"/Applications/{app_name}",
        f"/Applications/Utilities/{app_name}.app",
        f"/System/Applications/{app_name}.app",
        f"/System/Applications/Utilities/{app_name}.app",
        f"/Applications/Setapp/{app_name}.app",
        f"{home_str}/Applications/{app_name}.app",
        f"{home_str}/Applications/{app_name}",
        f"/Users/Shared/{app_name}",
    ]:
        add(install_target)

    for candidate in name_candidates:
        add(f"{home_str}/Library/Application Support/{candidate}")
        add(f"/Library/Application Support/{candidate}")
        add(f"{home_str}/Library/Preferences/{candidate}.plist")
        add(f"/Library/Preferences/{candidate}.plist")
        add(f"{home_str}/Library/Logs/{candidate}")
        add(f"/Library/Logs/{candidate}")
        add(f"{home_str}/Library/LaunchAgents/{candidate}.plist")
        add(f"/Library/LaunchAgents/{candidate}.plist")
        add(f"/Library/LaunchDaemons/{candidate}.plist")
        add(f"{home_str}/Library/Caches/{candidate}")
        add(f"/Library/Caches/{candidate}")

    for bundle in bundle_candidates:
        add(f"{home_str}/Library/Preferences/{bundle}.plist")
        add(f"/Library/Preferences/{bundle}.plist")
        add(f"{home_str}/Library/Application Scripts/{bundle}")
        add(f"{home_str}/Library/Containers/{bundle}")
        add(f"{home_str}/Library/Group Containers/{bundle}")
        add(f"{home_str}/Library/Saved Application State/{bundle}.savedState")
        add(f"/Library/Saved Application State/{bundle}.savedState")
        add(f"{home_str}/Library/Application Support/{bundle}")
        add(f"/Library/Application Support/{bundle}")
        add(f"{home_str}/Library/Caches/{bundle}")
        add(f"/Library/Caches/{bundle}")
        add(f"{home_str}/Library/Logs/{bundle}")
        add(f"/Library/Logs/{bundle}")

    return locations


def find_all_matches_in_home(
    app_name: str, *, output: OutputManager | None = None
) -> list[str]:
    """
    Recursively searches the current user's home directory for any file or folder whose
    name contains the app name (case-insensitive).

    Args:
        app_name (str): Name of the app.
        output (OutputManager | None): Optional output manager for user feedback.

    Returns:
        List[str]: List of full paths to matched files/folders.
    """
    manager = output or output_manager
    user_home = Path.home()
    pattern = re.compile(re.escape(app_name), re.IGNORECASE)
    matches: list[str] = []
    with manager.status(f"Sniffing home for '{app_name}' pawprints"):
        for path in user_home.rglob("*"):
            if pattern.search(path.name):
                matches.append(str(path))
    return matches


def gather_app_entries(
    app_name: str,
    additional_locations: list[str] | None = None,
    *,
    output: OutputManager | None = None,
) -> list[tuple[str, str, bool, str]]:
    """
    Searches default macOS and additional locations for top-level folders/files
    whose name contains the app name. Playful 'app-hound' themed console messages.
    Only found paths go into audit data.

    Returns:
        List[Tuple[str, str, bool, str]]: (app_name, base path, is_folder(bool), file/folder name or 'none')
    """
    manager = output or output_manager
    search_paths = find_all_matches_in_home(app_name, output=manager)
    if additional_locations:
        search_paths.extend(additional_locations)
    pattern = re.compile(re.escape(app_name.lower()), re.IGNORECASE)

    entries: list[tuple[str, str, bool, str]] = []
    if additional_locations:
        manager.rule(f"🐶 app-hound sniffs extra spots for '{app_name}'!")
        with manager.progress(
            f"Checking custom burrows for '{app_name}'",
            total=len(additional_locations),
            transient=True,
        ) as task:
            for add_path in additional_locations:
                task.advance(1.0)
                path = Path(add_path).expanduser()
                styled_path = manager.stylize(str(path), palette_key="highlight")
                if path.exists():
                    manager.success(
                        f"app-hound checks custom path: {styled_path}... Bingo! Found!",
                        emoji="🐶",
                    )
                else:
                    manager.warning(
                        f"app-hound checks custom path: {styled_path}... No scent detected!",
                        emoji="🐶",
                    )
    total_reviews = len(search_paths)
    with manager.progress(
        f"Reviewing pawprints for '{app_name}'",
        total=total_reviews if total_reviews > 0 else None,
        transient=True,
    ) as task:
        for raw_path in search_paths:
            task.advance(1.0)
            path = Path(raw_path).expanduser()
            if path.exists():
                top_name = path.name
                if pattern.search(top_name.lower()):
                    path_str = str(path)
                    styled_path = manager.stylize(path_str, palette_key="highlight")
                    if path.is_dir():
                        manager.success(
                            f"app-hound sniffs: {styled_path} (folder exists). Ready to fetch all traces!",
                            emoji="🐶",
                        )
                        entries.append((app_name, path_str, True, "none"))
                    else:
                        manager.info(
                            f"app-hound fetches: {styled_path} (file exists).",
                            emoji="🐶",
                        )
                        entries.append((app_name, path_str, False, top_name))
    return entries


def export_multiple_apps_files(
    apps_config: AppsConfig,
    csv_filepath: str,
    verbose: bool = True,
    *,
    output: OutputManager | None = None,
) -> None:
    """
    Exports all top-level folders and files related to all apps in config to a CSV.
    Args:
        apps_config (List[Dict]): Apps to process.
        csv_filepath (str): Output CSV file path.
        verbose (bool): Print section headers for each app audit.
        output (OutputManager | None): Optional output manager for user feedback.

    Writes columns: App Name, Base Path, Folder, File name
    """
    manager = output or output_manager
    all_entries: list[tuple[str, str, bool, str]] = []
    apps_list = apps_config["apps"]
    iterable = (
        manager.track(
            apps_list,
            "Sniffing every app trail",
            total=len(apps_list) if apps_list else None,
            transient=True,
        )
        if verbose
        else apps_list
    )
    for app in iterable:
        name: str | None = app.get("name")
        additional_locations = app.get("additional_locations", [])
        if verbose:
            manager.rule(f"🐶 app-hound is sniffing for '{name}'!")
        entries = gather_app_entries(
            name,
            additional_locations,
            output=manager,
        )
        all_entries.extend(entries)
    with open(csv_filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["App Name", "Base Path", "Folder", "File name"])
        writer.writerows(all_entries)
    manager.finalize("app-hound says: Audit Complete!")
