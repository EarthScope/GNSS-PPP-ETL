"""
dev_resource_probe.py — Probe all remote resources for product availability.

Queries every product variant in the catalog, connects to each remote
server, lists the target directory, and checks whether any file matches
the expected regex.  Results are grouped by product spec and written to
``resource_probe.json``.

Run:
    uv run dev/dev_resource_probe.py
"""

from __future__ import annotations

import datetime
import json
import re
import sys
import time
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

from gnss_ppp_products.assets.query_spec import ProductQuery
from gnss_ppp_products.server.ftp import ftp_list_directory, ftp_find_best_match_in_listing
from gnss_ppp_products.server.http import http_list_directory, extract_filenames_from_html

# ── Configuration ─────────────────────────────────────────────────
PROBE_DATE = datetime.date(2025, 1, 15)
OUTPUT_FILE = "resource_probe.json"
FTP_TIMEOUT = 30

# ── Directory listing cache (server+directory → basenames) ────────
_listing_cache: Dict[Tuple[str, str], Optional[List[str]]] = {}
_listing_errors: Dict[Tuple[str, str], str] = {}


def _list_remote(
    server: str,
    directory: str,
    protocol: str,
) -> Optional[List[str]]:
    """Return a list of filenames at *server*/*directory*, or None on failure.

    Results are cached per (server, directory) so each directory is
    listed at most once even if many product variants share it.
    """
    key = (server, directory)
    if key in _listing_cache:
        return _listing_cache[key]

    filenames: Optional[List[str]] = None
    try:
        if protocol in ("ftp", "ftps"):
            use_tls = protocol == "ftps"
            filenames = ftp_list_directory(
                server, directory, timeout=FTP_TIMEOUT, use_tls=use_tls
            )
        elif protocol in ("http", "https"):
            html = http_list_directory(server, directory)
            if html:
                filenames = extract_filenames_from_html(html)
            else:
                filenames = None
        else:
            _listing_errors[key] = f"unsupported protocol: {protocol}"
    except Exception as exc:
        _listing_errors[key] = str(exc)

    _listing_cache[key] = filenames
    return filenames


def _match_regex(filenames: List[str], regex: str) -> List[str]:
    """Return filenames that match the given regex."""
    pat = re.compile(regex, re.IGNORECASE)
    return [f for f in filenames if pat.search(f)]


# ── Main ──────────────────────────────────────────────────────────

def main() -> None:
    print(f"Probing remote resources for date {PROBE_DATE} ...\n")
    t0 = time.time()

    q = ProductQuery(date=PROBE_DATE)
    results = q.results
    print(f"  Catalog size: {len(results)} product variants")
    print(f"  Specs:   {q.specs()}")
    print(f"  Centers: {q.centers()}\n")

    # ── Probe each result ─────────────────────────────────────────
    probe_records: List[dict] = []

    for i, r in enumerate(results, 1):
        server = r.remote_server
        directory = r.remote_directory
        protocol = r.remote_protocol
        regex = r.regex

        listing = _list_remote(server, directory, protocol)

        matched: List[str] = []
        available = False
        error: Optional[str] = None

        if listing is None:
            key = (server, directory)
            error = _listing_errors.get(key, "directory listing returned empty")
        elif not regex:
            error = "no regex defined"
        else:
            matched = _match_regex(listing, regex)
            available = len(matched) > 0

        status = "OK" if available else ("ERR" if error else "MISS")
        tag = f"[{status:>4s}]"
        label = f"{r.spec:<14s} {r.center:<6s} {r.product_id}"
        print(f"  {i:>3d}/{len(results)}  {tag}  {label}")

        probe_records.append({
            "spec": r.spec,
            "center": r.center,
            "product_id": r.product_id,
            "campaign": r.campaign,
            "solution": r.solution,
            "sampling": r.sampling,
            "regex": regex,
            "remote_url": r.remote_url,
            "protocol": protocol,
            "available": available,
            "matched_files": matched[:5],  # cap to keep output manageable
            "error": error,
        })

    # ── Sort by product spec, then center, then product_id ────────
    probe_records.sort(key=lambda rec: (rec["spec"], rec["center"], rec["product_id"]))

    # ── Build output grouped by product spec ──────────────────────
    grouped: Dict[str, List[dict]] = {}
    for rec in probe_records:
        grouped.setdefault(rec["spec"], []).append(rec)

    # ── Summary stats ─────────────────────────────────────────────
    n_available = sum(1 for r in probe_records if r["available"])
    n_missing   = sum(1 for r in probe_records if not r["available"] and not r["error"])
    n_errors    = sum(1 for r in probe_records if r["error"])

    summary = {
        "probe_date": str(PROBE_DATE),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_variants": len(probe_records),
        "available": n_available,
        "missing": n_missing,
        "errors": n_errors,
    }

    output = {
        "summary": summary,
        "results_by_spec": grouped,
    }

    # ── Write JSON ────────────────────────────────────────────────
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Probe complete in {elapsed:.1f}s")
    print(f"  Total variants: {len(probe_records)}")
    print(f"  Available:      {n_available}")
    print(f"  Missing:        {n_missing}")
    print(f"  Errors:         {n_errors}")
    print(f"  Output:         {OUTPUT_FILE}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
