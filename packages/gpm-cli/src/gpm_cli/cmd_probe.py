"""gnssommelier probe — check server connectivity or product availability.

Examples::

    # Connectivity mode (no --date, no --product)
    gnssommelier probe
    gnssommelier probe --center WUM --center COD

    # Product search mode (--date and/or --product provided)
    gnssommelier probe --date 2025-01-15
    gnssommelier probe --date 2025-01-15 --product ORBIT --product CLOCK
    gnssommelier probe --date 2025-01-15 --center GFZ --workers 4
    gnssommelier probe --date 2025-01-15 --json results.json

Exit code: 0 if all checks pass, 1 if any fail.

Note: CDDIS requires FTPS credentials in ~/.netrc::

    machine gdc.cddis.eosdis.nasa.gov login <user> password <pass>
"""

from __future__ import annotations

import datetime
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer
from gnss_product_management import GNSSClient
from gnss_product_management.defaults import DefaultProductEnvironment
from gnss_product_management.factories.connection_pool import ConnectionPoolFactory
from gnss_product_management.specifications.remote.resource import Server
from rich.table import Table

from gpm_cli import SIMPLE_HEAD, console, progress, summary

_SKIP_PRODUCTS: frozenset[str] = frozenset({"LEO_L1B"})
_DEFAULT_DATE = "2025-01-15"


# ── Data models ───────────────────────────────────────────────────────────────


class ConnStatus(str, Enum):
    """Outcome of a server connectivity probe."""

    CONNECTED = "CONNECTED"
    AUTH_REQUIRED = "AUTH REQUIRED"
    UNREACHABLE = "UNREACHABLE"
    ERROR = "ERROR"


class SearchStatus(str, Enum):
    """Outcome of a product availability probe."""

    FOUND = "FOUND"
    NOT_FOUND = "NOT FOUND"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


@dataclass
class ConnResult:
    """Result of probing a single remote server."""

    server: Server
    centers: list[str]
    status: ConnStatus
    elapsed: float = 0.0
    note: str = ""


@dataclass
class ProbeResult:
    """Result of probing a single (center, product) pair."""

    center_id: str
    product_name: str
    status: SearchStatus
    filename: str = ""
    n_found: int = 0
    elapsed: float = 0.0
    error: str = ""


# ── Registry helpers ──────────────────────────────────────────────────────────


def _unique_servers(center_filter: list[str] | None) -> list[tuple[Server, list[str]]]:
    """Return deduplicated (Server, [center_ids]) pairs from DefaultProductEnvironment."""
    cf = {c.upper() for c in center_filter} if center_filter else None
    seen: dict[str, tuple[Server, list[str]]] = {}

    for catalog in DefaultProductEnvironment.catalogs:
        if cf and catalog.id.upper() not in cf:
            continue
        for server in catalog.servers:
            if server.hostname not in seen:
                seen[server.hostname] = (server, [])
            seen[server.hostname][1].append(catalog.id)

    return list(seen.values())


def _center_products(
    center_filter: list[str] | None,
    product_filter: list[str] | None,
) -> list[tuple[str, str]]:
    """Return (center_id, product_name) pairs from DefaultProductEnvironment."""
    cf = {c.upper() for c in center_filter} if center_filter else None
    pf = {p.upper() for p in product_filter} if product_filter else None

    seen: set[tuple[str, str]] = set()
    results: list[tuple[str, str]] = []

    for catalog in DefaultProductEnvironment.catalogs:
        if cf and catalog.id.upper() not in cf:
            continue
        for query in catalog.queries:
            product_name = query.product.name
            if pf and product_name.upper() not in pf:
                continue
            key = (catalog.id, product_name)
            if key not in seen:
                seen.add(key)
                results.append(key)

    return results


# ── Connectivity probe ────────────────────────────────────────────────────────


