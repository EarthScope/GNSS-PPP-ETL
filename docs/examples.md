# Examples

Three worked examples covering the most common workflows. Each example is
self-contained and runnable after `uv sync --all-packages`.

---

## 1. Surveying product availability across analysis centers

**Goal:** For a given day, find which IGS analysis centers have final SP3
orbits and CLK clocks available, compare the candidates, and pull the
top-ranked orbit file.

Useful before committing to a processing campaign — you can verify that
FIN products exist for your date range before writing a dependency spec.

```python
"""
Survey SP3 orbit and CLK clock availability across IGS analysis centers
for a single day, then download the highest-ranked orbit.
"""

from datetime import datetime, timezone
from pathlib import Path

from gnss_product_management import GNSSClient

# Build client from bundled center specs.
# No base_dir → search-only; add base_dir to enable download.
client = GNSSClient.from_defaults(base_dir=Path.home() / "gnss_data")
date = datetime(2025, 1, 15, tzinfo=timezone.utc)  # 2025 DOY 015

# ── Orbit availability ────────────────────────────────────────────────────
print(f"SP3 orbit candidates for {date.date()}\n{'─'*55}")
orbits = (
    client.query()
    .for_product("ORBIT")
    .on(date)
    .prefer(TTT=["FIN", "RAP", "ULT"], AAA=["WUM", "COD", "GFZ", "ESA"])
    .search()
)
for r in orbits:
    print(f"  {r.center:<4s}  {r.quality:<3s}  {r.protocol:<5s}  {r.filename}")

# ── Clock availability ────────────────────────────────────────────────────
print(f"\nCLK clock candidates for {date.date()}\n{'─'*55}")
clocks = (
    client.query()
    .for_product("CLOCK")
    .on(date)
    .where(TTT="FIN")                            # hard filter: finals only
    .prefer(AAA=["WUM", "COD", "GFZ", "ESA"])
    .search()
)
for r in clocks:
    print(f"  {r.center:<4s}  {r.quality:<3s}  {r.protocol:<5s}  {r.filename}")

# ── Bias availability (required for PPP-AR integer fixing) ────────────────
print(f"\nBIA bias candidates for {date.date()}\n{'─'*55}")
biases = (
    client.query()
    .for_product("BIA")
    .on(date)
    .where(TTT="FIN")
    .search()
)
for r in biases:
    print(f"  {r.center:<4s}  {r.quality:<3s}  {r.filename}")

# ── Download the best orbit ───────────────────────────────────────────────
if orbits:
    best = orbits[0]
    print(f"\nDownloading: {best.filename}  ({best.center} / {best.quality})")
    paths = client.download([best], sink_id="local")
    if paths:
        print(f"Saved to: {paths[0]}")
```

---

## 2. Automated dependency resolution with a shared  workspace

**Goal:** Resolve a full PPP-AR product set (orbit, clock, bias, ERP, ATX)
for a date range using a timeliness cascade, store results, and
demonstrate the lockfile fast-path on a second call.

This pattern suits a production pipeline where multiple workers share a
common product store. A worker that finds an existing `DependencyLockFile`
for `(package, task, date)` skips all network activity.

```python
"""
Resolve IGS products for a 7-day window and store them in an S3 workspace.
Demonstrates the lockfile fast-path and handling of missing required products.
"""

from datetime import datetime, timedelta, timezone

from gnss_product_management import GNSSClient

# S3 workspace — replace with your bucket/prefix.
# All path operations (search, download, lockfile I/O) are identical to local.
client = GNSSClient.from_defaults(
    base_dir="s3://my-bucket/gnss/products",
    max_connections=6,      # tune per-center rate limits
)

dep_spec = "path/to/pride_pppar.yaml"   # DependencySpec YAML path
start    = datetime(2025, 1, 9,  tzinfo=timezone.utc)
end      = datetime(2025, 1, 15, tzinfo=timezone.utc)

dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]

for date in dates:
    resolution, lockfile_path = client.resolve_dependencies(
        dep_spec, date, sink_id="local"
    )

    if not resolution.all_required_fulfilled:
        missing = [r.spec for r in resolution.missing if r.required]
        print(f"{date.date()}  INCOMPLETE  missing={missing}")
        continue

    # On repeat runs the lockfile is detected and this returns immediately.
    print(f"{date.date()}  OK  lockfile={lockfile_path}")
    for spec, path in resolution.product_paths().items():
        print(f"    {spec:<14s}  {path.name}")

# ── Second pass: all dates return from lockfile ───────────────────────────
print("\nSecond pass (lockfile fast-path):")
for date in dates:
    resolution, _ = client.resolve_dependencies(dep_spec, date, sink_id="local")
    status = "cached" if resolution.all_required_fulfilled else "incomplete"
    print(f"  {date.date()}  {status}")

# ── Date-range search (parallel across dates) ─────────────────────────────
print("\nDate-range orbit search:")
results = (
    client.query()
    .for_product("ORBIT")
    .on_range(start, end)          # searches each day in parallel (≤8 threads)
    .where(TTT="FIN")
    .sources("WUM", "COD")
    .search()
)
by_date = {}
for r in results:
    by_date.setdefault(r.date.date(), []).append(r)
for d, rs in sorted(by_date.items()):
    centers = ", ".join(r.center for r in rs)
    print(f"  {d}  {len(rs)} files  ({centers})")
```

