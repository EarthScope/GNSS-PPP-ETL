"""
dev_test_leo.py — Test LEO (GRACE / GRACE-FO) products exclusively.

Validates:
  1. Product spec registry loads LEO_L1B format and product
  2. Remote resource registry has GRACE-FO and GRACE products in GFZ
  3. Regex generation produces correct filename patterns
  4. Directory templates resolve per-instrument
  5. Unified query can narrow by spec, center, and instrument
  6. Query results have correct extras metadata
  7. Local collection mapping

Run:
    uv run dev/dev_test_leo.py
"""

from __future__ import annotations

import datetime
import re
import sys

from gnss_ppp_products.assets.product_spec import ProductSpecRegistry
from gnss_ppp_products.assets.remote_resource_spec import RemoteResourceRegistry
from gnss_ppp_products.assets.local_resource_spec import LocalResourceRegistry
from gnss_ppp_products.assets.query_spec import ProductQuery, QuerySpecRegistry

sep = "=" * 72
errors: list[str] = []

GRACE_FO_DATE = datetime.date(2024, 1, 15)
GRACE_DATE = datetime.date(2016, 6, 15)

GRACE_FO_INSTRUMENTS = ["GNV1B", "ACC1B", "SCA1B", "KBR1B", "LRI1B"]
GRACE_INSTRUMENTS = ["GNV1B", "ACC1B", "SCA1B", "KBR1B"]


def section(title: str) -> None:
    print(f"\n{sep}")
    print(f"  {title}")
    print(sep)


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  OK: {label}")
    else:
        msg = f"FAIL: {label}"
        if detail:
            msg += f" — {detail}"
        print(f"  {msg}")
        errors.append(msg)


# ──────────────────────────────────────────────────────────────────
# 1. Product spec — format and product exist
# ──────────────────────────────────────────────────────────────────
section("1. ProductSpecRegistry — LEO_L1B format & product")

check(
    "LEO_L1B format exists",
    "LEO_L1B" in ProductSpecRegistry.formats,
    f"available formats: {list(ProductSpecRegistry.formats.keys())}",
)

check(
    "LEO_L1B product exists",
    "LEO_L1B" in ProductSpecRegistry.products,
    f"available products: {list(ProductSpecRegistry.products.keys())}",
)

# Check filename templates
templates = ProductSpecRegistry.resolve_filename_templates("LEO_L1B", 0)
check(
    "LEO_L1B has at least one filename template",
    len(templates) > 0,
)
if templates:
    print(f"    template: {templates[0]}")
    check(
        "Template contains {INSTRUMENT}",
        "{INSTRUMENT}" in templates[0],
    )
    check(
        "Template contains {SPACECRAFT}",
        "{SPACECRAFT}" in templates[0],
    )


# ──────────────────────────────────────────────────────────────────
# 2. Remote resource registry — GFZ LEO products
# ──────────────────────────────────────────────────────────────────
section("2. RemoteResourceRegistry — GFZ LEO products")

gfz = RemoteResourceRegistry.get_center("GFZ")
leo_products = gfz.products_for_spec("LEO_L1B")
check(
    "GFZ has 2 LEO_L1B products (grace-fo + grace)",
    len(leo_products) == 2,
    f"found {len(leo_products)}",
)

product_ids = {p.id for p in leo_products}
check(
    "Product IDs include gfz_grace_fo_l1b",
    "gfz_grace_fo_l1b" in product_ids,
    f"IDs: {product_ids}",
)
check(
    "Product IDs include gfz_grace_l1b",
    "gfz_grace_l1b" in product_ids,
    f"IDs: {product_ids}",
)

# Check instrument metadata
fo_prod = RemoteResourceRegistry.get_product("gfz_grace_fo_l1b")
check(
    "GRACE-FO has 5 instruments",
    len(fo_prod.metadata.get("INSTRUMENT", [])) == 5,
    f"got {fo_prod.metadata.get('INSTRUMENT', [])}",
)
check(
    "GRACE-FO includes LRI1B",
    "LRI1B" in fo_prod.metadata.get("INSTRUMENT", []),
)

