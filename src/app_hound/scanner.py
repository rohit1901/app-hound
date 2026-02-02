from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Protocol, Sequence, Tuple, runtime_checkable

from app_hound.configuration import AppConfiguration
from app_hound.domain import (
    Artifact,
    ArtifactCategory,
    ArtifactKind,
    ArtifactScope,
    RemovalSafety,
    ScanResult,
)


@runtime_checkable
class Filesystem(Protocol):
    """Minimal filesystem gateway used by the scanner."""

    def exists(self, path: Path) -> bool: ...

    def is_dir(self, path: Path) -> bool: ...

    def is_file(self, path: Path) -> bool: ...

    def is_symlink(self, path: Path) -> bool: ...

    def stat(self, path: Path): ...

    def is_writable(self, path: Path) -> bool: ...

    def resolve(self, path: Path) -> Path: ...

    def home(self) -> Path: ...


class LocalFilesystem(Filesystem):
    """Concrete filesystem gateway backed by :mod:`pathlib` and :mod:`os`."""

    def exists(self, path: Path) -> bool:
        return path.exists()

    def is_dir(self, path: Path) -> bool:
        return path.is_dir()

    def is_file(self, path: Path) -> bool:
        return path.is_file()

    def is_symlink(self, path: Path) -> bool:
        return path.is_symlink()

    def stat(self, path: Path):
        return path.stat()

    def is_writable(self, path: Path) -> bool:
        return os.access(path, os.W_OK)

    def resolve(self, path: Path) -> Path:
        expanded = Path(os.path.expandvars(str(path))).expanduser()
        try:
            return expanded.resolve(strict=True)
        except (FileNotFoundError, RuntimeError):
            try:
                return expanded.resolve(strict=False)
            except (FileNotFoundError, RuntimeError):
                return expanded

    def home(self) -> Path:
        return Path.home()


@dataclass(frozen=True)
class ScanCandidate:
    """Internal representation of a candidate artifact path."""

    path: Path
    category: ArtifactCategory
    scope: ArtifactScope
    removal_safety: RemovalSafety
    notes: Tuple[str, ...] = ()


