import argparse
import csv
import sys
from contextlib import nullcontext
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
    validate_config_paths,
    write_audit_csv,
)
from app_hound.types import AppConfigEntry, AppsConfig


class DummyManager:
    def __init__(self):
        self.messages: list[str] = []

    def highlight(self, *_args, **_kwargs) -> None:
        return None

    def info(self, *_args, **_kwargs) -> None:
        return None

    def success(self, *_args, **_kwargs) -> None:
        self.messages.append("success")

    def warning(self, *_args, **_kwargs) -> None:
        return None

    def error(self, *_args, **_kwargs) -> None:
        return None

    def stylize(self, message: str, *, palette_key: str | None = None) -> str:
        key = palette_key or "style"
        return f"<{key}>{message}</{key}>"

    def status(self, *_args, **_kwargs):
        return nullcontext()

    def finalize(self, *_args, **_kwargs) -> None:
        self.messages.append("finalize")

    def track(self, iterable, *_args, **_kwargs):
        return iter(iterable)


# --- parse_arguments ---
def test_parse_arguments_required(monkeypatch: MonkeyPatch):
    argv = ["prog", "-i", "/some/path", "-o", "/tmp/out.csv"]
    monkeypatch.setattr(sys, "argv", argv)
    args = parse_arguments()
    assert args.input == "/some/path"
    assert args.output == "/tmp/out.csv"
    assert args.app is None
    assert args.quiet is False
    assert args.no_progress is False
    assert args.accent_color is None


def test_parse_arguments_defaults(monkeypatch: MonkeyPatch):
    # Only input is required, output should default
    argv = ["prog", "-i", "/another/path"]
    monkeypatch.setattr(sys, "argv", argv)
    args = parse_arguments()
    assert args.input == "/another/path"
    assert args.output.endswith("audit.csv")  # Should use default AUDIT_DIR
    assert args.app is None
    assert args.quiet is False
    assert args.no_progress is False
    assert args.info_color is None


def test_parse_arguments_single_app(monkeypatch: MonkeyPatch):
    argv = ["prog", "-a", "SoloApp"]
    monkeypatch.setattr(sys, "argv", argv)
    args = parse_arguments()
    assert args.app == "SoloApp"
    assert args.input == str(Path.cwd())
    assert args.output.endswith("audit.csv")
    assert args.quiet is False
    assert args.no_progress is False


def test_parse_arguments_app_name_alias(monkeypatch: MonkeyPatch):
    argv = ["prog", "--app-name", "AliasApp"]
    monkeypatch.setattr(sys, "argv", argv)
    args = parse_arguments()
    assert args.app == "AliasApp"
    assert args.input == str(Path.cwd())
    assert args.output.endswith("audit.csv")
    assert args.quiet is False
    assert args.no_progress is False


def test_parse_arguments_quiet_and_colors(monkeypatch: MonkeyPatch):
    argv = [
        "prog",
        "--quiet",
        "--no-progress",
        "--accent-color",
        "bold_cyan",
        "--info-color",
        "cyan",
        "--success-color",
        "green",
        "--warning-color",
        "yellow",
        "--error-color",
        "red",
        "--highlight-color",
        "magenta",
        "--muted-color",
        "dim",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    args = parse_arguments()
    assert args.quiet is True
    assert args.no_progress is True
    assert args.accent_color == "bold_cyan"
    assert args.info_color == "cyan"
    assert args.success_color == "green"
    assert args.warning_color == "yellow"
    assert args.error_color == "red"
    assert args.highlight_color == "magenta"
    assert args.muted_color == "dim"


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
    validate_config_paths([conf])
    captured = capsys.readouterr()
    assert captured.out == ""


def test_validate_config_path_missing(tmp_path: Path, capsys: CaptureFixture[str]):
    conf = tmp_path / "missing.json"
    with pytest.raises(SystemExit):
        validate_config_paths([conf])
    captured = capsys.readouterr()
    assert "couldn't find" in captured.out
    assert APP_CONFIG_NAME in captured.out


def test_parse_arguments_multiple_configs(monkeypatch: MonkeyPatch):
    argv = ["prog", "-i", "/path1,/path2"]
    monkeypatch.setattr(sys, "argv", argv)
    args = parse_arguments()
    assert args.input == "/path1,/path2"


def test_validate_config_paths_success(tmp_path: Path):
    conf1 = tmp_path / "apps_config1.json"
    conf2 = tmp_path / "apps_config2.json"
    _ = conf1.write_text("{}")
    _ = conf2.write_text("{}")
    validate_config_paths([conf1, conf2])


def test_validate_config_paths_missing(tmp_path: Path, capsys: CaptureFixture[str]):
    conf1 = tmp_path / "apps_config1.json"
    conf2 = tmp_path / "missing.json"
    _ = conf1.write_text("{}")
    with pytest.raises(SystemExit):
        validate_config_paths([conf1, conf2])
    captured = capsys.readouterr()
    assert "couldn't find" in captured.out
    assert "missing.json" in captured.out


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
        lambda app, output=None: [(app["name"], "p", True, "f")],  # pyright: ignore [reportUnknownLambdaType, reportUnknownArgumentType]
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
    dummy_manager = DummyManager()
    monkeypatch.setattr(
        "app_hound.main.configure_output_manager",
        lambda **kwargs: dummy_manager,
    )
    monkeypatch.setattr(
        "app_hound.main.parse_arguments",
        lambda: argparse.Namespace(
            input=str(tmp_path),
            output=str(tmp_path / "out.csv"),
            app=None,
            quiet=False,
            no_progress=False,
            accent_color=None,
            info_color=None,
            success_color=None,
            warning_color=None,
            error_color=None,
            highlight_color=None,
            muted_color=None,
        ),
    )
    monkeypatch.setattr("app_hound.main.ensure_directories_exist", lambda *paths: paths)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr(
        "app_hound.main.validate_config_paths",
        lambda p, output=None: None,
    )  # pyright: ignore [reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr("app_hound.main.load_apps_from_json", lambda p: {"apps": []})  # pyright: ignore [reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr(
        "app_hound.main.collect_audit_results",
        lambda apps, output=None: [],
    )  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr(
        "app_hound.main.write_audit_csv",
        lambda results, path, output=None: None,
    )  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    main()


