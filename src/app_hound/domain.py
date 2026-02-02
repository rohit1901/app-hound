from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Sequence, Tuple


class ArtifactKind(Enum):
    """Represents the filesystem nature of an artifact."""

    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    UNKNOWN = "unknown"


class ArtifactScope(Enum):
    """Describes how an artifact was selected for inspection."""

    DEFAULT = "default"
    CONFIGURED = "configured"
    DISCOVERED = "discovered"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class ArtifactCategory(Enum):
    """High-level categorisation of installation traces."""

    APPLICATION = "application"
    SUPPORT = "support"
    CACHE = "cache"
    PREFERENCES = "preferences"
    LOGS = "logs"
    LAUNCH_AGENT = "launch-agent"
    OTHER = "other"


class RemovalSafety(Enum):
    """Guidance for downstream removal tooling."""

    SAFE = "safe"
    CAUTION = "caution"
    REVIEW = "review"


@dataclass(frozen=True)
class Artifact:
    """
    Represents a single filesystem trace tied to an application.

    The dataclass is intentionally frozen to keep mutation explicit. Utility
    helpers such as ``with_notes`` and ``mark_missing`` return new instances
    using :func:`dataclasses.replace`.
    """

    app_name: str
    path: Path
    kind: ArtifactKind = ArtifactKind.UNKNOWN
    scope: ArtifactScope = ArtifactScope.UNKNOWN
    category: ArtifactCategory = ArtifactCategory.OTHER
    removal_safety: RemovalSafety = RemovalSafety.REVIEW
    exists: bool = True
    writable: bool | None = None
    size_bytes: int | None = None
    last_modified: datetime | None = None
    notes: Tuple[str, ...] = field(default_factory=tuple)
    removal_instructions: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        """Serialize the artifact to a JSON-friendly dictionary."""
        return {
            "app_name": self.app_name,
            "path": str(self.path),
            "kind": self.kind.value,
            "scope": self.scope.value,
            "category": self.category.value,
            "removal_safety": self.removal_safety.value,
            "exists": self.exists,
            "writable": self.writable,
            "size_bytes": self.size_bytes,
            "last_modified": self.last_modified.isoformat()
            if self.last_modified is not None
            else None,
            "notes": list(self.notes),
            "removal_instructions": list(self.removal_instructions),
        }

    def with_notes(self, *notes: str) -> Artifact:
        """Return a copy with additional notes appended."""
        if not notes:
            return self
        return replace(self, notes=self.notes + tuple(notes))

    def with_removal_instructions(self, *instructions: str) -> Artifact:
        """Return a copy with additional removal instructions appended."""
        if not instructions:
            return self
        return replace(
            self, removal_instructions=self.removal_instructions + tuple(instructions)
        )

    def mark_missing(self) -> Artifact:
        """Return a copy that indicates the backing path no longer exists."""
        return replace(self, exists=False)

    def with_metadata(
        self,
        *,
        exists: bool | None = None,
        writable: bool | None = None,
        size_bytes: int | None = None,
        last_modified: datetime | None = None,
    ) -> Artifact:
        """Return a copy with updated filesystem metadata."""
        return replace(
            self,
            exists=self.exists if exists is None else exists,
            writable=self.writable if writable is None else writable,
            size_bytes=self.size_bytes if size_bytes is None else size_bytes,
            last_modified=self.last_modified
            if last_modified is None
            else last_modified,
        )


@dataclass(frozen=True)
class ScanResult:
    """
    Aggregate of artifacts discovered for a single application scan.

    ``errors`` captures non-fatal issues encountered during the scan so that
    callers can surface them without halting execution.
    """

    app_name: str
    artifacts: Tuple[Artifact, ...] = field(default_factory=tuple)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    errors: Tuple[str, ...] = field(default_factory=tuple)

    def existing_artifacts(self) -> Tuple[Artifact, ...]:
        """Return only the artifacts that still exist on disk."""
        return tuple(artifact for artifact in self.artifacts if artifact.exists)

    def missing_artifacts(self) -> Tuple[Artifact, ...]:
        """Return artifacts that are no longer present on disk."""
        return tuple(artifact for artifact in self.artifacts if not artifact.exists)

    def by_category(self, category: ArtifactCategory) -> Tuple[Artifact, ...]:
        """Return all artifacts matching the given category."""
        return tuple(
            artifact for artifact in self.artifacts if artifact.category == category
        )

    def add_artifacts(self, *artifacts: Artifact) -> ScanResult:
        """Return a copy with the provided artifacts appended."""
        if not artifacts:
            return self
        return replace(self, artifacts=self.artifacts + tuple(artifacts))

    def add_errors(self, *messages: str) -> ScanResult:
        """Return a copy with additional error messages recorded."""
        if not messages:
            return self
        return replace(self, errors=self.errors + tuple(messages))


@dataclass(frozen=True)
class ScanSummary:
    """Roll-up metrics that help present scan outcomes."""

    app_name: str
    total_artifacts: int
    existing_artifacts: int
    missing_artifacts: int
    removable_artifacts: int

    @classmethod
    def from_result(cls, result: ScanResult) -> ScanSummary:
        """Create a summary from a :class:`ScanResult`."""
        total = len(result.artifacts)
        existing = len(result.existing_artifacts())
        missing = total - existing
        removable = sum(
            1
            for artifact in result.artifacts
            if artifact.removal_safety in (RemovalSafety.SAFE, RemovalSafety.CAUTION)
        )
        return cls(
            app_name=result.app_name,
            total_artifacts=total,
            existing_artifacts=existing,
            missing_artifacts=missing,
            removable_artifacts=removable,
        )


def flatten_artifacts(results: Iterable[ScanResult]) -> Tuple[Artifact, ...]:
    """Flatten artifacts from multiple scan results into a single tuple."""
    collected: list[Artifact] = []
    for result in results:
        collected.extend(result.artifacts)
    return tuple(collected)


def summarize_all(results: Sequence[ScanResult]) -> Tuple[ScanSummary, ...]:
    """Produce summaries for each scan result in the provided sequence."""
    return tuple(ScanSummary.from_result(result) for result in results)


__all__ = [
    "Artifact",
    "ArtifactCategory",
    "ArtifactKind",
    "ArtifactScope",
    "RemovalSafety",
    "ScanResult",
    "ScanSummary",
    "flatten_artifacts",
    "summarize_all",
]
