"""
dev_test_deps.py — Test dependency specification and resolution.

Validates:
  1. DependencySpec loads from YAML
  2. Model structure (preferences, dependencies)
  3. DependencyResolver builds catalog and narrows correctly
  4. Preference cascade works (axes skipped for inapplicable products)
  5. Local resolution (no downloads — just preference ordering + regex)
  6. Resolution result accessors and summary
  7. product_paths() for fulfilled mock scenario

Run:
    uv run dev/dev_test_deps.py
"""

from __future__ import annotations

import datetime
import sys
import tempfile
from pathlib import Path

from gnss_ppp_products.assets.dependency_spec import (
    DependencyResolution,
    DependencyResolver,
    DependencySpec,
    ResolvedDependency,
)
from gnss_ppp_products.assets.query_spec import ProductQuery

sep = "=" * 72
errors: list[str] = []

SPEC_PATH = Path(__file__).resolve().parent.parent / (
    "src/gnss_ppp_products/assets/dependency_spec/pride_ppp_kin.yml"
)
DATE = datetime.date(2025, 1, 15)


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
# 1. Load YAML spec
# ──────────────────────────────────────────────────────────────────
section("1. Load DependencySpec from YAML")

spec = DependencySpec.from_yaml(SPEC_PATH)
print(f"  name: {spec.name}")
print(f"  description: {spec.description[:60]}...")

check(
    "name is 'pride_ppp_kinematic'",
    spec.name == "pride_ppp_kinematic",
    f"got: {spec.name}",
)


# ──────────────────────────────────────────────────────────────────
# 2. Preferences structure
# ──────────────────────────────────────────────────────────────────
section("2. Preferences structure")

check(
    "Has 7 preferences",
    len(spec.preferences) == 7,
    f"got {len(spec.preferences)}",
)

print("  Preference cascade:")
for i, p in enumerate(spec.preferences):
    label = p.center
    if p.solution:
        label += f"/{p.solution}"
    if p.campaign:
        label += f"/{p.campaign}"
    print(f"    [{i}] {label}")

check(
    "First preference is WUM/FIN/MGX",
    spec.preferences[0].center == "WUM"
    and spec.preferences[0].solution == "FIN"
    and spec.preferences[0].campaign == "MGX",
)

check(
    "Second preference is IGS/FIN/OPS",
    spec.preferences[1].center == "IGS"
    and spec.preferences[1].solution == "FIN"
    and spec.preferences[1].campaign == "OPS",
)


# ──────────────────────────────────────────────────────────────────
# 3. Dependencies structure
# ──────────────────────────────────────────────────────────────────
section("3. Dependencies structure")

check(
    "Has 8 dependencies",
    len(spec.dependencies) == 8,
    f"got {len(spec.dependencies)}",
)

required_specs = {d.spec for d in spec.dependencies if d.required}
optional_specs = {d.spec for d in spec.dependencies if not d.required}

check(
    "6 required: ORBIT, CLOCK, ERP, BIA, ATTOBX, RNX3_BRDC",
    required_specs == {"ORBIT", "CLOCK", "ERP", "BIA", "ATTOBX", "RNX3_BRDC"},
    f"got: {sorted(required_specs)}",
)

check(
    "2 optional: LEAP_SEC, SAT_PARAMS",
    optional_specs == {"LEAP_SEC", "SAT_PARAMS"},
    f"got: {sorted(optional_specs)}",
)


# ──────────────────────────────────────────────────────────────────
# 4. Resolver — dry resolve (no downloads, empty local dir)
# ──────────────────────────────────────────────────────────────────
section("4. Resolver — dry resolve (empty local, no download)")