def _check_server(server: Server, centers: list[str]) -> ConnResult:
    """Probe a single server using ConnectionPoolFactory."""
    t0 = time.monotonic()
    factory = ConnectionPoolFactory(max_connections=1)
    factory.add_connection(server.hostname)

    listing = factory.list_directory(server.hostname, "/")
    elapsed = time.monotonic() - t0

    pool = factory._pools.get(server.hostname)

    if pool is None or pool._failed:
        return ConnResult(
            server=server,
            centers=centers,
            status=ConnStatus.UNREACHABLE,
            elapsed=elapsed,
            note="connection failed",
        )

    if listing:
        return ConnResult(
            server=server,
            centers=centers,
            status=ConnStatus.CONNECTED,
            elapsed=elapsed,
            note=f"{len(listing)} entries at /",
        )

    if pool._initialized:
        if server.auth_required:
            return ConnResult(
                server=server,
                centers=centers,
                status=ConnStatus.AUTH_REQUIRED,
                elapsed=elapsed,
                note="credentials required — add to ~/.netrc",
            )
        return ConnResult(
            server=server,
            centers=centers,
            status=ConnStatus.CONNECTED,
            elapsed=elapsed,
            note="root directory empty or inaccessible",
        )

    return ConnResult(
        server=server,
        centers=centers,
        status=ConnStatus.UNREACHABLE,
        elapsed=elapsed,
        note="pool did not initialise",
    )


# ── Product search probe ──────────────────────────────────────────────────────


def _probe_one(
    center_id: str,
    product_name: str,
    date: datetime.datetime,
    client: GNSSClient,
) -> ProbeResult:
    """Search for a single (center, product) via GNSSClient."""
    if product_name in _SKIP_PRODUCTS:
        return ProbeResult(
            center_id=center_id, product_name=product_name, status=SearchStatus.SKIPPED
        )
    t0 = time.monotonic()
    try:
        results = client.query().for_product(product_name).on(date).sources(center_id).search()
        found = [r for r in results if r.filename]
        return ProbeResult(
            center_id=center_id,
            product_name=product_name,
            status=SearchStatus.FOUND if found else SearchStatus.NOT_FOUND,
            filename=found[0].filename if found else "",
            n_found=len(found),
            elapsed=time.monotonic() - t0,
        )
    except Exception as exc:  # noqa: BLE001
        return ProbeResult(
            center_id=center_id,
            product_name=product_name,
            status=SearchStatus.ERROR,
            error=str(exc),
            elapsed=time.monotonic() - t0,
        )


# ── Rich tables ───────────────────────────────────────────────────────────────

_CONN_MARKUP: dict[ConnStatus, str] = {
    ConnStatus.CONNECTED: "[bold green]CONNECTED[/bold green]",
    ConnStatus.AUTH_REQUIRED: "[bold yellow]AUTH REQUIRED[/bold yellow]",
    ConnStatus.UNREACHABLE: "[bold red]UNREACHABLE[/bold red]",
    ConnStatus.ERROR: "[bold red]ERROR[/bold red]",
}
_SEARCH_MARKUP: dict[SearchStatus, str] = {
    SearchStatus.FOUND: "[bold green]FOUND[/bold green]",
    SearchStatus.NOT_FOUND: "[bold red]NOT FOUND[/bold red]",
    SearchStatus.ERROR: "[bold yellow]ERROR[/bold yellow]",
    SearchStatus.SKIPPED: "[dim]SKIPPED[/dim]",
}


def _connectivity_table(results: list[ConnResult]) -> Table:
    """Build a Rich table summarising server connectivity results."""
    t = Table(box=SIMPLE_HEAD, header_style="bold", expand=False)
    t.add_column("Centers", style="bold cyan")
    t.add_column("Hostname")
    t.add_column("Protocol", justify="center", min_width=8)
    t.add_column("Status", min_width=13)
    t.add_column("Time", justify="right", min_width=6)
    t.add_column("Note")
    for r in sorted(results, key=lambda r: r.server.hostname):
        parsed = urlparse(r.server.hostname)
        host = f"[dim]{parsed.scheme}://[/dim]{parsed.hostname}"
        note_style = "dim" if r.status == ConnStatus.CONNECTED else "yellow"
        t.add_row(
            ", ".join(r.centers),
            host,
            (r.server.protocol or "").upper(),
            _CONN_MARKUP[r.status],
            f"{r.elapsed:.1f}s",
            f"[{note_style}]{r.note}[/{note_style}]",
        )
    return t


