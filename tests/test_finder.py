import tempfile
import json
from pathlib import Path
import csv
import pytest

from app_hound.finder import (
    run_installer,
    load_apps_from_json,
    export_multiple_apps_files,
    gather_app_entries,
)


def test_run_installer_not_found(tmp_path):
    # Should return 1 for missing installer
    path = tmp_path / "not_installer.pkg"
    code = run_installer(str(path))
    assert code == 1


def test_run_installer_dmg(tmp_path):
    dmg = tmp_path / "file.dmg"
    dmg.write_text("not really a dmg")
    code = run_installer(str(dmg))
    assert code == 2


def test_app_entries_files_and_dirs(tmp_path):
    # Set up a mock app folder and file in it
    app_dir = tmp_path / "MyApp"
    app_dir.mkdir()
    file1 = app_dir / "file1.txt"
    file1.write_text("hi")
    entries = gather_app_entries("TestApp", [str(app_dir), str(file1)])
    assert (str(app_dir), str(file1)) in entries
    assert any(
        "not found" in entry
        for entry in gather_app_entries("MissingApp", ["/not/exist"])
    )


def test_load_apps_from_json(tmp_path):
    # Create a small mock config in project root
    data = {"apps": [{"name": "Sample", "paths": [str(tmp_path / "file")]}]}
    config = tmp_path / "app_config.json"
    config.write_text(json.dumps(data))
    loaded = load_apps_from_json(str(config))
    assert loaded[0]["name"] == "Sample"
    assert loaded[0]["paths"][0] == str(tmp_path / "file")


def test_export_multiple_apps_files(tmp_path):
    # Setup a config and a small folder to scan
    app_dir = tmp_path / "ScanApp"
    app_dir.mkdir()
    file1 = app_dir / "found.txt"
    file1.write_text("hello")
    config = [{"name": "ScanApp", "paths": [str(app_dir)]}]
    csv_path = tmp_path / "export.csv"
    export_multiple_apps_files(config, str(csv_path), verbose=False)
    # Check contents of the CSV
    with open(csv_path) as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["App Name", "Base Path", "File"]
    assert any("ScanApp" in row for row in rows)


@pytest.mark.parametrize("installer", [".pkg", ".app"])
def test_run_installer_fake(monkeypatch, tmp_path, installer):
    # Simulate subprocess, don't execute anything
    file = tmp_path / f"test{installer}"
    if installer == ".app":
        file.mkdir()
    else:
        file.write_text("dummy")
    monkeypatch.setattr("subprocess.call", lambda args: 0)
    code = run_installer(str(file))
    assert code == 0