with tempfile.TemporaryDirectory() as tmpdir:
    resolver = DependencyResolver(spec, base_dir=tmpdir)
    result = resolver.resolve(DATE, download=False)

    print(f"\n  {result.summary()}")

    check(
        "All 8 deps resolved (status may be missing)",
        len(result.resolved) == 8,
        f"got {len(result.resolved)}",
    )

    # Everything should be missing (empty local dir, no download)
    check(
        "All 8 missing (no local files, no download)",
        len(result.missing) == 8,
        f"missing={len(result.missing)}, fulfilled={len(result.fulfilled)}",
    )

    check(
        "all_required_fulfilled is False",
        not result.all_required_fulfilled,
    )

    check(
        "product_paths() is empty",
        len(result.product_paths()) == 0,
    )


# ──────────────────────────────────────────────────────────────────
# 5. Preference cascade — verify ordering logic
# ──────────────────────────────────────────────────────────────────
section("5. Preference cascade — ordering logic")

# Build catalog and narrow to ORBIT to inspect preference resolution
q = ProductQuery(date=DATE)
q_orbit = q.narrow(spec="ORBIT")

print(f"\n  ORBIT results in catalog: {q_orbit.count}")
print(f"  Centers with ORBIT: {q_orbit.centers()}")
print(f"  Solutions: {q_orbit.solutions()}")
print(f"  Campaigns: {q_orbit.campaigns()}")

# Verify WUM FIN MGX orbit exists in the catalog
try:
    q_wum_fin = q_orbit.narrow(center="WUM", solution="FIN", campaign="MGX")
    check(
        "WUM FIN MGX ORBIT available in catalog",
        q_wum_fin.count > 0,
        f"count: {q_wum_fin.count}",
    )
    for r in q_wum_fin.results[:2]:
        print(f"    {r.regex[:60]}  dir={r.remote_directory[:40]}")
except ValueError as e:
    check("WUM FIN MGX ORBIT available in catalog", False, str(e))

# Verify IGS FIN OPS orbit exists
try:
    q_igs_fin = q_orbit.narrow(center="IGS", solution="FIN", campaign="OPS")
    check(
        "IGS FIN OPS ORBIT available in catalog",
        q_igs_fin.count > 0,
        f"count: {q_igs_fin.count}",
    )
except ValueError as e:
    check("IGS FIN OPS ORBIT available in catalog", False, str(e))


# ──────────────────────────────────────────────────────────────────
# 6. Axes skipping — static products and navigation
# ──────────────────────────────────────────────────────────────────
section("6. Axes skipping — LEAP_SEC and RNX3_BRDC")

# LEAP_SEC has no solution/campaign axes — preferences should
# still try each center in order
q_leap = q.narrow(spec="LEAP_SEC")
print(f"\n  LEAP_SEC results: {q_leap.count}")
print(f"  Centers: {q_leap.centers()}")
print(f"  Solutions: {q_leap.solutions()}")
print(f"  Campaigns: {q_leap.campaigns()}")

check(
    "LEAP_SEC has no solutions",
    len(q_leap.solutions()) == 0,
)
check(
    "LEAP_SEC has no campaigns",
    len(q_leap.campaigns()) == 0,
)
check(
    "LEAP_SEC has at least 1 center",
    len(q_leap.centers()) > 0,
    f"centers: {q_leap.centers()}",
)

# RNX3_BRDC has no solution/campaign either
q_brdc = q.narrow(spec="RNX3_BRDC")
print(f"\n  RNX3_BRDC results: {q_brdc.count}")
print(f"  Centers: {q_brdc.centers()}")
print(f"  Solutions: {q_brdc.solutions()}")

check(
    "RNX3_BRDC has no solutions",
    len(q_brdc.solutions()) == 0,
)


# ──────────────────────────────────────────────────────────────────
# 7. Simulated local resolution — place a fake file
# ──────────────────────────────────────────────────────────────────
section("7. Simulated local resolution")

