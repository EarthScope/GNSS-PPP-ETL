"""Download GNSS products from analysis center servers.

This script demonstrates how to use :class:`GNSSClient` to search for GNSS
products and then download them to a local directory.

Background
----------
GNSS Precise Point Positioning (PPP) requires precise orbit and clock files
that are computed by international analysis centers (e.g. CODE, ESA, GFZ).
Products come in three solution tiers:

- ``FIN`` (final)    — highest accuracy; available ~2 weeks after observation.
- ``RAP`` (rapid)    — intermediate accuracy; available ~17 hours later.
- ``ULT`` (ultra)    — near-real-time; lower accuracy, available within hours.

For post-processing (e.g. academic research) you typically want FIN products.
For near-real-time applications RAP or ULT products are used.

How downloading works
---------------------
1. Call :meth:`GNSSClient.from_defaults` with ``base_dir`` — a local directory
   where downloaded files will be stored.  The directory will be created if it
   does not already exist.
2. Use the fluent query builder to search for matching products.
3. Inspect the :class:`FoundResource` list before deciding what to download.
4. Call :meth:`GNSSClient.download` with ``sink_id="local"`` to fetch the
   selected files.  After download, each :class:`FoundResource` object has its
   ``local_path`` attribute set to the downloaded file on disk.

What this script does
---------------------
- **Example A** — Search, inspect, then download the single highest-ranked
  orbit file for 2 January 2025 (prefer FIN, fall back to RAP or ULT).
- **Example B** — Use :meth:`ProductQuery.download` to search and download in
  a single fluent chain.

Usage
-----
Set ``base_dir`` to any writable directory on your machine::

    python examples/download_from_center.py

Files are saved under ``base_dir / gnss_products`` (the default workspace
layout created by :meth:`GNSSClient.from_defaults`).
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path

from gnss_product_management import GNSSClient

# ---------------------------------------------------------------------------
# Logging setup
# Set to logging.DEBUG to see every HTTP/FTP request.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s — %(message)s",
)

# ---------------------------------------------------------------------------
# Local storage directory — change this path to wherever you want files saved.
# Using Path.home() ensures this works on any machine.
# ---------------------------------------------------------------------------
base_dir = Path.home() / "gnss_data"
base_dir.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Build the client
# ---------------------------------------------------------------------------
client = GNSSClient.from_defaults(base_dir=base_dir)

# Target date — all times must be UTC-aware.
date = datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc)

# ===========================================================================
# Example A — Search first, inspect, then download
# ===========================================================================
# Search broadly across CODE, ESA, and IGS centers for a final orbit file.
# .prefer() controls the ranking order when multiple candidates are found.
# The query returns a list of FoundResource objects — no files are fetched yet.
print("\n=== Example A: Search → Inspect → Download ===\n")

results = (
    client.query()
    .for_product("ORBIT")
    .on(date)
    .where(TTT="FIN")
    .sources("COD", "ESA", "IGS")
    .prefer(TTT=["FIN", "RAP", "ULT"])
    .search()
)

if not results:
    print("No orbit files found — check your network connection.")
else:
    print(f"Found {len(results)} candidate(s).  Top 3:\n")
    for i, r in enumerate(results[:3], start=1):
        # Each FoundResource exposes convenience properties:
        #   r.center    — e.g. "COD", "ESA"
        #   r.quality   — e.g. "FIN", "RAP"
        #   r.protocol  — e.g. "ftp", "https"
        #   r.hostname  — e.g. "ftp.aiub.unibe.ch"
        #   r.filename  — just the file name
        #   r.uri       — full remote URL or local path
        print(
            f"  [{i}] center={r.center!r:>4s}  quality={r.quality!r}  "
            f"file={r.filename!r}"
        )

    # Download only the top-ranked result.
    # client.download() returns a list of local Path objects.
    print(f"\nDownloading top result to: {base_dir}")
    paths = client.download(results=results[:1], sink_id="local")

    if paths:
        print(f"\nDownloaded successfully:")
        for p in paths:
            print(f"  {p}")
        # After download, FoundResource.local_path is also populated:
        for r in results[:1]:
            if r.local_path:
                print(f"\nVerified via FoundResource.local_path: {r.local_path}")
    else:
        print("Download failed — see log output above for details.")

# ===========================================================================
# Example B — Search and download in a single fluent chain
# ===========================================================================
# ProductQuery.download() is equivalent to calling .search() followed by
# GNSSClient.download(), but written as a single expression.
print("\n=== Example B: Single-chain search + download ===\n")

paths = (
    client.query()
    .for_product("CLOCK")
    .on(date)
    .where(TTT="FIN")
    .sources("COD")
    .prefer(TTT=["FIN", "RAP", "ULT"])
    .download(sink_id="local", limit=1)
)

if paths:
    print(f"Clock file(s) downloaded:")
    for p in paths:
        print(f"  {p}")
else:
    print("No clock file downloaded — see log output above.")
