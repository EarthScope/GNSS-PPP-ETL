"""gnss resolve — resolve and download all products for a dependency spec.

Usage
-----
  gnss resolve pride --date 2025-01-15
  gnss resolve pride --date 2025-01-15 --mode final
  gnss resolve pride --date 2025-01-01 --to 2025-01-07
  gnss resolve pride --date 2025-01-15 --json lockfile.json
  gnss resolve --list

Named specs
-----------
  pride       PRIDE-PPPAR (default cascade: FIN → RAP → ULT)
  pride-final PRIDE-PPPAR restricted to final products only
"""

from __future__ import annotations

import datetime
import json
import time
from pathlib import Path
from typing import Annotated

import typer
from gnss_product_management import GNSSClient
from gnss_product_management.specifications.dependencies.dependencies import DependencySpec
from rich.table import Table

from gnss_ppp_etl_cli import SIMPLE_HEAD, console, progress, summary
from gnss_ppp_etl_cli.config import ConfigLoader

# Map short names → YAML paths (loaded lazily to avoid import at startup)
_SPEC_NAMES: dict[str, str] = {
    "pride": "pride_pppar",
    "pride-final": "pride_pppar_final",
}


def _resolve_spec(name: str) -> DependencySpec:
    """Resolve a short spec name or YAML path to a DependencySpec."""
    from pride_ppp.defaults import PRIDE_PPPAR_FINAL_SPEC, PRIDE_PPPAR_SPEC

    _PATHS = {
        "pride": PRIDE_PPPAR_SPEC,
        "pride-final": PRIDE_PPPAR_FINAL_SPEC,
    }
    key = name.lower().strip()
    if key in _PATHS:
        return DependencySpec.from_yaml(_PATHS[key])
    # Try as a direct file path
    p = Path(name)
    if p.exists():
        return DependencySpec.from_yaml(p)
    raise ValueError(
        f"Unknown spec name {name!r}. "
        f"Valid names: {', '.join(_SPEC_NAMES)}  or a path to a YAML file."
    )


def resolve(
    spec: Annotated[
        str | None,
        typer.Argument(
            help="Dependency spec name ('pride', 'pride-final') or path to a YAML file."
        ),
    ] = None,
    date: Annotated[str | None, typer.Option("--date", help="UTC date YYYY-MM-DD.")] = None,
    to: Annotated[
        str | None, typer.Option("--to", help="End date for range resolution (inclusive).")
    ] = None,
    output_json: Annotated[
        Path | None, typer.Option("--json", help="Write resolution summary to JSON.")
    ] = None,
    list_specs: Annotated[
        bool, typer.Option("--list", help="List available named dependency specs and exit.")
    ] = False,
) -> None:
    """Resolve and download all products required by a dependency spec.

    Checks local disk first; downloads only what is missing.
    Written lockfiles prevent redundant downloads on subsequent runs.

    Exit code 0 if all required products are fulfilled.
    """
    if list_specs:
        t = Table(box=SIMPLE_HEAD, header_style="bold", expand=False)
        t.add_column("Name", style="bold cyan")
        t.add_column("Description")
        t.add_row("pride", "PRIDE-PPPAR default cascade (FIN → RAP → ULT)")
        t.add_row("pride-final", "PRIDE-PPPAR final products only (FIN)")
        console.print()
        console.print(t)
        console.print()
        return

    if spec is None:
        console.print("[red]Provide a spec name or --list to see available specs.[/red]")
        raise typer.Exit(1)

    if date is None:
        console.print("[red]--date is required.[/red]")
        raise typer.Exit(1)

    cfg = ConfigLoader.load()
    if not cfg.client.base_dir:
        console.print(
            "[red]base-dir is not configured.[/red]  "
            "Run [bold]gnss config set base-dir <path>[/bold] first."
        )
        raise typer.Exit(1)

    try:
        dep_spec = _resolve_spec(spec)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    # Build date list
    try:
        start_dt = datetime.datetime.strptime(date, "%Y-%m-%d").replace(
            tzinfo=datetime.timezone.utc
        )
        end_dt = (
            datetime.datetime.strptime(to, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
            if to
            else start_dt
        )
    except ValueError as exc:
        console.print(f"[red]Invalid date: {exc}[/red]")
        raise typer.Exit(1)

    dates: list[datetime.datetime] = []
    cur = start_dt
    while cur <= end_dt:
        dates.append(cur)
        cur += datetime.timedelta(days=1)

    client = GNSSClient.from_defaults(**cfg.to_client_kwargs())

    console.print()
    range_label = f"[cyan]{date}[/cyan]" + (f" → [cyan]{to}[/cyan]" if to else "")
    console.rule(
        f"[bold]Resolve[/bold]  ·  [cyan]{spec}[/cyan]  ·  {range_label}  ·  {len(dates)} day(s)"
    )
    console.print()

    t0 = time.monotonic()
    all_rows: list[dict] = []
    any_missing = False

    with progress() as prog:
        task = prog.add_task("[cyan]Resolving...", total=len(dates))
        for dt in dates:
            try:
                resolution, lockfile_path = client.resolve_dependencies(
                    dep_spec, dt, sink_id="local"
                )
                for rd in resolution.resolved:
                    all_rows.append(
                        {
                            "date": str(dt.date()),
                            "spec": rd.spec,
                            "status": rd.status,
                            "path": str(rd.local_path) if getattr(rd, "local_path", None) else None,
                        }
                    )
                if not resolution.all_required_fulfilled:
                    any_missing = True
                icon = "[green]✓[/green]" if resolution.all_required_fulfilled else "[red]✗[/red]"
            except Exception as exc:
                any_missing = True
                all_rows.append(
                    {"date": str(dt.date()), "spec": "ERROR", "status": str(exc), "path": None}
                )
                icon = "[red]![/red]"
            prog.update(
                task,
                advance=1,
                description=f"[cyan]Resolving...[/cyan] {icon} [dim]{dt.date()}[/dim]",
            )

    elapsed = time.monotonic() - t0

    # Print summary table
    t_out = Table(box=SIMPLE_HEAD, header_style="bold", expand=False)
    t_out.add_column("Date", min_width=10)
    t_out.add_column("Product", style="bold cyan", min_width=12)
    t_out.add_column("Status", min_width=10)
    t_out.add_column("Local path")

    _STATUS_COLOR = {
        "local": "cyan",
        "remote": "green",
        "missing": "red",
        "cached": "cyan",
        "downloaded": "green",
    }
    for row in all_rows:
        color = _STATUS_COLOR.get(row["status"], "yellow")
        t_out.add_row(
            row["date"],
            row["spec"],
            f"[{color}]{row['status']}[/{color}]",
            f"[dim]{row['path'] or '—'}[/dim]",
        )
    console.print(t_out)

    fulfilled = sum(
        1 for r in all_rows if r["status"] in ("local", "remote", "downloaded", "cached")
    )
    extras: list[str] = []
    if n := sum(1 for r in all_rows if r["status"] == "missing"):
        extras.append(f"[red]✗ {n} missing[/red]")
    console.print(summary(fulfilled, len(all_rows), extras, elapsed, "Resolve summary"))

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(all_rows, indent=2))
        console.print(f"[dim]Results saved to {output_json}[/dim]\n")

    if any_missing:
        raise typer.Exit(1)