with tempfile.TemporaryDirectory() as tmpdir:
    resolver = DependencyResolver(spec, base_dir=tmpdir)

    # Find what regex/directory the first ORBIT preference would use
    q = ProductQuery(date=DATE)
    q_orbit = q.narrow(spec="ORBIT")

    # Narrow to first preference: WUM FIN MGX
    q_pref = q_orbit.narrow(center="WUM", solution="FIN", campaign="MGX")
    if q_pref.results:
        first = q_pref.results[0]
        # Create the local directory + a fake file matching the regex
        local_dir = Path(tmpdir) / first.local_directory
        local_dir.mkdir(parents=True, exist_ok=True)

        # Build a fake filename that matches the regex
        fake_name = "WUM0MGXFIN_20250150000_01D_05M_ORB.SP3.gz"
        (local_dir / fake_name).write_text("fake content")
        print(f"  Planted fake file: {local_dir / fake_name}")

        # Now resolve — ORBIT should be found locally
        result = resolver.resolve(DATE, download=False)

        orbit_result = next(
            (r for r in result.resolved if r.spec == "ORBIT"), None
        )
        check(
            "ORBIT resolved as 'local'",
            orbit_result is not None and orbit_result.status == "local",
            f"status: {orbit_result.status if orbit_result else 'not found'}",
        )
        if orbit_result and orbit_result.status == "local":
            check(
                "ORBIT local_path points to the fake file",
                orbit_result.local_path is not None
                and orbit_result.local_path.name == fake_name,
                f"path: {orbit_result.local_path}",
            )
            check(
                "ORBIT preference_rank is 0 (first preference)",
                orbit_result.preference_rank == 0,
                f"rank: {orbit_result.preference_rank}",
            )
            check(
                "ORBIT preference_label contains 'WUM'",
                "WUM" in orbit_result.preference_label,
                f"label: {orbit_result.preference_label}",
            )

        # Other products should still be missing
        non_orbit = [r for r in result.resolved if r.spec != "ORBIT"]
        check(
            "Other 7 deps still missing",
            all(r.status == "missing" for r in non_orbit),
            f"statuses: {[r.status for r in non_orbit]}",
        )

        print(f"\n  {result.summary()}")
    else:
        check("WUM FIN MGX ORBIT in catalog", False, "no results")


# ──────────────────────────────────────────────────────────────────
# 8. Preference fallback — file only matches second preference
# ──────────────────────────────────────────────────────────────────
section("8. Preference fallback — IGS FIN OPS over WUM")

with tempfile.TemporaryDirectory() as tmpdir:
    resolver = DependencyResolver(spec, base_dir=tmpdir)

    q = ProductQuery(date=DATE)
    q_orbit = q.narrow(spec="ORBIT")

    # Narrow to second preference: IGS FIN OPS
    try:
        q_igs = q_orbit.narrow(center="IGS", solution="FIN", campaign="OPS")
    except ValueError:
        q_igs = None

    if q_igs and q_igs.results:
        first = q_igs.results[0]
        local_dir = Path(tmpdir) / first.local_directory
        local_dir.mkdir(parents=True, exist_ok=True)

        fake_name = "IGS0OPSFIN_20250150000_01D_05M_ORB.SP3.gz"
        (local_dir / fake_name).write_text("fake content")
        print(f"  Planted fake IGS file: {local_dir / fake_name}")

        result = resolver.resolve(DATE, download=False)
        orbit_result = next(
            (r for r in result.resolved if r.spec == "ORBIT"), None
        )
        check(
            "ORBIT falls back to IGS/FIN/OPS (rank 1)",
            orbit_result is not None and orbit_result.preference_rank == 1,
            f"rank: {orbit_result.preference_rank if orbit_result else 'N/A'}",
        )
        if orbit_result and orbit_result.local_path:
            check(
                "ORBIT local file is the IGS file",
                "IGS" in orbit_result.local_path.name,
                f"name: {orbit_result.local_path.name}",
            )
    else:
        print("  Skipping — IGS FIN OPS ORBIT not in catalog")


# ──────────────────────────────────────────────────────────────────
# 9. Result accessors and table
# ──────────────────────────────────────────────────────────────────
section("9. Result accessors and table output")

