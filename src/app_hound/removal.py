from __future__ import annotations

import json
import os
import stat
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .domain import (
    Artifact,
    ArtifactCategory,
    ArtifactKind,
    ArtifactScope,
    RemovalSafety,
    ScanResult,
)

# Public types and utilities for planning and performing removals.


@dataclass(frozen=True)
class PlanEntry:
    """
    A single actionable deletion target derived from an Artifact.

    The plan normalizes the artifact metadata into a command suggestion,
    reason/safety notes, and whether the action should be considered enabled
    by default (e.g., caches are often SAFE, preferences are CAUTION).
    """

    app_name: str
    path: Path
    kind: ArtifactKind
    category: ArtifactCategory
    scope: ArtifactScope
    exists: bool
    writable: bool | None
    removal_safety: RemovalSafety
    notes: tuple[str, ...] = field(default_factory=tuple)
    removal_instructions: tuple[str, ...] = field(default_factory=tuple)
    enabled: bool = False

    def suggested_command(self) -> str:
        """
        Return a suggested shell command for removing the entry safely.

        - Directories: `rm -rf "path"`
        - Files/symlinks: `rm -f "path"`
        """
        quoted = shell_quote(str(self.path))
        if self.kind == ArtifactKind.DIRECTORY:
            return f"rm -rf {quoted}"
        # Treat unknown as file for conservative default
        return f"rm -f {quoted}"

    def to_dict(self) -> dict[str, object]:
        return {
            "app_name": self.app_name,
            "path": str(self.path),
            "kind": self.kind.value,
            "category": self.category.value,
            "scope": self.scope.value,
            "exists": self.exists,
            "writable": self.writable,
            "removal_safety": self.removal_safety.value,
            "notes": list(self.notes),
            "removal_instructions": list(self.removal_instructions),
            "enabled": self.enabled,
            "suggested_command": self.suggested_command(),
        }


@dataclass(frozen=True)
class DeletionPlan:
    """
    A deletion plan groups actionable entries per application and captures
    metadata useful for rendering or executing removal scripts.
    """

    generated_at: datetime
    entries: tuple[PlanEntry, ...] = field(default_factory=tuple)

    def for_app(self, app_name: str) -> tuple[PlanEntry, ...]:
        return tuple(entry for entry in self.entries if entry.app_name == app_name)

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def enabled_entries(self) -> tuple[PlanEntry, ...]:
        return tuple(entry for entry in self.entries if entry.enabled)

    @staticmethod
    def from_scan_results(
        results: Sequence[ScanResult],
        *,
        enable_policy: Callable[[Artifact], bool] | None = None,
    ) -> DeletionPlan:
        """
        Build a plan from scanner results.

        The `enable_policy` determines which artifacts should be enabled by default
        (e.g., caches and logs might be enabled, preferences often CAUTION).
        If omitted, a sensible default is used:
          - SAFE -> enabled
          - CAUTION/REVIEW -> disabled
        """
        entries: list[PlanEntry] = []
        for result in results:
            for artifact in result.artifacts:
                enabled = _default_enable_policy(artifact)
                if enable_policy is not None:
                    try:
                        enabled = bool(enable_policy(artifact))
                    except Exception:
                        # Defensive: if a custom policy fails, fall back to default.
                        enabled = _default_enable_policy(artifact)
                entries.append(
                    PlanEntry(
                        app_name=artifact.app_name,
                        path=artifact.path,
                        kind=artifact.kind,
                        category=artifact.category,
                        scope=artifact.scope,
                        exists=artifact.exists,
                        writable=artifact.writable,
                        removal_safety=artifact.removal_safety,
                        notes=artifact.notes,
                        removal_instructions=artifact.removal_instructions,
                        enabled=enabled,
                    )
                )
        return DeletionPlan(
            generated_at=datetime.now(timezone.utc), entries=tuple(entries)
        )


def _default_enable_policy(artifact: Artifact) -> bool:
    """
    Default decision for enabling deletion:
      - Enable deletion for SAFE artifacts (e.g., caches, logs)
      - Disable for CAUTION/REVIEW
      - Only consider entries that currently exist
    """
    if not artifact.exists:
        return False
    return artifact.removal_safety == RemovalSafety.SAFE


