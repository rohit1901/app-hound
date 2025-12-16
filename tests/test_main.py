import argparse
import csv
import sys
from pathlib import Path

import pytest
from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from app_hound.main import (
    APP_CONFIG_NAME,
    collect_audit_results,
    ensure_directories_exist,
    main,
    parse_arguments,
    process_app_entries,
    validate_config_path,
    write_audit_csv,
)
from app_hound.types import AppConfigEntry, AppsConfig


# --- parse_arguments ---
def test_parse_arguments_required(monkeypatch: MonkeyPatch):
    argv = ["prog", "-i", "/some/path", "-o", "/tmp/out.csv"]
    monkeypatch.setattr(sys, "argv", argv)
    args = parse_arguments()
    assert args.input == "/some/path"
    assert args.output == "/tmp/out.csv"
    assert args.app_name is None


def test_parse_arguments_defaults(monkeypatch: MonkeyPatch):
    # Only input is required, output should default
    argv = ["prog", "-i", "/another/path"]
    monkeypatch.setattr(sys, "argv", argv)
    args = parse_arguments()
    assert args.input == "/another/path"
    assert args.output.endswith("audit.csv")  # Should use default AUDIT_DIR
    assert args.app_name is None


def test_parse_arguments_single_app(monkeypatch: MonkeyPatch):
    argv = ["prog", "-a", "SoloApp"]
    monkeypatch.setattr(sys, "argv", argv)
    args = parse_arguments()
    assert args.app_name == "SoloApp"
    assert args.input == str(Path.cwd())
    assert args.output.endswith("audit.csv")


# --- ensure_directories_exist ---
def test_ensure_directories_exist(tmp_path: Path):
    new_dir = tmp_path / "sub" / "dir"
    assert not new_dir.exists()
    ensure_directories_exist(new_dir)
    assert new_dir.exists()
    another_dir = tmp_path / "second" / "dir"
    assert not another_dir.exists()
    ensure_directories_exist(new_dir, another_dir)
    assert another_dir.exists()


# --- validate_config_path ---
def test_validate_config_path_exists(tmp_path: Path, capsys: CaptureFixture[str]):
    conf = tmp_path / "apps_config.json"
    _ = conf.write_text("{}")
    # Should not raise since file exists
    validate_config_path(conf)
    captured = capsys.readouterr()
    assert captured.out == ""


def test_validate_config_path_missing(tmp_path: Path, capsys: CaptureFixture[str]):
    conf = tmp_path / "missing.json"
    with pytest.raises(SystemExit):
        validate_config_path(conf)
    captured = capsys.readouterr()
    assert "couldn't find" in captured.out
    assert APP_CONFIG_NAME in captured.out


@pytest.mark.skip(reason="Test is deprecated")
def test_process_app_entries_calls_installer(monkeypatch: MonkeyPatch):
    called = {"run": False}
    dummy_app: AppConfigEntry = {
        "name": "FooApp",
        "additional_locations": ["/my/path"],
        "installation_path": "/dummy/installer",
    }
    _ = monkeypatch.setattr(
        "app_hound.finder.run_installer",
        lambda path: called.update({"run": True}),  # pyright: ignore [reportUnknownLambdaType, reportUnknownArgumentType]
    )
    _ = monkeypatch.setattr(
        "app_hound.finder.gather_app_entries",
        lambda n, l: [("n", "p", True, "f")],  # pyright: ignore [reportUnknownLambdaType, reportUnknownArgumentType]
    )
    result = process_app_entries(dummy_app)
    assert called["run"]
    assert result == [("n", "p", True, "f")]


@pytest.mark.skip(reason="Test is deprecated")
def test_process_app_entries_skips_installer(monkeypatch: MonkeyPatch):
    dummy_app: AppConfigEntry = {
        "name": "BarApp",
        "additional_locations": ["/none/path"],
        "installation_path": "/dummy/installer",
    }
    monkeypatch.setattr("app_hound.finder.run_installer", lambda path: None)  # pyright: ignore [reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr(
        "app_hound.finder.gather_app_entries",
        lambda n, loc: [("n", "p", False, "f")],  # pyright: ignore [reportUnknownLambdaType, reportUnknownArgumentType]
    )
    result = process_app_entries(dummy_app)
    assert result == [("n", "p", False, "f")]


