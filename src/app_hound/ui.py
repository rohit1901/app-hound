from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, fields, replace
from typing import Any, Iterable, Iterator, Sized, TypeVar

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

T = TypeVar("T")


@dataclass(frozen=True)
class ColorPalette:
    """Defines the styles used across the console output layer."""

    accent: str = "bold cyan"
    info: str = "cyan"
    success: str = "bold green"
    warning: str = "bold yellow"
    error: str = "bold red"
    highlight: str = "bold magenta"
    muted: str = "dim"
    progress_bar: str = "magenta"
    progress_complete: str = "green"
    progress_description: str = "cyan"

    def with_overrides(self, **styles: str) -> "ColorPalette":
        """Return a new palette with a subset of styles overridden."""
        valid = {field.name for field in fields(self)}
        applied = {
            key: value for key, value in styles.items() if key in valid and value
        }
        if not applied:
            return self
        return replace(self, **applied)

    def get(self, key: str, *, default: str | None = None) -> str | None:
        """Return a style value if it exists on the palette."""
        if hasattr(self, key):
            value = getattr(self, key)
            if isinstance(value, str):
                return value
        return default


DEFAULT_PALETTE = ColorPalette()


class SilentProgressTask:
    """No-op progress task used when quiet mode is active."""

    def advance(self, amount: float = 1.0) -> None:
        return None

    def update(
        self,
        *,
        total: float | None = None,
        completed: float | None = None,
        description: str | None = None,
        refresh: bool = False,
    ) -> None:
        return None

    def stop(self) -> None:
        return None

    @property
    def completed(self) -> float:
        return 0.0

    @property
    def total(self) -> float | None:
        return None


class ProgressTask:
    """Wrapper providing a stable API around Rich progress tasks."""

    def __init__(self, progress: Progress, task_id: TaskID) -> None:
        self._progress = progress
        self._task_id = task_id

    def advance(self, amount: float = 1.0) -> None:
        self._progress.advance(self._task_id, amount)

    def update(
        self,
        *,
        total: float | None = None,
        completed: float | None = None,
        description: str | None = None,
        refresh: bool = True,
    ) -> None:
        kwargs: dict[str, Any] = {}
        if total is not None:
            kwargs["total"] = total
        if completed is not None:
            kwargs["completed"] = completed
        if description is not None:
            kwargs["description"] = description
        self._progress.update(self._task_id, **kwargs)
        if refresh:
            self._progress.refresh()

    def stop(self) -> None:
        self._progress.stop_task(self._task_id)

    @property
    def completed(self) -> float:
        task = self._progress.tasks[self._task_id]
        return float(task.completed)

    @property
    def total(self) -> float | None:
        task = self._progress.tasks[self._task_id]
        return float(task.total) if task.total is not None else None


