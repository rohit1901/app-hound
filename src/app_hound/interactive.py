"""Interactive mode for reviewing and selecting artifacts for deletion."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from app_hound.domain import (
    Artifact,
    ArtifactCategory,
    RemovalSafety,
    ScanResult,
)
from app_hound.removal import (
    ArtifactRemover,
    ConsoleLike,
    PlanEntry,
    RemovalReport,
)


@dataclass
class InteractiveSession:
    """
    Manages an interactive artifact selection and deletion session.

    This class encapsulates the state and behavior for the TUI-based
    artifact review workflow.
    """

    results: Sequence[ScanResult]
    console: Console
    selected_indices: set[int]

    def __init__(
        self,
        results: Sequence[ScanResult],
        console: Console | None = None,
    ) -> None:
        self.results = results
        self.console = console or Console()
        self.selected_indices = set()
        self._artifacts_list = self._build_artifacts_list()

    def _build_artifacts_list(self) -> list[tuple[ScanResult, Artifact]]:
        """Build a flat list of (result, artifact) tuples for indexing."""
        artifacts = []
        for result in self.results:
            for artifact in result.artifacts:
                artifacts.append((result, artifact))
        return artifacts

    def run(self) -> RemovalReport | None:
        """
        Run the interactive session.

        Returns a RemovalReport if deletions were executed, None otherwise.
        """
        if not self._artifacts_list:
            self.console.print(
                "[yellow]No artifacts found to review.[/yellow]",
                emoji=True,
            )
            return None

        self._show_welcome()

        while True:
            self._display_artifacts()
            action = self._prompt_action()

            if action == "quit":
                self.console.print("[cyan]Exiting without changes.[/cyan]")
                return None
            elif action == "select":
                self._select_artifacts()
            elif action == "deselect":
                self._deselect_artifacts()
            elif action == "select_all":
                self._select_all()
            elif action == "deselect_all":
                self._deselect_all()
            elif action == "filter":
                self._apply_filters()
            elif action == "delete":
                return self._execute_deletion()

    def _show_welcome(self) -> None:
        """Display welcome message and instructions."""
        welcome = Panel(
            "[bold cyan]🐶 Interactive Artifact Review[/bold cyan]\n\n"
            + "Review artifacts discovered during the scan.\n"
            + "Select items to delete, then execute the deletion plan.\n\n"
            + "[dim]Use arrow keys and number selections to navigate.[/dim]",
            border_style="cyan",
        )
        self.console.print(welcome)
        self.console.print()

    def _display_artifacts(self) -> None:
        """Display artifacts in a table format."""
        table = Table(
            title="📦 Discovered Artifacts",
            show_header=True,
            header_style="bold magenta",
            border_style="blue",
        )

        table.add_column("#", justify="right", style="dim", width=5)
        table.add_column("✓", justify="center", width=3)
        table.add_column("App", style="cyan", width=15)
        table.add_column("Category", width=12)
        table.add_column("Safety", width=10)
        table.add_column("Path", style="white", overflow="fold")
        table.add_column("Size", justify="right", width=10)
        table.add_column("Status", justify="center", width=8)

        for idx, (result, artifact) in enumerate(self._artifacts_list):
            selected = "✓" if idx in self.selected_indices else " "

            # Style based on removal safety
            safety_style = self._get_safety_style(artifact.removal_safety)
            category_style = self._get_category_style(artifact.category)

            # Format size
            size_str = (
                self._format_size(artifact.size_bytes) if artifact.size_bytes else "-"
            )

            # Status indicator
            status = "✓" if artifact.exists else "✗"
            status_style = "green" if artifact.exists else "red"

            table.add_row(
                str(idx),
                selected,
                artifact.app_name[:15],
                f"[{category_style}]{artifact.category.value}[/{category_style}]",
                f"[{safety_style}]{artifact.removal_safety.value}[/{safety_style}]",
                str(artifact.path),
                size_str,
                f"[{status_style}]{status}[/{status_style}]",
            )

        self.console.print(table)
        self._display_summary()

    def _display_summary(self) -> None:
        """Display selection summary."""
        total = len(self._artifacts_list)
        selected = len(self.selected_indices)

        # Calculate total size of selected items
        total_size = sum(
            artifact.size_bytes or 0
            for idx, (_, artifact) in enumerate(self._artifacts_list)
            if idx in self.selected_indices and artifact.exists
        )

        summary = (
            f"[bold]Selected:[/bold] {selected}/{total} artifacts | "
            f"[bold]Space to free:[/bold] {self._format_size(total_size)}"
        )

        self.console.print()
        self.console.print(Panel(summary, border_style="green"))
        self.console.print()

    def _prompt_action(self) -> str:
        """Prompt user for next action."""
        self.console.print("[bold]Actions:[/bold]")
        self.console.print("  [cyan]s[/cyan] - Select artifacts")
        self.console.print("  [cyan]d[/cyan] - Deselect artifacts")
        self.console.print("  [cyan]a[/cyan] - Select all")
        self.console.print("  [cyan]n[/cyan] - Deselect all")
        self.console.print("  [cyan]f[/cyan] - Filter artifacts")
        self.console.print("  [cyan]x[/cyan] - Execute deletion")
        self.console.print("  [cyan]q[/cyan] - Quit without changes")
        self.console.print()

        action = Prompt.ask(
            "Choose action",
            choices=["s", "d", "a", "n", "f", "x", "q"],
            default="s",
        )

        action_map = {
            "s": "select",
            "d": "deselect",
            "a": "select_all",
            "n": "deselect_all",
            "f": "filter",
            "x": "delete",
            "q": "quit",
        }

        return action_map[action]

    def _select_artifacts(self) -> None:
        """Prompt user to select artifacts by index."""
        self.console.print(
            "[cyan]Enter artifact numbers to select (comma-separated, or range like 0-5):[/cyan]"
        )
        selection = Prompt.ask("Selection", default="")

        if not selection.strip():
            return

        indices = self._parse_selection(selection)
        self.selected_indices.update(indices)
        self.console.print(f"[green]Selected {len(indices)} artifact(s)[/green]")

    def _deselect_artifacts(self) -> None:
        """Prompt user to deselect artifacts by index."""
        self.console.print(
            "[cyan]Enter artifact numbers to deselect (comma-separated, or range like 0-5):[/cyan]"
        )
        selection = Prompt.ask("Selection", default="")

        if not selection.strip():
            return

        indices = self._parse_selection(selection)
        self.selected_indices.difference_update(indices)
        self.console.print(f"[yellow]Deselected {len(indices)} artifact(s)[/yellow]")

    def _select_all(self) -> None:
        """Select all artifacts."""
        self.selected_indices = set(range(len(self._artifacts_list)))
        self.console.print("[green]Selected all artifacts[/green]")

    def _deselect_all(self) -> None:
        """Deselect all artifacts."""
        self.selected_indices.clear()
        self.console.print("[yellow]Deselected all artifacts[/yellow]")

    def _apply_filters(self) -> None:
        """Apply filters to artifact selection."""
        self.console.print("[bold cyan]Filter Options:[/bold cyan]")
        self.console.print("  [cyan]1[/cyan] - Select by app name")
        self.console.print("  [cyan]2[/cyan] - Select by category")
        self.console.print("  [cyan]3[/cyan] - Select by safety level")
        self.console.print("  [cyan]4[/cyan] - Select safe items only")
        self.console.print("  [cyan]5[/cyan] - Cancel")

        choice = Prompt.ask(
            "Filter type", choices=["1", "2", "3", "4", "5"], default="5"
        )

        if choice == "1":
            self._filter_by_app()
        elif choice == "2":
            self._filter_by_category()
        elif choice == "3":
            self._filter_by_safety()
        elif choice == "4":
            self._select_safe_items()

    def _filter_by_app(self) -> None:
        """Filter artifacts by app name."""
        app_names = sorted(set(result.app_name for result in self.results))

        self.console.print("[cyan]Available apps:[/cyan]")
        for idx, name in enumerate(app_names):
            self.console.print(f"  {idx}: {name}")

        selection = Prompt.ask("Select app number", default="0")

        try:
            app_idx = int(selection)
            if 0 <= app_idx < len(app_names):
                app_name = app_names[app_idx]
                indices = {
                    idx
                    for idx, (result, _) in enumerate(self._artifacts_list)
                    if result.app_name == app_name
                }
                self.selected_indices.update(indices)
                self.console.print(
                    f"[green]Selected {len(indices)} artifact(s) for {app_name}[/green]"
                )
        except ValueError:
            self.console.print("[red]Invalid selection[/red]")

    def _filter_by_category(self) -> None:
        """Filter artifacts by category."""
        categories = list(ArtifactCategory)

        self.console.print("[cyan]Categories:[/cyan]")
        for idx, cat in enumerate(categories):
            self.console.print(f"  {idx}: {cat.value}")

        selection = Prompt.ask("Select category number", default="0")

        try:
            cat_idx = int(selection)
            if 0 <= cat_idx < len(categories):
                category = categories[cat_idx]
                indices = {
                    idx
                    for idx, (_, artifact) in enumerate(self._artifacts_list)
                    if artifact.category == category
                }
                self.selected_indices.update(indices)
                self.console.print(
                    f"[green]Selected {len(indices)} {category.value} artifact(s)[/green]"
                )
        except ValueError:
            self.console.print("[red]Invalid selection[/red]")

    def _filter_by_safety(self) -> None:
        """Filter artifacts by safety level."""
        safety_levels = list(RemovalSafety)

        self.console.print("[cyan]Safety levels:[/cyan]")
        for idx, safety in enumerate(safety_levels):
            self.console.print(f"  {idx}: {safety.value}")

        selection = Prompt.ask("Select safety level", default="0")

        try:
            safety_idx = int(selection)
            if 0 <= safety_idx < len(safety_levels):
                safety = safety_levels[safety_idx]
                indices = {
                    idx
                    for idx, (_, artifact) in enumerate(self._artifacts_list)
                    if artifact.removal_safety == safety
                }
                self.selected_indices.update(indices)
                self.console.print(
                    f"[green]Selected {len(indices)} {safety.value} artifact(s)[/green]"
                )
        except ValueError:
            self.console.print("[red]Invalid selection[/red]")

    def _select_safe_items(self) -> None:
        """Select only items marked as safe to remove."""
        indices = {
            idx
            for idx, (_, artifact) in enumerate(self._artifacts_list)
            if artifact.removal_safety == RemovalSafety.SAFE and artifact.exists
        }
        self.selected_indices.update(indices)
        self.console.print(f"[green]Selected {len(indices)} safe artifact(s)[/green]")

    def _execute_deletion(self) -> RemovalReport | None:
        """Execute deletion of selected artifacts."""
        if not self.selected_indices:
            self.console.print("[yellow]No artifacts selected for deletion.[/yellow]")
            return None

        # Build list of selected artifacts
        selected_artifacts = [
            (result, artifact)
            for idx, (result, artifact) in enumerate(self._artifacts_list)
            if idx in self.selected_indices
        ]

        # Show deletion summary
        self._show_deletion_summary(selected_artifacts)

        # Confirm deletion
        if not Confirm.ask(
            "[bold red]⚠️  Proceed with deletion?[/bold red]",
            default=False,
        ):
            self.console.print("[cyan]Deletion cancelled.[/cyan]")
            return None

        # Ask for dry run first
        dry_run = Confirm.ask(
            "[yellow]Perform dry run first (recommended)?[/yellow]",
            default=True,
        )

        # Create plan entries from selected artifacts
        plan_entries = [
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
                enabled=True,
            )
            for _, artifact in selected_artifacts
        ]

        # Execute removal
        remover = ArtifactRemover(output=self._create_console_adapter())

        if dry_run:
            self.console.print()
            self.console.print(
                "[bold yellow]🔍 Dry Run - No files will be deleted[/bold yellow]"
            )
            self.console.print()
            report = remover.remove(plan_entries, dry_run=True)
            self._show_removal_report(report, dry_run=True)

            if not Confirm.ask(
                "[bold red]Proceed with actual deletion?[/bold red]",
                default=False,
            ):
                self.console.print("[cyan]Deletion cancelled.[/cyan]")
                return report

        # Actual deletion
        self.console.print()
        self.console.print("[bold red]🗑️  Deleting files...[/bold red]")
        self.console.print()
        report = remover.remove(plan_entries, dry_run=False, prompt=False)
        self._show_removal_report(report, dry_run=False)

        return report

    def _show_deletion_summary(
        self,
        selected: list[tuple[ScanResult, Artifact]],
    ) -> None:
        """Display summary of items to be deleted."""
        table = Table(
            title="🗑️  Deletion Summary",
            show_header=True,
            header_style="bold red",
            border_style="red",
        )

        table.add_column("App", style="cyan")
        table.add_column("Path", style="white")
        table.add_column("Size", justify="right")
        table.add_column("Safety", justify="center")

        for _, artifact in selected:
            size_str = (
                self._format_size(artifact.size_bytes) if artifact.size_bytes else "-"
            )
            safety_style = self._get_safety_style(artifact.removal_safety)

            table.add_row(
                artifact.app_name,
                str(artifact.path),
                size_str,
                f"[{safety_style}]{artifact.removal_safety.value}[/{safety_style}]",
            )

        self.console.print(table)
        self.console.print()

    def _show_removal_report(self, report: RemovalReport, dry_run: bool) -> None:
        """Display removal report."""
        mode = "DRY RUN" if dry_run else "ACTUAL DELETION"

        self.console.print()
        self.console.print(f"[bold]{'=' * 60}[/bold]")
        self.console.print(f"[bold cyan]{mode} REPORT[/bold cyan]")
        self.console.print(f"[bold]{'=' * 60}[/bold]")
        self.console.print()

        self.console.print(f"[green]✓ Succeeded:[/green] {len(report.succeeded)}")
        self.console.print(f"[red]✗ Failed:[/red] {len(report.failed)}")
        self.console.print(f"[yellow]⊘ Skipped:[/yellow] {len(report.skipped)}")

        if report.failed:
            self.console.print()
            self.console.print("[bold red]Failed items:[/bold red]")
            for entry, error in report.failed:
                self.console.print(f"  [red]✗[/red] {entry.path}")
                self.console.print(f"    [dim]{error}[/dim]")

        self.console.print()

    def _create_console_adapter(self) -> ConsoleAdapter:
        """Create a console adapter for the remover."""
        return ConsoleAdapter(self.console)

    def _parse_selection(self, selection: str) -> set[int]:
        """Parse user selection string into set of indices."""
        indices: set[int] = set()

        for part in selection.split(","):
            part = part.strip()
            if "-" in part:
                # Range selection (e.g., "0-5")
                try:
                    start, end = part.split("-")
                    start_idx = int(start.strip())
                    end_idx = int(end.strip())
                    indices.update(range(start_idx, end_idx + 1))
                except ValueError:
                    self.console.print(f"[red]Invalid range: {part}[/red]")
            else:
                # Single index
                try:
                    idx = int(part)
                    if 0 <= idx < len(self._artifacts_list):
                        indices.add(idx)
                    else:
                        self.console.print(f"[red]Index out of range: {idx}[/red]")
                except ValueError:
                    self.console.print(f"[red]Invalid index: {part}[/red]")

        return indices

    @staticmethod
    def _get_safety_style(safety: RemovalSafety) -> str:
        """Get Rich style for removal safety level."""
        return {
            RemovalSafety.SAFE: "green",
            RemovalSafety.CAUTION: "yellow",
            RemovalSafety.REVIEW: "red",
        }.get(safety, "white")

    @staticmethod
    def _get_category_style(category: ArtifactCategory) -> str:
        """Get Rich style for artifact category."""
        return {
            ArtifactCategory.APPLICATION: "cyan",
            ArtifactCategory.CACHE: "green",
            ArtifactCategory.LOGS: "yellow",
            ArtifactCategory.PREFERENCES: "magenta",
            ArtifactCategory.SUPPORT: "blue",
            ArtifactCategory.LAUNCH_AGENT: "red",
            ArtifactCategory.OTHER: "white",
        }.get(category, "white")

    @staticmethod
    def _format_size(size_bytes: int | None) -> str:
        """Format file size in human-readable format."""
        if size_bytes is None:
            return "-"

        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0

        return f"{size:.1f}PB"


class ConsoleAdapter(ConsoleLike):
    """Adapter to make Rich Console compatible with ArtifactRemover's ConsoleLike protocol."""

    def __init__(self, console: Console) -> None:
        self._console: Console = console

    def info(self, message: str) -> None:
        self._console.print(f"[cyan]ℹ️  {message}[/cyan]")

    def success(self, message: str) -> None:
        self._console.print(f"[green]✓ {message}[/green]")

    def warning(self, message: str) -> None:
        self._console.print(f"[yellow]⚠️  {message}[/yellow]")

    def error(self, message: str) -> None:
        self._console.print(f"[red]✗ {message}[/red]")

    def highlight(self, message: str) -> None:
        self._console.print(f"[bold magenta]{message}[/bold magenta]")


def run_interactive_mode(
    results: Sequence[ScanResult],
    console: Console | None = None,
) -> RemovalReport | None:
    """
    Run interactive artifact selection and deletion mode.

    Args:
        results: Sequence of scan results to review
        console: Optional Rich Console instance

    Returns:
        RemovalReport if deletions were executed, None otherwise
    """
    session = InteractiveSession(results, console)
    return session.run()


__all__ = [
    "InteractiveSession",
    "ConsoleAdapter",
    "run_interactive_mode",
]