def test_main_single_app(monkeypatch: MonkeyPatch, tmp_path: Path):
    capture = {}
    dummy_manager = DummyManager()
    monkeypatch.setattr(
        "app_hound.main.configure_output_manager",
        lambda **kwargs: dummy_manager,
    )
    monkeypatch.setattr(
        "app_hound.main.parse_arguments",
        lambda: argparse.Namespace(
            input=str(tmp_path),
            output=str(tmp_path / "out.csv"),
            app="SoloApp",
            quiet=False,
            no_progress=False,
            accent_color=None,
            info_color=None,
            success_color=None,
            warning_color=None,
            error_color=None,
            highlight_color=None,
            muted_color=None,
        ),
    )
    monkeypatch.setattr(
        "app_hound.main.ensure_directories_exist",
        lambda *paths: None,  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    )
    monkeypatch.setattr(
        "app_hound.main.validate_config_paths",
        lambda *_args, **_kwargs: pytest.fail(
            "validate_config_paths should not be called in single-app mode"
        ),
    )
    monkeypatch.setattr(
        "app_hound.main.load_apps_from_json",
        lambda *_args, **_kwargs: pytest.fail(
            "load_apps_from_json should not be called in single-app mode"
        ),
    )
    monkeypatch.setattr(
        "app_hound.main.collect_audit_results",
        lambda apps, output=None: [("SoloApp", "/fetch/path", True, "none")],  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    )
    monkeypatch.setattr(
        "app_hound.main.write_audit_csv",
        lambda results, path, output=None: capture.update(
            {"results": results, "path": path}
        ),  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    )
    main()
    assert capture["results"][0][0] == "SoloApp"
    assert capture["path"] == tmp_path / "out.csv"
    assert "finalize" in dummy_manager.messages


def test_main_config_missing(monkeypatch: MonkeyPatch, tmp_path: Path):
    # validate_config_paths should exit if config missing
    dummy_manager = DummyManager()
    monkeypatch.setattr(
        "app_hound.main.configure_output_manager",
        lambda **kwargs: dummy_manager,
    )
    monkeypatch.setattr(
        "app_hound.main.parse_arguments",
        lambda: argparse.Namespace(
            input=str(tmp_path),
            output=str(tmp_path / "out.csv"),
            app=None,
            quiet=False,
            no_progress=False,
            accent_color=None,
            info_color=None,
            success_color=None,
            warning_color=None,
            error_color=None,
            highlight_color=None,
            muted_color=None,
        ),
    )
    _ = monkeypatch.setattr(
        "app_hound.main.ensure_directories_exist", lambda *paths: paths
    )  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    _ = monkeypatch.setattr(
        "app_hound.main.validate_config_paths",
        lambda *_args, **_kwargs: sys.exit(1),  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    )
    with pytest.raises(SystemExit):
        main()
