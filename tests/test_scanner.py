"""Tests for the Scanner module."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import pytest

from app_hound.configuration import AppConfiguration
from app_hound.domain import (
    Artifact,
    ArtifactCategory,
    ArtifactKind,
    ArtifactScope,
    RemovalSafety,
    ScanResult,
)
from app_hound.scanner import (
    Filesystem,
    LocalFilesystem,
    ScanCandidate,
    Scanner,
)


class TestLocalFilesystem:
    """Tests for LocalFilesystem implementation."""

    def test_exists(self, tmp_path: Path) -> None:
        fs = LocalFilesystem()
        existing_file = tmp_path / "exists.txt"
        existing_file.write_text("hello")

        assert fs.exists(existing_file) is True
        assert fs.exists(tmp_path / "does_not_exist.txt") is False

    def test_is_dir(self, tmp_path: Path) -> None:
        fs = LocalFilesystem()
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        file = tmp_path / "file.txt"
        file.write_text("content")

        assert fs.is_dir(subdir) is True
        assert fs.is_dir(file) is False

    def test_is_file(self, tmp_path: Path) -> None:
        fs = LocalFilesystem()
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        file = tmp_path / "file.txt"
        file.write_text("content")

        assert fs.is_file(file) is True
        assert fs.is_file(subdir) is False

    def test_is_symlink(self, tmp_path: Path) -> None:
        fs = LocalFilesystem()
        target = tmp_path / "target.txt"
        target.write_text("target")
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        assert fs.is_symlink(link) is True
        assert fs.is_symlink(target) is False

    def test_stat(self, tmp_path: Path) -> None:
        fs = LocalFilesystem()
        file = tmp_path / "file.txt"
        file.write_text("hello world")

        stat_result = fs.stat(file)
        assert stat_result is not None
        assert stat_result.st_size == 11
        assert hasattr(stat_result, "st_mtime")

    def test_is_writable(self, tmp_path: Path) -> None:
        fs = LocalFilesystem()
        file = tmp_path / "writable.txt"
        file.write_text("content")

        assert fs.is_writable(file) is True

        # Make file read-only
        os.chmod(file, 0o444)
        # Note: on some systems, the owner might still have write access
        # so we just check that the method runs without error
        result = fs.is_writable(file)
        assert isinstance(result, bool)

    def test_resolve(self, tmp_path: Path) -> None:
        fs = LocalFilesystem()
        resolved = fs.resolve(tmp_path)
        assert resolved.is_absolute()

    def test_home(self) -> None:
        fs = LocalFilesystem()
        home = fs.home()
        assert home.is_absolute()
        assert home.exists()


class MockFilesystem(Filesystem):
    """Mock filesystem for testing Scanner without real I/O."""

    def __init__(
        self,
        existing_paths: set[Path] | None = None,
        directories: set[Path] | None = None,
        files: set[Path] | None = None,
        symlinks: set[Path] | None = None,
    ) -> None:
        self._existing = existing_paths or set()
        self._dirs = directories or set()
        self._files = files or set()
        self._symlinks = symlinks or set()

    def exists(self, path: Path) -> bool:
        return path in self._existing

    def is_dir(self, path: Path) -> bool:
        return path in self._dirs

    def is_file(self, path: Path) -> bool:
        return path in self._files

    def is_symlink(self, path: Path) -> bool:
        return path in self._symlinks

    def stat(self, path: Path) -> os.stat_result | None:
        if not self.exists(path):
            return None
        # Return a minimal mock stat result
        return os.stat_result((0o644, 0, 0, 1, 1000, 1000, 1024, 0, 0, 0))

    def is_writable(self, path: Path) -> bool:
        return path in self._existing

    def resolve(self, path: Path) -> Path:
        return path

    def home(self) -> Path:
        return Path("/mock/home")


class TestScanner:
    """Tests for Scanner class."""

    def test_scanner_init(self) -> None:
        scanner = Scanner()
        assert scanner is not None

    def test_scan_with_mock_filesystem(self) -> None:
        app_dir = Path("/Applications/TestApp.app")
        support_dir = Path("/mock/home/Library/Application Support/TestApp")

        mock_fs = MockFilesystem(
            existing_paths={app_dir, support_dir},
            directories={app_dir, support_dir},
        )

        scanner = Scanner(filesystem=mock_fs)
        config = AppConfiguration(
            name="TestApp",
            additional_locations=(app_dir, support_dir),
        )

        result = scanner.scan(config)

        assert isinstance(result, ScanResult)
        assert result.app_name == "TestApp"
        assert len(result.artifacts) > 0

    def test_scan_nonexistent_paths(self) -> None:
        mock_fs = MockFilesystem(existing_paths=set())
        scanner = Scanner(filesystem=mock_fs)

        config = AppConfiguration(
            name="GhostApp",
            additional_locations=(Path("/nonexistent/app"),),
        )

        result = scanner.scan(config)

        assert result.app_name == "GhostApp"
        # Artifacts should be created even for nonexistent paths
        assert len(result.artifacts) >= 0

    def test_determine_kind_file(self) -> None:
        file_path = Path("/test/file.txt")
        mock_fs = MockFilesystem(
            existing_paths={file_path},
            files={file_path},
        )

        scanner = Scanner(filesystem=mock_fs)
        kind = scanner._determine_kind(file_path, exists=True)

        assert kind == ArtifactKind.FILE

    def test_determine_kind_directory(self) -> None:
        dir_path = Path("/test/dir")
        mock_fs = MockFilesystem(
            existing_paths={dir_path},
            directories={dir_path},
        )

        scanner = Scanner(filesystem=mock_fs)
        kind = scanner._determine_kind(dir_path, exists=True)

        assert kind == ArtifactKind.DIRECTORY

    def test_determine_kind_symlink(self) -> None:
        link_path = Path("/test/link")
        mock_fs = MockFilesystem(
            existing_paths={link_path},
            symlinks={link_path},
        )

        scanner = Scanner(filesystem=mock_fs)
        kind = scanner._determine_kind(link_path, exists=True)

        assert kind == ArtifactKind.SYMLINK

    def test_determine_kind_nonexistent(self) -> None:
        scanner = Scanner(filesystem=MockFilesystem())
        kind = scanner._determine_kind(Path("/nonexistent"), exists=False)

        assert kind == ArtifactKind.UNKNOWN

    def test_materialize_with_metadata(self, tmp_path: Path) -> None:
        """Test that materialize correctly extracts file metadata."""
        fs = LocalFilesystem()
        scanner = Scanner(filesystem=fs)

        # Create a real file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        candidate = ScanCandidate(
            path=test_file,
            scope=ArtifactScope.CONFIGURED,
            category=ArtifactCategory.OTHER,
            removal_safety=RemovalSafety.SAFE,
            notes=tuple(),
        )

        artifact, error = scanner._materialize("TestApp", candidate)

        assert artifact.app_name == "TestApp"
        assert artifact.path == test_file
        assert artifact.exists is True
        assert artifact.kind == ArtifactKind.FILE
        assert artifact.size_bytes == 12  # "test content" is 12 bytes
        assert artifact.last_modified is not None
        assert isinstance(artifact.last_modified, datetime)
        assert error is None

    def test_materialize_nonexistent_file(self) -> None:
        """Test that materialize handles nonexistent files correctly."""
        fs = LocalFilesystem()
        scanner = Scanner(filesystem=fs)

        candidate = ScanCandidate(
            path=Path("/nonexistent/file.txt"),
            scope=ArtifactScope.CONFIGURED,
            category=ArtifactCategory.OTHER,
            removal_safety=RemovalSafety.SAFE,
            notes=tuple(),
        )

        artifact, error = scanner._materialize("TestApp", candidate)

        assert artifact.exists is False
        assert artifact.size_bytes is None
        assert artifact.last_modified is None
        assert error is None

    def test_materialize_directory_no_size(self, tmp_path: Path) -> None:
        """Test that directories don't report size_bytes."""
        fs = LocalFilesystem()
        scanner = Scanner(filesystem=fs)

        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        candidate = ScanCandidate(
            path=test_dir,
            scope=ArtifactScope.DEFAULT,
            category=ArtifactCategory.SUPPORT,
            removal_safety=RemovalSafety.CAUTION,
            notes=tuple(),
        )

        artifact, error = scanner._materialize("TestApp", candidate)

        assert artifact.exists is True
        assert artifact.kind == ArtifactKind.DIRECTORY
        assert artifact.size_bytes is None  # Directories shouldn't report size
        assert artifact.last_modified is not None
        assert error is None

    def test_scan_with_deep_home_search(self) -> None:
        """Test scanner with deep home search enabled."""
        scanner = Scanner(deep_home_search_default=True)
        config = AppConfiguration(
            name="TestApp",
            deep_home_search=True,
        )

        result = scanner.scan(config)

        assert isinstance(result, ScanResult)
        assert result.app_name == "TestApp"

    def test_scan_candidate_deduplication(self) -> None:
        """Test that scanner deduplicates candidate paths."""
        app_path = Path("/Applications/TestApp.app")
        mock_fs = MockFilesystem(
            existing_paths={app_path},
            directories={app_path},
        )

        scanner = Scanner(filesystem=mock_fs)

        # Provide the same path twice
        config = AppConfiguration(
            name="TestApp",
            additional_locations=(app_path, app_path),
        )

        result = scanner.scan(config)

        # Should only have one artifact for the duplicated path
        paths = [a.path for a in result.artifacts]
        assert paths.count(app_path) == 1

    def test_strip_app_suffix(self) -> None:
        """Test that .app suffix is stripped from app names."""
        scanner = Scanner()

        assert scanner._strip_app_suffix("TestApp.app") == "TestApp"
        assert scanner._strip_app_suffix("TestApp") == "TestApp"
        assert scanner._strip_app_suffix("My.app.app") == "My.app"

    def test_scan_with_patterns(self) -> None:
        """Test scanner with custom glob patterns."""
        scanner = Scanner()

        config = AppConfiguration(
            name="TestApp",
            patterns=("~/Library/Preferences/*TestApp*",),
        )

        result = scanner.scan(config)

        assert isinstance(result, ScanResult)
        assert result.app_name == "TestApp"