def test_collect_audit_results(monkeypatch: MonkeyPatch):
    sample_apps: AppsConfig = {
        "apps": [
            {"name": "A", "additional_locations": []},
            {"name": "B", "additional_locations": []},
        ]
    }
    monkeypatch.setattr(
        "app_hound.main.process_app_entries",
        lambda app: [(app["name"], "p", True, "f")],  # pyright: ignore [reportUnknownLambdaType, reportUnknownArgumentType]
    )
    results = collect_audit_results(sample_apps)
    assert ("A", "p", True, "f") in results
    assert ("B", "p", True, "f") in results


# --- write_audit_csv ---
def test_write_audit_csv(tmp_path: Path, capsys: CaptureFixture[str]):
    output_csv = tmp_path / "foo.csv"
    results = [
        ("App1", "/base1", True, "file1"),
        ("App2", "/base2", False, "file2"),
    ]
    write_audit_csv(results, output_csv)
    out = capsys.readouterr()
    assert "Audit report saved" in out.out
    with open(output_csv, newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["App Name", "Base Path", "Folder", "File name"]
    assert rows[1][0] == "App1"
    assert rows[2][0] == "App2"


# --- main ---
def test_main_success(monkeypatch: MonkeyPatch, tmp_path: Path):
    f = tmp_path / "apps_config.json"
    _ = f.write_text('{"apps": []}')
    # Patch all used functions and vars
    monkeypatch.setattr(
        "app_hound.main.parse_arguments",
        lambda: argparse.Namespace(
            input=str(tmp_path), output=str(tmp_path / "out.csv"), app_name=None
        ),
    )
    monkeypatch.setattr("app_hound.main.ensure_directories_exist", lambda *paths: paths)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr("app_hound.main.validate_config_path", lambda p: None)  # pyright: ignore [reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr("app_hound.main.load_apps_from_json", lambda p: {"apps": []})  # pyright: ignore [reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr("app_hound.main.collect_audit_results", lambda apps: [])  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr("app_hound.main.write_audit_csv", lambda results, path: None)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    main()  # Should cover all working branches without error


def test_main_single_app(monkeypatch: MonkeyPatch, tmp_path: Path):
    capture = {}
    monkeypatch.setattr(
        "app_hound.main.parse_arguments",
        lambda: argparse.Namespace(
            input=str(tmp_path),
            output=str(tmp_path / "out.csv"),
            app_name="SoloApp",
        ),
    )
    monkeypatch.setattr(
        "app_hound.main.ensure_directories_exist",
        lambda *paths: None,  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    )
    monkeypatch.setattr(
        "app_hound.main.validate_config_path",
        lambda _: pytest.fail(
            "validate_config_path should not be called in single-app mode"
        ),
    )
    monkeypatch.setattr(
        "app_hound.main.load_apps_from_json",
        lambda _: pytest.fail(
            "load_apps_from_json should not be called in single-app mode"
        ),
    )
    monkeypatch.setattr(
        "app_hound.main.collect_audit_results",
        lambda apps: [("SoloApp", "/fetch/path", True, "none")],  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    )
    monkeypatch.setattr(
        "app_hound.main.write_audit_csv",
        lambda results, path: capture.update({"results": results, "path": path}),  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    )
    main()
    assert capture["results"][0][0] == "SoloApp"
    assert capture["path"] == tmp_path / "out.csv"


def test_main_config_missing(monkeypatch: MonkeyPatch, tmp_path: Path):
    # validate_config_path should exit if config missing
    monkeypatch.setattr(
        "app_hound.main.parse_arguments",
        lambda: argparse.Namespace(
            input=str(tmp_path), output=str(tmp_path / "out.csv"), app_name=None
        ),
    )
    _ = monkeypatch.setattr(
        "app_hound.main.ensure_directories_exist", lambda *paths: paths
    )  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    _ = monkeypatch.setattr(
        "app_hound.main.validate_config_path",
        lambda p: sys.exit(1),  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    )
    with pytest.raises(SystemExit):
        main()
