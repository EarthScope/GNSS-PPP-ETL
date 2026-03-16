"""
dev_test_deps.py — Resolve PRIDE-PPP dependencies and download products.

Loads the pride_ppp_kin.yml dependency spec, resolves all products for
2025-01-01, and downloads missing files into ~/gnss_products/.

Run:
    uv run dev/dev_test_deps.py
"""

from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path
import time

from gnss_ppp_products.assets.dependency_spec import (
    DependencyResolution,
    DependencyResolver,
    DependencySpec,
    ResolvedDependency,
)
from gnss_ppp_products.assets.query_spec import ProductQuery

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s: %(message)s",
)

sep = "=" * 72
errors: list[str] = []

SPEC_PATH = Path(__file__).resolve().parent.parent / (
    "src/gnss_ppp_products/assets/dependency_spec/pride_ppp_kin.yml"
)
BASE_DIR = Path.home() / "gnss_products"
DATE = datetime.date(2025, 1, 4)


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
# 1. Load spec
# ──────────────────────────────────────────────────────────────────
section("1. Load DependencySpec")

spec = DependencySpec.from_yaml(SPEC_PATH)
print(f"  name:        {spec.name}")
print(f"  description: {spec.description}")
print(f"  preferences: {len(spec.preferences)}")
print(f"  dependencies: {len(spec.dependencies)}")

for i, p in enumerate(spec.preferences):
    label = p.center
    if p.solution:
        label += f"/{p.solution}"
    if p.campaign:
        label += f"/{p.campaign}"
    print(f"    [{i}] {label}")

check("spec loaded", spec.name == "pride_ppp_kinematic", f"got: {spec.name}")


# ──────────────────────────────────────────────────────────────────
# 2. Prepare local directory
# ──────────────────────────────────────────────────────────────────
section("2. Prepare local directory")

BASE_DIR.mkdir(parents=True, exist_ok=True)
print(f"  base_dir: {BASE_DIR}")
print(f"  date:     {DATE}")


# ──────────────────────────────────────────────────────────────────
# 3. Resolve + download
# ──────────────────────────────────────────────────────────────────
section("3. Resolve dependencies (download=True)")

resolver = DependencyResolver(spec, base_dir=str(BASE_DIR))
time_start = time.time()
result = resolver.resolve(DATE, download=True)
time_end = time.time()
elapsed = time_end - time_start
print(f"\n  Resolution completed in {elapsed:.1f} seconds")

# ──────────────────────────────────────────────────────────────────
# 4. Results
# ──────────────────────────────────────────────────────────────────
section("4. Results")

print(f"\n  {result.summary()}\n")
print(result.table())

paths = result.product_paths()
if paths:
    print("\n  Product paths:")
    for spec_name, p in sorted(paths.items()):
        print(f"    {spec_name:12s} → {p}")

check(
    "all_required_fulfilled",
    result.all_required_fulfilled,
    f"fulfilled={len(result.fulfilled)}, missing={len(result.missing)}",
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
    print("\n  All checks passed!")
    sys.exit(0)