def _search_table(results: list[ProbeResult]) -> Table:
    """Build a Rich table summarising product availability probe results."""
    t = Table(box=SIMPLE_HEAD, header_style="bold", expand=False)
    t.add_column("Center", style="bold cyan", min_width=8)
    t.add_column("Product", min_width=12)
    t.add_column("Status", min_width=10)
    t.add_column("Time", justify="right", min_width=6)
    t.add_column("File / Error")
    for r in sorted(results, key=lambda r: (r.center_id, r.product_name)):
        elapsed = f"{r.elapsed:.1f}s" if r.elapsed else "—"
        if r.status == SearchStatus.FOUND:
            count = f" [dim]({r.n_found})[/dim]" if r.n_found > 1 else ""
            detail = f"[dim]{r.filename}[/dim]{count}"
        elif r.status == SearchStatus.ERROR:
            detail = f"[yellow]{r.error}[/yellow]"
        else:
            detail = "[dim]—[/dim]"
        t.add_row(r.center_id, r.product_name, _SEARCH_MARKUP[r.status], elapsed, detail)
    return t


# ── Mode runners ──────────────────────────────────────────────────────────────


def _run_connectivity(
    center_filter: list[str] | None, workers: int, output_json: Path | None
) -> bool:
    """Run connectivity probes against all matching servers in parallel.

    Args:
        center_filter: Restrict probes to these center IDs, or None for all.
        workers: Number of concurrent probe threads.
        output_json: Write JSON results to this path when provided.

    Returns:
        True if every server is reachable (CONNECTED or AUTH_REQUIRED).
    """
    pairs = _unique_servers(center_filter)
    if not pairs:
        console.print("[red]No servers matched the given filters.[/red]")
        raise typer.Exit(1)

    console.print()
    console.rule(
        f"[bold]Server connectivity check[/bold]  ·  {len(pairs)} servers  ·  {workers} workers"
    )
    console.print()

    results: list[ConnResult] = []
    t0 = time.monotonic()
    _ICON = {
        ConnStatus.CONNECTED: "[green]✓[/green]",
        ConnStatus.AUTH_REQUIRED: "[yellow]~[/yellow]",
        ConnStatus.UNREACHABLE: "[red]✗[/red]",
        ConnStatus.ERROR: "[red]![/red]",
    }

    with progress() as prog:
        task = prog.add_task("[cyan]Connecting...", total=len(pairs))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_check_server, srv, centers): srv for srv, centers in pairs}
            for future in as_completed(futures):
                r = future.result()
                results.append(r)
                prog.update(
                    task,
                    advance=1,
                    description=f"[cyan]Connecting...[/cyan] {_ICON[r.status]} [dim]{r.server.hostname}[/dim]",
                )

    elapsed = time.monotonic() - t0
    console.print(_connectivity_table(results))

    connected = sum(
        1 for r in results if r.status in (ConnStatus.CONNECTED, ConnStatus.AUTH_REQUIRED)
    )
    extra = []
    if n := sum(1 for r in results if r.status == ConnStatus.AUTH_REQUIRED):
        extra.append(f"[yellow]~ {n} auth required[/yellow]")
    if n := sum(1 for r in results if r.status == ConnStatus.UNREACHABLE):
        extra.append(f"[red]✗ {n} unreachable[/red]")
    if n := sum(1 for r in results if r.status == ConnStatus.ERROR):
        extra.append(f"[red]! {n} errors[/red]")
    console.print(summary(connected, len(results), extra, elapsed, "Connectivity summary"))

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(
                {
                    "mode": "connectivity",
                    "servers": [
                        {
                            "hostname": r.server.hostname,
                            "protocol": r.server.protocol,
                            "centers": r.centers,
                            "status": r.status.value,
                            "elapsed_s": round(r.elapsed, 2),
                            "note": r.note,
                        }
                        for r in sorted(results, key=lambda r: r.server.hostname)
                    ],
                },
                indent=2,
            )
        )
        console.print(f"[dim]Results saved to {output_json}[/dim]\n")

    return all(r.status in (ConnStatus.CONNECTED, ConnStatus.AUTH_REQUIRED) for r in results)


