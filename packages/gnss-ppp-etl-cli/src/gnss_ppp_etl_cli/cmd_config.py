"""gnss config — manage persistent user configuration.

Subcommands
-----------
  init      Interactive first-run wizard.
  show      Display all current settings.
  set       Update a key in the user config file.
  reset     Remove the user config file.
  validate  Check directories, center IDs, and server reachability.

Config file
-----------
All settings are stored in TOML at::

    ~/.config/gnss-ppp-etl/config.toml

A project-local override can live in ``gnss-ppp-etl.toml`` (the project
directory).  Set ``GNSS_CONFIG=/path/to/file.toml`` for a one-shot override.

TOML schema example::

    log_level = "WARNING"
    base_dir = "~/gnss_data"
    max_connections = 4
    centers = ["COD", "ESA", "GFZ"]
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer
from gnss_product_management.defaults import DefaultProductEnvironment
from gnss_product_management.factories.connection_pool import ConnectionPoolFactory
from rich.prompt import Confirm, Prompt
from rich.table import Table

from gnss_ppp_etl_cli import SIMPLE_HEAD, console, progress, summary
from gnss_ppp_etl_cli.config import ENV_VAR, USER_CONFIG_PATH, ConfigLoader

# ── flat-key → TOML-path mapping (for `gnss config set`) ────────────────────
_FLAT_KEY_MAP: dict[str, tuple[str, ...]] = {
    "base-dir": ("base_dir",),
    "max-connections": ("max_connections",),
    "centers": ("centers",),
    "log-level": ("log_level",),
}

_SOURCE_STYLE = {
    "user": "[bold green]user[/bold green]",
    "project": "[bold yellow]project[/bold yellow]",
    "$GNSS_CONFIG": "[bold blue]$GNSS_CONFIG[/bold blue]",
}


def _source_markup(src: str) -> str:
    for prefix, markup in _SOURCE_STYLE.items():
        if src.startswith(prefix):
            return markup
    return "[dim]default[/dim]"


def _make_table() -> Table:
    t = Table(box=SIMPLE_HEAD, header_style="bold", show_header=True, show_edge=False)
    t.add_column("Key", style="cyan", min_width=22)
    t.add_column("Value")
    t.add_column("Source", style="dim")
    return t


config_app = typer.Typer(
    name="config",
    help="Read, write, and validate gnss-ppp-etl configuration.",
    no_args_is_help=True,
)


# ── init ──────────────────────────────────────────────────────────────────────


@config_app.command("init")
def config_init() -> None:
    """Interactive first-run setup wizard."""
    console.print("\n[bold cyan]gnss config init[/bold cyan] — one-time setup\n")

    cfg = ConfigLoader.load()

    base_dir = Prompt.ask(
        "  Local product directory  (client.base_dir)",
        default=str(cfg.client.base_dir or Path.home() / "gnss_data"),
    )

    centers_str = Prompt.ask(
        "  Preferred centers — comma-separated, blank = all",
        default=",".join(cfg.client.centers) if cfg.client.centers else "",
    )
    conn_str = Prompt.ask(
        "  Max connections per host",
        default=str(cfg.client.max_connections),
    )

    updates: dict = {
        "base_dir": str(Path(base_dir).expanduser()),
        "max_connections": int(conn_str) if conn_str.isdigit() else cfg.client.max_connections,
        "centers": [c.strip().upper() for c in centers_str.split(",") if c.strip()],
    }
    ConfigLoader.update_user_config(updates)
    console.print(f"\n[green]✓ Config saved to {USER_CONFIG_PATH}[/green]\n")


# ── show ──────────────────────────────────────────────────────────────────────


@config_app.command("show")
def config_show() -> None:
    """Display all current configuration values, grouped by section."""
    cfg = ConfigLoader.load()

    def _src(key: str) -> str:
        return _source_markup(cfg._sources.get(key, "default"))

    console.print()

    # Root
    t = _make_table()
    t.add_row("log-level", cfg.log_level, _src("log_level"))
    console.print(t)

    # Client
    console.print("\n[bold]client:[/bold]")
    t = _make_table()
    t.add_row(
        "  base-dir",
        str(cfg.client.base_dir) if cfg.client.base_dir else "[dim]—[/dim]",
        _src("client"),
    )
    t.add_row("  max-connections", str(cfg.client.max_connections), _src("client"))
    t.add_row(
        "  centers",
        ", ".join(cfg.client.centers) if cfg.client.centers else "[dim]all[/dim]",
        _src("client"),
    )
    console.print(t)

    console.print(f"\n[dim]User config:  {USER_CONFIG_PATH}[/dim]")
    console.print(f"[dim]Override env: {ENV_VAR}={os.environ.get(ENV_VAR, '(not set)')}[/dim]\n")


# ── set ───────────────────────────────────────────────────────────────────────


@config_app.command("set")
def config_set(
    key: Annotated[
        str,
        typer.Argument(
            help="Config key. Valid keys: base-dir, centers, max-connections, log-level.",
        ),
    ],
    values: Annotated[list[str], typer.Argument(help="Value(s) to set.")],
) -> None:
    """Set a configuration value in the user config file.

    Examples::

      gnss config set base-dir ~/gnss_data
      gnss config set centers COD ESA GFZ
      gnss config set max-connections 6
      gnss config set log-level DEBUG
    """
    norm_key = key.lower().replace("_", "-")
    path_tuple = _FLAT_KEY_MAP.get(norm_key)
    if path_tuple is None:
        console.print(
            f"[red]Unknown key: {key!r}[/red]\nValid keys: {', '.join(sorted(_FLAT_KEY_MAP))}"
        )
        raise typer.Exit(1)

    yaml_key = path_tuple[-1]

    if yaml_key == "centers":
        coerced: object = [v.upper() for v in values]
    elif yaml_key == "max_connections":
        if len(values) != 1 or not values[0].isdigit():
            console.print("[red]max-connections requires a single integer value.[/red]")
            raise typer.Exit(1)
        coerced = int(values[0])
    else:
        if len(values) != 1:
            console.print(f"[red]{key!r} takes exactly one value.[/red]")
            raise typer.Exit(1)
        coerced = values[0]

    # Build nested update dict from path_tuple
    update: dict = {}
    node = update
    for part in path_tuple[:-1]:
        node[part] = {}
        node = node[part]
    node[path_tuple[-1]] = coerced

    ConfigLoader.update_user_config(update)
    console.print(f"[green]✓[/green] {norm_key} = [cyan]{coerced}[/cyan]")


# ── reset ─────────────────────────────────────────────────────────────────────


@config_app.command("reset")
def config_reset(
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt.")] = False,
) -> None:
    """Remove the user config file, reverting all settings to compiled defaults."""
    if not yes:
        confirmed = Confirm.ask(f"Delete {USER_CONFIG_PATH}?", default=False)
        if not confirmed:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit(0)
    ConfigLoader.reset_user_config()
    console.print(f"[green]✓ Config removed ({USER_CONFIG_PATH})[/green]")


# ── validate ──────────────────────────────────────────────────────────────────


@config_app.command("validate")
def config_validate(
    workers: Annotated[int, typer.Option("--workers", help="Concurrent connection checks.")] = 6,
    no_connectivity: Annotated[
        bool,
        typer.Option("--no-connectivity", help="Skip live server connectivity checks."),
    ] = False,
    output_json: Annotated[
        Path | None, typer.Option("--json", help="Write validation results to JSON.")
    ] = None,
) -> None:
    """Check configured directories, center IDs, and server reachability.

    Uses the same ConnectionPoolFactory the library uses internally — no
    GNSSClient required, so this works even before base-dir is configured.
    Pass --no-connectivity to skip the live server checks.
    """

    cfg = ConfigLoader.load()
    t0 = time.monotonic()

    # ── 1. Check configured paths exist ──────────────────────────────────────
    dir_checks: list[tuple[str, Path | None]] = [
        ("base_dir", cfg.base_dir),
    ]
    console.print()
    console.rule("[bold]Directory checks[/bold]")
    console.print()
    dir_results: list[dict] = []
    dir_ok = True
    for label, path in dir_checks:
        if path is None:
            status, markup = "not set", "[dim]not set[/dim]"
        elif path.exists():
            status, markup = "ok", "[green]✓ exists[/green]"
        else:
            status, markup = "missing", "[yellow]⚠ does not exist[/yellow]"
            dir_ok = False
        console.print(f"  {label:<28} {markup}  [dim]{path or ''}[/dim]")
        dir_results.append({"key": label, "path": str(path) if path else None, "status": status})

    # ── 2. Check center IDs are known ────────────────────────────────────────
    console.print()
    known_ids = {c.id.upper() for c in DefaultProductEnvironment.catalogs}
    center_results: list[dict] = []
    bad_centers: list[str] = []
    if cfg.client.centers:
        console.rule("[bold]Center ID checks[/bold]")
        console.print()
        for cid in cfg.client.centers:
            if cid.upper() in known_ids:
                console.print(f"  {cid:<8} [green]✓ known[/green]")
                center_results.append({"center": cid, "status": "known"})
            else:
                console.print(
                    f"  {cid:<8} [red]✗ unknown[/red]  (valid: {', '.join(sorted(known_ids))})"
                )
                center_results.append({"center": cid, "status": "unknown"})
                bad_centers.append(cid)

    # ── 3. Server connectivity ──────────────────────────────────────────────
    conn_results: list[dict] = []

    if not no_connectivity:
        console.print()
        console.rule("[bold]Server connectivity[/bold]")
        console.print()

        cf = {c.upper() for c in cfg.client.centers} if cfg.client.centers else None
        seen: dict[str, tuple] = {}
        for catalog in DefaultProductEnvironment.catalogs:
            if cf and catalog.id.upper() not in cf:
                continue
            for srv in catalog.servers:
                if srv.hostname not in seen:
                    seen[srv.hostname] = (srv, [])
                seen[srv.hostname][1].append(catalog.id)

        pairs = list(seen.values())

        def _check(srv, ctrs):
            ct0 = time.monotonic()
            factory = ConnectionPoolFactory(max_connections=1)
            factory.add_connection(srv.hostname)
            listing = factory.list_directory(srv.hostname, "/")
            pool = factory._pools.get(srv.hostname)
            elapsed = time.monotonic() - ct0
            if pool is None or pool._failed:
                return srv, ctrs, "UNREACHABLE", elapsed
            if listing or pool._initialized:
                return srv, ctrs, "CONNECTED" if not srv.auth_required else "AUTH REQUIRED", elapsed
            return srv, ctrs, "UNREACHABLE", elapsed

        _CONN_COLOR = {
            "CONNECTED": "green",
            "AUTH REQUIRED": "yellow",
            "UNREACHABLE": "red",
        }

        with progress() as prog:
            task = prog.add_task("[cyan]Checking servers...", total=len(pairs))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_check, srv, ctrs): srv for srv, ctrs in pairs}
                for future in as_completed(futures):
                    srv, ctrs, status, elapsed = future.result()
                    color = _CONN_COLOR.get(status, "red")
                    parsed = urlparse(srv.hostname)
                    host = f"{parsed.scheme}://{parsed.hostname}" if parsed.scheme else srv.hostname
                    conn_results.append(
                        {
                            "hostname": srv.hostname,
                            "centers": ctrs,
                            "status": status,
                            "elapsed_s": round(elapsed, 2),
                        }
                    )
                    prog.update(
                        task,
                        advance=1,
                        description=(
                            f"[cyan]Checking...[/cyan] [{color}]{status}[/{color}] "
                            f"[dim]{host}[/dim]"
                        ),
                    )

        ct = Table(box=SIMPLE_HEAD, header_style="bold", expand=False)
        ct.add_column("Hostname")
        ct.add_column("Centers", style="dim cyan")
        ct.add_column("Status")
        ct.add_column("Time", justify="right")
        for r in sorted(conn_results, key=lambda x: x["hostname"]):
            color = _CONN_COLOR.get(r["status"], "red")
            ct.add_row(
                r["hostname"],
                ", ".join(r["centers"]),
                f"[{color}]{r['status']}[/{color}]",
                f"{r['elapsed_s']:.1f}s",
            )
        console.print(ct)

    elapsed_total = time.monotonic() - t0

    ok_count = sum(1 for r in conn_results if r["status"] in ("CONNECTED", "AUTH REQUIRED"))
    total_conn = len(conn_results)
    extras = []
    if n := sum(1 for r in conn_results if r["status"] == "AUTH REQUIRED"):
        extras.append(f"[yellow]~ {n} auth required[/yellow]")
    if n := sum(1 for r in conn_results if r["status"] == "UNREACHABLE"):
        extras.append(f"[red]✗ {n} unreachable[/red]")
    if bad_centers:
        extras.append(f"[red]✗ unknown centers: {', '.join(bad_centers)}[/red]")
    conn_ok = (ok_count == total_conn) if total_conn else True
    all_ok = dir_ok and not bad_centers and conn_ok
    console.print(
        summary(
            ok_count if total_conn else (1 if all_ok else 0),
            total_conn if total_conn else 1,
            extras,
            elapsed_total,
            "Validation summary",
        )
    )

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(
                {
                    "directories": dir_results,
                    "centers": center_results,
                    "connectivity": conn_results,
                },
                indent=2,
            )
        )
        console.print(f"[dim]Results saved to {output_json}[/dim]\n")

    if not all_ok:
        raise typer.Exit(1)
