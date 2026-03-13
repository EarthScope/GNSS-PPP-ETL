"""
Dev test script for the local storage system.

Tests LocalStorageConfig (YAML → directory resolution) and
LocalFileQuery (directory → file search) against a real PRIDE
PPP-AR folder on disk.

Usage
-----
    cd gnss-ppp-products
    uv run python dev/test_local_storage.py
"""

import datetime
import sys
from pathlib import Path

from gnss_ppp_products.local.config import LocalStorageConfig, TemporalCategory
from gnss_ppp_products.local.query import LocalFileQuery, _product_type_from_query
from gnss_ppp_products.assets.base import (
    ProductType,
    ProductFileFormat,
    ProductContentType,
)

# ---------------------------------------------------------------------------
# Configuration — change BASE to point at your PRIDE data root
# ---------------------------------------------------------------------------

BASE = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP")
DATE = datetime.date(2024, 8, 26)  # DOY 239

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_SKIP = "\033[33mSKIP\033[0m"

_counts = {"pass": 0, "fail": 0, "skip": 0}


def check(label: str, condition: bool, detail: str = ""):
    tag = _PASS if condition else _FAIL
    _counts["pass" if condition else "fail"] += 1
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{tag}] {label}{suffix}")


def skip(label: str, reason: str = ""):
    _counts["skip"] += 1
    suffix = f"  ({reason})" if reason else ""
    print(f"  [{_SKIP}] {label}{suffix}")


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# Guard: check that the data volume is mounted
# ---------------------------------------------------------------------------

