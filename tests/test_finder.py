import tempfile
import json
import os
from pathlib import Path
import pytest

from app_hound.finder import (
    run_installer,
    load_apps_from_json,
    get_default_locations,
    gather_app_entries,
    export_multiple_apps_files,
)


@pytest.mark.parametrize(
    "installer_suffix, expected",
    [
        (".pkg", 1),  # Simulate not found
        (".dmg", 1),
        (".app", 1),
    ],
)
def test_run_installer_not_found(tmp_path, installer_suffix, expected):
    fake_installer = tmp_path / f"missing{installer_suffix}"
    code = run_installer(str(fake_installer))
    assert code == expected


def test_run_installer_dmg(tmp_path):
    f = tmp_path / "foo.dmg"
    f.write_text("dummy")
    code = run_installer(str(f))
    assert code == 2


def test_run_installer_app(monkeypatch, tmp_path):
    app_dir = tmp_path / "TestApp.app"
    app_dir.mkdir()
    monkeypatch.setattr("subprocess.call", lambda args: 0)
    assert run_installer(str(app_dir)) == 0


def test_run_installer_pkg(monkeypatch, tmp_path):
    pkg = tmp_path / "foo.pkg"
    pkg.write_text("hi")
    monkeypatch.setattr("subprocess.call", lambda args: 0)
    assert run_installer(str(pkg)) == 0


def test_load_apps_from_json(tmp_path):
    config_path = tmp_path / "apps_config.json"
    data = {
        "apps": [{"name": "Foo", "additional_locations": [str(tmp_path / "extra")]}]
    }
    config_path.write_text(json.dumps(data))
    result = load_apps_from_json(str(config_path))
    assert isinstance(result, list)
    assert result[0]["name"] == "Foo"


def test_get_default_locations():
    locs = get_default_locations("FakeApp")
    assert any("FakeApp" in loc for loc in locs)
    assert any(loc.startswith(str(Path.home())) for loc in locs)


def test_gather_app_entries_top_level_dir(tmp_path, capsys):
    dir1 = tmp_path / "TestApp"
    dir1.mkdir()
    entries = gather_app_entries("TestApp", [str(dir1)])
    # Only the directory should show up, not its contents
    assert any(e[1] == str(dir1) and e[2] is True for e in entries)
    captured = capsys.readouterr()
    assert "app-hound sniffs" in captured.out
    assert not any("not found" in e for e in captured.out.splitlines())


def test_gather_app_entries_top_level_file(tmp_path, capsys):
    myfile = tmp_path / "TestApp.plist"
    myfile.write_text("data")
    entries = gather_app_entries("TestApp", [str(myfile)])
    assert any(e[1] == str(myfile) and e[2] is False for e in entries)
    captured = capsys.readouterr()
    assert "app-hound fetches" in captured.out


def test_gather_app_entries_case_insensitive(tmp_path):
    # Try mixed case app name
    topdir = tmp_path / "TestApp"
    topdir.mkdir()
    entries = gather_app_entries("testapp", [str(topdir)])
    assert any(e[1] == str(topdir) for e in entries)


def test_gather_app_entries_additional_console(tmp_path, capsys):
    extra = tmp_path / "ExtraLocation"
    entries = gather_app_entries("ExtraLocation", [str(extra)])
    captured = capsys.readouterr()
    assert (
        "app-hound checks custom path" in captured.out
    )  # CHANGED (was 'additional path')
    assert "No scent detected!" in captured.out
    extra.mkdir()
    entries = gather_app_entries("ExtraLocation", [str(extra)])
    captured = capsys.readouterr()
    assert "Bingo! Found!" in captured.out


def test_export_multiple_apps_files_csv_structure(tmp_path):
    app1dir = tmp_path / "A1"
    app1dir.mkdir()
    app2file = tmp_path / "B2.app"
    app2file.write_text("dummy")
    config = [
        {"name": "A1", "additional_locations": [str(app1dir)]},
        {"name": "B2", "additional_locations": [str(app2file)]},
    ]
    outcsv = tmp_path / "final.csv"
    export_multiple_apps_files(config, str(outcsv), verbose=False)
    lines = outcsv.read_text().splitlines()
    header = lines[0].split(",")
    assert header == ["App Name", "Base Path", "Folder", "File name"]
    datalines = [line.split(",") for line in lines[1:]]
    # Should find the top-level folder named "A1"
    assert any(
        dl[0] == "A1" and dl[1] == str(app1dir) and dl[2] == "True" and dl[3] == "none"
        for dl in datalines
    )
    # Should find the top-level file named "B2.app"
    assert any(
        dl[0] == "B2"
        and dl[1] == str(app2file)
        and dl[2] == "False"
        and dl[3] == "B2.app"
        for dl in datalines
    )


def test_find_all_matches_in_home(tmp_path, monkeypatch):
    # Mock user's home dir structure
    app_name = "TestApp"
    # Create mock home layout:
    # - /tmp/fakehome/TestApp/abc.txt
    # - /tmp/fakehome/Work/TestAppFile.pdf
    # - /tmp/fakehome/Stuff/Other.txt
    home = tmp_path / "fakehome"
    home.mkdir()
    (home / "TestApp").mkdir()
    (home / "TestApp" / "abc.txt").write_text("data")
    (home / "Work").mkdir()
    (home / "Work" / "TestAppFile.pdf").write_text("pdfdata")
    (home / "Stuff").mkdir()
    (home / "Stuff" / "Other.txt").write_text("irrelevant")
    # Patch Path.home() to return our fake home
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    # Import or define your function (as previously suggested)
    from app_hound.finder import find_all_matches_in_home

    matches = find_all_matches_in_home(app_name)
    # Should find /TestApp (folder) and /Work/TestAppFile.pdf (file)
    found_names = [Path(m).name for m in matches]
    assert "TestApp" in found_names
    assert "TestAppFile.pdf" in found_names
    assert "Other.txt" not in found_names
