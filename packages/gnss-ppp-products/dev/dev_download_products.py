"""
Dev script — query all remote resources for a given date, list available
files, and download them to the local store.

Usage
-----
    cd packages/gnss-ppp-products
    uv run python dev/dev_download_products.py
"""

from __future__ import annotations

import datetime
import logging
import re
import sys
from pathlib import Path

from gnss_ppp_products.defaults.defaults import (
    MetaDataRegistry,
    ProductSpecReg,
    RemoteResourceReg,
    LocalResourceReg,
    QuerySpecReg,
)
from gnss_ppp_products.catalogs import ProductQuery, QueryResult
from gnss_ppp_products.server.ftp import (
    ftp_list_directory,
    ftp_download_file,
)
from gnss_ppp_products.server.http import (
    http_list_directory,
    extract_filenames_from_html,
    http_get_file,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP")
DATE = datetime.date(2024, 8, 26)  # DOY 239

DRY_RUN = "--dry-run" in sys.argv  # pass --dry-run to skip actual downloads
VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv

LocalResourceReg.base_dir = BASE

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG if VERBOSE else logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dev_download")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _match_template(file_template: str, filename: str) -> bool:
    """Check if *filename* matches the resolved *file_template*.

    The template may contain regex-like character classes from format
    field defaults (e.g. ``[A-Z0-9]{3}``).  We try it as a regex first;
    if it's not a valid pattern we fall back to a plain substring check.
    """
    try:
        return bool(re.search(file_template, filename, re.IGNORECASE))
    except re.error:
        return file_template in filename


def _list_remote(result: QueryResult) -> list[str]:
    """List files in the remote directory of *result*."""
    proto = result.remote_protocol.upper()
    server = result.remote_server
    directory = result.remote_directory

    if proto in ("FTP", "FTPS"):
        use_tls = proto == "FTPS"
        return ftp_list_directory(server, directory, use_tls=use_tls)

    if proto in ("HTTP", "HTTPS"):
        html = http_list_directory(server, directory)
        if html is None:
            return []
        return extract_filenames_from_html(html)

    log.warning("Unsupported protocol %s for %s", proto, result.product_id)
    return []


def _download(
    result: QueryResult,
    filename: str,
    dest_dir: Path,
) -> bool:
    """Download *filename* from the remote described by *result*."""
    proto = result.remote_protocol.upper()
    server = result.remote_server
    directory = result.remote_directory
    dest_path = dest_dir / filename

    if dest_path.exists() and dest_path.stat().st_size > 0:
        log.info("  SKIP (exists) %s", dest_path)
        return True

    if proto in ("FTP", "FTPS"):
        use_tls = proto == "FTPS"
        return ftp_download_file(
            server, directory, filename, dest_path, use_tls=use_tls
        )

    if proto in ("HTTP", "HTTPS"):
        got = http_get_file(server, directory, filename, dest_dir=dest_dir)
        return got is not None

    log.warning("Unsupported protocol %s", proto)
    return False


# ---------------------------------------------------------------------------
# Guard: check that the data volume is mounted
# ---------------------------------------------------------------------------

if not BASE.exists():
    print(f"Data directory not found: {BASE}")
    print("Mount the volume or update BASE in this script.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 1) Build the product query
# ---------------------------------------------------------------------------

log.info("Building product query for %s …", DATE)

query = ProductQuery(
    DATE,
    query_spec=QuerySpecReg,
    remote_factory=RemoteResourceReg,
    local_factory=LocalResourceReg,
    meta_catalog=MetaDataRegistry,
    product_catalog=ProductSpecReg,
)

log.info("Query produced %d results across specs: %s", query.count, query.specs())
log.info("Centers: %s", query.centers())
log.info("Solutions: %s", query.solutions())
log.info("Campaigns: %s", query.campaigns())

print()
print(query.table())
print()

# ---------------------------------------------------------------------------
# 2) Iterate results, list remotes, match, and download
# ---------------------------------------------------------------------------

stats = {"listed": 0, "matched": 0, "downloaded": 0, "skipped": 0, "failed": 0}

for r in query.results:
    label = f"{r.spec}/{r.center}/{r.campaign}/{r.solution}/{r.sampling}"

    # -- resolve local destination -----------------------------------
    if not r.local_directory:
       
        dest_dir = LocalResourceReg.resolve_directory(
            spec_name=r.spec,
            date=DATE,
            meta_catalog=MetaDataRegistry,
        )
        dest_dir.mkdir(parents=True, exist_ok=True)

    else:
        dest_dir = Path(r.local_directory)
        
    # -- list remote directory ---------------------------------------
    log.info("[%s] listing %s %s/%s …", label, r.remote_protocol, r.remote_server, r.remote_directory)
    listing = _list_remote(r)
    stats["listed"] += len(listing)

    if not listing:
        log.warning("  (empty listing)")
        continue

    # -- match against resolved file_template -----------------------
    if not r.file_template:
        log.warning("  (no file_template — skipping)")
        continue

    matches = [f for f in listing if _match_template(r.file_template, f)]
    stats["matched"] += len(matches)

    if not matches:
        log.info("  0 matches for template: %s", r.file_template[:80])
        continue

    log.info("  %d match(es): %s", len(matches), matches[:5])

    # -- download ----------------------------------------------------
    for fname in matches:
        if DRY_RUN:
            log.info("  DRY-RUN would download: %s → %s", fname, dest_dir)
            stats["skipped"] += 1
            continue

        ok = _download(r, fname, dest_dir)
        if ok:
            log.info("  OK  %s → %s", fname, dest_dir)
            stats["downloaded"] += 1
        else:
            log.error("  FAIL  %s", fname)
            stats["failed"] += 1

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print()
print("=" * 60)
print(f"  Date:         {DATE}  (DOY {DATE.timetuple().tm_yday})")
print(f"  Base dir:     {BASE}")
print(f"  Results:      {query.count}")
print(f"  Remote files: {stats['listed']}")
print(f"  Matched:      {stats['matched']}")
print(f"  Downloaded:   {stats['downloaded']}")
print(f"  Skipped:      {stats['skipped']}")
print(f"  Failed:       {stats['failed']}")
if DRY_RUN:
    print("  (DRY RUN — no files were actually downloaded)")
print("=" * 60)
