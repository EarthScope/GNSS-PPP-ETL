"""
dev_test_env.py — Test the Environment system end-to-end.

Exercises both loader paths (from_yaml, default), validates cross-
references, runs a scoped query, and resolves dependencies through
Environment-scoped registries.

Run:
    uv run dev/dev_test_env.py
"""

from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path

from gnss_ppp_products.assets.environment import Environment
from gnss_ppp_products.assets.environment.environment import (
    EnvironmentValidationError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s: %(message)s",
)

sep = "=" * 72
errors: list[str] = []

MANIFEST = (
    Path(__file__).resolve().parent.parent
    / "src/gnss_ppp_products/assets/environment/pride_ppp_kin_env.yml"
)
DATE = datetime.date(2025, 1, 1)


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
# 1. Load from YAML manifest
# ──────────────────────────────────────────────────────────────────
section("1. Load Environment from manifest YAML")

env = Environment.from_yaml(MANIFEST)
print(f"  {env!r}")
print()
print(env.summary())

check("name", env.name == "pride_ppp_kinematic", f"got: {env.name}")
check("base_dir exists logic", env.base_dir is not None)
check(
    "has centers",
    len(env.remote.centers) >= 5,
    f"got {len(env.remote.centers)} centers",
)
check(
    "has product specs",
    len(env.products.products) >= 10,
    f"got {len(env.products.products)} product specs",
)
check(
    "has dependencies",
    env.dependencies is not None,
    "no dependencies loaded",
)
check(
    "defaults present",
    "solution" in env.defaults,
    f"defaults: {env.defaults}",
)


# ──────────────────────────────────────────────────────────────────
# 2. Load with default() builder
# ──────────────────────────────────────────────────────────────────
section("2. Load Environment via default() builder")

env2 = Environment.default(
    name="default_test",
    dependency_file="pride_ppp_kin.yml",
)
print(f"  {env2!r}")
check("default has centers", len(env2.remote.centers) >= 5)
check("default has product specs", len(env2.products.products) >= 10)
check("default has dependencies", env2.dependencies is not None)


# ──────────────────────────────────────────────────────────────────
# 3. Cross-validation
# ──────────────────────────────────────────────────────────────────
section("3. Cross-validation")

validation_errors = env.validate()
if validation_errors:
    print(f"  validation returned {len(validation_errors)} error(s):")
    for ve in validation_errors:
        print(f"    - {ve}")
else:
    print("  No validation errors — environment is consistent.")

check("validation clean", len(validation_errors) == 0, f"errors: {validation_errors}")

# Also test validate_or_raise
try:
    env.validate_or_raise()
    check("validate_or_raise", True)
except EnvironmentValidationError as exc:
    check("validate_or_raise", False, str(exc))


# ──────────────────────────────────────────────────────────────────
# 4. Scoped query (no download)
# ──────────────────────────────────────────────────────────────────
section("4. Environment-scoped query")

q = env.query(DATE)
print(f"  Query date: {DATE}")
print(f"  Catalog entries: {len(q._results)}")

# Narrow to ORBIT
q_orbit = q.narrow(spec="ORBIT")
print(f"  ORBIT entries: {len(q_orbit._results)}")
check("orbit entries > 0", len(q_orbit._results) > 0)

# Best orbit
best = q_orbit.best()
if best:
    print(f"  Best ORBIT: {best.product_id} @ {best.center}")
    check("best orbit has center", best.center is not None)
else:
    check("best orbit found", False, "no best orbit returned")


# ──────────────────────────────────────────────────────────────────
# 5. Environment-scoped dependency resolution (NO download)
# ──────────────────────────────────────────────────────────────────
section("5. Environment-scoped dependency resolution (download=False)")

result = env.resolve(DATE, download=False)
print(f"\n  {result.summary()}")
print(result.table())

# We don't expect all files to be present locally, but the
# resolver should at least run without error.
check(
    "resolution ran",
    result is not None,
)
check(
    "resolved count > 0 or missing count > 0",
    len(result.resolved) > 0,
    f"resolved={len(result.resolved)}",
)


# ──────────────────────────────────────────────────────────────────
# 6. Backward compatibility — global singletons still work
# ──────────────────────────────────────────────────────────────────
section("6. Backward compatibility — global singletons")

from gnss_ppp_products.assets.query_spec.engine import ProductQuery

q_global = ProductQuery(date=DATE)
print(f"  Global catalog entries: {len(q_global._results)}")
check("global query works", len(q_global._results) > 0)


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
