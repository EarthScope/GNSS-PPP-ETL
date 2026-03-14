"""
dev_query_spec.py — Demonstrate the unified query spec + regex cascade.

The query engine reads ``query_v2.yaml`` to know which axes each product
supports, then builds a catalog from RemoteResourceRegistry +
LocalResourceRegistry and lets you narrow progressively.

Run:
    python dev/dev_query_spec.py
"""

from __future__ import annotations

import datetime
import json

# ── imports ────────────────────────────────────────────────────────
from gnss_ppp_products.assets.query_spec import QuerySpecRegistry, ProductQuery
from gnss_ppp_products.assets.remote_resource_spec import RemoteResourceRegistry
from gnss_ppp_products.assets.local_resource_spec import LocalResourceRegistry

# ── target date ────────────────────────────────────────────────────
date = datetime.date(2025, 1, 15)
sep = "=" * 72

# ──────────────────────────────────────────────────────────────────
# 1. Show the query spec
# ──────────────────────────────────────────────────────────────────
print(f"\n{sep}")
print("  Query Specification (from query_v2.yaml)")
print(sep)

print(f"\n  Global axes: {list(QuerySpecRegistry.axes.keys())}")
print(f"  Solution preference: {QuerySpecRegistry.solution_preference}")
print(f"\n  Product profiles ({len(QuerySpecRegistry.spec_names)}):")
for name in QuerySpecRegistry.spec_names:
    p = QuerySpecRegistry.profile(name)
    extra = list(p.extra_axes.keys())
    print(f"    {name:<12s}  axes={p.axes}"
          + (f"  extra={extra}" if extra else "")
          + (f"  fixed={p.fixed}" if p.fixed else "")
          + f"  temporal={p.temporal}")

# ──────────────────────────────────────────────────────────────────
# 2. Progressive narrowing demo
# ──────────────────────────────────────────────────────────────────
print(f"\n{sep}")
print(f"  Progressive Query Narrowing   (date = {date})")
print(sep)

q = ProductQuery(date=date)
print(f"\n  ProductQuery(date={date})")
print(f"    {q}")
print(f"    specs:     {q.specs()}")
print(f"    centers:   {q.centers()}")

# Narrow to ORBIT
q1 = q.narrow(spec="ORBIT")
print(f"\n  .narrow(spec='ORBIT')")
print(f"    {q1}")
print(f"    centers:   {q1.centers()}")
print(f"    campaigns: {q1.campaigns()}")
print(f"    solutions: {q1.solutions()}")
print(f"    samplings: {q1.samplings()}")

# Narrow to IGS
q2 = q1.narrow(center="IGS")
print(f"\n  .narrow(center='IGS')")
print(f"    {q2}")
print(f"    campaigns: {q2.campaigns()}")
print(f"    solutions: {q2.solutions()}")
print(f"    samplings: {q2.samplings()}")

# Narrow to FIN
q3 = q2.narrow(solution="FIN")
print(f"\n  .narrow(solution='FIN')")
print(f"    {q3}")
print(f"    samplings: {q3.samplings()}")

# Narrow to 05M — single result
q4 = q3.narrow(sampling="05M")
print(f"\n  .narrow(sampling='05M')")
print(f"    {q4}")
b = q4.best()
if b:
    print(f"    regex:     {b.regex}")
    print(f"    remote:    {b.remote_url}")
    print(f"    local:     {b.local_directory}")

# ──────────────────────────────────────────────────────────────────
# 3. Multi-product query
# ──────────────────────────────────────────────────────────────────
print(f"\n{sep}")
print("  Multi-Product Query (all FIN products from IGS)")
print(sep)

q_igs_fin = q.narrow(center="IGS", solution="FIN")
print(f"\n  q.narrow(center='IGS', solution='FIN')")
print(f"    {q_igs_fin}")
print(f"    specs: {q_igs_fin.specs()}")
for r in q_igs_fin.results:
    print(f"    [{r.spec:<10s}] {r.regex[:65]}")

# ──────────────────────────────────────────────────────────────────
# 4. Branching: compare WUM vs IGS orbits
# ──────────────────────────────────────────────────────────────────
print(f"\n{sep}")
print("  Branching: WUM vs IGS Orbits")
print(sep)