def _run_product_search(
    date: str,
    center_filter: list[str] | None,
    product_filter: list[str] | None,
    workers: int,
    output_json: Path | None,
) -> bool:
    """Search all matching (center, product) pairs for the given date in parallel.

    Args:
        date: UTC date string in ``YYYY-MM-DD`` format.
        center_filter: Restrict to these center IDs, or None for all.
        product_filter: Restrict to these product names, or None for all.
        workers: Number of concurrent search threads.
        output_json: Write JSON results to this path when provided.

    Returns:
        True if every probe returned FOUND (no NOT_FOUND or ERROR results).
    """
    probe_date = datetime.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
    pairs = _center_products(center_filter, product_filter)
    if not pairs:
        console.print("[red]No (center, product) pairs matched the given filters.[/red]")
        raise typer.Exit(1)

    client = GNSSClient.from_defaults()

    console.print()
    console.rule(
        f"[bold]Product search[/bold]  ·  [cyan]{date}[/cyan]  ·  {len(pairs)} pairs  ·  {workers} workers"
    )
    console.print()

    results: list[ProbeResult] = []
    t0 = time.monotonic()
    _ICON = {
        "FOUND": "[green]✓[/green]",
        "NOT FOUND": "[red]✗[/red]",
        "ERROR": "[yellow]![/yellow]",
        "SKIPPED": "[dim]–[/dim]",
    }

    with progress() as prog:
        task = prog.add_task("[cyan]Probing...", total=len(pairs))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_probe_one, cid, pname, probe_date, client): (cid, pname)
                for cid, pname in pairs
            }
            for future in as_completed(futures):
                r = future.result()
                results.append(r)
                prog.update(
                    task,
                    advance=1,
                    description=f"[cyan]Probing...[/cyan] {_ICON[r.status]} [dim]{r.center_id}/{r.product_name}[/dim]",
                )

    elapsed = time.monotonic() - t0
    console.print(_search_table(results))

    found = sum(1 for r in results if r.status == SearchStatus.FOUND)
    extra = []
    if n := sum(1 for r in results if r.status == SearchStatus.NOT_FOUND):
        extra.append(f"[red]✗ {n} not found[/red]")
    if n := sum(1 for r in results if r.status == SearchStatus.ERROR):
        extra.append(f"[yellow]! {n} errors[/yellow]")
    if n := sum(1 for r in results if r.status == SearchStatus.SKIPPED):
        extra.append(f"[dim]– {n} skipped[/dim]")
    console.print(summary(found, len(results), extra, elapsed, "Search summary"))

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(
                {
                    "mode": "search",
                    "date": date,
                    "probes": [
                        {
                            "center": r.center_id,
                            "product": r.product_name,
                            "status": r.status.value,
                            "filename": r.filename,
                            "n_found": r.n_found,
                            "elapsed_s": round(r.elapsed, 2),
                            "error": r.error,
                        }
                        for r in sorted(results, key=lambda r: (r.center_id, r.product_name))
                    ],
                },
                indent=2,
            )
        )
        console.print(f"[dim]Results saved to {output_json}[/dim]\n")

    return not any(r.status in (SearchStatus.NOT_FOUND, SearchStatus.ERROR) for r in results)


# ── Command ───────────────────────────────────────────────────────────────────


def probe(
    date: Annotated[
        str | None,
        typer.Option("--date", help="UTC date YYYY-MM-DD. Omit for connectivity-only mode."),
    ] = None,
    center: Annotated[
        list[str] | None,
        typer.Option("--center", help="Center IDs to probe (repeatable)."),
    ] = None,
    product: Annotated[
        list[str] | None,
        typer.Option("--product", help="Product names to probe (repeatable). Implies search mode."),
    ] = None,
    workers: Annotated[int, typer.Option("--workers", help="Max concurrent connections.")] = 8,
    output_json: Annotated[
        Path | None, typer.Option("--json", help="Save results to JSON.")
    ] = None,
) -> None:
    """Probe server connectivity or product availability in the GNSS catalog.

    [bold]Connectivity mode[/bold] (no --date, no --product)\n
      Attempt a connection against every registered server and report
      CONNECTED / AUTH REQUIRED / UNREACHABLE for each hostname.

    [bold]Product search mode[/bold] (--date and/or --product provided)\n
      For every (center, product) pair run a live directory listing and
      assert at least one file is found for the given date.
    """
    search_mode = date is not None or bool(product)
    ok = (
        _run_product_search(date or _DEFAULT_DATE, center, product, workers, output_json)
        if search_mode
        else _run_connectivity(center, workers, output_json)
    )
    if not ok:
        raise typer.Exit(1)