if not BASE.exists():
    print(f"Data directory not found: {BASE}")
    print("Mount the volume or update BASE in this script.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 1) Config loading
# ---------------------------------------------------------------------------

section("1. LocalStorageConfig — YAML loading")

cfg = LocalStorageConfig(BASE)

check(
    "All 24 ProductType members are mapped",
    len(cfg.product_types) == len(ProductType),
    f"mapped={len(cfg.product_types)}, enum={len(ProductType)}",
)

# Spot-check collection assignments
check("SP3 → common", cfg.collection_for(ProductType.SP3) == "common")
check("RINEX3_NAV → navigation", cfg.collection_for(ProductType.RINEX3_NAV) == "navigation")
check("GRACE_GNV → leo", cfg.collection_for(ProductType.GRACE_GNV) == "leo")
check("ATX → antennae", cfg.collection_for(ProductType.ATX) == "antennae")
check("LEAP_SECONDS → reference_tables", cfg.collection_for(ProductType.LEAP_SECONDS) == "reference_tables")
check("OROGRAPHY → orography", cfg.collection_for(ProductType.OROGRAPHY) == "orography")


# ---------------------------------------------------------------------------
# 2) Temporal categories
# ---------------------------------------------------------------------------

section("2. Temporal categories")

check("SP3 is daily", cfg.temporal_for(ProductType.SP3) == TemporalCategory.DAILY)
check("ATX is epoch", cfg.temporal_for(ProductType.ATX) == TemporalCategory.EPOCH)
check("LEAP_SECONDS is static", cfg.temporal_for(ProductType.LEAP_SECONDS) == TemporalCategory.STATIC)
check("OROGRAPHY is static", cfg.temporal_for(ProductType.OROGRAPHY) == TemporalCategory.STATIC)
check("GRACE_GNV is daily", cfg.temporal_for(ProductType.GRACE_GNV) == TemporalCategory.DAILY)


# ---------------------------------------------------------------------------
# 3) Directory resolution — all types
# ---------------------------------------------------------------------------

section("3. Directory resolution (all product types)")

for pt in cfg.product_types:
    temporal = cfg.temporal_for(pt)
    if temporal in (TemporalCategory.DAILY, TemporalCategory.HOURLY):
        path = cfg.resolve(pt, DATE)
    else:
        path = cfg.resolve(pt)
    check(f"{pt.name:20s} exists", path.exists(), str(path))


# ---------------------------------------------------------------------------
# 4) Expected path patterns
# ---------------------------------------------------------------------------

section("4. Path structure spot-checks")

sp3_dir = cfg.resolve(ProductType.SP3, DATE)
check(
    "Common dir matches PRIDE layout",
    str(sp3_dir).endswith("products/2024/product/common"),
    str(sp3_dir),
)

rnx_dir = cfg.resolve(ProductType.RINEX3_NAV, DATE)
check(
    "Navigation dir matches PRIDE layout",
    str(rnx_dir).endswith("rinex/2024/239"),
    str(rnx_dir),
)

leo_dir = cfg.resolve(ProductType.GRACE_GNV, DATE)
check(
    "LEO dir matches PRIDE layout",
    str(leo_dir).endswith("products/2024/239/leo"),
    str(leo_dir),
)

atx_dir = cfg.resolve(ProductType.ATX)
check(
    "ATX dir matches static layout",
    str(atx_dir).endswith("static/atx"),
    str(atx_dir),
)


# ---------------------------------------------------------------------------
# 5) LocalFileQuery — product type inference
# ---------------------------------------------------------------------------

section("5. ProductType inference from FileQuery variants")

from gnss_ppp_products.assets.products.query import ProductFileQuery
from gnss_ppp_products.assets.antennae.query import AntennaeFileQuery
from gnss_ppp_products.assets.rinex.query import RinexFileQuery
from gnss_ppp_products.assets.troposphere.query import TroposphereFileQuery
from gnss_ppp_products.assets.orography.query import OrographyFileQuery
from gnss_ppp_products.assets.leo.query import LEOFileQuery
from gnss_ppp_products.assets.reference_tables.query import ReferenceTableFileQuery
from gnss_ppp_products.assets.reference_tables.base import ReferenceTableType
from gnss_ppp_products.assets.troposphere.base import VMFProduct
from gnss_ppp_products.assets.leo.base import GRACEInstrument

check(
    "ProductFileQuery(SP3) → SP3",
    _product_type_from_query(ProductFileQuery(format=ProductFileFormat.SP3)) == ProductType.SP3,
)
check(
    "ProductFileQuery(CLK) → CLK",
    _product_type_from_query(ProductFileQuery(format=ProductFileFormat.CLK)) == ProductType.CLK,
)
check(
    "AntennaeFileQuery → ATX",
    _product_type_from_query(AntennaeFileQuery()) == ProductType.ATX,
)
check(
    "OrographyFileQuery → OROGRAPHY",
    _product_type_from_query(OrographyFileQuery()) == ProductType.OROGRAPHY,
)
check(
    "ReferenceTableFileQuery(LEAP) → LEAP_SECONDS",
    _product_type_from_query(
        ReferenceTableFileQuery(table_type=ReferenceTableType.LEAP_SECONDS)
    ) == ProductType.LEAP_SECONDS,
)
check(
    "TroposphereFileQuery(VMF3) → VMF3",
    _product_type_from_query(
        TroposphereFileQuery(product=VMFProduct.VMF3)
    ) == ProductType.VMF3,
)
check(
    "LEOFileQuery(GNV) → GRACE_GNV",
    _product_type_from_query(
        LEOFileQuery(instrument=GRACEInstrument.GNV)
    ) == ProductType.GRACE_GNV,
)


# ---------------------------------------------------------------------------
# 6) File search — SP3
# ---------------------------------------------------------------------------

section("6. File search — SP3 in common dir")

lfq = LocalFileQuery(cfg)

q_sp3 = ProductFileQuery(
    format=ProductFileFormat.SP3,
    content=ProductContentType.ORB,
    date=DATE,
    filename=r".*ORB\.SP3",
)
sp3_results = lfq.search(q_sp3)
check("SP3 search returns files", len(sp3_results) > 0, f"found {len(sp3_results)}")
if sp3_results:
    check(
        "All results end with .SP3",
        all(r.name.upper().endswith(".SP3") for r in sp3_results),
    )
    print(f"    First : {sp3_results[0].name}")
    print(f"    Last  : {sp3_results[-1].name}")


# ---------------------------------------------------------------------------
# 7) File search — CLK
# ---------------------------------------------------------------------------

section("7. File search — CLK in common dir")

q_clk = ProductFileQuery(
    format=ProductFileFormat.CLK,
    date=DATE,
    filename=r".*\.CLK",
)
clk_results = lfq.search(q_clk)
check("CLK search returns files", len(clk_results) > 0, f"found {len(clk_results)}")


# ---------------------------------------------------------------------------
# 8) File search — ANTEX
# ---------------------------------------------------------------------------

section("8. File search — ANTEX")

q_atx = AntennaeFileQuery(filename=r"igs20.*\.atx")
atx_results = lfq.search(q_atx)
check("ATX search returns files", len(atx_results) > 0, f"found {len(atx_results)}")
if atx_results:
    check(
        "All results contain 'igs20'",
        all("igs20" in r.name for r in atx_results),
    )


# ---------------------------------------------------------------------------
# 9) File search — reference tables
# ---------------------------------------------------------------------------

section("9. File search — reference tables")

q_leap = ReferenceTableFileQuery(
    table_type=ReferenceTableType.LEAP_SECONDS,
    filename=r"leap.*",
)
leap_results = lfq.search(q_leap)
check("leap.sec found", len(leap_results) > 0, f"found {len(leap_results)}")

q_sat = ReferenceTableFileQuery(
    table_type=ReferenceTableType.SAT_PARAMETERS,
    filename=r"sat_parameters.*",
)
sat_results = lfq.search(q_sat)
check("sat_parameters found", len(sat_results) > 0, f"found {len(sat_results)}")


# ---------------------------------------------------------------------------
# 10) exists() and best_match()
# ---------------------------------------------------------------------------

section("10. exists() and best_match()")

check("exists(SP3 query) is True", lfq.exists(q_sp3))
check("exists(ATX query) is True", lfq.exists(q_atx))

best_sp3 = lfq.best_match(q_sp3)
check("best_match(SP3) returns a file", best_sp3 is not None)
if best_sp3:
    print(f"    best_match → {best_sp3.name}")

best_atx = lfq.best_match(q_atx)
check("best_match(ATX) returns a file", best_atx is not None)
if best_atx:
    print(f"    best_match → {best_atx.name}")


# ---------------------------------------------------------------------------
# 11) Edge case — missing date for daily collection
# ---------------------------------------------------------------------------

section("11. Edge cases")

try:
    cfg.resolve(ProductType.SP3)  # daily product without a date
    check("SP3 without date raises ValueError", False)
except ValueError:
    check("SP3 without date raises ValueError", True)

try:
    _product_type_from_query(ProductFileQuery(format=None))
    check("ProductFileQuery(format=None) raises ValueError", False)
except ValueError:
    check("ProductFileQuery(format=None) raises ValueError", True)

try:
    lfq.search(ProductFileQuery(format=ProductFileFormat.SP3, date=DATE, filename=None))
    check("search with filename=None raises ValueError", False)
except ValueError:
    check("search with filename=None raises ValueError", True)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(f"\n{'='*60}")
total = _counts["pass"] + _counts["fail"] + _counts["skip"]
print(f"  Results: {_counts['pass']} passed, {_counts['fail']} failed, {_counts['skip']} skipped  ({total} total)")
print(f"{'='*60}")

sys.exit(1 if _counts["fail"] > 0 else 0)
