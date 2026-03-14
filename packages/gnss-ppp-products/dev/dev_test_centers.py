"""
dev_test_centers.py — Test all migrated center configurations.

Loads every *_v2.yml remote resource spec and exercises:
  1. Registry loading — all centers discovered
  2. Per-center product listing and regex generation
  3. Unified query across all centers
  4. Per-center query narrowing + validation

Run:
    uv run dev/dev_test_centers.py
"""

from __future__ import annotations

import datetime
import sys

from gnss_ppp_products.assets.remote_resource_spec import RemoteResourceRegistry
from gnss_ppp_products.assets.query_spec import ProductQuery, QuerySpecRegistry

date = datetime.date(2025, 1, 15)
sep = "=" * 72
errors: list[str] = []


def section(title: str) -> None:
    print(f"\n{sep}")
    print(f"  {title}")
    print(sep)


# ──────────────────────────────────────────────────────────────────
# 1. Registry loading
# ──────────────────────────────────────────────────────────────────
section("1. Registry — all centers loaded")

expected_centers = {"CDDIS", "COD", "ESA", "GFZ", "IGS", "VMF", "WUM"}
loaded = set(RemoteResourceRegistry.centers.keys())
print(f"\n  Loaded centers: {sorted(loaded)}")
missing = expected_centers - loaded
if missing:
    errors.append(f"Missing centers: {missing}")
    print(f"  ERROR — missing: {missing}")
else:
    print("  OK — all expected centers present")

print(f"\n  Total products across all centers: {len(RemoteResourceRegistry.all_products)}")


# ──────────────────────────────────────────────────────────────────
# 2. Per-center: products, servers, regex generation
# ──────────────────────────────────────────────────────────────────
section("2. Per-center product listing + regex generation")

for center_id in sorted(RemoteResourceRegistry.centers.keys()):
    center = RemoteResourceRegistry.get_center(center_id)
    print(f"\n  ── {center_id} ({center.name}) ──")
    print(f"     Servers: {[s.id for s in center.servers]}")

    for rp in center.products:
        n_combos = len(rp._metadata_combinations())
        try:
            regexes = rp.to_regexes(date)
            n_regex = len(regexes)
            sample = regexes[0][:65] if regexes else "(none)"
        except Exception as e:
            n_regex = 0
            sample = f"ERROR: {e}"
            errors.append(f"{center_id}/{rp.id}: regex generation failed: {e}")

        dir_resolved = rp.resolve_directory(date) if rp.directory else "(none)"
        print(
            f"     {rp.id:<25s}  spec={rp.spec_name:<12s}  "
            f"combos={n_combos:<3d}  regexes={n_regex:<3d}  "
            f"dir={dir_resolved}"
        )
        print(f"       sample: {sample}")


# ──────────────────────────────────────────────────────────────────
# 3. Unified query — full catalog
# ──────────────────────────────────────────────────────────────────
section("3. Unified query — full catalog")

q = ProductQuery(date=date)
print(f"\n  {q}")
print(f"  Centers:   {q.centers()}")
print(f"  Specs:     {q.specs()}")
print(f"  Campaigns: {q.campaigns()}")
print(f"  Solutions: {q.solutions()}")
print(f"  Samplings: {q.samplings()}")


# ──────────────────────────────────────────────────────────────────
# 4. Per-center narrowing tests
# ──────────────────────────────────────────────────────────────────
section("4. Per-center narrowing tests")

for center_id in sorted(q.centers()):
    qc = q.narrow(center=center_id)
    print(f"\n  ── {center_id}: {qc.count} results ──")
    print(f"     Specs:     {qc.specs()}")
    print(f"     Campaigns: {qc.campaigns()}")
    print(f"     Solutions: {qc.solutions()}")
    print(f"     Samplings: {qc.samplings()}")

    # Try narrowing to ORBIT if available
    if "ORBIT" in qc.specs():
        qo = qc.narrow(spec="ORBIT")
        b = qo.best()
        if b:
            print(f"     Best ORBIT: solution={b.solution} sampling={b.sampling}")
            print(f"       regex: {b.regex[:70]}")
            print(f"       remote: {b.remote_url}")
        else:
            print("     Best ORBIT: (none)")


# ──────────────────────────────────────────────────────────────────
# 5. CDDIS — mirror site with multi-AC products
# ──────────────────────────────────────────────────────────────────
section("5. CDDIS — mirror products from multiple analysis centers")