class ArtifactRemover:
    """
    ArtifactRemover encapsulates the deletion pipeline with dry-run support,
    per-entry prompting, and error reporting.

    It operates over a DeletionPlan (or iterables of PlanEntry) so it is agnostic
    of how artifacts were discovered and modeled.
    """

    def __init__(
        self,
        *,
        output: ConsoleLike | None = None,
        command_runner: CommandRunner | None = None,
    ) -> None:
        self._out: ConsoleLike = output or _SilentConsole()
        self._run: CommandRunner = command_runner or _default_command_runner

    def remove(
        self,
        entries: Iterable[PlanEntry],
        *,
        dry_run: bool = True,
        prompt: bool = False,
        force: bool = False,
        stop_on_error: bool = False,
    ) -> RemovalReport:
        """
        Execute removals for the provided entries.

        - dry_run: if True, no filesystem modifications are made; only prints actions.
        - prompt: if True, ask the user to confirm each enabled entry.
        - force: if True, ignore `enabled` and attempt all existing entries.
        - stop_on_error: if True, abort on the first failure.

        Returns a RemovalReport summarizing successes and failures.
        """
        succeeded: list[PlanEntry] = []
        failed: list[tuple[PlanEntry, str]] = []
        skipped: list[PlanEntry] = []

        for entry in entries:
            should_attempt = (entry.enabled or force) and entry.exists
            if not should_attempt:
                skipped.append(entry)
                continue

            if prompt:
                response = input(f"Delete {entry.path}? [y/N] ").strip().lower()
                if response not in ("y", "yes"):
                    self._out.info(f"Skipped (user choice): {entry.path}")
                    skipped.append(entry)
                    continue

            cmd = entry.suggested_command()
            if dry_run:
                self._out.highlight(f"DRY-RUN → {cmd}")
                succeeded.append(entry)
                continue

            # Execute removal safely
            try:
                # Prefer Python-based removal for better error handling
                self._python_remove(entry)
                self._out.success(f"Removed: {entry.path}")
                succeeded.append(entry)
            except Exception as exc:
                msg = f"{exc.__class__.__name__}: {exc}"
                self._out.error(f"Failed to remove {entry.path} — {msg}")
                failed.append((entry, msg))
                if stop_on_error:
                    break

        return RemovalReport(
            succeeded=tuple(succeeded),
            failed=tuple(failed),
            skipped=tuple(skipped),
        )

    def _python_remove(self, entry: PlanEntry) -> None:
        """
        Perform removal using Python primitives (os.unlink / os.rmdir / shutil.rmtree),
        with basic permission adjustments if needed.
        """
        path = entry.path
        # Refresh existence and writability just-in-time
        if not path.exists() and not path.is_symlink():
            # Symlinks that broke (.exists False) can still be unlinked
            raise FileNotFoundError(str(path))

        # Ensure writable if possible (best-effort)
        try:
            make_writable_best_effort(path)
        except Exception:
            # Continue even if we fail to change permissions; the removal may still succeed.
            pass

        # Decide removal by kind; watch for symlinks
        if path.is_symlink() or entry.kind == ArtifactKind.SYMLINK:
            os.unlink(path)
            return

        # Directories vs files
        if entry.kind == ArtifactKind.DIRECTORY or path.is_dir():
            # Use shutil.rmtree for directories (more robust than os.rmdir)
            import shutil

            shutil.rmtree(path)
            return

        # Files and unknown defaults to unlink
        os.unlink(path)


# Simple console abstraction to avoid coupling to the UI layer while still
# providing user-friendly messages in a CLI context. This mirrors OutputManager
# semantics lightly without importing rich or app-hound's presenter directly.