grace_prod = RemoteResourceRegistry.get_product("gfz_grace_l1b")
check(
    "GRACE has 4 instruments",
    len(grace_prod.metadata.get("INSTRUMENT", [])) == 4,
    f"got {grace_prod.metadata.get('INSTRUMENT', [])}",
)
check(
    "GRACE does not include LRI1B",
    "LRI1B" not in grace_prod.metadata.get("INSTRUMENT", []),
)


# ──────────────────────────────────────────────────────────────────
# 3. Regex generation — GRACE-FO
# ──────────────────────────────────────────────────────────────────
section("3. Regex generation — GRACE-FO (2024-01-15)")

fo_regexes = fo_prod.to_regexes(GRACE_FO_DATE)
check(
    f"GRACE-FO generates {len(GRACE_FO_INSTRUMENTS)} regexes (one per instrument)",
    len(fo_regexes) == len(GRACE_FO_INSTRUMENTS),
    f"got {len(fo_regexes)}",
)

for i, (inst, rx) in enumerate(zip(GRACE_FO_INSTRUMENTS, fo_regexes)):
    print(f"    [{i}] {rx}")
    check(
        f"GRACE-FO regex[{i}] contains {inst}",
        inst in rx,
    )
    check(
        f"GRACE-FO regex[{i}] contains date 2024",
        "2024" in rx,
    )

# Test that regex matches a real filename
test_filename = "GNV1B_2024-01-15_C_04.dat.gz"
gnv_regex = fo_regexes[0]  # first instrument is GNV1B
check(
    f"GNV1B regex matches '{test_filename}'",
    bool(re.search(gnv_regex, test_filename)),
    f"regex: {gnv_regex}",
)

# Test non-match: wrong date
bad_filename = "GNV1B_2024-02-20_C_04.dat.gz"
check(
    f"GNV1B regex does NOT match '{bad_filename}'",
    not bool(re.search(gnv_regex, bad_filename)),
)


# ──────────────────────────────────────────────────────────────────
# 4. Regex generation — GRACE (original)
# ──────────────────────────────────────────────────────────────────
section("4. Regex generation — GRACE (2016-06-15)")

g_regexes = grace_prod.to_regexes(GRACE_DATE)
check(
    f"GRACE generates {len(GRACE_INSTRUMENTS)} regexes",
    len(g_regexes) == len(GRACE_INSTRUMENTS),
    f"got {len(g_regexes)}",
)

for i, (inst, rx) in enumerate(zip(GRACE_INSTRUMENTS, g_regexes)):
    print(f"    [{i}] {rx}")
    check(
        f"GRACE regex[{i}] contains {inst}",
        inst in rx,
    )
    check(
        f"GRACE regex[{i}] contains date 2016",
        "2016" in rx,
    )


# ──────────────────────────────────────────────────────────────────
# 5. Directory resolution — per-instrument
# ──────────────────────────────────────────────────────────────────
section("5. Directory resolution — per-instrument via catalog")

q = ProductQuery(date=GRACE_FO_DATE)
q_leo = q.narrow(spec="LEO_L1B")
print(f"\n  LEO_L1B results: {q_leo.count}")

# Check directories differ per instrument
dirs = {r.remote_directory for r in q_leo.results}
check(
    "Multiple distinct directories (one per instrument combo)",
    len(dirs) > 1,
    f"unique dirs: {len(dirs)}",
)

for r in q_leo.results:
    inst = r.extras.get("INSTRUMENT", "?")
    print(f"    {r.product_id:<22s}  inst={inst:<6s}  dir={r.remote_directory}")
    if inst != "?":
        check(
            f"Directory for {inst} contains the instrument code",
            inst in r.remote_directory,
            f"dir: {r.remote_directory}",
        )

