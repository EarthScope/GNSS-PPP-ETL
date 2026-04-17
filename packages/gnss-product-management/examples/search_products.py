"""Search for GNSS products on remote analysis center servers.

This script demonstrates how to use :class:`GNSSClient` to discover which
GNSS data products are available from global analysis centers for a given
date — without downloading anything.

Background
----------
Global Navigation Satellite System (GNSS) Precise Point Positioning (PPP)
requires a set of auxiliary products computed by international analysis
centers (e.g. CODE, ESA, GFZ, Wuhan University).  These include:

- **ORBIT** — precise satellite orbit files (SP3 format).  Tell you
  exactly where each satellite was at every epoch.
- **CLOCK** — precise satellite and receiver clock corrections (CLK
  format).  Essential for centimetre-level timing accuracy.
- **BIA** — observable-specific signal bias files.  Correct for
  hardware-induced phase and code offsets on each signal frequency.
- **ERP** — Earth rotation parameters.  Needed to convert between
  Earth-fixed and inertial reference frames.

All four products are versioned by *solution type* (TTT parameter):

- ``FIN`` (final) — highest accuracy, available ~2 weeks after observation.
- ``RAP`` (rapid) — intermediate accuracy, available ~17 hours later.
- ``ULT`` (ultra-rapid) — near-real-time, lower accuracy.

What this script does
---------------------
1. Creates a client using the bundled default product/center specifications.
2. Demonstrates four progressively narrower search patterns:
   - Broad search across all centers.
   - Filtered to specific centers.
   - Filtered by solution type.
   - Filtered to a single center and solution type.
3. Prints a summary table of everything found.

Usage
-----
No local storage directory is needed — search-only mode is the default
when ``base_dir`` is omitted from :meth:`GNSSClient.from_defaults`::

    python examples/search_products.py
"""

from __future__ import annotations

import datetime
import logging

from gnss_product_management import GNSSClient

# ---------------------------------------------------------------------------
# Logging
# Configure logging so you can see INFO-level messages while the search runs.
# Change ``level=logging.INFO`` to ``level=logging.DEBUG`` to see every
# individual directory listing request.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s — %(message)s",
)

# ---------------------------------------------------------------------------
# Step 1 — Create the client
#
# ``from_defaults()`` loads the bundled product catalog and all registered
# remote center specifications (CODE, ESA, GFZ, IGS, Wuhan, etc.).
# No ``base_dir`` is needed here because we are only searching, not
# downloading.
# ---------------------------------------------------------------------------
client = GNSSClient.from_defaults()

# Display the registered products and centers in a rich table so you can
# see what is available before running any search.
print("Available products and centers:")
client.display()
print()

# ---------------------------------------------------------------------------
# Step 2 — Choose a target date
#
# Dates must be timezone-aware.  Always use UTC for GNSS work — the
# satellite clock products are referenced to GPS time, which tracks UTC.
# ---------------------------------------------------------------------------
date = datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc)
print(f"Searching for products on: {date.date()}\n")

# ---------------------------------------------------------------------------
# Step 3 — Build a reusable query base
#
# The fluent builder pattern lets you chain method calls.  ``client.query()``
# returns a :class:`~gnss_product_management.client.product_query.ProductQuery`
# object.  Calling ``.on(date)`` pins the date; subsequent ``.for_product()``
# calls reuse the same date.
# ---------------------------------------------------------------------------
base_query = client.product_query().on(date)


def print_results(label: str, results: list) -> None:
    """Print a formatted list of search results.

    Args:
        label: Header to print before the result rows.
        results: List of :class:`~gnss_product_management.FoundResource` objects.
    """
    print(f"{label}")
    print("-" * (len(label)))
    if not results:
        print("  (no results)")
    for r in results:
        src = "[LOCAL]" if r.is_local else "[REMOTE]"
        center = f"  {r.center:<6s}" if r.center else "       "
        quality = f"  {r.quality:<4s}" if r.quality else "      "
        print(f"  {src}{center}{quality}  {r.hostname:<35s}  {r.filename}")
    print()


# ---------------------------------------------------------------------------
# Example A — Broad search: all centers, all solution types
#
# This is the widest possible net.  Results are ranked best-first by a
# combination of protocol preference (local > HTTPS > FTP) and solution type.
# ---------------------------------------------------------------------------
print("=" * 60)
print("EXAMPLE A — All centers, all solution types")
print("=" * 60)

orbit_all = base_query.for_product("ORBIT").search()
print_results(f"ORBIT on {date.date()}", orbit_all)

clock_all = base_query.for_product("CLOCK").search()
print_results(f"CLOCK on {date.date()}", clock_all)

# ---------------------------------------------------------------------------
# Example B — Restrict to specific analysis centers
#
# Pass center IDs to ``.sources()`` to limit the search.  This reduces
# search time and network requests when you already know which center
# you trust for a given product.
# ---------------------------------------------------------------------------
print("=" * 60)
print("EXAMPLE B — Specific centers: COD and ESA only")
print("=" * 60)

orbit_targeted = base_query.for_product("ORBIT").sources("COD", "ESA").search()
print_results(f"ORBIT — COD & ESA on {date.date()}", orbit_targeted)

# ---------------------------------------------------------------------------
# Example C — Filter by solution type
#
# The ``TTT`` parameter codes the solution type.  Passing ``where(TTT="FIN")``
# restricts results to final solutions only.  The ``.prefer()`` call then
# sorts the remaining results so preferred centers come first.
# ---------------------------------------------------------------------------
print("=" * 60)
print("EXAMPLE C — Final solutions only, with center preference")
print("=" * 60)

clock_final = (
    base_query.for_product("CLOCK")
    .where(TTT="FIN")
    .prefer(AAA=["WUM", "COD", "GFZ", "ESA"])
    .search()
)
print_results(f"CLOCK final solutions on {date.date()}", clock_final)

bias_final = base_query.for_product("BIA").where(TTT="FIN").prefer(AAA=["WUM", "COD"]).search()
print_results(f"BIA final solutions on {date.date()}", bias_final)

# ---------------------------------------------------------------------------
# Example D — Single center, single solution type
#
# The most precise search.  Useful when you want exactly one file from a
# specific, trusted source.  ``results[0]`` is the top-ranked candidate.
# ---------------------------------------------------------------------------
print("=" * 60)
print("EXAMPLE D — Single center (COD) + final orbit")
print("=" * 60)

orbit_cod_fin = base_query.for_product("ORBIT").sources("COD").where(TTT="FIN").search()
print_results(f"ORBIT COD/FIN on {date.date()}", orbit_cod_fin)

if orbit_cod_fin:
    best = orbit_cod_fin[0]
    print("Top-ranked result:")
    print(f"  Product  : {best.product}")
    print(f"  Center   : {best.center}")
    print(f"  Quality  : {best.quality}")
    print(f"  Protocol : {best.protocol}")
    print(f"  URI      : {best.uri}")
    print()
