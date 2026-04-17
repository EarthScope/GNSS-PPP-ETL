"""gnssommelier search — search for GNSS products across analysis centers.

Examples::

    gnssommelier search ORBIT --date 2025-01-15
    gnssommelier search ORBIT --date 2025-01-15 --where TTT=FIN --where AAA=COD
    gnssommelier search ORBIT --date 2025-01-01 --to 2025-01-07
    gnssommelier search ORBIT --date 2025-01-15 --sources COD ESA GFZ
    gnssommelier search ORBIT --date 2025-01-15 --json results.json
"""

from __future__ import annotations

import datetime
import json
import time
from pathlib import Path
from typing import Annotated

import typer
from gnss_product_management import GNSSClient
from rich.table import Table

from gpm_cli import SIMPLE_HEAD, console, summary
from gpm_cli.config import ConfigLoader


def search(
    product: Annotated[str, typer.Argument(help="Product name (e.g. ORBIT, CLOCK, BIA, ERP).")],
    date: Annotated[str, typer.Option("--date", help="UTC date YYYY-MM-DD.")],
    to: Annotated[
        str | None, typer.Option("--to", help="End date for range search (inclusive).")
    ] = None,
    where: Annotated[
        list[str] | None,
        typer.Option("--where", help="Parameter filter KEY=VALUE (repeatable). e.g. TTT=FIN"),
    ] = None,
    sources: Annotated[
        list[str] | None,
        typer.Option("--sources", help="Restrict to these center IDs (repeatable)."),
    ] = None,
    output_json: Annotated[
        Path | None, typer.Option("--json", help="Save results to JSON.")
    ] = None,
) -> None:
    """Search for IGS products matching the given criteria.

    Exit code 0 if at least one result is found, 1 if nothing matches.
    """
    cfg = ConfigLoader.load()

    # Parse --where KEY=VALUE pairs
    params: dict[str, str] = {}
    for expr in where or []:
        if "=" not in expr:
            console.print(f"[red]--where must be KEY=VALUE, got: {expr!r}[/red]")
            raise typer.Exit(1)
        k, _, v = expr.partition("=")
        params[k.strip()] = v.strip()

    # Build center list: --sources overrides config centers
    center_ids = sources or (cfg.client.centers if cfg.client.centers else None)

    # Parse dates
    try:
        start_dt = _parse_date(date)
    except ValueError:
        console.print(f"[red]Invalid --date: {date!r}  (expected YYYY-MM-DD)[/red]")
        raise typer.Exit(1)

    end_dt: datetime.datetime | None = None
    if to:
        try:
            end_dt = _parse_date(to)
        except ValueError:
            console.print(f"[red]Invalid --to: {to!r}  (expected YYYY-MM-DD)[/red]")
            raise typer.Exit(1)

    client = GNSSClient.from_defaults(**cfg.to_client_kwargs())

    console.print()
    range_label = f"[cyan]{date}[/cyan]" + (f" → [cyan]{to}[/cyan]" if to else "")
    console.rule(
        f"[bold]Search[/bold]  ·  [cyan]{product.upper()}[/cyan]  ·  {range_label}"
        + (f"  ·  centers: {','.join(center_ids)}" if center_ids else "")
    )
    console.print()

    t0 = time.monotonic()

    try:
        q = client.product_query().for_product(product)
        if end_dt:
            q = q.on_range(start_dt, end_dt)
        else:
            q = q.on(start_dt)
        if params:
            q = q.where(**params)
        if center_ids:
            q = q.sources(*center_ids)
        results = q.search()
    except Exception as exc:
        console.print(f"[red]Search failed: {exc}[/red]")
        raise typer.Exit(1)

    elapsed = time.monotonic() - t0

    if not results:
        console.print("[yellow]No results found.[/yellow]\n")
        raise typer.Exit(1)

    # Build table
    t = Table(box=SIMPLE_HEAD, header_style="bold", expand=False)
    t.add_column("Center", style="bold cyan", min_width=8)
    t.add_column("Quality", min_width=4)
    t.add_column("Filename")
    t.add_column("Local", justify="center", min_width=5)
    t.add_column("Server")

    for r in sorted(results, key=lambda r: (r.center, r.quality, r.filename)):
        local_mark = "[green]✓[/green]" if r.is_local else "[dim]—[/dim]"
        t.add_row(
            r.center or "[dim]—[/dim]",
            r.quality or "[dim]—[/dim]",
            f"[dim]{r.filename}[/dim]",
            local_mark,
            f"[dim]{r.hostname}[/dim]",
        )

    console.print(t)

    local_count = sum(1 for r in results if r.is_local)
    extras = [f"[dim]{local_count} local[/dim]"] if local_count else []
    console.print(summary(len(results), len(results), extras, elapsed, "Search summary"))

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(
                [
                    {
                        "product": r.product,
                        "center": r.center,
                        "quality": r.quality,
                        "filename": r.filename,
                        "uri": r.uri,
                        "is_local": r.is_local,
                        "parameters": r.parameters,
                    }
                    for r in results
                ],
                indent=2,
            )
        )
        console.print(f"[dim]Results saved to {output_json}[/dim]\n")


def _parse_date(s: str) -> datetime.datetime:
    """Parse a ``YYYY-MM-DD`` string into a UTC-aware datetime."""
    return datetime.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
