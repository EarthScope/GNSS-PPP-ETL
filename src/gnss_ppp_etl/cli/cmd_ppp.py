"""gnss ppp — batch RINEX → kinematic PPP-AR via PRIDE-PPP-AR.

Usage
-----
  gnss ppp NCC12540.25o
  gnss ppp /obs/*.rnx --mode final --workers 4
  gnss ppp /obs/*.rnx --pride-dir ~/pride --output-dir ~/output
  gnss ppp /obs/*.rnx --override --json results.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from gnss_ppp_etl.cli import SIMPLE_HEAD, console, progress, summary
from gnss_ppp_etl.config import ConfigLoader


def ppp(
    rinex: Annotated[list[Path], typer.Argument(help="RINEX observation files to process.")],
    mode: Annotated[
        str,
        typer.Option("--mode", help="Product timeliness: 'default' (FIN→RAP→ULT) or 'final'."),
    ] = "",
    pride_dir: Annotated[
        Path | None,
        typer.Option("--pride-dir", help="PRIDE working directory (overrides config)."),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir", help="Output directory for .kin / .res files (overrides config)."
        ),
    ] = None,
    workers: Annotated[
        int, typer.Option("--workers", help="Max concurrent pdp3 subprocesses.")
    ] = 4,
    override: Annotated[
        bool,
        typer.Option(
            "--override/--no-override", help="Re-run even when valid .kin already exists."
        ),
    ] = False,
    output_json: Annotated[
        Path | None, typer.Option("--json", help="Write per-file results to JSON.")
    ] = None,
) -> None:
    """Process RINEX observation files through PRIDE-PPP-AR.

    Products are resolved once per unique date, then pdp3 subprocesses
    are dispatched in parallel.  Already-cached .kin outputs are skipped
    unless --override is set.

    Exit code 0 if all files processed successfully (exit code 1 otherwise).
    """
    from pride_ppp import PrideProcessor, ProcessingMode

    if not rinex:
        console.print("[red]No RINEX files provided.[/red]")
        raise typer.Exit(1)

    cfg = ConfigLoader.load()

    # Resolve directories: CLI flag > config > sensible default
    eff_pride_dir = pride_dir or cfg.processor.pride_dir or Path("pride")
    eff_output_dir = output_dir or cfg.processor.output_dir or Path("output")
    eff_mode = mode if mode else cfg.processor.default_mode

    try:
        processing_mode = ProcessingMode(eff_mode.upper())
    except ValueError:
        console.print(f"[red]Unknown mode '{eff_mode}'. Choose 'default' or 'final'.[/red]")
        raise typer.Exit(1)

    processor = PrideProcessor(
        pride_dir=eff_pride_dir,
        output_dir=eff_output_dir,
        mode=processing_mode,
    )

    console.print()
    console.rule(
        f"[bold]PPP[/bold]  ·  {len(rinex)} file(s)"
        f"  ·  mode=[cyan]{eff_mode}[/cyan]"
        f"  ·  {workers} workers"
        f"  ·  output → [dim]{eff_output_dir}[/dim]"
    )
    console.print()

    t0 = time.monotonic()
    results_data: list[dict] = []

    _STATUS_MARKUP = {
        "success": "[bold green]SUCCESS[/bold green]",
        "cached": "[bold cyan]CACHED[/bold cyan]",
        "failed": "[bold red]FAILED[/bold red]",
        "error": "[bold yellow]ERROR[/bold yellow]",
    }

    rows: list[tuple[str, str, str, str, str, str, str]] = []

    with progress() as prog:
        task = prog.add_task("[cyan]Processing...", total=len(rinex))
        file_t0 = time.monotonic()
        for pr in processor.process_batch(rinex, max_workers=workers, override=override):
            elapsed = time.monotonic() - file_t0
            file_t0 = time.monotonic()

            # Classify result
            cached = pr.config_path.name == "(cached)"
            if pr.success:
                status = "cached" if cached else "success"
                error = ""
            elif pr.returncode != 0:
                status = "failed"
                last_line = pr.stderr.strip().splitlines()[-1] if pr.stderr else ""
                error = last_line[:80]
            else:
                status = "error"
                error = (pr.stderr.strip().splitlines()[-1] if pr.stderr else "unknown")[:80]

            # Extract stats
            wrms_str, epochs_str = "—", "—"
            try:
                df = pr.positions()
                if df is not None and not df.empty:
                    epochs_str = str(len(df))
                    if "wrms" in df.columns:
                        vals = df["wrms"].dropna()
                        if not vals.empty:
                            wrms_str = f"{vals.mean():.2f}"
            except Exception:
                pass

            out_path = str(pr.kin_path) if pr.kin_path else (error or "—")
            rows.append(
                (
                    pr.rinex_path.name,
                    pr.site,
                    str(pr.date) if pr.date else "—",
                    status,
                    epochs_str,
                    wrms_str,
                    out_path,
                )
            )
            results_data.append(
                {
                    "rinex": str(pr.rinex_path),
                    "site": pr.site,
                    "date": str(pr.date) if pr.date else None,
                    "status": status,
                    "kin_path": str(pr.kin_path) if pr.kin_path else None,
                    "wrms_mm": wrms_str if wrms_str != "—" else None,
                    "elapsed_s": round(elapsed, 2),
                    "error": error,
                }
            )

            icon = "[green]✓[/green]" if status in ("success", "cached") else "[red]✗[/red]"
            prog.update(
                task,
                advance=1,
                description=f"[cyan]Processing...[/cyan] {icon} [dim]{pr.rinex_path.name}[/dim]",
            )

    elapsed_total = time.monotonic() - t0

    # Print summary table
    t_out = Table(box=SIMPLE_HEAD, header_style="bold", expand=False)
    t_out.add_column("RINEX", style="bold cyan")
    t_out.add_column("Site", min_width=5)
    t_out.add_column("Date", min_width=10)
    t_out.add_column("Status", min_width=9)
    t_out.add_column("Epochs", justify="right", min_width=7)
    t_out.add_column("WRMS (mm)", justify="right", min_width=9)
    t_out.add_column("Output / Error")

    for name, site, date_str, status, epochs, wrms, out in sorted(rows, key=lambda r: (r[2], r[1])):
        t_out.add_row(
            name,
            site,
            date_str,
            _STATUS_MARKUP.get(status, status),
            epochs,
            wrms,
            f"[dim]{out}[/dim]",
        )
    console.print(t_out)

    succeeded = sum(1 for r in results_data if r["status"] in ("success", "cached"))
    extras: list[str] = []
    if n := sum(1 for r in results_data if r["status"] == "cached"):
        extras.append(f"[cyan]~ {n} cached[/cyan]")
    if n := sum(1 for r in results_data if r["status"] == "failed"):
        extras.append(f"[red]✗ {n} failed[/red]")
    if n := sum(1 for r in results_data if r["status"] == "error"):
        extras.append(f"[yellow]! {n} errors[/yellow]")
    console.print(summary(succeeded, len(results_data), extras, elapsed_total, "PPP summary"))

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(results_data, indent=2))
        console.print(f"[dim]Results saved to {output_json}[/dim]\n")

    if succeeded < len(results_data):
        raise typer.Exit(1)