---

## 3. Processing a station-year of RINEX files with PRIDE-PPPAR

**Goal:** Process 365 daily RINEX observation files from a single GNSS
station, one per day, share product resolution across files on the same
date, and inspect the kinematic output.

`process_batch` resolves IGS products once per unique date before
dispatching `pdp3`. A year of data from one station requires at most 365
product resolution calls regardless of how many files share a date.

```python
"""
Process a full station-year with PRIDE-PPPAR.
Products are resolved once per day; pdp3 runs in parallel.
"""

from pathlib import Path

import pandas as pd

from pride_ppp import PrideProcessor, ProcessingMode

# ── Setup ─────────────────────────────────────────────────────────────────
# Use FINAL mode: only accept IGS final products (FIN).
# Switch to DEFAULT if your dates are within the last two weeks.
processor = PrideProcessor(
    pride_dir=Path("/data/pride"),          # products + config_file per doy
    output_dir=Path("/data/output/SITE"),   # .kin and .res files per day
    mode=ProcessingMode.FINAL,
)

# Collect one RINEX file per day (IGS long filename: SITE00CCC_R_YYYYDDDHHMM_01D_30S_MO.rnx)
rinex_dir   = Path("/data/rinex/SITE")
rinex_files = sorted(rinex_dir.glob("*.rnx"))
print(f"Found {len(rinex_files)} RINEX files")

# ── Batch processing ─────────────────────────────────────────────────────
# max_workers=4 runs four pdp3 subprocesses concurrently.
# Product resolution and config writing are always single-threaded.
succeeded = []
failed    = []

for result in processor.process_batch(rinex_files, max_workers=4):
    if result.success:
        succeeded.append(result)
        print(f"  OK    {result.date}  {result.site}")
    else:
        failed.append(result)
        print(f"  FAIL  {result.date}  rc={result.returncode}")

print(f"\n{len(succeeded)}/{len(rinex_files)} days processed successfully")
if failed:
    print(f"Failed dates: {[r.date for r in failed]}")

# ── Inspect positions for one day ─────────────────────────────────────────
if succeeded:
    sample = succeeded[0]
    df = sample.positions()
    if df is not None:
        print(f"\n{sample.date} — {len(df)} epochs")
        print(df[["epoch", "X", "Y", "Z"]].head())

# ── Aggregate all positions into one DataFrame ────────────────────────────
frames = [r.positions() for r in succeeded if r.positions() is not None]
if frames:
    all_positions = pd.concat(frames, ignore_index=True)
    print(f"\nTotal epochs across station-year: {len(all_positions)}")

# ── Check product resolution for a failed day ─────────────────────────────
if failed:
    bad = failed[0]
    print(f"\nDependency resolution for failed day {bad.date}:")
    print(bad.resolution.summary())
    missing = [r.spec for r in bad.resolution.missing if r.required]
    if missing:
        print(f"Missing required products: {missing}")

# ── Re-process failed days with override ──────────────────────────────────
if failed:
    print("\nRe-processing failed days:")
    for result in processor.process_batch(
        [r.rinex_path for r in failed],
        max_workers=2,
        override=True,          # ignore cached .kin files
    ):
        status = "OK" if result.success else "FAIL"
        print(f"  [{status}] {result.date}")
```

---

## Running the examples

The scripts above are written to be copied and adapted. The package also
ships minimal runnable scripts under each package's `examples/` directory:

| Script | Package | Description |
|---|---|---|
| [`search_products.py`](https://github.com/EarthScope/GNSSommelier/blob/main/packages/gnss-product-management/examples/search_products.py) | gnss-product-management | Four progressively narrower search patterns |
| [`download_from_center.py`](https://github.com/EarthScope/GNSSommelier/blob/main/packages/gnss-product-management/examples/download_from_center.py) | gnss-product-management | Search → inspect → download |
| [`process_rinex.py`](https://github.com/EarthScope/GNSSommelier/blob/main/packages/pride-ppp/examples/process_rinex.py) | pride-ppp | Single RINEX file end-to-end |
| [`batch_process.py`](https://github.com/EarthScope/GNSSommelier/blob/main/packages/pride-ppp/examples/batch_process.py) | pride-ppp | Batch processing with `process_batch` |