class OutputManager:
    """Centralizes console styling, quiet mode, and progress reporting."""

    def __init__(
        self,
        *,
        console: Console | None = None,
        palette: ColorPalette | None = None,
        quiet: bool = False,
        show_progress: bool = True,
    ) -> None:
        self._console = console or Console()
        self._palette = palette or DEFAULT_PALETTE
        self._quiet = quiet
        self._show_progress = show_progress

    @property
    def console(self) -> Console:
        return self._console

    @property
    def palette(self) -> ColorPalette:
        return self._palette

    @property
    def quiet(self) -> bool:
        return self._quiet

    @property
    def show_progress(self) -> bool:
        return self._show_progress

    def set_palette(self, palette: ColorPalette) -> None:
        self._palette = palette

    def update_palette(self, **styles: str) -> None:
        self._palette = self._palette.with_overrides(**styles)

    def set_quiet(self, quiet: bool) -> None:
        self._quiet = quiet

    def set_show_progress(self, show: bool) -> None:
        self._show_progress = show

    @contextmanager
    def temporarily(
        self,
        *,
        quiet: bool | None = None,
        palette: ColorPalette | None = None,
        show_progress: bool | None = None,
    ) -> Iterator["OutputManager"]:
        original_quiet = self._quiet
        original_palette = self._palette
        original_show_progress = self._show_progress
        if quiet is not None:
            self._quiet = quiet
        if palette is not None:
            self._palette = palette
        if show_progress is not None:
            self._show_progress = show_progress
        try:
            yield self
        finally:
            self._quiet = original_quiet
            self._palette = original_palette
            self._show_progress = original_show_progress

    def _resolve_style(
        self,
        *,
        style: str | None = None,
        palette_key: str | None = None,
        highlight: bool = False,
    ) -> str | None:
        if style:
            return style
        if palette_key:
            palette_value = self._palette.get(palette_key)
            if palette_value:
                return palette_value
        if highlight:
            return self._palette.highlight
        return None

    def stylize(
        self,
        message: str,
        *,
        style: str | None = None,
        palette_key: str | None = None,
        highlight: bool = False,
    ) -> str:
        resolved = self._resolve_style(
            style=style, palette_key=palette_key, highlight=highlight
        )
        if resolved:
            return f"[{resolved}]{message}[/{resolved}]"
        return message

    def print(
        self,
        message: str,
        *,
        style: str | None = None,
        palette_key: str | None = None,
        emoji: str | None = None,
        highlight: bool = False,
        force: bool = False,
    ) -> None:
        if self._quiet and not force:
            return
        text = f"{emoji} {message}" if emoji else message
        applied_style = self._resolve_style(
            style=style, palette_key=palette_key, highlight=highlight
        )
        self._console.print(text, style=applied_style)

    def info(self, message: str, *, emoji: str = "ℹ️", force: bool = False) -> None:
        self.print(message, style=self._palette.info, emoji=emoji, force=force)

    def success(self, message: str, *, emoji: str = "✅", force: bool = False) -> None:
        self.print(message, style=self._palette.success, emoji=emoji, force=force)

    def warning(self, message: str, *, emoji: str = "⚠️", force: bool = False) -> None:
        self.print(message, style=self._palette.warning, emoji=emoji, force=force)

    def error(self, message: str, *, emoji: str = "❌", force: bool = False) -> None:
        self.print(message, style=self._palette.error, emoji=emoji, force=force)

    def highlight(
        self, message: str, *, emoji: str = "🌟", force: bool = False
    ) -> None:
        self.print(message, style=self._palette.highlight, emoji=emoji, force=force)

    def muted(self, message: str, *, emoji: str | None = None) -> None:
        self.print(message, style=self._palette.muted, emoji=emoji)

    def rule(self, title: str, *, force: bool = False) -> None:
        if self._quiet and not force:
            return
        style = self._palette.accent
        self._console.rule(f"[{style}]{title}[/{style}]")

    @contextmanager
    def status(self, message: str) -> Iterator[None]:
        if self._quiet:
            yield
            return
        style = self._palette.accent
        with self._console.status(f"[{style}]{message}[/{style}]"):
            yield

    @contextmanager
    def progress(
        self,
        description: str,
        *,
        total: float | None = None,
        transient: bool = False,
    ) -> Iterator[ProgressTask | SilentProgressTask]:
        if self._quiet or not self._show_progress:
            yield SilentProgressTask()
            return
        progress = Progress(
            SpinnerColumn(style=self._palette.accent),
            TextColumn("{task.description}", style=self._palette.progress_description),
            BarColumn(
                bar_width=None,
                style=self._palette.progress_bar,
                complete_style=self._palette.progress_complete,
                finished_style=self._palette.progress_complete,
                pulse_style=self._palette.progress_bar,
            ),
            TimeElapsedColumn(),
            console=self._console,
            transient=transient,
        )
        with progress as live_progress:
            task_id = live_progress.add_task(description, total=total)
            yield ProgressTask(live_progress, task_id)

    def track(
        self,
        iterable: Iterable[T],
        description: str,
        *,
        total: int | None = None,
        transient: bool = False,
    ) -> Iterator[T]:
        if self._quiet or not self._show_progress:
            for item in iterable:
                yield item
            return
        inferred_total = total
        if inferred_total is None and isinstance(iterable, Sized):
            inferred_total = len(iterable)
        with self.progress(
            description,
            total=None if inferred_total == 0 else inferred_total,
            transient=transient,
        ) as task:
            if inferred_total == 0:
                task.update(total=1.0)
            for item in iterable:
                yield item
                task.advance(1.0)

    def finalize(self, message: str) -> None:
        """Display wrapping message unless quiet mode suppresses output."""
        if self._quiet:
            return
        self.print(message, style=self._palette.accent, emoji="🐶")


__all__ = [
    "ColorPalette",
    "DEFAULT_PALETTE",
    "OutputManager",
    "ProgressTask",
    "SilentProgressTask",
]