# Verify GRACE-FO directories have RL04 and grace-fo
fo_results = [r for r in q_leo.results if r.product_id == "gfz_grace_fo_l1b"]
for r in fo_results:
    check(
        f"GRACE-FO dir contains 'grace-fo' and 'RL04'",
        "grace-fo" in r.remote_directory and "RL04" in r.remote_directory,
        f"dir: {r.remote_directory}",
    )


# ──────────────────────────────────────────────────────────────────
# 6. Query narrowing — instrument axis
# ──────────────────────────────────────────────────────────────────
section("6. Query narrowing — instrument axis")

q_gnv = q_leo.narrow(instrument="GNV1B")
check(
    "Narrowing to GNV1B yields 2 results (FO + original)",
    q_gnv.count == 2,
    f"got {q_gnv.count}",
)
for r in q_gnv.results:
    check(
        f"GNV1B result '{r.product_id}' has INSTRUMENT=GNV1B",
        r.extras.get("INSTRUMENT") == "GNV1B",
    )

q_lri = q_leo.narrow(instrument="LRI1B")
check(
    "Narrowing to LRI1B yields 1 result (FO only)",
    q_lri.count == 1,
    f"got {q_lri.count}",
)
if q_lri.results:
    check(
        "LRI1B result is from gfz_grace_fo_l1b",
        q_lri.results[0].product_id == "gfz_grace_fo_l1b",
    )


# ──────────────────────────────────────────────────────────────────
# 7. Query narrowing — center axis
# ──────────────────────────────────────────────────────────────────
section("7. Query narrowing — center axis")

q_gfz_leo = q.narrow(spec="LEO_L1B", center="GFZ")
check(
    "LEO_L1B + GFZ returns 9 results (5 FO + 4 GRACE)",
    q_gfz_leo.count == 9,
    f"got {q_gfz_leo.count}",
)


# ──────────────────────────────────────────────────────────────────
# 8. extras metadata population
# ──────────────────────────────────────────────────────────────────
section("8. extras metadata — INSTRUMENT stored correctly")

for r in q_leo.results:
    check(
        f"{r.product_id} extras has INSTRUMENT key",
        "INSTRUMENT" in r.extras,
        f"extras: {r.extras}",
    )
    check(
        f"{r.product_id} extras INSTRUMENT value is valid",
        r.extras["INSTRUMENT"] in GRACE_FO_INSTRUMENTS + GRACE_INSTRUMENTS,
        f"got: {r.extras.get('INSTRUMENT')}",
    )


# ──────────────────────────────────────────────────────────────────
# 9. instruments() helper
# ──────────────────────────────────────────────────────────────────
section("9. instruments() helper")

instruments = q_leo.instruments()
print(f"  Instruments: {instruments}")
check(
    "instruments() returns 5 unique instruments",
    len(instruments) == 5,
    f"got {len(instruments)}: {instruments}",
)
for inst in ["ACC1B", "GNV1B", "KBR1B", "LRI1B", "SCA1B"]:
    check(
        f"'{inst}' in instruments()",
        inst in instruments,
    )


# ──────────────────────────────────────────────────────────────────
# 10. allowed_values for instrument axis
# ──────────────────────────────────────────────────────────────────
section("10. allowed_values for instrument axis")

allowed = q_leo.allowed_values("instrument")
print(f"  allowed_values('instrument'): {allowed}")
check(
    "allowed_values returns 5 instruments",
    len(allowed) == 5,
    f"got {len(allowed)}: {allowed}",
)


# ──────────────────────────────────────────────────────────────────
# 11. Validation — bad instrument rejected
# ──────────────────────────────────────────────────────────────────
section("11. Validation — bad instrument rejected")

try:
    q_leo.narrow(instrument="BOGUS1B")
    errors.append("instrument='BOGUS1B' should have raised ValueError")
    print("  FAIL: instrument='BOGUS1B' was accepted")
