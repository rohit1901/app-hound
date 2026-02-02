import argparse
import csv
import json
import sys
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, cast

import pytest
from _pytest.monkeypatch import MonkeyPatch


class FeedbackProto(Protocol):
    def highlight(self, message: str) -> None: ...
    def info(self, message: str) -> None: ...
    def warning(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...


import app_hound.main as main_module
from app_hound.configuration import (
    AppConfiguration,
    AppsConfiguration,
    ConfigurationError,
)
from app_hound.domain import (
    Artifact,
    ArtifactCategory,
    ArtifactKind,
    ArtifactScope,
    RemovalSafety,
    ScanResult,
)
from app_hound.installer import InstallerStatus
from app_hound.main import (
    DEFAULT_CSV,
    ParsedArgs,
    build_single_app_configuration,
    display_overall_summary,
    emit_scan_summary,
    ensure_directories_exist,
    execute_installers_if_requested,
    load_app_configurations,
    main,
    parse_arguments,
    perform_scans,
    serialise_artifact,
    serialise_scan_result,
    write_csv_report,
    write_json_report,
)
from app_hound.ui import OutputManager


class SpyOutputManager:
    def __init__(self) -> None:
        self.highlight_messages: list[str] = []
        self.info_messages: list[str] = []
        self.success_messages: list[str] = []
        self.warning_messages: list[str] = []
        self.error_messages: list[str] = []
        self.rule_messages: list[str] = []
        self.status_messages: list[str] = []
        self.finalized_message: str | None = None
        self.tracked_invocations: list[dict[str, object]] = []
        self.palette_updates: list[dict[str, str]] = []

    def highlight(self, message: str, **_kwargs: object) -> None:
        self.highlight_messages.append(message)

    def info(self, message: str, **_kwargs: object) -> None:
        self.info_messages.append(message)

    def success(self, message: str, **_kwargs: object) -> None:
        self.success_messages.append(message)

    def warning(self, message: str, **_kwargs: object) -> None:
        self.warning_messages.append(message)

    def error(self, message: str, **_kwargs: object) -> None:
        self.error_messages.append(message)

    def rule(self, title: str, **_kwargs: object) -> None:
        self.rule_messages.append(title)

    def update_palette(self, **styles: str) -> None:
        self.palette_updates.append(styles)

    def stylize(
        self, message: str, *, palette_key: str | None = None, **_kwargs: object
    ) -> str:
        key = palette_key or "style"
        return f"<{key}>{message}</{key}>"

    @contextmanager
    def status(self, message: str) -> Iterator[None]:
        self.status_messages.append(message)
        yield

    def track(
        self,
        iterable: Iterable[object],
        description: str,
        *,
        total: int | None = None,
        transient: bool = False,
    ) -> Iterator[object]:
        items = list(iterable)
        self.tracked_invocations.append(
            {
                "items": items,
                "description": description,
                "total": total,
                "transient": transient,
            }
        )
        for item in items:
            yield item

    def finalize(self, message: str) -> None:
        self.finalized_message = message


def make_namespace(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "input": str(Path.cwd()),
        "output": str(DEFAULT_CSV),
        "json_output": None,
        "plan": None,
        "app": None,
        "additional_locations": [],
        "patterns": [],
        "installation_path": None,
        "deep_home_search": False,
        "run_installers": False,
        "quiet": False,
        "no_progress": False,
        "accent_color": None,
        "info_color": None,
        "success_color": None,
        "warning_color": None,
        "error_color": None,
        "highlight_color": None,
        "muted_color": None,
        "progress_bar_color": None,
        "progress_complete_color": None,
        "progress_description_color": None,
    }
    base.update(overrides)
    if base["additional_locations"] is None:
        base["additional_locations"] = []
    elif isinstance(base["additional_locations"], list):
        base["additional_locations"] = list(base["additional_locations"])
    else:
        base["additional_locations"] = [base["additional_locations"]]
    if base["patterns"] is None:
        base["patterns"] = []
    elif isinstance(base["patterns"], list):
        base["patterns"] = list(base["patterns"])
    else:
        base["patterns"] = [base["patterns"]]
    return argparse.Namespace(**base)


def test_parse_arguments_defaults(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["prog"])
    args = parse_arguments()
    assert args.input == str(Path.cwd())
    assert Path(args.output) == DEFAULT_CSV
    assert Path(args.json_output) == main_module.AUDIT_DIR / "artifacts.json"
    assert Path(args.plan) == main_module.AUDIT_DIR / "plan.json"
    assert args.quiet is False
    assert args.no_progress is False


def test_parse_arguments_with_overrides(monkeypatch: MonkeyPatch) -> None:
    argv = [
        "prog",
        "-i",
        "/configs/apps_config.json",
        "--output",
        "/tmp/out.csv",
        "--json-output",
        "/tmp/out.json",
        "--plan",
        "/tmp/plan.json",
        "-a",
        "SoloApp",
        "--additional-location",
        "~/Library/SoloApp",
        "--pattern",
        "~/Library/**/SoloApp*.plist",
        "--installation-path",
        "~/Downloads/solo.pkg",
        "--deep-home-search",
        "--run-installers",
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
        "--progress-bar-color",
        "blue",
        "--progress-complete-color",
        "white",
        "--progress-description-color",
        "gray",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    args = parse_arguments()
    assert args.input == "/configs/apps_config.json"
    assert args.output == "/tmp/out.csv"
    assert args.json_output == "/tmp/out.json"
    assert args.plan == "/tmp/plan.json"
    assert args.app == "SoloApp"
    assert args.additional_locations == ["~/Library/SoloApp"]
    assert args.patterns == ["~/Library/**/SoloApp*.plist"]
    assert args.installation_path == "~/Downloads/solo.pkg"
    assert args.deep_home_search is True
    assert args.run_installers is True
    assert args.quiet is True
    assert args.no_progress is True
    assert args.accent_color == "bold_cyan"
    assert args.info_color == "cyan"
    assert args.success_color == "green"
    assert args.warning_color == "yellow"
    assert args.error_color == "red"
    assert args.highlight_color == "magenta"
    assert args.muted_color == "dim"
    assert args.progress_bar_color == "blue"
    assert args.progress_complete_color == "white"
    assert args.progress_description_color == "gray"


def test_parsed_args_properties_resolve_paths() -> None:
    ns = make_namespace(
        output="~/audit.csv",
        json_output="~/audit.json",
        plan="~/plan.json",
        accent_color="bold blue",
        success_color="bold green",
        progress_complete_color="green",
    )
    args = ParsedArgs(ns)
    assert args.csv_output_path == Path("~/audit.csv").expanduser()
    assert args.json_output_path == Path("~/audit.json").expanduser()
    assert args.plan_output_path == Path("~/plan.json").expanduser()
    palette = args.palette_overrides
    assert palette["accent"] == "bold blue"
    assert palette["success"] == "bold green"
    assert palette["progress_complete"] == "green"
    assert "info" not in palette


def test_ensure_directories_exist_creates_directories(tmp_path: Path) -> None:
    first = tmp_path / "nested" / "dir"
    second = tmp_path / "another"
    ensure_directories_exist(first, second)
    assert first.exists()
    assert second.exists()


def test_build_single_app_configuration_constructs_expected_values(
    tmp_path: Path,
) -> None:
    ns = make_namespace(
        app="SoloApp",
        additional_locations=[str(tmp_path / "Custom")],
        patterns=["~/Library/**/SoloApp*"],
        installation_path=str(tmp_path / "installer.pkg"),
        deep_home_search=True,
    )
    args = ParsedArgs(ns)
    config = build_single_app_configuration(args)
    assert config.name == "SoloApp"
    assert config.additional_locations == (Path(tmp_path / "Custom"),)
    assert config.patterns == ("~/Library/**/SoloApp*",)
    assert config.installation_path == Path(tmp_path / "installer.pkg")
    assert config.deep_home_search is True


def test_load_app_configurations_single_app_mode(tmp_path: Path) -> None:
    ns = make_namespace(
        app="SoloApp",
        additional_locations=[str(tmp_path / "Extra")],
        patterns=["~/Library/**"],
        installation_path=str(tmp_path / "installer.pkg"),
        deep_home_search=True,
    )
    args = ParsedArgs(ns)
    manager = SpyOutputManager()
    config = load_app_configurations(args, cast(OutputManager, cast(object, manager)))
    assert isinstance(config, AppsConfiguration)
    assert len(config.apps) == 1
    app_config = config.apps[0]
    assert app_config.name == "SoloApp"
    assert app_config.additional_locations == (Path(tmp_path / "Extra"),)
    assert app_config.patterns == ("~/Library/**",)
    assert app_config.installation_path == Path(tmp_path / "installer.pkg")
    assert app_config.deep_home_search is True


def test_load_app_configurations_from_directory(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "apps_config.json"
    (config_dir / "relative").mkdir()
    payload = {
        "apps": [
            {
                "name": "FooApp",
                "additional_locations": ["relative"],
                "deep_home_search": True,
            }
        ]
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    ns = make_namespace(input=str(config_dir))
    args = ParsedArgs(ns)
    manager = SpyOutputManager()
    apps_config = load_app_configurations(
        args, cast(OutputManager, cast(object, manager))
    )
    assert len(apps_config.apps) == 1
    entry = apps_config.apps[0]
    assert entry.name == "FooApp"
    assert entry.additional_locations == (config_dir / "relative",)
    assert entry.deep_home_search is True


def test_load_app_configurations_missing_raises(tmp_path: Path) -> None:
    ns = make_namespace(input=str(tmp_path / "missing_dir"))
    args = ParsedArgs(ns)
    manager = SpyOutputManager()
    with pytest.raises(ConfigurationError):
        load_app_configurations(args, cast(OutputManager, cast(object, manager)))


def test_execute_installers_if_requested_runs_when_enabled(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    class FakeInstallerRunner:
        calls: list[dict[str, object]] = []

        def __init__(self, *_, **__) -> None:
            pass

        def run(self, path: Path, *, feedback: FeedbackProto | None = None):
            if feedback is not None and hasattr(feedback, "highlight"):
                feedback.highlight(f"Running installer at {path}")
            self.calls.append({"path": Path(path), "feedback": feedback})
            return SimpleNamespace(
                status=InstallerStatus.SUCCESS,
                path=Path(path),
                exit_code=0,
                message="installed",
            )

    FakeInstallerRunner.calls = []
    monkeypatch.setattr(main_module, "InstallerRunner", FakeInstallerRunner)

    apps = (
        AppConfiguration(name="NoInstaller"),
        AppConfiguration(
            name="WithInstaller", installation_path=tmp_path / "installer.pkg"
        ),
    )
    manager = SpyOutputManager()
    execute_installers_if_requested(
        apps, manager=cast(OutputManager, cast(object, manager)), run_installers=True
    )
    assert len(FakeInstallerRunner.calls) == 1
    assert FakeInstallerRunner.calls[0]["path"] == tmp_path / "installer.pkg"
    assert manager.highlight_messages  # feedback should add a highlight


def test_execute_installers_if_requested_skips_when_disabled(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    class FakeInstallerRunner:
        calls: list[Path] = []

        def __init__(self, *_, **__) -> None:
            pass

        def run(self, path: Path, *, feedback: FeedbackProto | None = None):
            self.calls.append(Path(path))
            return SimpleNamespace(
                status=InstallerStatus.SUCCESS,
                path=Path(path),
                exit_code=0,
                message="installed",
            )

    FakeInstallerRunner.calls = []
    monkeypatch.setattr(main_module, "InstallerRunner", FakeInstallerRunner)

    apps = (AppConfiguration(name="App", installation_path=tmp_path / "installer.pkg"),)
    manager = SpyOutputManager()
    execute_installers_if_requested(
        apps, manager=cast(OutputManager, cast(object, manager)), run_installers=False
    )
    assert FakeInstallerRunner.calls == []


def test_perform_scans_uses_scanner(monkeypatch: MonkeyPatch) -> None:
    class FakeScanner:
        instances: list["FakeScanner"] = []
        scanned: list[str] = []

        def __init__(
            self,
            _filesystem: object | None = None,
            *,
            deep_home_search_default: bool = False,
        ) -> None:
            self.deep_home_search_default: bool = deep_home_search_default
            FakeScanner.instances.append(self)

        def scan(self, configuration: AppConfiguration) -> ScanResult:
            FakeScanner.scanned.append(configuration.name)
            artifact = Artifact(
                app_name=configuration.name,
                path=Path(f"/tmp/{configuration.name}"),
                kind=ArtifactKind.FILE,
                scope=ArtifactScope.CONFIGURED,
                category=ArtifactCategory.SUPPORT,
                removal_safety=RemovalSafety.SAFE,
            )
            return ScanResult(app_name=configuration.name, artifacts=(artifact,))

    FakeScanner.instances = []
    FakeScanner.scanned = []
    monkeypatch.setattr(main_module, "Scanner", FakeScanner)

    apps_configuration = AppsConfiguration(
        apps=(
            AppConfiguration(name="FooApp"),
            AppConfiguration(name="BarApp"),
        )
    )
    manager = SpyOutputManager()
    results = perform_scans(
        apps_configuration,
        manager=cast(OutputManager, cast(object, manager)),
        deep_home_search_default=True,
    )
    assert len(FakeScanner.instances) == 1
    assert FakeScanner.instances[0].deep_home_search_default is True
    assert FakeScanner.scanned == ["FooApp", "BarApp"]
    assert [result.app_name for result in results] == ["FooApp", "BarApp"]
    assert len(manager.rule_messages) == 2
    assert len(manager.info_messages) == 2  # summaries emitted


def test_write_csv_report_writes_expected_rows(tmp_path: Path) -> None:
    output_path = tmp_path / "audit.csv"
    artifact = Artifact(
        app_name="TestApp",
        path=Path("/tmp/test"),
        kind=ArtifactKind.FILE,
        scope=ArtifactScope.CONFIGURED,
        category=ArtifactCategory.SUPPORT,
        removal_safety=RemovalSafety.SAFE,
        exists=True,
        writable=True,
        size_bytes=1200,
        last_modified=datetime(2024, 1, 1, tzinfo=timezone.utc),
        notes=("note",),
        removal_instructions=("remove",),
    )
    result = ScanResult(app_name="TestApp", artifacts=(artifact,))
    manager = SpyOutputManager()
    write_csv_report([result], output_path, cast(OutputManager, cast(object, manager)))
    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == [
        "App Name",
        "Artifact Path",
        "Kind",
        "Scope",
        "Category",
        "Exists",
        "Writable",
        "Size (bytes)",
        "Last Modified",
        "Removal Safety",
        "Notes",
        "Removal Instructions",
    ]
    assert rows[1][0] == "TestApp"
    assert rows[1][1] == "/tmp/test"
    assert rows[1][2] == ArtifactKind.FILE.value
    assert rows[1][9] == RemovalSafety.SAFE.value
    assert "note" in rows[1][10]
    assert "remove" in rows[1][11]
    assert manager.success_messages
    assert str(output_path) in manager.success_messages[0]


def test_write_json_report_writes_expected_payload(tmp_path: Path) -> None:
    output_path = tmp_path / "audit.json"
    artifact = Artifact(
        app_name="TestApp",
        path=Path("/tmp/test"),
        kind=ArtifactKind.DIRECTORY,
        scope=ArtifactScope.DEFAULT,
        category=ArtifactCategory.CACHE,
        removal_safety=RemovalSafety.CAUTION,
        exists=False,
    )
    result = ScanResult(app_name="TestApp", artifacts=(artifact,))
    manager = SpyOutputManager()
    write_json_report(
        [result],
        output_path,
        manager=cast(OutputManager, cast(object, manager)),
        label="artifact report",
    )
    data = cast(
        list[dict[str, object]], json.loads(output_path.read_text(encoding="utf-8"))
    )
    assert isinstance(data, list)
    assert data[0]["app_name"] == "TestApp"
    assert data[0]["errors"] == []
    assert manager.success_messages
    assert "artifact report" in manager.success_messages[0]


def test_serialise_artifact_contains_expected_fields() -> None:
    artifact = Artifact(
        app_name="TestApp",
        path=Path("/tmp/test"),
        kind=ArtifactKind.SYMLINK,
        scope=ArtifactScope.SYSTEM,
        category=ArtifactCategory.OTHER,
        removal_safety=RemovalSafety.REVIEW,
        exists=True,
        writable=False,
        size_bytes=42,
        last_modified=datetime(2023, 5, 1, 12, 30, tzinfo=timezone.utc),
        notes=("alpha", "beta"),
        removal_instructions=("gamma",),
    )
    payload = serialise_artifact(artifact)
    assert payload["app_name"] == "TestApp"
    assert payload["path"] == "/tmp/test"
    assert payload["kind"] == ArtifactKind.SYMLINK.value
    assert payload["scope"] == ArtifactScope.SYSTEM.value
    assert payload["category"] == ArtifactCategory.OTHER.value
    assert payload["removal_safety"] == RemovalSafety.REVIEW.value
    assert payload["writable"] is False
    assert payload["size_bytes"] == 42
    assert payload["last_modified"] == "2023-05-01T12:30:00+00:00"
    assert payload["notes"] == ["alpha", "beta"]
    assert payload["removal_instructions"] == ["gamma"]


def test_serialise_scan_result_includes_artifacts() -> None:
    artifact = Artifact(
        app_name="TestApp",
        path=Path("/tmp/test"),
        kind=ArtifactKind.FILE,
        scope=ArtifactScope.CONFIGURED,
        category=ArtifactCategory.SUPPORT,
        removal_safety=RemovalSafety.SAFE,
    )
    generated = datetime(2024, 2, 2, 2, 2, tzinfo=timezone.utc)
    result = ScanResult(
        app_name="TestApp",
        artifacts=(artifact,),
        generated_at=generated,
        errors=("warning",),
    )
    payload = cast(dict[str, object], serialise_scan_result(result))
    assert payload["app_name"] == "TestApp"
    assert payload["generated_at"] == "2024-02-02T02:02:00+00:00"
    assert payload["errors"] == ["warning"]
    artifacts = cast(list[dict[str, object]], payload["artifacts"])
    assert artifacts[0]["path"] == "/tmp/test"


def test_emit_scan_summary_records_messages() -> None:
    manager = SpyOutputManager()
    artifact_present = Artifact(
        app_name="TestApp",
        path=Path("/tmp/present"),
        kind=ArtifactKind.FILE,
        scope=ArtifactScope.DEFAULT,
        category=ArtifactCategory.SUPPORT,
        removal_safety=RemovalSafety.SAFE,
        exists=True,
    )
    artifact_missing = Artifact(
        app_name="TestApp",
        path=Path("/tmp/missing"),
        kind=ArtifactKind.FILE,
        scope=ArtifactScope.CONFIGURED,
        category=ArtifactCategory.CACHE,
        removal_safety=RemovalSafety.CAUTION,
        exists=False,
    )
    result = ScanResult(
        app_name="TestApp",
        artifacts=(artifact_present, artifact_missing),
        errors=("Metadata unavailable",),
    )
    emit_scan_summary("TestApp", result, cast(OutputManager, cast(object, manager)))
    assert manager.info_messages
    assert "TestApp" in manager.info_messages[0]
    assert "1/2" in manager.info_messages[0]
    assert manager.warning_messages == ["TestApp — Metadata unavailable"]


def test_display_overall_summary_no_results() -> None:
    manager = SpyOutputManager()
    display_overall_summary([], cast(OutputManager, cast(object, manager)))
    assert manager.info_messages == ["No artifacts were discovered."]


def test_display_overall_summary_with_results() -> None:
    artifact = Artifact(
        app_name="AppOne",
        path=Path("/tmp/one"),
        kind=ArtifactKind.FILE,
        scope=ArtifactScope.DEFAULT,
        category=ArtifactCategory.SUPPORT,
        removal_safety=RemovalSafety.SAFE,
    )
    result1 = ScanResult(app_name="AppOne", artifacts=(artifact,))
    result2 = ScanResult(app_name="AppTwo", artifacts=(artifact,))
    manager = SpyOutputManager()
    display_overall_summary(
        [result1, result2], cast(OutputManager, cast(object, manager))
    )
    assert manager.highlight_messages
    assert "Summary:" in manager.highlight_messages[0]
    assert "flagged safe or caution" in manager.highlight_messages[0]


def test_main_success_flow(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    manager = SpyOutputManager()

    def fake_output_manager(*, quiet: bool, show_progress: bool) -> SpyOutputManager:
        assert isinstance(quiet, bool)
        assert isinstance(show_progress, bool)
        return manager

    monkeypatch.setattr(main_module, "OutputManager", fake_output_manager)

    args_namespace = make_namespace(
        input=str(tmp_path / "configs"),
        output=str(tmp_path / "audit.csv"),
        app=None,
        json_output=str(main_module.AUDIT_DIR / "artifacts.json"),
        plan=str(main_module.AUDIT_DIR / "plan.json"),
        run_installers=False,
        quiet=False,
        no_progress=False,
        deep_home_search=False,
        plan_script=str(main_module.AUDIT_DIR / "delete.sh"),
    )
    monkeypatch.setattr(main_module, "parse_arguments", lambda: args_namespace)

    captured: dict[str, object] = {}

    def fake_load_app_configurations(
        args: ParsedArgs, manager_arg: SpyOutputManager
    ) -> AppsConfiguration:
        assert manager_arg is manager
        captured["loaded_args"] = args
        return AppsConfiguration(apps=(AppConfiguration(name="FooApp"),))

    monkeypatch.setattr(
        main_module, "load_app_configurations", fake_load_app_configurations
    )

    def fake_execute_installers(*_args, **_kwargs) -> None:
        captured["installers_invoked"] = True

    monkeypatch.setattr(
        main_module, "execute_installers_if_requested", fake_execute_installers
    )

    scan_result = ScanResult(app_name="FooApp", artifacts=())
    monkeypatch.setattr(
        main_module,
        "perform_scans",
        lambda *_args, **_kwargs: [scan_result],
    )

    def fake_write_csv(results, path, manager_arg):
        captured["csv_results"] = list(results)
        captured["csv_path"] = path
        assert manager_arg is manager

    monkeypatch.setattr(main_module, "write_csv_report", fake_write_csv)

    def fake_write_json(*_args, **_kwargs):
        captured["json_written"] = True

    monkeypatch.setattr(main_module, "write_json_report", fake_write_json)

    def fake_display_summary(results, manager_arg):
        captured["summary_results"] = list(results)
        assert manager_arg is manager

    monkeypatch.setattr(main_module, "display_overall_summary", fake_display_summary)

    directories_recorded: list[tuple[Path, ...]] = []

    def fake_ensure_dirs(*paths: Path) -> None:
        directories_recorded.append(tuple(paths))

    monkeypatch.setattr(main_module, "ensure_directories_exist", fake_ensure_dirs)

    main()

    assert captured["csv_results"] == [scan_result]
    assert captured["csv_path"] == Path(args_namespace.output)
    assert captured["summary_results"] == [scan_result]
    assert captured.get("json_written") is True
    assert directories_recorded
    assert manager.highlight_messages[0] == "app-hound is on the trail!"
    assert manager.status_messages[0].startswith("Compiling reports")
    assert manager.finalized_message == "app-hound says: Fetch complete! 🦴"


def test_main_handles_configuration_error(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    manager = SpyOutputManager()

    def fake_output_manager(*, quiet: bool, show_progress: bool) -> SpyOutputManager:
        return manager

    monkeypatch.setattr(main_module, "OutputManager", fake_output_manager)

    args_namespace = make_namespace(
        input=str(tmp_path / "configs"),
        output=str(tmp_path / "audit.csv"),
        app=None,
        json_output=str(tmp_path / "artifacts.json"),
        plan=str(tmp_path / "plan.json"),
        run_installers=False,
        quiet=False,
        no_progress=False,
        deep_home_search=False,
        plan_script=str(tmp_path / "delete.sh"),
    )
    monkeypatch.setattr(main_module, "parse_arguments", lambda: args_namespace)

    monkeypatch.setattr(
        main_module,
        "ensure_directories_exist",
        lambda *paths: None,
    )

    def failing_load(*_args, **_kwargs):
        raise ConfigurationError("boom")

    monkeypatch.setattr(main_module, "load_app_configurations", failing_load)

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    assert "boom" in manager.error_messages[0]
    assert manager.finalized_message is None