class Scanner:
    """
    Deterministic artifact scanner that produces rich :class:`Artifact` objects.

    The scanner is intentionally decoupled from any presentation layer. It
    gathers filesystem metadata via the injected :class:`Filesystem` gateway,
    making it straightforward to substitute a fake filesystem in tests.
    """

    def __init__(
        self,
        filesystem: Filesystem | None = None,
        *,
        deep_home_search_default: bool = False,
    ) -> None:
        self._fs = filesystem or LocalFilesystem()
        self._deep_home_search_default = deep_home_search_default

    def scan(self, configuration: AppConfiguration) -> ScanResult:
        should_deep_search = (
            configuration.deep_home_search or self._deep_home_search_default
        )
        candidates, candidate_errors = self._build_candidates(
            configuration, should_deep_search
        )

        artifacts: list[Artifact] = []
        errors: list[str] = list(candidate_errors)
        seen_paths: set[str] = set()

        for candidate in candidates:
            canonical = self._canonical_key(candidate.path)
            if canonical in seen_paths:
                continue
            seen_paths.add(canonical)

            artifact, error = self._materialize(configuration.name, candidate)
            include_missing = (
                not artifact.exists and candidate.scope == ArtifactScope.CONFIGURED
            )
            if artifact.exists or include_missing:
                artifacts.append(artifact)
            if error:
                errors.append(error)

        return ScanResult(
            app_name=configuration.name,
            artifacts=tuple(artifacts),
            errors=tuple(errors),
        )

    def _materialize(
        self,
        app_name: str,
        candidate: ScanCandidate,
    ) -> tuple[Artifact, str | None]:
        resolved_path = self._fs.resolve(candidate.path)
        exists = self._fs.exists(resolved_path)
        kind = self._determine_kind(resolved_path, exists)

        writable = self._fs.is_writable(resolved_path) if exists else None
        size_bytes: int | None = None
        last_modified: datetime | None = None
        error_message: str | None = None

        if exists:
            try:
                stats = self._fs.stat(resolved_path)
                if kind == ArtifactKind.FILE and not self._fs.is_symlink(resolved_path):
                    size_bytes = stats.st_size  # type: ignore[attr-defined]
                last_modified = datetime.fromtimestamp(
                    stats.st_mtime,  # type: ignore[attr-defined]
                    tz=timezone.utc,
                )
            except OSError as exc:
                error_message = f"Failed to read metadata for {resolved_path}: {exc}"

        artifact = Artifact(
            app_name=app_name,
            path=resolved_path,
            kind=kind,
            scope=candidate.scope,
            category=candidate.category,
            removal_safety=candidate.removal_safety,
            exists=exists,
            writable=writable,
            size_bytes=size_bytes,
            last_modified=last_modified,
            notes=candidate.notes,
        )
        return artifact, error_message

    def _canonical_key(self, path: Path) -> str:
        resolved = self._fs.resolve(path)
        return str(resolved)

    def _determine_kind(self, path: Path, exists: bool) -> ArtifactKind:
        if not exists:
            return ArtifactKind.UNKNOWN
        if self._fs.is_symlink(path):
            return ArtifactKind.SYMLINK
        if self._fs.is_dir(path):
            return ArtifactKind.DIRECTORY
        if self._fs.is_file(path):
            return ArtifactKind.FILE
        return ArtifactKind.UNKNOWN

    def _build_candidates(
        self,
        configuration: AppConfiguration,
        deep_home_search: bool,
    ) -> tuple[list[ScanCandidate], list[str]]:
        candidates = self._default_candidates(configuration.name)
        configured_candidates, configured_errors = self._configured_candidates(
            configuration
        )
        candidates.extend(configured_candidates)

        deep_candidates: list[ScanCandidate] = []
        deep_errors: list[str] = []
        if deep_home_search:
            deep_candidates, deep_errors = self._deep_home_candidates(
                configuration.name
            )
            candidates.extend(deep_candidates)

        all_errors = [*configured_errors, *deep_errors]
        return candidates, all_errors

    def _default_candidates(self, app_name: str) -> list[ScanCandidate]:
        home = self._fs.home()
        name_candidates = self._name_candidates(app_name)
        bundle_candidates = self._bundle_candidates(app_name, name_candidates)
        app_titles = self._unique(
            self._strip_app_suffix(candidate) for candidate in name_candidates
        )
        bundle_names = self._unique(f"{title}.app" for title in app_titles if title)

        combined_names = list(name_candidates) + list(bundle_candidates)
        candidates: list[ScanCandidate] = []

        def add_candidate(
            path: Path,
            category: ArtifactCategory,
            scope: ArtifactScope,
            safety: RemovalSafety,
            note: str,
        ) -> None:
            candidates.append(
                ScanCandidate(
                    path=path,
                    category=category,
                    scope=scope,
                    removal_safety=safety,
                    notes=(note,),
                )
            )

        application_roots = [
            (
                Path("/Applications"),
                ArtifactScope.SYSTEM,
                "System Applications directory",
            ),
            (
                Path("/Applications/Utilities"),
                ArtifactScope.SYSTEM,
                "System Utilities directory",
            ),
            (
                Path("/System/Applications"),
                ArtifactScope.SYSTEM,
                "System managed Applications directory",
            ),
            (
                Path("/System/Applications/Utilities"),
                ArtifactScope.SYSTEM,
                "System managed Utilities directory",
            ),
            (Path("/Applications/Setapp"), ArtifactScope.SYSTEM, "Setapp directory"),
            (
                home / "Applications",
                ArtifactScope.DEFAULT,
                "User Applications directory",
            ),
        ]

        for root, scope, note in application_roots:
            for bundle in bundle_names:
                add_candidate(
                    root / bundle,
                    ArtifactCategory.APPLICATION,
                    scope,
                    RemovalSafety.CAUTION,
                    note,
                )
            for title in app_titles:
                add_candidate(
                    root / title,
                    ArtifactCategory.APPLICATION,
                    scope,
                    RemovalSafety.CAUTION,
                    note,
                )

        shared_root = Path("/Users/Shared")
        for title in app_titles:
            add_candidate(
                shared_root / title,
                ArtifactCategory.SUPPORT,
                ArtifactScope.SYSTEM,
                RemovalSafety.CAUTION,
                "Shared user directory",
            )

        support_roots = [
            (
                home / "Library" / "Application Support",
                ArtifactScope.DEFAULT,
                "User Application Support location",
            ),
            (
                Path("/Library/Application Support"),
                ArtifactScope.SYSTEM,
                "System Application Support location",
            ),
        ]
        for root, scope, note in support_roots:
            for candidate_name in combined_names:
                add_candidate(
                    root / candidate_name,
                    ArtifactCategory.SUPPORT,
                    scope,
                    RemovalSafety.CAUTION,
                    note,
                )

        preference_roots = [
            (
                home / "Library" / "Preferences",
                ArtifactScope.DEFAULT,
                "User preferences plist",
            ),
            (
                Path("/Library/Preferences"),
                ArtifactScope.SYSTEM,
                "System preferences plist",
            ),
        ]
        preference_targets = self._unique(
            list(name_candidates) + [f"{bundle}.plist" for bundle in bundle_candidates]
        )
        for root, scope, note in preference_roots:
            for target in preference_targets:
                suffix = target if target.endswith(".plist") else f"{target}.plist"
                add_candidate(
                    root / suffix,
                    ArtifactCategory.PREFERENCES,
                    scope,
                    RemovalSafety.CAUTION,
                    note,
                )

        launch_roots = [
            (
                home / "Library" / "LaunchAgents",
                ArtifactScope.DEFAULT,
                "User LaunchAgents plist",
            ),
            (
                Path("/Library/LaunchAgents"),
                ArtifactScope.SYSTEM,
                "System LaunchAgents plist",
            ),
            (
                Path("/Library/LaunchDaemons"),
                ArtifactScope.SYSTEM,
                "System LaunchDaemons plist",
            ),
        ]
        for root, scope, note in launch_roots:
            for candidate_name in combined_names:
                add_candidate(
                    root / f"{candidate_name}.plist",
                    ArtifactCategory.LAUNCH_AGENT,
                    scope,
                    RemovalSafety.CAUTION,
                    note,
                )

        cache_roots = [
            (home / "Library" / "Caches", ArtifactScope.DEFAULT, "User caches"),
            (Path("/Library/Caches"), ArtifactScope.SYSTEM, "System caches"),
        ]
        for root, scope, note in cache_roots:
            for candidate_name in combined_names:
                add_candidate(
                    root / candidate_name,
                    ArtifactCategory.CACHE,
                    scope,
                    RemovalSafety.SAFE,
                    note,
                )

        log_roots = [
            (home / "Library" / "Logs", ArtifactScope.DEFAULT, "User logs"),
            (Path("/Library/Logs"), ArtifactScope.SYSTEM, "System logs"),
        ]
        for root, scope, note in log_roots:
            for candidate_name in combined_names:
                add_candidate(
                    root / candidate_name,
                    ArtifactCategory.LOGS,
                    scope,
                    RemovalSafety.SAFE,
                    note,
                )

        saved_state_roots = [
            (
                home / "Library" / "Saved Application State",
                ArtifactScope.DEFAULT,
                "User saved application state",
            ),
            (
                Path("/Library/Saved Application State"),
                ArtifactScope.SYSTEM,
                "System saved application state",
            ),
        ]
        for root, scope, note in saved_state_roots:
            for bundle in bundle_candidates:
                add_candidate(
                    root / f"{bundle}.savedState",
                    ArtifactCategory.SUPPORT,
                    scope,
                    RemovalSafety.CAUTION,
                    note,
                )

        container_roots = [
            (
                home / "Library" / "Containers",
                ArtifactScope.DEFAULT,
                "User application containers",
            ),
            (
                home / "Library" / "Group Containers",
                ArtifactScope.DEFAULT,
                "User group containers",
            ),
            (
                home / "Library" / "Application Scripts",
                ArtifactScope.DEFAULT,
                "User application scripts",
            ),
        ]
        for root, scope, note in container_roots:
            for bundle in bundle_candidates:
                add_candidate(
                    root / bundle,
                    ArtifactCategory.SUPPORT,
                    scope,
                    RemovalSafety.CAUTION,
                    note,
                )

        return candidates

    def _deep_home_candidates(
        self, app_name: str
    ) -> tuple[list[ScanCandidate], list[str]]:
        home = self._fs.home()
        pattern = re.compile(re.escape(app_name), re.IGNORECASE)
        candidates: list[ScanCandidate] = []
        errors: list[str] = []
        max_matches = 500

        def _onerror(exc: OSError) -> None:
            errors.append(
                f"Deep home search encountered an error at {exc.filename}: {exc.strerror}"
            )

        match_count = 0
        truncated = False
        for root, dirnames, filenames in os.walk(home, onerror=_onerror):
            if truncated:
                break
            for entry in dirnames:
                if pattern.search(entry):
                    candidate_path = Path(root) / entry
                    candidates.append(
                        ScanCandidate(
                            path=candidate_path,
                            category=ArtifactCategory.OTHER,
                            scope=ArtifactScope.DISCOVERED,
                            removal_safety=RemovalSafety.REVIEW,
                            notes=("Deep home search match",),
                        )
                    )
                    match_count += 1
                    if match_count >= max_matches:
                        truncated = True
                        errors.append("Deep home search truncated after 500 matches.")
                        break
            if truncated:
                break
            for entry in filenames:
                if pattern.search(entry):
                    candidate_path = Path(root) / entry
                    candidates.append(
                        ScanCandidate(
                            path=candidate_path,
                            category=ArtifactCategory.OTHER,
                            scope=ArtifactScope.DISCOVERED,
                            removal_safety=RemovalSafety.REVIEW,
                            notes=("Deep home search match",),
                        )
                    )
                    match_count += 1
                    if match_count >= max_matches:
                        truncated = True
                        errors.append("Deep home search truncated after 500 matches.")
                        break

        return candidates, errors

    def _configured_candidates(
        self,
        configuration: AppConfiguration,
    ) -> tuple[list[ScanCandidate], list[str]]:
        candidates: list[ScanCandidate] = []
        errors: list[str] = []

        for location in configuration.additional_locations:
            candidates.append(
                ScanCandidate(
                    path=location,
                    category=ArtifactCategory.OTHER,
                    scope=ArtifactScope.CONFIGURED,
                    removal_safety=RemovalSafety.REVIEW,
                    notes=("Configured additional location",),
                )
            )

        for pattern in configuration.patterns:
            expanded = os.path.expanduser(os.path.expandvars(pattern))
            matches = list(glob.iglob(expanded, recursive=True))
            if matches:
                for match in matches:
                    candidates.append(
                        ScanCandidate(
                            path=Path(match),
                            category=ArtifactCategory.OTHER,
                            scope=ArtifactScope.CONFIGURED,
                            removal_safety=RemovalSafety.REVIEW,
                            notes=(f"Matched configured pattern '{pattern}'",),
                        )
                    )
            else:
                errors.append(f"Pattern '{pattern}' did not match any paths.")

        return candidates, errors

    def _name_candidates(self, app_name: str) -> tuple[str, ...]:
        normalized = re.sub(r"[^A-Za-z0-9]+", "", app_name)
        spaced_lower = app_name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", spaced_lower).strip("-")
        compact = normalized.lower() if normalized else spaced_lower.replace(" ", "")

        candidates = [
            app_name,
            self._strip_app_suffix(app_name),
            spaced_lower,
            self._strip_app_suffix(spaced_lower),
            app_name.replace(" ", ""),
            spaced_lower.replace(" ", ""),
            app_name.replace(" ", "-"),
            spaced_lower.replace(" ", "-"),
            app_name.replace(" ", "_"),
            spaced_lower.replace(" ", "_"),
            slug.replace("-", ""),
            slug,
            compact,
        ]
        return tuple(self._unique(candidates))

    def _bundle_candidates(
        self,
        app_name: str,
        name_candidates: Sequence[str],
    ) -> tuple[str, ...]:
        normalized = re.sub(r"[^A-Za-z0-9]+", "", app_name)
        spaced_lower = app_name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", spaced_lower).strip("-")
        compact = normalized.lower() if normalized else spaced_lower.replace(" ", "")

        raw_candidates: list[str] = [
            compact,
            slug.replace("-", "."),
            f"com.{compact}" if compact else "",
        ]
        raw_candidates.extend(
            candidate for candidate in name_candidates if candidate.startswith("com.")
        )
        raw_candidates.extend(
            f"com.{candidate}"
            for candidate in name_candidates
            if candidate and not candidate.startswith("com.")
        )

        bundle_candidates = self._unique(raw_candidates)
        if not bundle_candidates:
            bundle_candidates = (
                [compact]
                if compact
                else [candidate for candidate in name_candidates if candidate]
            )
        return tuple(bundle_candidates)

    @staticmethod
    def _strip_app_suffix(value: str) -> str:
        if value.lower().endswith(".app"):
            return value[: -len(".app")]
        return value

    @staticmethod
    def _unique(values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for raw in values:
            cleaned = raw.strip()
            if not cleaned:
                continue
            if cleaned in seen:
                continue
            ordered.append(cleaned)
            seen.add(cleaned)
        return ordered


__all__ = ["Scanner", "Filesystem", "LocalFilesystem", "ScanCandidate"]