with tempfile.TemporaryDirectory() as tmpdir:
    resolver = DependencyResolver(spec, base_dir=tmpdir)

    # Plant fake files for multiple products
    q = ProductQuery(date=DATE)

    # Plant ORBIT (WUM FIN MGX)
    try:
        q_wum = q.narrow(spec="ORBIT", center="WUM", solution="FIN", campaign="MGX")
        if q_wum.results:
            d = Path(tmpdir) / q_wum.results[0].local_directory
            d.mkdir(parents=True, exist_ok=True)
            (d / "WUM0MGXFIN_20250150000_01D_05M_ORB.SP3.gz").write_text("fake")
    except ValueError:
        pass

    # Plant CLOCK (WUM FIN MGX)
    try:
        q_clk = q.narrow(spec="CLOCK", center="WUM", solution="FIN", campaign="MGX")
        if q_clk.results:
            d = Path(tmpdir) / q_clk.results[0].local_directory
            d.mkdir(parents=True, exist_ok=True)
            (d / "WUM0MGXFIN_20250150000_01D_30S_CLK.CLK.gz").write_text("fake")
    except ValueError:
        pass

    result = resolver.resolve(DATE, download=False)

    print(f"\n  {result.summary()}")
    print()
    print(result.table())

    local_count = len(result.fulfilled)
    check(
        "At least 2 products found locally",
        local_count >= 2,
        f"got {local_count}",
    )

    paths = result.product_paths()
    check(
        "product_paths has ORBIT",
        "ORBIT" in paths,
        f"keys: {list(paths.keys())}",
    )
    check(
        "product_paths has CLOCK",
        "CLOCK" in paths,
        f"keys: {list(paths.keys())}",
    )

    check(
        "all_required_fulfilled is False (only 2 of 6 required)",
        not result.all_required_fulfilled,
    )


# ──────────────────────────────────────────────────────────────────
# 10. Constraints — extra axis pinning
# ──────────────────────────────────────────────────────────────────
section("10. Constraints — extra axis pinning")

# Build a spec with a sampling constraint on ORBIT
from gnss_ppp_products.assets.dependency_spec.models import (
    Dependency,
    DependencySpec as DS,
    SearchPreference,
)

constrained = DS(
    name="constrained_test",
    preferences=[
        SearchPreference(center="WUM"),
    ],
    dependencies=[
        Dependency(
            spec="ORBIT",
            required=True,
            constraints={"sampling": "15M"},
        ),
    ],
)

with tempfile.TemporaryDirectory() as tmpdir:
    resolver = DependencyResolver(constrained, base_dir=tmpdir)

    # Build catalogs to see what's available
    q = ProductQuery(date=DATE)
    q_orbit_15m = q.narrow(spec="ORBIT", center="WUM", sampling="15M")
    print(f"\n  WUM ORBIT 15M results: {q_orbit_15m.count}")

    if q_orbit_15m.results:
        d = Path(tmpdir) / q_orbit_15m.results[0].local_directory
        d.mkdir(parents=True, exist_ok=True)

        # Plant a 15M orbit file
        fake_15m = "WUM0MGXFIN_20250150000_01D_15M_ORB.SP3.gz"
        (d / fake_15m).write_text("fake")

        # Also plant a 05M file that should NOT be selected
        fake_05m = "WUM0MGXFIN_20250150000_01D_05M_ORB.SP3.gz"
        (d / fake_05m).write_text("fake")

        result = resolver.resolve(DATE, download=False)
        orbit_r = result.resolved[0]
        check(
            "Constrained ORBIT resolves to 15M file",
            orbit_r.status == "local"
            and orbit_r.local_path is not None
            and "15M" in orbit_r.local_path.name,
            f"path: {orbit_r.local_path}",
        )
    else:
        print("  Skipping — no WUM ORBIT 15M in catalog")


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
    print("\n  All dependency tests passed!")
    sys.exit(0)