qc = q.narrow(center="CDDIS")
print(f"\n  CDDIS total: {qc.count} results")

# Show orbit variants grouped by regex AAA prefix
orbits = qc.narrow(spec="ORBIT", solution="FIN")
print(f"\n  CDDIS FIN orbits: {orbits.count} variants")
for r in orbits.results:
    print(f"    campaign={r.campaign:<4s} sampling={r.sampling:<4s}  {r.regex[:65]}")


# ──────────────────────────────────────────────────────────────────
# 6. CODE — GPS + MGEX + ionosphere
# ──────────────────────────────────────────────────────────────────
section("6. CODE — products including ionosphere")

qc = q.narrow(center="COD")
print(f"\n  COD total: {qc.count} results")
print(f"  Specs: {qc.specs()}")

# IONEX with PRD (predicted) solution — unique to CODE
ionex = qc.narrow(spec="IONEX")
print(f"\n  COD IONEX: {ionex.count} results")
print(f"  Solutions: {ionex.solutions()}")
for r in ionex.results[:4]:
    print(f"    solution={r.solution:<4s} sampling={r.sampling:<4s}  {r.regex[:65]}")


# ──────────────────────────────────────────────────────────────────
# 7. ESA — GPS + Galileo
# ──────────────────────────────────────────────────────────────────
section("7. ESA — ORBIT, CLOCK, IONEX")

qc = q.narrow(center="ESA")
print(f"\n  ESA total: {qc.count} results")
print(f"  Specs: {qc.specs()}")

best_orbit = qc.narrow(spec="ORBIT").best()
if best_orbit:
    print(f"\n  Best ORBIT: {best_orbit.regex[:65]}")
    print(f"    remote: {best_orbit.remote_url}")


# ──────────────────────────────────────────────────────────────────
# 8. GFZ — GPS (GFZ) + MGEX (GBM)
# ──────────────────────────────────────────────────────────────────
section("8. GFZ — dual AAA codes (GFZ + GBM)")

qc = q.narrow(center="GFZ")
print(f"\n  GFZ total: {qc.count} results")
print(f"  Specs: {qc.specs()}")

orbits = qc.narrow(spec="ORBIT", solution="FIN")
print(f"\n  GFZ FIN orbits: {orbits.count} variants")
for r in orbits.results:
    print(f"    campaign={r.campaign:<4s} sampling={r.sampling:<4s}  {r.regex[:65]}")


# ──────────────────────────────────────────────────────────────────
# 9. VMF — troposphere + orography
# ──────────────────────────────────────────────────────────────────
section("9. VMF — troposphere mapping functions + orography")

qc = q.narrow(center="VMF")
print(f"\n  VMF total: {qc.count} results")
print(f"  Specs: {qc.specs()}")

vmf_prods = qc.narrow(spec="VMF")
print(f"\n  VMF products: {vmf_prods.count} results")
for r in vmf_prods.results[:6]:
    print(f"    {r.regex}")

orog = qc.narrow(spec="OROGRAPHY")
print(f"\n  OROGRAPHY products: {orog.count} results")
for r in orog.results:
    print(f"    {r.regex}  dir={r.remote_url}")


# ──────────────────────────────────────────────────────────────────
# 10. Cross-center comparison: who provides ORBIT FIN 05M?
# ──────────────────────────────────────────────────────────────────
section("10. Cross-center comparison: ORBIT FIN 05M")

q_orbit = q.narrow(spec="ORBIT", solution="FIN", sampling="05M")
print(f"\n  ORBIT FIN 05M: {q_orbit.count} results across {q_orbit.centers()}")
for r in q_orbit.results:
    print(f"    center={r.center:<6s} campaign={r.campaign:<4s}  {r.regex[:55]}  remote={r.remote_url[:50]}")


# ──────────────────────────────────────────────────────────────────
# 11. Validation — ensures bad values are rejected
# ──────────────────────────────────────────────────────────────────
section("11. Validation — bad values rejected")

test_cases = [
    ("center", "NONEXISTENT"),
    ("solution", "BOGUS"),
    ("spec", "FAKE_PRODUCT"),
]
for axis, value in test_cases:
    try:
        q.narrow(**{axis: value})
        errors.append(f"Validation failed: {axis}={value} should have raised ValueError")
        print(f"  FAIL: {axis}={value!r} was accepted (should be rejected)")
    except ValueError as e:
        print(f"  OK: {axis}={value!r} → ValueError: {e}")


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
    print("\n  All tests passed!")
    sys.exit(0)
