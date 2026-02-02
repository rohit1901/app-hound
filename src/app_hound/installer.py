from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Protocol


class InstallerStatus(Enum):
    """High-level summary of an installer execution attempt."""

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    MANUAL_ACTION_REQUIRED = "manual_action_required"
    ERROR = "error"


@dataclass(frozen=True)
class InstallerOutcome:
    """Result payload describing the outcome of an installer run."""

    status: InstallerStatus
    path: Path
    exit_code: int | None = None
    message: str | None = None


class InstallerFeedback(Protocol):
    """Abstraction over progress/output mechanisms (CLI, logs, etc.)."""

    def highlight(self, message: str) -> None: ...

    def info(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...


class _SilentFeedback:
    """No-op feedback implementation used when no presenter is supplied."""

    def highlight(self, message: str) -> None:  # noqa: D401 - intentionally silent
        return None

    def info(self, message: str) -> None:
        return None

    def warning(self, message: str) -> None:
        return None

    def error(self, message: str) -> None:
        return None


CommandRunner = Callable[[list[str]], int]


class InstallerRunner:
    """Encapsulates the logic required to execute macOS installers safely."""

    def __init__(
        self,
        *,
        command_runner: CommandRunner | None = None,
    ) -> None:
        self._run_command = command_runner or subprocess.call

    def run(
        self,
        installer_path: str | Path,
        *,
        feedback: InstallerFeedback | None = None,
    ) -> InstallerOutcome:
        """
        Execute the installer located at ``installer_path``.

        The method handles the common macOS extensions (.pkg, .dmg, .app) and
        gracefully reports when manual user intervention is required (e.g. DMGs).
        """
        presenter = feedback or _SilentFeedback()
        path = self._prepare_path(installer_path)

        if not path.exists():
            message = f"Installer not found at {path}"
            presenter.error(message)
            return InstallerOutcome(
                status=InstallerStatus.NOT_FOUND,
                path=path,
                message=message,
            )

        presenter.highlight(f"Launching installer at {path}")
        suffix = path.suffix.lower()

        if suffix == ".pkg":
            exit_code = self._run_command(
                ["sudo", "installer", "-pkg", str(path), "-target", "/"]
            )
            return self._handle_exit_code(
                exit_code,
                path=path,
                presenter=presenter,
                success_message="Package installed successfully.",
            )

        if suffix == ".dmg":
            message = (
                f"Manual action required: mount the DMG at {path} and complete the "
                "installation from the mounted volume."
            )
            presenter.warning(message)
            return InstallerOutcome(
                status=InstallerStatus.MANUAL_ACTION_REQUIRED,
                path=path,
                message=message,
            )

        if path.is_dir() and path.name.endswith(".app"):
            exit_code = self._run_command(["open", str(path)])
            return self._handle_exit_code(
                exit_code,
                path=path,
                presenter=presenter,
                success_message="Application bundle opened.",
            )

        exit_code = self._run_command([str(path)])
        return self._handle_exit_code(
            exit_code,
            path=path,
            presenter=presenter,
            success_message="Installer executed.",
        )

    def _handle_exit_code(
        self,
        exit_code: int,
        *,
        path: Path,
        presenter: InstallerFeedback,
        success_message: str,
    ) -> InstallerOutcome:
        if exit_code == 0:
            presenter.info(success_message)
            return InstallerOutcome(
                status=InstallerStatus.SUCCESS,
                path=path,
                exit_code=exit_code,
                message=success_message,
            )

        message = (
            f"Installer at {path} exited with a non-zero status ({exit_code}). "
            "Review the installer logs for more details."
        )
        presenter.error(message)
        return InstallerOutcome(
            status=InstallerStatus.ERROR,
            path=path,
            exit_code=exit_code,
            message=message,
        )

    @staticmethod
    def _prepare_path(installer_path: str | Path) -> Path:
        expanded = os.path.expandvars(str(installer_path))
        return Path(expanded).expanduser()


def run_installer(
    installer_path: str | Path,
    *,
    feedback: InstallerFeedback | None = None,
    command_runner: CommandRunner | None = None,
) -> InstallerOutcome:
    """
    Convenience helper that executes an installer using :class:`InstallerRunner`.
    """
    runner = InstallerRunner(command_runner=command_runner)
    return runner.run(installer_path, feedback=feedback)


__all__ = [
    "InstallerStatus",
    "InstallerOutcome",
    "InstallerFeedback",
    "InstallerRunner",
    "run_installer",
]
