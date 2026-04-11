"""gnss download — download GNSS products to the configured base directory.

Usage
-----
  gnss download ORBIT --date 2025-01-15
  gnss download ORBIT CLOCK ERP --date 2025-01-15
  gnss download ORBIT --date 2025-01-15 --sources COD ESA
  gnss download ORBIT --date 2025-01-15 --dry-run
  gnss download ORBIT --date 2025-01-15 --where TTT=FIN
"""

from __future__ import annotations

import datetime
import time
from pathlib import Path
from typing import Annotated

import typer
from gnss_product_management import GNSSClient
from rich.table import Table

from gnss_ppp_etl.config import ConfigLoader
from gnss_ppp_etl_cli import SIMPLE_HEAD, console, progress, summary


def download(
    products: Annotated[
        list[str], typer.Argument(help="One or more product names (e.g. ORBIT CLOCK ERP).")
    ],
    date: Annotated[str, typer.Option("--date", help="UTC date YYYY-MM-DD.")],
    where: Annotated[
        list[str] | None,
        typer.Option("--where", help="Parameter filter KEY=VALUE (repeatable)."),
    ] = None,
    sources: Annotated[
        list[str] | None,
        typer.Option("--sources", help="Restrict to these center IDs (repeatable)."),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run/--no-dry-run", help="Preview without downloading.")
    ] = False,
) -> None:
    """Download GNSS products to base-dir.

    Already-cached files are skipped automatically.
    Exit code 0 if all requested products were found and downloaded.
    """
    cfg = ConfigLoader.load()

    if not cfg.client.base_dir and not dry_run:
        console.print(
            "[red]base-dir is not configured.[/red]  "
            "Run [bold]gnss config set base-dir <path>[/bold] first, "
            "or pass [bold]GNSS_BASE_DIR[/bold] via env."
        )
        raise typer.Exit(1)

    # Parse params
    params: dict[str, str] = {}
    for expr in where or []:
        if "=" not in expr:
            console.print(f"[red]--where must be KEY=VALUE, got: {expr!r}[/red]")
            raise typer.Exit(1)
        k, _, v = expr.partition("=")
        params[k.strip()] = v.strip()

    center_ids = sources or (cfg.client.centers if cfg.client.centers else None)

    try:
        target_dt = datetime.datetime.strptime(date, "%Y-%m-%d").replace(
            tzinfo=datetime.timezone.utc
        )
    except ValueError:
        console.print(f"[red]Invalid --date: {date!r}[/red]")
        raise typer.Exit(1)

    client = GNSSClient.from_defaults(**cfg.to_client_kwargs())

    console.print()
    dry_label = "  [bold yellow](dry-run)[/bold yellow]" if dry_run else ""
    console.rule(
        f"[bold]Download[/bold]{dry_label}  ·  [cyan]{' '.join(p.upper() for p in products)}[/cyan]"
        f"  ·  [cyan]{date}[/cyan]"
    )
    console.print()

    t0 = time.monotonic()

    # Collect all search results first
    all_results = []
    for prod in products:
        try:
            q = client.query().for_product(prod).on(target_dt)
            if params:
                q = q.where(**params)
            if center_ids:
                q = q.sources(*center_ids)
            found = q.search()
            # Take best one per product (already ranked by quality + preference)
            if found:
                all_results.append((prod, found[0]))
            else:
                all_results.append((prod, None))
        except Exception as exc:
            all_results.append((prod, None))
            console.print(f"[yellow]Search for {prod}: {exc}[/yellow]")

    # Show what will be downloaded
    t = Table(box=SIMPLE_HEAD, header_style="bold", expand=False)
    t.add_column("Product", style="bold cyan", min_width=10)
    t.add_column("Center", min_width=6)
    t.add_column("Quality", min_width=4)
    t.add_column("Filename")
    t.add_column("Status")

    for prod, r in all_results:
        if r is None:
            t.add_row(prod, "—", "—", "—", "[red]not found[/red]")
        elif r.is_local:
            t.add_row(prod, r.center, r.quality, f"[dim]{r.filename}[/dim]", "[cyan]cached[/cyan]")
        else:
            t.add_row(
                prod,
                r.center,
                r.quality,
                f"[dim]{r.filename}[/dim]",
                "[yellow]will download[/yellow]" if not dry_run else "[dim]dry-run[/dim]",
            )

    console.print(t)

    if dry_run:
        console.print("[yellow]Dry-run — no files downloaded.[/yellow]\n")
        return

    # Download non-local results
    to_download = [(prod, r) for prod, r in all_results if r is not None and not r.is_local]
    downloaded_paths: list[Path] = []
    failed: list[str] = []

    if to_download:
        with progress() as prog:
            task = prog.add_task("[cyan]Downloading...", total=len(to_download))
            for prod, r in to_download:
                try:
                    paths = client.download([r], sink_id="local")
                    downloaded_paths.extend(paths)
                    prog.update(
                        task,
                        advance=1,
                        description=f"[cyan]Downloading...[/cyan] [green]✓[/green] [dim]{r.filename}[/dim]",
                    )
                except Exception as exc:
                    failed.append(f"{prod}: {exc}")
                    prog.update(
                        task,
                        advance=1,
                        description=f"[cyan]Downloading...[/cyan] [red]✗[/red] [dim]{r.filename}[/dim]",
                    )

    elapsed = time.monotonic() - t0
    cached_count = sum(1 for _, r in all_results if r is not None and r.is_local)
    not_found_count = sum(1 for _, r in all_results if r is None)
    ok_count = len(downloaded_paths) + cached_count

    extras: list[str] = []
    if cached_count:
        extras.append(f"[cyan]~ {cached_count} cached[/cyan]")
    if failed:
        for msg in failed:
            extras.append(f"[red]✗ {msg}[/red]")
    if not_found_count:
        extras.append(f"[red]✗ {not_found_count} not found[/red]")

    total = len(all_results)
    console.print(summary(ok_count, total, extras, elapsed, "Download summary"))

    if failed or not_found_count:
        raise typer.Exit(1)
