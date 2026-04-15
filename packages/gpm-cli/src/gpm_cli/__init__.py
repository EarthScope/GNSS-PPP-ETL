"""gnss CLI — shared console, progress factory, and root Typer app."""

from __future__ import annotations

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

# ── Shared singletons ─────────────────────────────────────────────────────────

console = Console()

# ── Shared Rich helpers ───────────────────────────────────────────────────────


def progress() -> Progress:
    """Return a :class:`Progress` instance pre-configured for CLI use."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )


def summary(ok: int, total: int, extra: list[str], elapsed: float, title: str) -> Panel:
    """Return a Rich :class:`Panel` summarising a command's outcome."""
    color = "green" if ok == total else "red"
    parts = [f"[{color}]✓ {ok}/{total}[/{color}]"] + extra + [f"[dim]{elapsed:.1f}s[/dim]"]
    return Panel("   ·   ".join(parts), title=f"[bold]{title}[/bold]", expand=False)


# Re-export box for subcommand convenience
SIMPLE_HEAD = box.SIMPLE_HEAD

# ── Root Typer app ────────────────────────────────────────────────────────────

app = typer.Typer(
    name="gnssommelier",
    help=(
        "GNSS-PPP-ETL command-line interface.\n\n"
        "Manage configuration, search for IGS products, download them, resolve "
        "dependency sets, and run PRIDE-PPP-AR processing — all from the shell."
    ),
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)