class ConsoleLike:
    def info(self, message: str) -> None: ...
    def success(self, message: str) -> None: ...
    def warning(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...
    def highlight(self, message: str) -> None: ...


class _SilentConsole(ConsoleLike):
    def info(self, message: str) -> None:
        return None

    def success(self, message: str) -> None:
        return None

    def warning(self, message: str) -> None:
        return None

    def error(self, message: str) -> None:
        return None

    def highlight(self, message: str) -> None:
        return None


CommandRunner = Callable[[list[str]], int]


def _default_command_runner(args: list[str]) -> int:
    """
    Default command runner fallback. Prefer Python filesystem APIs; this is here
    for potential future shell-based paths.
    """
    import subprocess

    return subprocess.call(args)


@dataclass(frozen=True)
class RemovalReport:
    """
    Summary of a removal run, including successes, failures (with messages), and skips.
    """

    succeeded: tuple[PlanEntry, ...]
    failed: tuple[tuple[PlanEntry, str], ...]
    skipped: tuple[PlanEntry, ...]


def shell_quote(value: str) -> str:
    """
    Quote a string for safe inclusion in shell commands.
    """
    # Use shlex.quote for portability
    import shlex

    return shlex.quote(value)


def make_writable_best_effort(path: Path) -> None:
    """
    Attempt to make a file/directory writable (best-effort).
    """
    try:
        mode = path.stat().st_mode
        # Add user write bit
        os.chmod(path, mode | stat.S_IWUSR)
    except Exception:
        # Ignore failures silently; deletion may still work or be handled upstream.
        pass


def generate_plan_from_artifacts(
    artifacts: Iterable[Artifact],
    *,
    enable_policy: Callable[[Artifact], bool] | None = None,
) -> DeletionPlan:
    """
    Build a DeletionPlan directly from an iterable of artifacts.
    """
    # Wrap artifacts into a pseudo ScanResult to reuse the factory
    pseudo_result = ScanResult(
        app_name="(plan)",
        artifacts=tuple(artifacts),
        errors=tuple(),
    )
    return DeletionPlan.from_scan_results((pseudo_result,), enable_policy=enable_policy)


def iter_shell_script_lines(
    plan: DeletionPlan,
    *,
    include_header: bool = True,
    only_enabled: bool = True,
    prompt_each: bool = True,
) -> Iterator[str]:
    """
    Yield lines of a portable bash script that performs deletions from a plan.

    - include_header: include shebang and safety prologue.
    - only_enabled: if True, include only entries with enabled=True.
    - prompt_each: if True, prompt before deleting each entry.
    """
    if include_header:
        yield "#!/usr/bin/env bash"
        yield "set -euo pipefail"
        yield ""
        yield "# app-hound deletion plan"
        yield f"# generated_at: {plan.generated_at.isoformat()}"
        yield ""
        yield "confirm() {"
        yield '  read -r -p "$1 [y/N] " response'
        yield '  case "$response" in'
        yield "    [yY][eE][sS]|[yY]) true ;;"
        yield "    *) false ;;"
        yield "  esac"
        yield "}"
        yield ""

    entries = plan.enabled_entries() if only_enabled else plan.entries
    for entry in entries:
        quoted = shell_quote(str(entry.path))
        cmd = entry.suggested_command()
        yield f"# {entry.app_name} — {entry.category.value} ({entry.removal_safety.value})"
        for note in entry.notes:
            yield f"# note: {note}"
        for instr in entry.removal_instructions:
            yield f"# instruction: {instr}"
        if prompt_each:
            yield f'if confirm "Delete {quoted}?"; then'
            yield f"  {cmd}"
            yield "fi"
        else:
            yield f"{cmd}"
        yield ""

    yield "# End of deletion plan"


def write_shell_script(
    plan: DeletionPlan,
    output_path: Path,
    *,
    only_enabled: bool = True,
    prompt_each: bool = True,
    executable: bool = True,
) -> Path:
    """
    Write a deletion shell script to disk from the plan and optionally mark it executable.
    """
    lines = list(
        iter_shell_script_lines(
            plan,
            include_header=True,
            only_enabled=only_enabled,
            prompt_each=prompt_each,
        )
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    if executable:
        mode = output_path.stat().st_mode
        os.chmod(output_path, mode | stat.S_IXUSR)
    return output_path


__all__ = [
    "PlanEntry",
    "DeletionPlan",
    "ArtifactRemover",
    "RemovalReport",
    "generate_plan_from_artifacts",
    "iter_shell_script_lines",
    "write_shell_script",
    "shell_quote",
]
