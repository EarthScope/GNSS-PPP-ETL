#!/usr/bin/env python3
"""Find and download GNSS products for a given date.

Demonstrates the core workflow:
  1. Create a ProductEnvironment (auto-loads bundled specs)
  2. Build queries via QueryFactory
  3. Search remote servers with ResourceFetcher
  4. Download matched files to local storage

Usage
-----
    # Search for final orbit products from Wuhan on 2025-01-15
    python examples/find_and_download.py

    # Actually download the files
    python examples/find_and_download.py --download

    # Customize via environment variables:
    WORKSPACE=/data/gnss  PRODUCT=CLOCK  CENTER=COD  DATE=2025-03-01 \
        python examples/find_and_download.py --download
"""

from __future__ import annotations

import asyncio
import datetime
import os
import sys
import tempfile
from pathlib import Path

from gnss_ppp_products.factories import (
    ProductEnvironment,
    QueryFactory,
    ResourceFetcher,
    FetchResult,
)


# ── Configuration ─────────────────────────────────────────────────
# Override any of these with environment variables.

WORKSPACE = Path(os.environ.get("WORKSPACE", tempfile.mkdtemp(prefix="gnss_example_")))
PRODUCT   = os.environ.get("PRODUCT", "ORBIT")
VERSION   = os.environ.get("VERSION", "1")
CENTER    = os.environ.get("CENTER", "WUM")       # e.g. WUM, COD, IGS, GFZ
DATE_STR  = os.environ.get("DATE", "2025-01-15")  # YYYY-MM-DD
DOWNLOAD  = "--download" in sys.argv               # pass --download to fetch files


def main() -> None:
    date = datetime.datetime.strptime(DATE_STR, "%Y-%m-%d").replace(
        tzinfo=datetime.timezone.utc
    )

    print("=" * 64)
    print("GNSS Product Finder — find & download example")
    print("=" * 64)
    print(f"  Workspace : {WORKSPACE}")
    print(f"  Product   : {PRODUCT} (version {VERSION})")
    print(f"  Center    : {CENTER}")
    print(f"  Date      : {date.strftime('%Y-%m-%d')} (DOY {date.strftime('%j')})")
    print()

    # ── 1. Create environment ─────────────────────────────────────
    # One-line construction loads all bundled parameter, format,
    # product, and resource specifications automatically.
    env = ProductEnvironment(workspace=WORKSPACE)

    products = sorted(env.product_catalog.products.keys())
    centers  = sorted(env.remote_factory.centers)
    print(f"  Loaded {len(products)} products, {len(centers)} remote centers")
    print(f"  Products: {', '.join(products)}")
    print()

    # ── 2. Build queries ──────────────────────────────────────────
    # QueryFactory resolves date fields (YYYY, DDD, WWWW, etc.),
    # narrows parameters to the requested center, and produces
    # a list of ResourceQuery objects — one per server/directory
    # that might contain matching files.
    qf = QueryFactory(
        remote_factory=env.remote_factory,
        local_factory=env.local_factory,
        product_catalog=env.product_catalog,
        parameter_catalog=env.parameter_catalog,
    )

    queries = qf.get(
        date=date,
        product={"name": PRODUCT, "version": [VERSION]},
        parameters={"AAA": [CENTER]},
    )
    print(f"  Generated {len(queries)} queries")

    # ── 3. Search ─────────────────────────────────────────────────
    # ResourceFetcher lists each server/directory (FTP, HTTP, or
    # local filesystem) and matches filenames against the product's
    # regex pattern.
    fetcher = ResourceFetcher()
    results = fetcher.search(queries)

    found = [r for r in results if r.found]
    total_files = sum(len(r.matched_filenames) for r in found)
    print(f"  Found {total_files} file(s) across {len(found)} source(s)")
    print()

    if not found:
        _print_errors(results)
        return

    _print_results(found)

    # ── 4. Download ───────────────────────────────────────────────
    # Downloads run concurrently in a thread pool. Files land in
    # the local factory's directory layout under WORKSPACE.
    if not DOWNLOAD:
        print("Pass --download to actually fetch the files.")
        return

    print("Downloading …")
    asyncio.run(fetcher.download(results, env.local_factory, date))

    for fr in found:
        if fr.downloaded:
            print(f"  ✓ {fr.query.server.hostname} → {fr.download_dest}")
        else:
            print(f"  ✗ {fr.query.server.hostname} — not downloaded")

    print()
    print("Done.")


# ── Helpers ───────────────────────────────────────────────────────

def _print_results(found: list[FetchResult]) -> None:
    """Print a summary table of found files."""
    for fr in found:
        hostname = fr.query.server.hostname
        protocol = (fr.query.server.protocol or "").upper()
        directory = ResourceFetcher._get_directory(fr.query) or "?"
        print(f"  [{protocol}] {hostname}:{directory}")
        for fname in fr.matched_filenames[:10]:
            print(f"    • {fname}")
        if len(fr.matched_filenames) > 10:
            print(f"    … and {len(fr.matched_filenames) - 10} more")
    print()


def _print_errors(results: list[FetchResult]) -> None:
    """Print diagnostic info when nothing was found."""
    print("  No files found. Diagnostics:")
    for r in results:
        hostname = r.query.server.hostname
        err = r.error or "no match"
        print(f"    {hostname}: {err}")
    print()


if __name__ == "__main__":
    main()
