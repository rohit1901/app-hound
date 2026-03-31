"""Tests for domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app_hound.domain import (
    Artifact,
    ArtifactCategory,
    ArtifactKind,
    ArtifactScope,
    RemovalSafety,
    ScanResult,
    ScanSummary,
    flatten_artifacts,
    summarize_all,
)


class TestEnums:
    """Tests for domain enums."""

    def test_artifact_kind_values(self) -> None:
        assert ArtifactKind.FILE.value == "file"
        assert ArtifactKind.DIRECTORY.value == "directory"
        assert ArtifactKind.SYMLINK.value == "symlink"
        assert ArtifactKind.UNKNOWN.value == "unknown"

    def test_artifact_scope_values(self) -> None:
        assert ArtifactScope.DEFAULT.value == "default"
        assert ArtifactScope.CONFIGURED.value == "configured"
        assert ArtifactScope.DISCOVERED.value == "discovered"
        assert ArtifactScope.SYSTEM.value == "system"
        assert ArtifactScope.UNKNOWN.value == "unknown"

    def test_artifact_category_values(self) -> None:
        assert ArtifactCategory.APPLICATION.value == "application"
        assert ArtifactCategory.SUPPORT.value == "support"
        assert ArtifactCategory.CACHE.value == "cache"
        assert ArtifactCategory.PREFERENCES.value == "preferences"
        assert ArtifactCategory.LOGS.value == "logs"
        assert ArtifactCategory.LAUNCH_AGENT.value == "launch-agent"
        assert ArtifactCategory.OTHER.value == "other"

    def test_removal_safety_values(self) -> None:
        assert RemovalSafety.SAFE.value == "safe"
        assert RemovalSafety.CAUTION.value == "caution"
        assert RemovalSafety.REVIEW.value == "review"


class TestArtifact:
    """Tests for Artifact dataclass."""

    def test_artifact_creation_minimal(self) -> None:
        artifact = Artifact(
            app_name="TestApp",
            path=Path("/test/path"),
        )

        assert artifact.app_name == "TestApp"
        assert artifact.path == Path("/test/path")
        assert artifact.kind == ArtifactKind.UNKNOWN
        assert artifact.scope == ArtifactScope.UNKNOWN
        assert artifact.category == ArtifactCategory.OTHER
        assert artifact.removal_safety == RemovalSafety.REVIEW
        assert artifact.exists is True
        assert artifact.writable is None
        assert artifact.size_bytes is None
        assert artifact.last_modified is None
        assert len(artifact.notes) == 0
        assert len(artifact.removal_instructions) == 0

    def test_artifact_creation_full(self) -> None:
        now = datetime.now(timezone.utc)
        artifact = Artifact(
            app_name="TestApp",
            path=Path("/test/path"),
            kind=ArtifactKind.FILE,
            scope=ArtifactScope.DEFAULT,
            category=ArtifactCategory.CACHE,
            removal_safety=RemovalSafety.SAFE,
            exists=True,
            writable=True,
            size_bytes=1024,
            last_modified=now,
            notes=("note1", "note2"),
            removal_instructions=("rm -f /test/path",),
        )

        assert artifact.app_name == "TestApp"
        assert artifact.kind == ArtifactKind.FILE
        assert artifact.scope == ArtifactScope.DEFAULT
        assert artifact.category == ArtifactCategory.CACHE
        assert artifact.removal_safety == RemovalSafety.SAFE
        assert artifact.exists is True
        assert artifact.writable is True
        assert artifact.size_bytes == 1024
        assert artifact.last_modified == now
        assert artifact.notes == ("note1", "note2")
        assert artifact.removal_instructions == ("rm -f /test/path",)

    def test_artifact_is_frozen(self) -> None:
        """Test that Artifact is immutable."""
        artifact = Artifact(
            app_name="TestApp",
            path=Path("/test/path"),
        )

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            setattr(artifact, "app_name", "NewApp")

    def test_artifact_to_dict(self) -> None:
        now = datetime.now(timezone.utc)
        artifact = Artifact(
            app_name="TestApp",
            path=Path("/test/path"),
            kind=ArtifactKind.FILE,
            scope=ArtifactScope.CONFIGURED,
            category=ArtifactCategory.SUPPORT,
            removal_safety=RemovalSafety.CAUTION,
            exists=True,
            writable=True,
            size_bytes=2048,
            last_modified=now,
            notes=("important",),
            removal_instructions=("backup first",),
        )

        data = artifact.to_dict()

        assert data["app_name"] == "TestApp"
        assert data["path"] == "/test/path"
        assert data["kind"] == "file"
        assert data["scope"] == "configured"
        assert data["category"] == "support"
        assert data["removal_safety"] == "caution"
        assert data["exists"] is True
        assert data["writable"] is True
        assert data["size_bytes"] == 2048
        assert data["last_modified"] == now.isoformat()
        assert data["notes"] == ["important"]
        assert data["removal_instructions"] == ["backup first"]

    def test_artifact_to_dict_with_none_values(self) -> None:
        artifact = Artifact(
            app_name="TestApp",
            path=Path("/test/path"),
        )

        data = artifact.to_dict()

        assert data["writable"] is None
        assert data["size_bytes"] is None
        assert data["last_modified"] is None

    def test_artifact_with_notes(self) -> None:
        artifact = Artifact(
            app_name="TestApp",
            path=Path("/test/path"),
            notes=("existing note",),
        )

        updated = artifact.with_notes("new note 1", "new note 2")

        assert artifact.notes == ("existing note",)  # Original unchanged
        assert updated.notes == ("existing note", "new note 1", "new note 2")

    def test_artifact_with_notes_empty(self) -> None:
        artifact = Artifact(
            app_name="TestApp",
            path=Path("/test/path"),
        )

        updated = artifact.with_notes()

        assert updated is artifact  # Should return same instance if no notes added

    def test_artifact_with_removal_instructions(self) -> None:
        artifact = Artifact(
            app_name="TestApp",
            path=Path("/test/path"),
            removal_instructions=("step 1",),
        )

        updated = artifact.with_removal_instructions("step 2", "step 3")

        assert artifact.removal_instructions == ("step 1",)  # Original unchanged
        assert updated.removal_instructions == ("step 1", "step 2", "step 3")

    def test_artifact_mark_missing(self) -> None:
        artifact = Artifact(
            app_name="TestApp",
            path=Path("/test/path"),
            exists=True,
        )

        missing = artifact.mark_missing()

        assert artifact.exists is True  # Original unchanged
        assert missing.exists is False

    def test_artifact_with_metadata(self) -> None:
        now = datetime.now(timezone.utc)
        artifact = Artifact(
            app_name="TestApp",
            path=Path("/test/path"),
        )

        updated = artifact.with_metadata(
            exists=True,
            writable=True,
            size_bytes=512,
            last_modified=now,
        )

        assert artifact.exists is True  # Original unchanged (default)
        assert artifact.writable is None
        assert updated.exists is True
        assert updated.writable is True
        assert updated.size_bytes == 512
        assert updated.last_modified == now

    def test_artifact_with_metadata_partial_update(self) -> None:
        artifact = Artifact(
            app_name="TestApp",
            path=Path("/test/path"),
            exists=True,
            writable=False,
            size_bytes=100,
        )

        updated = artifact.with_metadata(size_bytes=200)

        assert updated.exists is True  # Unchanged
        assert updated.writable is False  # Unchanged
        assert updated.size_bytes == 200  # Changed


class TestScanResult:
    """Tests for ScanResult dataclass."""

    def test_scan_result_creation_minimal(self) -> None:
        result = ScanResult(app_name="TestApp")

        assert result.app_name == "TestApp"
        assert len(result.artifacts) == 0
        assert isinstance(result.generated_at, datetime)
        assert len(result.errors) == 0

    def test_scan_result_creation_with_artifacts(self) -> None:
        artifacts = (
            Artifact(app_name="TestApp", path=Path("/path1")),
            Artifact(app_name="TestApp", path=Path("/path2")),
        )

        result = ScanResult(
            app_name="TestApp",
            artifacts=artifacts,
        )

        assert len(result.artifacts) == 2
        assert result.artifacts[0].path == Path("/path1")
        assert result.artifacts[1].path == Path("/path2")

    def test_scan_result_existing_artifacts(self) -> None:
        artifacts = (
            Artifact(app_name="TestApp", path=Path("/exists"), exists=True),
            Artifact(app_name="TestApp", path=Path("/missing"), exists=False),
            Artifact(app_name="TestApp", path=Path("/also_exists"), exists=True),
        )

        result = ScanResult(app_name="TestApp", artifacts=artifacts)
        existing = result.existing_artifacts()

        assert len(existing) == 2
        assert all(a.exists for a in existing)

    def test_scan_result_missing_artifacts(self) -> None:
        artifacts = (
            Artifact(app_name="TestApp", path=Path("/exists"), exists=True),
            Artifact(app_name="TestApp", path=Path("/missing1"), exists=False),
            Artifact(app_name="TestApp", path=Path("/missing2"), exists=False),
        )

        result = ScanResult(app_name="TestApp", artifacts=artifacts)
        missing = result.missing_artifacts()

        assert len(missing) == 2
        assert all(not a.exists for a in missing)

    def test_scan_result_by_category(self) -> None:
        artifacts = (
            Artifact(
                app_name="TestApp",
                path=Path("/cache1"),
                category=ArtifactCategory.CACHE,
            ),
            Artifact(
                app_name="TestApp",
                path=Path("/log1"),
                category=ArtifactCategory.LOGS,
            ),
            Artifact(
                app_name="TestApp",
                path=Path("/cache2"),
                category=ArtifactCategory.CACHE,
            ),
        )

        result = ScanResult(app_name="TestApp", artifacts=artifacts)

        cache_artifacts = result.by_category(ArtifactCategory.CACHE)
        assert len(cache_artifacts) == 2

        log_artifacts = result.by_category(ArtifactCategory.LOGS)
        assert len(log_artifacts) == 1

        pref_artifacts = result.by_category(ArtifactCategory.PREFERENCES)
        assert len(pref_artifacts) == 0

    def test_scan_result_add_artifacts(self) -> None:
        initial = ScanResult(
            app_name="TestApp",
            artifacts=(Artifact(app_name="TestApp", path=Path("/path1")),),
        )

        new_artifacts = (
            Artifact(app_name="TestApp", path=Path("/path2")),
            Artifact(app_name="TestApp", path=Path("/path3")),
        )

        updated = initial.add_artifacts(*new_artifacts)

        assert len(initial.artifacts) == 1  # Original unchanged
        assert len(updated.artifacts) == 3
        assert updated.artifacts[0].path == Path("/path1")
        assert updated.artifacts[1].path == Path("/path2")
        assert updated.artifacts[2].path == Path("/path3")

    def test_scan_result_add_artifacts_empty(self) -> None:
        result = ScanResult(app_name="TestApp")
        updated = result.add_artifacts()

        assert updated is result  # Should return same instance

    def test_scan_result_add_errors(self) -> None:
        result = ScanResult(
            app_name="TestApp",
            errors=("error 1",),
        )

        updated = result.add_errors("error 2", "error 3")

        assert len(result.errors) == 1  # Original unchanged
        assert len(updated.errors) == 3
        assert updated.errors == ("error 1", "error 2", "error 3")

    def test_scan_result_add_errors_empty(self) -> None:
        result = ScanResult(app_name="TestApp")
        updated = result.add_errors()

        assert updated is result  # Should return same instance

    def test_scan_result_is_frozen(self) -> None:
        """Test that ScanResult is immutable."""
        result = ScanResult(app_name="TestApp")

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            setattr(result, "app_name", "NewApp")


class TestScanSummary:
    """Tests for ScanSummary dataclass."""

    def test_scan_summary_creation(self) -> None:
        summary = ScanSummary(
            app_name="TestApp",
            total_artifacts=10,
            existing_artifacts=8,
            missing_artifacts=2,
            removable_artifacts=5,
        )

        assert summary.app_name == "TestApp"
        assert summary.total_artifacts == 10
        assert summary.existing_artifacts == 8
        assert summary.missing_artifacts == 2
        assert summary.removable_artifacts == 5

    def test_scan_summary_from_result(self) -> None:
        artifacts = (
            Artifact(
                app_name="TestApp",
                path=Path("/cache"),
                exists=True,
                removal_safety=RemovalSafety.SAFE,
            ),
            Artifact(
                app_name="TestApp",
                path=Path("/prefs"),
                exists=True,
                removal_safety=RemovalSafety.CAUTION,
            ),
            Artifact(
                app_name="TestApp",
                path=Path("/data"),
                exists=True,
                removal_safety=RemovalSafety.REVIEW,
            ),
            Artifact(
                app_name="TestApp",
                path=Path("/missing"),
                exists=False,
                removal_safety=RemovalSafety.SAFE,
            ),
        )

        result = ScanResult(app_name="TestApp", artifacts=artifacts)
        summary = ScanSummary.from_result(result)

        assert summary.app_name == "TestApp"
        assert summary.total_artifacts == 4
        assert summary.existing_artifacts == 3
        assert summary.missing_artifacts == 1
        assert (
            summary.removable_artifacts == 3
        )  # SAFE (existing) + CAUTION (existing) + SAFE (missing)

    def test_scan_summary_from_empty_result(self) -> None:
        result = ScanResult(app_name="EmptyApp")
        summary = ScanSummary.from_result(result)

        assert summary.app_name == "EmptyApp"
        assert summary.total_artifacts == 0
        assert summary.existing_artifacts == 0
        assert summary.missing_artifacts == 0
        assert summary.removable_artifacts == 0


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_flatten_artifacts(self) -> None:
        result1 = ScanResult(
            app_name="App1",
            artifacts=(
                Artifact(app_name="App1", path=Path("/path1")),
                Artifact(app_name="App1", path=Path("/path2")),
            ),
        )

        result2 = ScanResult(
            app_name="App2",
            artifacts=(Artifact(app_name="App2", path=Path("/path3")),),
        )

        flattened = flatten_artifacts([result1, result2])

        assert len(flattened) == 3
        assert flattened[0].path == Path("/path1")
        assert flattened[1].path == Path("/path2")
        assert flattened[2].path == Path("/path3")

    def test_flatten_artifacts_empty(self) -> None:
        flattened = flatten_artifacts([])
        assert len(flattened) == 0

    def test_flatten_artifacts_with_empty_results(self) -> None:
        result1 = ScanResult(app_name="App1")
        result2 = ScanResult(
            app_name="App2",
            artifacts=(Artifact(app_name="App2", path=Path("/path1")),),
        )

        flattened = flatten_artifacts([result1, result2])

        assert len(flattened) == 1
        assert flattened[0].path == Path("/path1")

    def test_summarize_all(self) -> None:
        results = [
            ScanResult(
                app_name="App1",
                artifacts=(
                    Artifact(app_name="App1", path=Path("/p1"), exists=True),
                    Artifact(app_name="App1", path=Path("/p2"), exists=False),
                ),
            ),
            ScanResult(
                app_name="App2",
                artifacts=(Artifact(app_name="App2", path=Path("/p3"), exists=True),),
            ),
        ]

        summaries = summarize_all(results)

        assert len(summaries) == 2
        assert summaries[0].app_name == "App1"
        assert summaries[0].total_artifacts == 2
        assert summaries[1].app_name == "App2"
        assert summaries[1].total_artifacts == 1

    def test_summarize_all_empty(self) -> None:
        summaries = summarize_all([])
        assert len(summaries) == 0