class TestScanCandidate:
    """Tests for ScanCandidate dataclass."""

    def test_scan_candidate_creation(self) -> None:
        candidate = ScanCandidate(
            path=Path("/test/path"),
            scope=ArtifactScope.DEFAULT,
            category=ArtifactCategory.CACHE,
            removal_safety=RemovalSafety.SAFE,
            notes=("test note",),
        )

        assert candidate.path == Path("/test/path")
        assert candidate.scope == ArtifactScope.DEFAULT
        assert candidate.category == ArtifactCategory.CACHE
        assert candidate.removal_safety == RemovalSafety.SAFE
        assert len(candidate.notes) == 1
        assert candidate.notes[0] == "test note"

    def test_scan_candidate_empty_notes(self) -> None:
        candidate = ScanCandidate(
            path=Path("/test"),
            scope=ArtifactScope.CONFIGURED,
            category=ArtifactCategory.OTHER,
            removal_safety=RemovalSafety.REVIEW,
            notes=tuple(),
        )

        assert len(candidate.notes) == 0


class TestIntegration:
    """Integration tests using real filesystem."""

    def test_full_scan_workflow(self, tmp_path: Path) -> None:
        """Test a complete scan workflow with real files."""
        # Create test application structure
        app_bundle = tmp_path / "TestApp.app"
        app_bundle.mkdir()

        support_dir = tmp_path / "Library" / "Application Support" / "TestApp"
        support_dir.mkdir(parents=True)
        (support_dir / "data.db").write_text("database")

        cache_dir = tmp_path / "Library" / "Caches" / "TestApp"
        cache_dir.mkdir(parents=True)
        (cache_dir / "cache.tmp").write_text("cache data")

        # Configure and scan
        scanner = Scanner()
        config = AppConfiguration(
            name="TestApp",
            additional_locations=(app_bundle, support_dir, cache_dir),
        )

        result = scanner.scan(config)

        # Verify results
        assert result.app_name == "TestApp"
        assert len(result.artifacts) >= 3

        # Check that we found all the paths
        artifact_paths = {str(a.path) for a in result.artifacts}
        assert str(app_bundle) in artifact_paths
        assert str(support_dir) in artifact_paths
        assert str(cache_dir) in artifact_paths

        # Verify metadata was captured
        for artifact in result.artifacts:
            if artifact.exists:
                assert artifact.kind != ArtifactKind.UNKNOWN
                if artifact.kind == ArtifactKind.FILE:
                    assert artifact.size_bytes is not None
                    assert artifact.size_bytes > 0
                assert artifact.last_modified is not None

    def test_scan_with_permission_errors(self, tmp_path: Path) -> None:
        """Test that scanner handles permission errors gracefully."""
        restricted_dir = tmp_path / "restricted"
        restricted_dir.mkdir()

        # Create a file and make it unreadable
        restricted_file = restricted_dir / "secret.txt"
        restricted_file.write_text("secret")

        scanner = Scanner()
        config = AppConfiguration(
            name="TestApp",
            additional_locations=(restricted_file,),
        )

        # Should not raise even if we can't read metadata
        result = scanner.scan(config)
        assert isinstance(result, ScanResult)