except ValueError as e:
    print(f"  OK: instrument='BOGUS1B' → ValueError: {e}")


# ──────────────────────────────────────────────────────────────────
# 12. Local storage mapping
# ──────────────────────────────────────────────────────────────────
section("12. Local storage — LEO collection")

local_coll = LocalResourceRegistry.collection_name_for_spec("LEO_L1B")
check(
    "LEO_L1B maps to 'leo' collection",
    local_coll == "leo",
    f"got: {local_coll}",
)

local_dir = LocalResourceRegistry.resolve_directory("LEO_L1B", GRACE_FO_DATE)
print(f"  Local directory: {local_dir}")
check(
    "Local directory contains '2024'",
    "2024" in local_dir,
    f"dir: {local_dir}",
)
check(
    "Local directory contains 'leo'",
    "leo" in local_dir,
    f"dir: {local_dir}",
)


# ──────────────────────────────────────────────────────────────────
# 13. axes_summary includes instrument
# ──────────────────────────────────────────────────────────────────
section("13. axes_summary includes instruments")

summary = q_leo.axes_summary()
print(f"  axes_summary: {summary}")
check(
    "axes_summary has 'instrument' key",
    "instrument" in summary,
)
check(
    "axes_summary['instrument'] has 5 values",
    len(summary.get("instrument", [])) == 5,
    f"got {len(summary.get('instrument', []))}",
)


# ──────────────────────────────────────────────────────────────────
# 14. QuerySpecRegistry knows LEO_L1B
# ──────────────────────────────────────────────────────────────────
section("14. QuerySpecRegistry — LEO_L1B profile")

check(
    "LEO_L1B in QuerySpecRegistry.products",
    "LEO_L1B" in QuerySpecRegistry.products,
    f"products: {list(QuerySpecRegistry.products.keys())}",
)

profile = QuerySpecRegistry.profile("LEO_L1B")
check(
    "LEO_L1B profile format_key is LEO_L1B",
    profile.format_key == "LEO_L1B",
    f"got: {profile.format_key}",
)
check(
    "LEO_L1B profile temporal is daily",
    profile.temporal == "daily",
)
check(
    "LEO_L1B profile local_collection is leo",
    profile.local_collection == "leo",
)
check(
    "LEO_L1B profile has extra_axes with 'instrument'",
    "instrument" in (profile.extra_axes or {}),
)


# ──────────────────────────────────────────────────────────────────
# 15. Full URL construction example
# ──────────────────────────────────────────────────────────────────
section("15. Full URL construction — GRACE-FO GNV1B")

q_gnv_fo = q.narrow(spec="LEO_L1B", center="GFZ", instrument="GNV1B")
fo_results = [r for r in q_gnv_fo.results if r.product_id == "gfz_grace_fo_l1b"]
check("Found GRACE-FO GNV1B result", len(fo_results) == 1)
if fo_results:
    r = fo_results[0]
    print(f"  URL: {r.remote_url}")
    print(f"  Regex: {r.regex}")
    check(
        "URL contains isdcftp.gfz-potsdam.de",
        "isdcftp.gfz-potsdam.de" in r.remote_url,
    )
    check(
        "URL contains grace-fo/Level-1B/JPL/GNV1B/RL04/2024",
        "grace-fo/Level-1B/JPL/GNV1B/RL04/2024" in r.remote_url,
    )
    check(
        "Regex matches real filename",
        bool(re.search(r.regex, "GNV1B_2024-01-15_C_04.dat.gz")),
        f"regex: {r.regex}",
    )


# ──────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────
section("Summary")

if errors:
    print(f"\n  ERRORS ({len(errors)}):")
    for e in errors:
        print(f"    - {e}")
    sys.exit(1)
else:
    print("\n  All LEO tests passed!")
    sys.exit(0)
