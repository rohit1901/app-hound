"""Tests for interactive mode module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from rich.console import Console

from app_hound.domain import (
    Artifact,
    ArtifactCategory,
    ArtifactKind,
    ArtifactScope,
    RemovalSafety,
    ScanResult,
)
from app_hound.interactive import (
    ConsoleAdapter,
    InteractiveSession,
    run_interactive_mode,
)
from app_hound.removal import PlanEntry, RemovalReport


class TestConsoleAdapter:
    """Tests for ConsoleAdapter class."""

    def test_console_adapter_creation(self) -> None:
        console = Console()
        adapter = ConsoleAdapter(console)
        assert adapter._console is console

    def test_console_adapter_info(self) -> None:
        console = Mock(spec=Console)
        adapter = ConsoleAdapter(console)

        adapter.info("test message")
        console.print.assert_called_once()

    def test_console_adapter_success(self) -> None:
        console = Mock(spec=Console)
        adapter = ConsoleAdapter(console)

        adapter.success("test message")
        console.print.assert_called_once()

    def test_console_adapter_warning(self) -> None:
        console = Mock(spec=Console)
        adapter = ConsoleAdapter(console)

        adapter.warning("test message")
        console.print.assert_called_once()

    def test_console_adapter_error(self) -> None:
        console = Mock(spec=Console)
        adapter = ConsoleAdapter(console)

        adapter.error("test message")
        console.print.assert_called_once()

    def test_console_adapter_highlight(self) -> None:
        console = Mock(spec=Console)
        adapter = ConsoleAdapter(console)

        adapter.highlight("test message")
        console.print.assert_called_once()


class TestInteractiveSession:
    """Tests for InteractiveSession class."""

    def create_test_results(self) -> list[ScanResult]:
        """Create test scan results."""
        artifacts = (
            Artifact(
                app_name="TestApp",
                path=Path("/test/cache"),
                kind=ArtifactKind.FILE,
                scope=ArtifactScope.DEFAULT,
                category=ArtifactCategory.CACHE,
                removal_safety=RemovalSafety.SAFE,
                exists=True,
                size_bytes=1024,
            ),
            Artifact(
                app_name="TestApp",
                path=Path("/test/prefs"),
                kind=ArtifactKind.FILE,
                scope=ArtifactScope.DEFAULT,
                category=ArtifactCategory.PREFERENCES,
                removal_safety=RemovalSafety.CAUTION,
                exists=True,
                size_bytes=512,
            ),
            Artifact(
                app_name="TestApp",
                path=Path("/test/data"),
                kind=ArtifactKind.DIRECTORY,
                scope=ArtifactScope.CONFIGURED,
                category=ArtifactCategory.SUPPORT,
                removal_safety=RemovalSafety.REVIEW,
                exists=True,
            ),
        )

        return [ScanResult(app_name="TestApp", artifacts=artifacts)]

    def test_session_creation(self) -> None:
        results = self.create_test_results()
        console = Mock(spec=Console)

        session = InteractiveSession(results, console)

        assert session.results == results
        assert session.console is console
        assert len(session.selected_indices) == 0
        assert len(session._artifacts_list) == 3

    def test_session_creation_default_console(self) -> None:
        results = self.create_test_results()

        session = InteractiveSession(results)

        assert isinstance(session.console, Console)

    def test_build_artifacts_list(self) -> None:
        results = self.create_test_results()
        console = Mock(spec=Console)

        session = InteractiveSession(results, console)

        assert len(session._artifacts_list) == 3
        assert all(
            isinstance(item, tuple) and len(item) == 2
            for item in session._artifacts_list
        )

    def test_parse_selection_single_index(self) -> None:
        results = self.create_test_results()
        console = Mock(spec=Console)
        session = InteractiveSession(results, console)

        indices = session._parse_selection("0")

        assert indices == {0}

    def test_parse_selection_multiple_indices(self) -> None:
        results = self.create_test_results()
        console = Mock(spec=Console)
        session = InteractiveSession(results, console)

        indices = session._parse_selection("0, 1, 2")

        assert indices == {0, 1, 2}

    def test_parse_selection_range(self) -> None:
        results = self.create_test_results()
        console = Mock(spec=Console)
        session = InteractiveSession(results, console)

        indices = session._parse_selection("0-2")

        assert indices == {0, 1, 2}

    def test_parse_selection_mixed(self) -> None:
        results = self.create_test_results()
        console = Mock(spec=Console)
        session = InteractiveSession(results, console)

        indices = session._parse_selection("0, 2-4, 6")

        assert 0 in indices
        assert 2 in indices
        # Note: indices beyond list length are handled by the method

    def test_parse_selection_invalid(self) -> None:
        results = self.create_test_results()
        console = Mock(spec=Console)
        session = InteractiveSession(results, console)

        indices = session._parse_selection("invalid")

        assert indices == set()

    def test_select_all(self) -> None:
        results = self.create_test_results()
        console = Mock(spec=Console)
        session = InteractiveSession(results, console)

        session._select_all()

        assert len(session.selected_indices) == 3
        assert session.selected_indices == {0, 1, 2}

    def test_deselect_all(self) -> None:
        results = self.create_test_results()
        console = Mock(spec=Console)
        session = InteractiveSession(results, console)

        session.selected_indices = {0, 1, 2}
        session._deselect_all()

        assert len(session.selected_indices) == 0

    def test_get_safety_style(self) -> None:
        assert InteractiveSession._get_safety_style(RemovalSafety.SAFE) == "green"
        assert InteractiveSession._get_safety_style(RemovalSafety.CAUTION) == "yellow"
        assert InteractiveSession._get_safety_style(RemovalSafety.REVIEW) == "red"

    def test_get_category_style(self) -> None:
        assert (
            InteractiveSession._get_category_style(ArtifactCategory.APPLICATION)
            == "cyan"
        )
        assert InteractiveSession._get_category_style(ArtifactCategory.CACHE) == "green"
        assert InteractiveSession._get_category_style(ArtifactCategory.LOGS) == "yellow"

    def test_format_size_bytes(self) -> None:
        assert InteractiveSession._format_size(100) == "100.0B"

    def test_format_size_kilobytes(self) -> None:
        result = InteractiveSession._format_size(1024)
        assert "1.0KB" in result

    def test_format_size_megabytes(self) -> None:
        result = InteractiveSession._format_size(1024 * 1024)
        assert "1.0MB" in result

    def test_format_size_gigabytes(self) -> None:
        result = InteractiveSession._format_size(1024 * 1024 * 1024)
        assert "1.0GB" in result

    def test_format_size_none(self) -> None:
        assert InteractiveSession._format_size(None) == "-"

    def test_select_safe_items(self) -> None:
        results = self.create_test_results()
        console = Mock(spec=Console)
        session = InteractiveSession(results, console)

        session._select_safe_items()

        # Only the cache artifact is SAFE and exists
        assert 0 in session.selected_indices
        assert len(session.selected_indices) == 1

    def test_empty_results(self) -> None:
        console = Mock(spec=Console)
        session = InteractiveSession([], console)

        assert len(session._artifacts_list) == 0


class TestRunInteractiveMode:
    """Tests for run_interactive_mode function."""

    def create_test_results(self) -> list[ScanResult]:
        """Create test scan results."""
        artifacts = (
            Artifact(
                app_name="TestApp",
                path=Path("/test/file"),
                exists=True,
            ),
        )
        return [ScanResult(app_name="TestApp", artifacts=artifacts)]

    @patch("app_hound.interactive.InteractiveSession")
    def test_run_interactive_mode(self, mock_session_class: MagicMock) -> None:
        results = self.create_test_results()
        console = Mock(spec=Console)

        mock_session = MagicMock()
        mock_session.run.return_value = None
        mock_session_class.return_value = mock_session

        result = run_interactive_mode(results, console)

        mock_session_class.assert_called_once_with(results, console)
        mock_session.run.assert_called_once()
        assert result is None

    @patch("app_hound.interactive.InteractiveSession")
    def test_run_interactive_mode_with_report(
        self, mock_session_class: MagicMock
    ) -> None:
        results = self.create_test_results()
        console = Mock(spec=Console)

        mock_report = RemovalReport(
            succeeded=tuple(),
            failed=tuple(),
            skipped=tuple(),
        )
        mock_session = MagicMock()
        mock_session.run.return_value = mock_report
        mock_session_class.return_value = mock_session

        result = run_interactive_mode(results, console)

        assert result is mock_report


class TestInteractiveSessionIntegration:
    """Integration tests for InteractiveSession."""

    def test_display_artifacts_does_not_crash(self) -> None:
        """Test that display methods don't crash."""
        artifacts = (
            Artifact(
                app_name="TestApp",
                path=Path("/test/file"),
                kind=ArtifactKind.FILE,
                category=ArtifactCategory.CACHE,
                removal_safety=RemovalSafety.SAFE,
                exists=True,
                size_bytes=1024,
            ),
        )
        results = [ScanResult(app_name="TestApp", artifacts=artifacts)]

        console = Mock(spec=Console)
        session = InteractiveSession(results, console)

        # Should not raise
        session._display_artifacts()
        assert console.print.called

    def test_show_welcome_does_not_crash(self) -> None:
        """Test that welcome message displays without error."""
        results = []
        console = Mock(spec=Console)
        session = InteractiveSession(results, console)

        # Should not raise
        session._show_welcome()
        assert console.print.called

    def test_multiple_apps(self) -> None:
        """Test session with artifacts from multiple apps."""
        artifacts1 = (Artifact(app_name="App1", path=Path("/app1/file"), exists=True),)
        artifacts2 = (Artifact(app_name="App2", path=Path("/app2/file"), exists=True),)

        results = [
            ScanResult(app_name="App1", artifacts=artifacts1),
            ScanResult(app_name="App2", artifacts=artifacts2),
        ]

        console = Mock(spec=Console)
        session = InteractiveSession(results, console)

        assert len(session._artifacts_list) == 2
        assert session._artifacts_list[0][1].app_name == "App1"
        assert session._artifacts_list[1][1].app_name == "App2"

    def test_selection_persistence(self) -> None:
        """Test that selections persist across operations."""
        artifacts = (
            Artifact(app_name="TestApp", path=Path("/test1"), exists=True),
            Artifact(app_name="TestApp", path=Path("/test2"), exists=True),
            Artifact(app_name="TestApp", path=Path("/test3"), exists=True),
        )
        results = [ScanResult(app_name="TestApp", artifacts=artifacts)]

        console = Mock(spec=Console)
        session = InteractiveSession(results, console)

        # Select all
        session._select_all()
        assert len(session.selected_indices) == 3

        # Deselect all
        session._deselect_all()
        assert len(session.selected_indices) == 0

        # Manual selection
        session.selected_indices.add(0)
        session.selected_indices.add(2)
        assert session.selected_indices == {0, 2}