q_orbit = q.narrow(spec="ORBIT", solution="FIN")
for center in ["IGS", "WUM"]:
    branch = q_orbit.narrow(center=center)
    print(f"\n  {center} FIN orbits: {branch.count} variants")
    for r in branch.results:
        print(f"    campaign={r.campaign:<4s} sampling={r.sampling:<4s}  {r.regex[:60]}")

# ──────────────────────────────────────────────────────────────────
# 5. axes_summary() for discovery
# ──────────────────────────────────────────────────────────────────
print(f"\n{sep}")
print("  axes_summary() — discover available filter values")
print(sep)

print("\n  Full catalog summary:")
for axis, vals in q.axes_summary().items():
    print(f"    {axis:<10s}: {vals}")

print("\n  After narrowing to WUM:")
q_wum = q.narrow(center="WUM")
for axis, vals in q_wum.axes_summary().items():
    print(f"    {axis:<10s}: {vals}")

# ──────────────────────────────────────────────────────────────────
# 6. Static products
# ──────────────────────────────────────────────────────────────────
print(f"\n{sep}")
print("  Static Products (no date narrowing)")
print(sep)

for static_spec in ["LEAP_SEC", "SAT_PARAMS", "ATTATX"]:
    qs = q.narrow(spec=static_spec)
    print(f"\n  {static_spec}: {qs.count} results")
    for r in qs.results:
        print(f"    center={r.center:<4s}  regex={r.regex:<30s}  local={r.local_directory}")

# ──────────────────────────────────────────────────────────────────
# 7. Navigation products
# ──────────────────────────────────────────────────────────────────
print(f"\n{sep}")
print("  Navigation (RINEX) Products")
print(sep)

q_nav = q.narrow(spec="RNX3_BRDC")
print(f"\n  RNX3_BRDC: {q_nav.count} results")
print(f"    centers: {q_nav.centers()}")
for r in q_nav.results:
    print(f"    center={r.center:<4s}  {r.regex}")

# ──────────────────────────────────────────────────────────────────
# 8. best() with solution preference
# ──────────────────────────────────────────────────────────────────
print(f"\n{sep}")
print("  best() — auto-select by solution quality preference")
print(sep)

for spec_name in ["ORBIT", "CLOCK", "ERP"]:
    q_spec = q.narrow(spec=spec_name, center="IGS")
    b = q_spec.best()
    if b:
        print(f"  {spec_name:<8s} best: solution={b.solution} sampling={b.sampling}")
        print(f"           regex: {b.regex[:65]}")

# ──────────────────────────────────────────────────────────────────
# 9. Ergonomic dependency pattern preview
# ──────────────────────────────────────────────────────────────────
print(f"\n{sep}")
print("  Dependency Pattern Preview")
print(f"  (how this query spec supports future dependency specs)")
print(sep)
print("""
  A PPP processing dependency spec could look like:

    dependencies:
      orbit:
        spec: ORBIT
        solution: [FIN, RAP]    # accept either, prefer FIN
        sampling: "05M"
      clock:
        spec: CLOCK
        solution: [FIN, RAP]
        sampling: "30S"
      erp:
        spec: ERP
        solution: [FIN, RAP]
      bias:
        spec: BIA
        solution: [FIN, RAP]
      nav:
        spec: RNX3_BRDC

  Each dependency expands into a ProductQuery:
""")

# Simulate dependency resolution
deps = {
    "orbit":  {"spec": "ORBIT",    "solution": "FIN", "sampling": "05M"},
    "clock":  {"spec": "CLOCK",    "solution": "FIN", "sampling": "30S"},
    "erp":    {"spec": "ERP",      "solution": "FIN"},
    "bias":   {"spec": "BIA",      "solution": "FIN"},
    "nav":    {"spec": "RNX3_BRDC"},
}

for dep_name, dep_axes in deps.items():
    dep_q = q.narrow(center="IGS", **dep_axes)
    b = dep_q.best()
    status = "RESOLVED" if b else "NOT FOUND"
    print(f"  {dep_name:<8s} → {dep_q} → {status}")
    if b:
        print(f"             regex: {b.regex[:65]}")
        print(f"             local: {b.local_directory}")

print(f"\n{sep}")
print("  Done.")
print(sep)
