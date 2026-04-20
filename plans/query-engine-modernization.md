# Query Engine Modernization: Architecture, Data Layer & Local Data Design

**Status:** Draft for discussion
**Relates to:** `plans/query-streamlining-design.md`, `docs/parquet-use-cases.md`, `docs/architecture.md`
**Scope:** Data layer, query engine, local data ingestion, HPC integration

---

## Executive Summary

The current system is well-designed at its core: immutable builder pattern, clean Protocol interfaces, configuration-driven product specs. But it was built for single-machine interactive use and has hit natural ceilings as workloads grow — hundreds of stations, date ranges spanning months, HPC submission, and collaborators who want to plug in locally archived data without writing Python.

This document proposes a layered modernization across five areas:

1. **Compilation layer** — Introduce an explicit compile step that transforms human-editable sources (YAML specs, protocol API responses) into optimized Arrow artifacts, cached across process starts.
2. **Data layer** — Replace YAML/JSON/CSV with Arrow-native formats (GeoParquet, Parquet) and add DuckDB as a zero-setup query layer. Use Polars for non-spatial tabular operations throughout.
3. **Async query engine** — Replace `ThreadPoolExecutor` blocking I/O with `asyncio` + `anyio` for station metadata and directory listing, unlocking real concurrency at 10× current throughput.
4. **Query API redesign** — Simplify the user-facing API with quality presets, a unified PPP query, and a preview/plan mode that returns a serializable manifest before any I/O.
5. **Local data protocol** — Make user-owned archives (disk, S3, SFTP) first-class citizens via a declarative `LocalDataSource` spec that auto-discovers RINEX files and caches a spatial catalog.

Each section is analyzed from three perspectives: **senior software engineer (SE)**, **geophysicist user (GEO)**, and **HPC operator (HPC)**.

---

## 1. Current Architecture Assessment

### What works well

- **Immutable builder pattern** (`copy.copy()` per method) — thread-safe, composable, reusable intermediate queries.
- **Protocol dispatch via `GNSSNetworkRegistry`** — new networks need only a YAML config + optional Python class. M3G fallback covers most networks automatically.
- **Lockfile-based cache** — `DependencyLockFile` provides a fast-path that skips all network calls on re-runs.
- **Connection pool per server** — `ConnectionPoolFactory` limits concurrent FTP connections per host, respecting server policies (e.g., CDDIS: max 4).
- **Configuration-driven product specs** — centers, networks, products, and local layout are all declarative YAML.

### Where the ceiling shows

| Pain point | Root cause | Impact |
|---|---|---|
| Station metadata queries are serial per network | `metadata()` iterates networks in a `for` loop; each HTTP call blocks | 5 networks × ~2s = 10s before any file search begins |
| YAML station catalogs re-parsed every process start | `yaml.safe_load()` on every startup; no compiled cache | 3,356 total station records parsed from scratch per process |
| No serializable query results | `list[FoundResource]` discarded after each run | No reproducibility; no HPC resume; no audit |
| Local data requires internal knowledge | `WorkSpace` + `local_config.yaml` exist but are undocumented for end users | Users either skip local data or write custom scripts |
| `max_workers` is a user-visible magic number | No adaptive pool sizing; no server-aware throttling | Overloading CDDIS or starving local SSD |
| No dry-run / preview mode | `.search()` mixes directory listing with result ranking | Can't inspect planned downloads before committing |
| Two disconnected query paths | `station_query()` and `product_query()` are entirely separate | PPP workflows require mentally composing two independent builders |

---

## 2. Compilation Layer

### 2.1 The core idea

Every `GNSSClient` startup currently runs the same expensive initialization chain:

```
YAML text → yaml.safe_load() → dict → Pydantic validation
  → ParameterCatalog → FormatCatalog → ProductCatalog
  → _build_match_table() → list[_MatchEntry(compiled_regex=re.compile(...))]
  + station YAML files → list[GNSSStation] × 3,356 records
  + HTTP calls to EarthScope / M3G APIs → live station lists
```

All of this happens before the first query runs. A compilation layer short-circuits the expensive parse-and-validate steps by storing the results as Arrow artifacts, checked against invalidation rules on load. The analogy is exact: Python compiles `.py` → `.pyc` once and reuses the bytecode until the source changes. Here, YAML compiles → Arrow/Parquet once and is reused until the source changes or a TTL expires.

The output of compilation is a **compiled environment** — a directory of Arrow artifacts that represents the complete runtime configuration of the system at a point in time.

### 2.2 Three tiers by change frequency

Not all inputs change at the same rate. The compilation strategy and invalidation rule must match the source's change characteristics:

| Tier | Inputs | Change frequency | Invalidation rule | Output format |
|---|---|---|---|---|
| **1 — Static specs** | `product_spec.yaml`, `format_spec.yaml`, `parameter_spec.yaml` | Package version update only | Version tag in Arrow metadata | Arrow IPC (`.arrow`) |
| **2 — Managed catalogs** | `igs_stations.yaml`, `cors_stations.yaml`, `ga_stations.yaml`, etc. | Package update or manual edit | mtime comparison (source vs. artifact) | GeoParquet (`.parquet`) |
| **3 — Protocol outputs** | EarthScope API, M3G API, any registered `NetworkProtocol.radius_spatial_query()` | Continuous — stations added/decommissioned | TTL (configurable per source, default 7 days) | GeoParquet (`.parquet`) |

### 2.3 Tier 1: Static spec compilation

`ProductRegistry.build()` calls `_build_match_table()`, which compiles regex patterns from all product-format combinations. The `re.Pattern` objects in `_MatchEntry.compiled_regex` cannot be serialized — but the pattern *strings* can. The compiled output stores strings; on load, `re.compile()` in a tight loop reconstructs the patterns in ~1ms, far faster than re-parsing the YAML chain.

**Compiled output (Arrow IPC):**
```python
import pyarrow as pa

match_table_schema = pa.schema([
    pa.field("template_len",  pa.int32()),
    pa.field("regex_pattern", pa.string()),    # stored as string, recompiled on load
    pa.field("product_name",  pa.string()),
    pa.field("format_name",   pa.string()),
    pa.field("version",       pa.string()),
    pa.field("variant",       pa.string()),
    pa.field("fixed_params",  pa.map_(pa.string(), pa.string())),
])

# Written once; loaded as Arrow, regex recompiled in one pass
```

**Metadata for invalidation:**
```python
# Embedded in Arrow file metadata
{
    "gnss_etl_version": "0.5.2",        # invalidate on package update
    "compiled_at": "2026-04-19T14:00Z",
    "source_hash": "sha256:abc123...",   # hash of all source YAML files
}
```

**Load path (fast, normal operation):**
```python
def _load_match_table(cache_path: Path) -> list[_MatchEntry]:
    table = pa.ipc.open_file(cache_path).read_all()
    return [
        _MatchEntry(
            template_len=row["template_len"],
            compiled_regex=re.compile(row["regex_pattern"]),  # ~1ms total
            product_name=row["product_name"],
            ...
        )
        for row in table.to_pylist()
    ]
```

**SE perspective:** The source YAMLs remain authoritative and human-editable. The Arrow artifact is a build artifact — git-ignored, reproducible, never committed. The version tag in metadata means a `pip install --upgrade` automatically invalidates the cache on next startup.

**GEO perspective:** Invisible. Startup is faster. On first run after an update, there's a one-time compile pause of ~1–2 seconds, similar to Python's `.pyc` compile.

**HPC perspective:** The compiled artifacts live in `{base_dir}/.gnss_compile/`. On a shared filesystem, one worker compiles and all subsequent workers load from cache — the OS page cache means the Arrow file is read from disk once and served from memory to all workers.

### 2.4 Tier 2: Managed catalog compilation

Covered in detail in Section 3.2 (GeoParquet station catalogs). The invalidation rule here is a simple mtime comparison: if the source YAML is newer than the GeoParquet artifact, recompile.

```python
def _load_or_compile_catalog(yaml_path: Path, parquet_path: Path) -> gpd.GeoDataFrame:
    if (parquet_path.exists() and
            parquet_path.stat().st_mtime > yaml_path.stat().st_mtime):
        return gpd.read_parquet(parquet_path)          # fast path: ~10ms
    gdf = _compile_station_yaml(yaml_path)
    gdf.to_parquet(parquet_path, compression="zstd")
    return gdf                                          # slow path: ~200ms, runs once
```

### 2.5 Tier 3: Protocol output catalog sync

This is the most consequential change for workflow. Currently, `EarthScopeProtocol.radius_spatial_query()` and `M3GNetworkProtocol` make live HTTP calls on every invocation. These APIs return station lists that evolve slowly — typically on the scale of weeks as stations are installed or decommissioned.

The model is **catalog synchronization** — the same concept as `apt update` or `conda index`:

```bash
# Explicit sync (runs on demand, or scheduled via cron on HPC)
gnss-etl sync-catalogs
# → Fetches EarthScope global station list → saves as ert_stations.parquet
# → Fetches M3G stations per registered network → saves per-network Parquet files
# → Updates .gnss_compile/sync_manifest.json with fetch timestamps
```

Queries use the cached catalog by default:

```python
# Default: cached catalog — fast, works offline, no API credentials at query time
client.station_query().within(lat, lon, radius).on(date).search()

# Override: force live API call for this query only
client.station_query().within(lat, lon, radius).on(date).live_catalog().search()
```

**Sync manifest** (`sync_manifest.json`):
```json
{
  "sources": {
    "ERT": {
      "catalog_path": ".gnss_compile/catalogs/ert_stations.parquet",
      "synced_at": "2026-04-12T08:00Z",
      "ttl_days": 7,
      "station_count": 1847,
      "api_url": "https://web-services.unavco.org/..."
    },
    "M3G_IGS": {
      "catalog_path": ".gnss_compile/catalogs/m3g_igs_stations.parquet",
      "synced_at": "2026-04-15T14:30Z",
      "ttl_days": 7,
      "station_count": 533
    }
  }
}
```

**Staleness warning on load:**
```python
def _check_catalog_freshness(sync_manifest: dict, source_id: str) -> None:
    entry = sync_manifest["sources"].get(source_id)
    if entry is None:
        logger.warning(f"{source_id}: no cached catalog — run `gnss-etl sync-catalogs`")
        return
    age_days = (datetime.now(UTC) - datetime.fromisoformat(entry["synced_at"])).days
    ttl_days = entry.get("ttl_days", 7)
    if age_days > ttl_days:
        logger.warning(
            f"{source_id} catalog is {age_days} days old (TTL: {ttl_days}d). "
            f"Run `gnss-etl sync-catalogs` to refresh."
        )
```

**SE perspective:** The sync step decouples credential management from query time. A sysadmin can run `gnss-etl sync-catalogs` with credentials on a schedule; users run queries without needing live API access. This also means the credential check happens once during sync, not on every query invocation.

**GEO perspective:** For an HPC batch job submitted to a queue, live API calls at query time are unreliable — the compute node may not have outbound internet access, or the API may be rate-limiting. Pre-synced catalogs make the job deterministic: it uses exactly the station list that was current at sync time.

**HPC perspective:** Schedule `gnss-etl sync-catalogs` as a weekly cron job on the HPC login node. All jobs submitted that week use the same catalog snapshot — consistent, reproducible, and fast.

### 2.6 The compiled environment as a reproducibility artifact

When all three tiers are compiled, the output is a complete snapshot of the system's runtime configuration:

```
{base_dir}/.gnss_compile/
  specs/
    match_table.arrow          # Tier 1: regex strings + product metadata
    parameter_catalog.arrow    # Tier 1: parameter definitions
  catalogs/
    igs_stations.parquet       # Tier 2: managed IGS catalog
    cors_stations.parquet      # Tier 2: managed CORS catalog
    ert_stations.parquet       # Tier 3: synced from EarthScope API
    m3g_igs_stations.parquet   # Tier 3: synced from M3G
    m3g_cors_stations.parquet  # Tier 3
  sync_manifest.json           # Timestamps + source versions for all Tier 3 artifacts
```

**Archiving this directory alongside PPP results** gives complete provenance: not just what files were downloaded (the audit log), but what station metadata, server specs, and product regex patterns were in use. This is the missing link in GNSS data reproducibility — most papers describe what data was downloaded but not what catalog metadata governed the station selection.

### 2.7 What cannot be compiled

The `compute` callables on `Parameter` objects — Python functions that derive values like `YYYY` from a query date at runtime — are intentionally not serializable and must remain as runtime logic. The compilation boundary is everything *above* the query date. Computed parameters are inherently query-dependent and belong in the execution layer, not the compiled layer.

Similarly, `ConnectionPool` state and authenticated filesystem handles are runtime-only — they depend on credentials, active connections, and server state that cannot be captured at compile time.

### 2.8 Implementation: compile subcommand

```bash
# Full compile (all tiers)
gnss-etl compile

# Compile specific tiers
gnss-etl compile --specs-only          # Tier 1: fast, no network
gnss-etl compile --catalogs-only       # Tier 2: fast, no network
gnss-etl sync-catalogs                 # Tier 3: requires network + credentials

# Force recompile even if cache is current
gnss-etl compile --force

# Show what is compiled and when
gnss-etl compile --status
# → Tier 1 (specs):     current   (package v0.5.2, compiled 2026-04-19)
# → Tier 2 (catalogs):  current   (igs: 3d ago, cors: 3d ago)
# → Tier 3 (protocols): STALE     (ert: 14d ago, ttl: 7d) — run sync-catalogs
```

---

## 3. Data Layer: Arrow, Parquet, Polars, DuckDB

### 2.1 Design principle: Arrow as the universal exchange format

Apache Arrow defines a common in-memory columnar format that every tool in this recommendation speaks natively: Polars, GeoPandas, DuckDB, PyArrow, pandas. By using Arrow as the internal exchange format between subsystems, we avoid repeated serialization/deserialization between formats.

```
YAML / CSV (source of truth)
    ↓ compile once
GeoParquet / Parquet (persistent, compressed, schema-enforced)
    ↓ zero-copy read
Arrow Table (in-process, columnar)
    ↓ view, no copy
Polars DataFrame  ←──── DuckDB SQL ────→  pandas DataFrame
    ↓ .to_arrow()                              ↓
GeoPandas GeoDataFrame ←──── STRtree ────→ spatial index
```

All four libraries share the same Arrow buffer — no data is copied between steps.

### 2.2 Station catalogs: YAML → GeoParquet

#### The current cost

Every `GNSSNetworkRegistry` startup re-runs:
```python
# CORS: 228 KB YAML → yaml.safe_load() → list[dict] → list[GNSSStation]
# IGS:  52 KB  YAML → ...
# GA:   64 KB  YAML → ...
# RBMC: 16 KB  YAML → ...
```
That is 3,356 Pydantic model constructions from dict parsing on every process startup. Each `GNSSStation` has optional date fields that require `datetime.date` parsing. The STRtree spatial index is then rebuilt from the coordinate list.

#### Proposed: compile to GeoParquet on first load, fast-path on subsequent loads

```
gpm-specs/configs/networks/
├── igs_config.yaml         ← authoritative source (human-edited)
├── igs_stations.yaml       ← authoritative source
├── .cache/
│   └── igs_stations.parquet   ← compiled artifact (git-ignored)
```

**Compile step** (triggered when YAML mtime > Parquet mtime):
```python
# GeoParquet schema — one row per station
import geopandas as gpd
import shapely

gdf = gpd.GeoDataFrame(
    {
        "site_code":   [s.site_code for s in stations],
        "network_id":  [s.network_id for s in stations],
        "server_id":   [s.data_center for s in stations],
        "start_date":  [s.start_date for s in stations],
        "end_date":    [s.end_date for s in stations],
        "rinex_v2":    [s.rinex_versions and "2" in s.rinex_versions for s in stations],
        "rinex_v3":    [s.rinex_versions and "3" in s.rinex_versions for s in stations],
    },
    geometry=gpd.points_from_xy(
        [s.lon for s in stations],
        [s.lat for s in stations],
        crs="EPSG:4326",
    ),
)
gdf.to_parquet(".cache/igs_stations.parquet", compression="zstd", index=False)
```

**Fast-path load** (normal operation):
```python
import geopandas as gpd
gdf = gpd.read_parquet(".cache/igs_stations.parquet")   # ~10ms vs ~200ms
tree = gdf.sindex   # GeoPandas uses Shapely STRtree — already built on read
```

The GeoParquet spec embeds CRS in file metadata — no reprojection on load.

**SE perspective:** YAML remains the authoritative source for human editing; Parquet is a build artifact. The compile step runs lazily (compare mtime) or explicitly via `gnss-etl compile-catalogs`. This is exactly how Python compiles `.py` → `.pyc` — same mental model.

**GEO perspective:** The catalog file is now openable in QGIS, ArcGIS Pro, or any GIS tool without writing Python. Spatial filter, color by network, export as shapefile. Station metadata becomes part of the GIS workflow.

**HPC perspective:** 32 array workers starting simultaneously all `mmap` the same GeoParquet file from the page cache — one disk read, zero redundant parse passes. The OS handles the sharing.

#### GeoPolars: the future-forward option

[GeoPolars](https://geopolars.org) (via `geoarrow-rust`) can read GeoParquet files into Polars DataFrames with native Arrow geometry encoding. Spatial predicates are then expressed as Polars expressions. As of 2025, GeoPolars supports point-in-polygon and radius queries via `geoarrow`:

```python
import polars as pl
import geoarrow.polars as ga

lf = pl.scan_parquet(".cache/igs_stations.parquet")
# Radius filter using geoarrow spatial expression (near-future API)
stations = lf.filter(
    ga.within_distance(pl.col("geometry"), center_point, radius_m)
).collect()
```

**When to use:** GeoPolars is production-ready for reading and filtering; the STRtree equivalent in Polars is not yet as mature as GeoPandas for nearest-neighbor queries. **Recommended hybrid:** Use Polars/GeoPolars for I/O and simple filters; use GeoPandas for STRtree spatial indexing. The zero-copy Arrow bridge makes the handoff free.

### 2.3 Query results: Polars-native manifests

#### Why Polars over pandas here

| Criterion | pandas | Polars |
|---|---|---|
| Lazy evaluation | No | Yes — `LazyFrame` defers computation |
| Multi-core | No (GIL-limited) | Yes — Rust + Rayon, all cores |
| Memory | Copies on most ops | Zero-copy slicing via Arrow |
| Type safety | Silent coercion | Explicit, strict |
| Startup time | ~200ms import | ~50ms import |
| Arrow interop | Via `pyarrow` bridge | Native (Polars IS Arrow) |
| Parquet I/O | Via `pyarrow` or `fastparquet` | Native, single dependency |

For this package, the decisive factor is **lazy evaluation**: a 30-day date range query produces thousands of `SearchTarget` objects. With Polars `LazyFrame`, the manifest can be filtered, sorted, and sliced without ever materializing the full dataset in memory.

#### The manifest as a Polars LazyFrame

```python
import polars as pl
from datetime import date

# Produced by .plan() — no I/O yet
schema = pl.Schema({
    "station_code": pl.String,
    "product":      pl.String,
    "date":         pl.Date,
    "uri":          pl.String,
    "server_id":    pl.String,
    "priority":     pl.Int32,        # lower = preferred; drives download order
    "rinex_version":pl.String,
    "size_est_mb":  pl.Float32,
    # Flattened RINEX parameters (not a nested dict — easier for DuckDB)
    "param_TTT":    pl.String,       # FIN / RAP / ULT / None
    "param_AAA":    pl.String,       # COD / ESA / None
    "param_V":      pl.String,       # "2" / "3" / None
    "param_SSSS":   pl.String,       # station code (redundant but useful)
})

manifest_lf = pl.LazyFrame(records, schema=schema)
# Write to Parquet (this is the only I/O in the plan phase)
manifest_lf.sink_parquet("manifest.parquet", compression="zstd")
```

**Reading a slice in an HPC worker:**
```python
# Worker reads only its stations — predicate pushdown skips unrelated row groups
my_stations = ["FAIR", "BREW", "ALTH"]
worker_df = pl.scan_parquet("manifest.parquet").filter(
    pl.col("station_code").is_in(my_stations)
).collect()
```

**GEO perspective:** Preview the manifest in a Jupyter notebook with one line:
```python
pl.read_parquet("manifest.parquet").group_by("server_id").agg(
    pl.len().alias("n_files"),
    pl.col("size_est_mb").sum().alias("total_gb") / 1024,
).sort("total_gb", descending=True)
```
Output:
```
┌───────────┬─────────┬──────────┐
│ server_id ┆ n_files ┆ total_gb │
│ ---       ┆ ---     ┆ ---      │
╞═══════════╪═════════╪══════════╡
│ CDDIS     ┆ 412     ┆ 18.3     │
│ NOAA_S3   ┆ 1796    ┆ 62.1     │
│ ERT       ┆ 88      ┆ 6.2      │
└───────────┴─────────┴──────────┘
```

### 2.4 Audit log: DuckDB over Parquet

DuckDB adds a SQL query layer over the Parquet files written during download runs. It requires no server, no migration, and no schema setup — it queries the files directly.

**Why DuckDB rather than SQLite:**
- DuckDB reads Parquet natively with predicate pushdown (SQLite cannot)
- DuckDB is columnar — aggregate queries over millions of rows are fast
- DuckDB supports full SQL including window functions and geospatial extensions
- The `duckdb` Python package is a single dependency (~30MB)

**Audit log schema (Parquet, partitioned by year/month):**
```
.gnss_audit/
  downloads/
    year=2026/month=01/
      part-0001.parquet
      part-0002.parquet
    year=2026/month=02/
      part-0001.parquet
```

```python
import duckdb

# Works without any setup — DuckDB finds all partitions automatically
con = duckdb.connect()

# What data did I use for this run?
con.execute("""
    SELECT station_code, date, uri, local_path, bytes_received
    FROM '.gnss_audit/downloads/**/*.parquet'
    WHERE run_id = 'abc-123'
      AND success = true
      AND product = 'RINEX_OBS'
    ORDER BY date, station_code
""").pl()  # → Polars DataFrame

# Which stations consistently fail?
con.execute("""
    SELECT station_code,
           COUNT(*) FILTER (WHERE success = false) AS failures,
           COUNT(*) AS total,
           ROUND(100.0 * COUNT(*) FILTER (WHERE success = false) / COUNT(*), 1) AS failure_pct
    FROM '.gnss_audit/downloads/**/*.parquet'
    GROUP BY station_code
    HAVING failures > 0
    ORDER BY failure_pct DESC
""").pl()
```

**SE perspective:** Audit logs are append-only — each download run writes a new Parquet partition. No update logic. DuckDB reads across all partitions transparently. Adding new columns to future runs doesn't break old queries (Parquet is schema-evolution friendly; DuckDB handles missing columns as null).

**GEO perspective:** Six months later, "what data did I use for this paper?" is one SQL query. The audit log is part of reproducibility the same way a lab notebook is.

**HPC perspective:** Each array worker writes its own partition file — no coordination, no locks. After all workers finish, one DuckDB query aggregates the full run's results.

### 2.5 PPP results: partitioned Parquet dataset

Pride PPP outputs `.kin` kinematic position files. Currently parsed into `pd.DataFrame` via `kin_to_kin_position_df()` and discarded. Proposed: write to a partitioned Parquet dataset immediately after parse.

```
{base_dir}/results/
  product=RINEX_OBS/
    year=2026/doy=004/station=FAIR/positions.parquet
    year=2026/doy=004/station=BREW/positions.parquet
  product=CLOCK/
    year=2026/doy=004/center=COD/clocks.parquet
```

**Multi-station load — the killer use case:**
```python
import polars as pl

# Load all stations, all of January 2026, in one call
positions = pl.scan_parquet(
    "{base_dir}/results/product=RINEX_OBS/**/*.parquet",
    hive_partitioning=True,
).filter(
    (pl.col("year") == 2026) & (pl.col("doy").is_between(1, 31))
).collect()

# WRMS per station
positions.group_by("station").agg(
    pl.col("height").std().alias("wrms_mm") * 1000
).sort("wrms_mm", descending=True)
```

**GEO perspective:** This is the highest-impact change for working geophysicists. Today, post-processing 100 stations requires writing a glob + concat loop in every analysis notebook. With partitioned Parquet and `scan_parquet(..., hive_partitioning=True)`, the entire dataset is one LazyFrame that loads only what's needed.

---

## 4. Async Query Engine

### 3.1 The case for asyncio

The two biggest serial bottlenecks in the current engine are:

1. **`StationQuery.metadata()` iterates networks in a `for` loop** — each call to `radius_spatial_query()` makes an HTTP GET and blocks until the response arrives. For 5 networks × ~2s = ~10s of wall time before any directory listing begins.

2. **`WormHole._list_dir()` uses `ThreadPoolExecutor`** — threads unblock the GIL for I/O, but each thread still blocks on `fsspec.ls()`. For CDDIS FTPS with a 4-connection limit, 100 pending directory listings queue behind 4 workers.

`asyncio` + `anyio` resolves both:
- HTTP station queries → `httpx.AsyncClient` (one `asyncio.gather()` for all networks in parallel)
- FTP/HTTPS directory listings → `asyncssh` / `aiohttp` with a semaphore per host (replaces ThreadPoolExecutor with a connection-aware coroutine pool)

**The constraint:** `asyncio` cannot easily be added to a synchronous call graph. The query builders are synchronous; the `.search()` and `.download()` terminals are where blocking occurs. This means the async engine runs inside those terminal methods, invisible to the caller.

```python
# Caller sees no change — still synchronous builder
results = (
    client.station_query()
    .within(64.9, -147.5, 1000)
    .networks("IGS", "CORS", "ERT")
    .on(date)
    .search()          # ← internally runs asyncio.run(_async_search())
)
```

### 3.2 Parallel network metadata queries

**Current (serial):**
```python
# ~10s for 5 networks
for network_id in network_ids:
    stations = self._query_spatial(network_id)  # blocks ~2s each
    all_stations.extend(stations)
```

**Proposed (parallel with asyncio):**
```python
import asyncio
import anyio

async def _query_all_networks(network_ids, spatial_filter, date):
    async with anyio.create_task_group() as tg:
        results = {}
        async def _query_one(nid):
            results[nid] = await _async_spatial_query(nid, spatial_filter, date)
        for nid in network_ids:
            tg.start_soon(_query_one, nid)
    return [s for stations in results.values() for s in stations]
```

With 5 networks that each take 2s, this completes in ~2s instead of ~10s. The `anyio` library makes this compatible with both `asyncio` and `trio` backends, future-proofing against different HPC environments.

### 3.3 Async WormHole with per-host semaphores

The current `ConnectionPoolFactory` already knows per-host connection limits. In an async model, these become semaphores:

```python
class AsyncConnectionPool:
    _semaphores: dict[str, asyncio.Semaphore] = {}
    _limits = {
        "gdc.cddis.eosdis.nasa.gov": 4,
        "ftp.aiub.unibe.ch": 8,         # COD — more permissive
        "igs.ign.fr": 6,
        "default": 4,
    }

    async def list_directory(self, hostname: str, path: str):
        sem = self._semaphores.setdefault(
            hostname,
            asyncio.Semaphore(self._limits.get(hostname, self._limits["default"]))
        )
        async with sem:
            return await self._async_list(hostname, path)
```

The semaphore replaces both the `ThreadPoolExecutor` and the per-host connection limit logic in the current `ConnectionPoolFactory`. 200 pending listings for CDDIS queue naturally behind 4 concurrent async coroutines, each waiting for `asyncssh` / `aiohttp` I/O without blocking a thread.

**SE perspective:** This is the most complex change — it requires async versions of `fsspec` operations (or direct `asyncssh`/`aiohttp`). The public API stays synchronous via `asyncio.run()` at the terminal methods. The intermediate builder is untouched. Estimated throughput improvement for 100-station runs: 5–10×.

**HPC perspective:** Worker processes each run their own `asyncio` event loop — no cross-worker coordination needed. The per-host semaphore prevents overloading shared FTP servers even when 32 workers run simultaneously, because each worker respects its own semaphore.

---

## 5. Query API Redesign

### 4.1 Current API friction points

The existing fluent API is good but requires knowing internal vocabulary:

```python
# Current — requires knowing TTT, AAA, FIN/RAP/ULT, sources by id
(client.product_query()
 .for_product("ORBIT")
 .where(TTT="FIN", AAA="COD")
 .sources("local", "COD", "ESA")
 .prefer(TTT=["FIN", "RAP", "ULT"])
 .on(date)
 .search())
```

A geophysicist's mental model is not "I want TTT=FIN" — it's "I want the best available orbit." The API should meet users at their vocabulary.

### 4.2 Quality presets

Map human vocabulary to the parameter constraints already used internally:

```python
# Quality presets (maps to TTT / RRR / LEN combinations)
QUALITY_PRESETS = {
    "final":   {"TTT": "FIN", "LEN": "01D"},
    "rapid":   {"TTT": "RAP", "LEN": "01D"},
    "ultra":   {"TTT": "ULT", "LEN": "01D"},
    "best":    None,   # No constraint — let preference cascade handle it
    "realtime":{"TTT": "NRT"},
}

# New API
(client.product_query()
 .for_product("ORBIT")
 .quality("final")          # ← replaces .where(TTT="FIN")
 .prefer_quality(["final", "rapid", "ultra"])  # ← replaces .prefer(TTT=[...])
 .sources("COD", "ESA", "GFZ")
 .on(date)
 .search())
```

Old `.where()` and `.prefer()` remain — the preset is a convenience that calls them internally.

### 4.3 Unified PPP query

PPP requires three things for every station-day: observations (RINEX_OBS), orbits (ORBIT), and clocks (CLOCK). Today these require two separate query chains that must be mentally composed and kept date-synchronized. A unified builder handles both:

```python
# New: one builder, one result, dates synchronized automatically
job = (
    client.ppp_query()
    .spatial(lat=64.978, lon=-147.499, radius_km=1000)
    .networks("IGS", "CORS", "ERT")
    .on(date)
    # Observations
    .observations(version="3", fallback_version="2")
    # Analysis center products — one call handles orbits + clocks + biases
    .products(quality="final", centers=["COD", "ESA", "GFZ"])
    .plan()     # → PPPManifest (serializable, no I/O)
)

print(job.summary())
# Planned: 412 observation files + 3 orbit files + 3 clock files
# Servers: CDDIS (270 files), NOAA_S3 (142 files), ERT (88 files)
# Estimated size: 4.2 GB

result = job.execute("local", max_workers=50)
result.observations   # list[FoundResource] for RINEX_OBS
result.orbits         # list[FoundResource] for ORBIT
result.clocks         # list[FoundResource] for CLOCK
result.save_manifest("run_2026_jan_04.parquet")
```

`PPPQuery` is a thin compositor over the existing `StationQuery` and `ProductQuery` — it does not replace them. The existing `.station_query()` and `.product_query()` paths remain for users who need fine-grained control.

**GEO perspective:** This is the most natural representation of a PPP workflow. A geophysicist thinks "I want to process these stations for this date" — not "I need to configure two separate query chains and keep their dates consistent." The unified builder removes an entire class of user errors.

### 4.4 Preview / plan mode

Every query builder gets a `.plan()` method that returns a manifest with no download I/O:

```python
manifest = (
    client.station_query()
    .within(64.978, -147.499, 1000)
    .on(date)
    .plan()     # No download — returns StationManifest
)

# Inspect before committing
manifest.summary()
# → {"stations": 87, "files": 87, "servers": ["CDDIS", "NOAA_S3", "ERT"], "est_gb": 3.1}

manifest.as_dataframe()   # → Polars DataFrame
manifest.save("manifest.parquet")

# Execute separately, potentially on a different machine
result = Downloader(client).execute(manifest, sink_id="local", max_workers=50)
```

**SE perspective:** `.plan()` calls everything up to and including `WormHole.search()` (directory listing) but stops before `WormHole.download_one()`. The manifest captures the output of `search()` as a serializable Parquet file. This makes the boundary between planning and execution explicit in both the API and the data model.

**HPC perspective:** A planning process runs on a login node (no compute allocation, lightweight). The manifest is written to shared storage. Worker nodes read their slice of the manifest. No login-node-to-worker communication beyond the Parquet file.

### 4.5 Named configuration profiles

Repetitive query configurations can be saved as named profiles:

```python
# Create and save a profile (written to {base_dir}/profiles/alaska_ppp.yaml)
client.save_profile(
    "alaska_ppp",
    client.ppp_query()
        .spatial(lat=64.978, lon=-147.499, radius_km=1000)
        .networks("IGS", "CORS", "ERT")
        .observations(version="3", fallback_version="2")
        .products(quality="final", centers=["COD", "ESA"])
)

# Later: load and run
job = client.load_profile("alaska_ppp").on(date)
result = job.execute("local")
```

Profiles are YAML files — shareable with collaborators, version-controllable, writable without Python. This connects Option C from `plans/query-streamlining-design.md` (Declarative YAML Job Specs) to the existing builder API.

```yaml
# profiles/alaska_ppp.yaml
version: 1
type: ppp_query
spatial:
  lat: 64.978
  lon: -147.499
  radius_km: 1000
networks: [IGS, CORS, ERT]
observations:
  version: "3"
  fallback_version: "2"
products:
  quality: final
  centers: [COD, ESA, GFZ]
```

---

## 6. Local Data Protocol: First-Class Local Archives

### 5.1 The problem with the current `WorkSpace` approach

`WorkSpace` + `local_config.yaml` support local RINEX archives, but:
- The feature is not documented in user-facing docs
- It requires knowing the internal spec format (`ResourceProductSpec`, `PathTemplate`)
- There is no spatial awareness — you cannot ask "find RINEX files in my local archive near this point"
- There is no auto-discovery — the user must manually tell the system what directory patterns to use
- There is no catalog caching — the local directory is listed on every query

### 5.2 `LocalDataSource`: a declarative local archive spec

A `LocalDataSource` is a simple YAML file that describes a local RINEX archive and can be registered with the client in one line:

```yaml
# my_lab_archive.yaml
id: lab_archive
name: Lab RINEX Archive
description: Local RINEX obs files collected during the 2025 expedition
base_dir: /Volumes/FieldDisk/gnss/rinex    # or s3://my-bucket/gnss/rinex

# Describe how files are organized
layout:
  type: rinex3_standard          # predefined layout: {YYYY}/{DDD}/{SSSS}*.rnx
  # OR define custom:
  # type: custom
  # pattern: "{YYYY}/{DDD}/{site}_{YYYY}{DDD}_{rate}.{ext}"
  # param_map:
  #   site: SSSS
  #   rate: "30S"

# Static station registry (optional — auto-discovered if omitted)
stations:
  - site_code: FAIR
    lat: 64.978
    lon: -147.499
    start_date: 2025-06-01
    end_date: 2025-06-30
  - site_code: MEAD
    lat: 64.501
    lon: -148.102
```

**Registration (one line of Python):**
```python
client = GNSSClient.from_defaults(base_dir="/data/gnss")
client.register_local_source("my_lab_archive.yaml")

# Now available in any query
results = (
    client.station_query()
    .within(64.978, -147.499, 500)
    .sources("lab_archive", "IGS")   # local source takes priority
    .on(date)
    .search()
)
```

**CLI registration (no Python):**
```bash
gnss-etl register-source my_lab_archive.yaml
# Writes to {base_dir}/.gnss_sources.yaml
```

### 5.3 Auto-discovery: building a spatial catalog from filenames

When `stations:` is not provided in the local source spec, the system scans the archive and builds a catalog from RINEX filenames:

```python
class LocalSourceDiscoverer:
    def discover(self, base_dir: Path, layout: LayoutSpec) -> list[GNSSStation]:
        """
        Walk base_dir, match files against layout pattern,
        extract site codes and dates from filenames.
        Returns unique stations with date ranges from first/last file.
        """
        files = self._find_rinex_files(base_dir, layout.pattern)
        stations = {}
        for f in files:
            params = layout.parse_filename(f.name)
            if not params:
                continue
            code = params["SSSS"].lower()
            if code not in stations:
                stations[code] = {"site_code": code, "dates": []}
            stations[code]["dates"].append(params["date"])

        return [
            GNSSStation(
                site_code=code,
                start_date=min(d),
                end_date=max(d),
                network_id="local",
                data_center=str(base_dir),
                lat=None,   # Unknown from filename — requires RINEX header read
                lon=None,
            )
            for code, data in stations.items()
        ]
```

**RINEX header extraction for coordinates (optional, slower):**
```python
class RINEXHeaderReader:
    def extract_coordinates(self, rinex_path: Path) -> tuple[float, float, float] | None:
        """Read APPROX POSITION XYZ from RINEX header, convert to lat/lon."""
        with open(rinex_path, "r", encoding="ascii", errors="replace") as f:
            for line in f:
                if "APPROX POSITION XYZ" in line:
                    x, y, z = float(line[0:14]), float(line[14:28]), float(line[28:42])
                    return ecef_to_geodetic(x, y, z)
                if "END OF HEADER" in line:
                    break
        return None
```

Coordinate extraction is optional and triggered only when `extract_coordinates: true` in the source spec. The resulting catalog is cached as GeoParquet for fast reuse.

### 5.4 Parquet catalog caching for local sources

```
{base_dir}/.gnss_sources/
  lab_archive/
    catalog.parquet       ← GeoParquet station catalog (auto-discovered or from YAML)
    manifest.parquet      ← File index with path, date, station_code, file_size
    catalog.mtime         ← Timestamp of last scan
```

On query, the system checks `catalog.mtime` against the archive modification time. If stale, re-scans. Otherwise, loads `catalog.parquet` in ~10ms.

**Search against local source:**
```python
# WorkSpace.source_product() is enhanced to query the Parquet manifest
def _search_local_manifest(self, source_id: str, station_codes: list[str], date: date):
    manifest = pl.scan_parquet(f".gnss_sources/{source_id}/manifest.parquet")
    return (
        manifest
        .filter(
            pl.col("station_code").is_in(station_codes) &
            (pl.col("date") == date)
        )
        .collect()
        .to_dicts()
    )
```

**SE perspective:** The manifest Parquet file is a complete index of the local archive. Searching it is a Polars predicate-pushdown filter — sub-millisecond for archives of any size. No filesystem walk on every query. The index is the single source of truth; the actual RINEX files are the payload.

**GEO perspective:** Connecting a field drive or S3 bucket to a query is now:
```yaml
# field_drive.yaml
id: field_drive
base_dir: /Volumes/FieldDisk/gnss
layout:
  type: rinex3_standard
```
```bash
gnss-etl register-source field_drive.yaml
```
That's it. The next query that includes `sources("field_drive")` will find files on that drive with the same priority as any remote archive.

**HPC perspective:** The Parquet manifest can live on a shared filesystem. All workers read it concurrently without locks. If the local archive is on a parallel filesystem (Lustre, GPFS), the manifest-then-read pattern avoids hammering the metadata server with `ls` calls from all workers simultaneously.

### 5.5 Source priority and fallback chain

Local sources should integrate naturally into the existing source priority system:

```python
(client.station_query()
 .within(lat, lon, radius_km)
 .sources(
     "field_drive",    # priority 1: local data from the expedition
     "lab_archive",    # priority 2: lab's S3 archive
     "IGS",            # priority 3: public IGS archive
     "CORS",           # priority 4: NOAA CORS
 )
 .on(date)
 .download("local", max_workers=50))
```

The fallback chain is explicit. If a station's file is in `field_drive`, it is returned first and the remaining candidates are skipped (existing per-station fallback logic in `StationQuery.download()`).

---

## 7. Formats Comparison Matrix

Rather than advocating a single format, different parts of the pipeline call for different tools:

| Data | Recommended format | Library | Why |
|---|---|---|---|
| Station catalogs (spatial) | GeoParquet | GeoPandas / GeoPolars | CRS-aware, QGIS-compatible, fast STRtree |
| Query manifests | Parquet (zstd) | Polars | Lazy reads, HPC slicing, schema-enforced |
| Audit / download history | Parquet (partitioned) | DuckDB + Polars | Append-only, SQL-queryable, no server |
| PPP results (positions) | Parquet (hive-partitioned) | Polars | Multi-station scan in one call |
| Remote directory cache | Parquet | Polars | Fast filter by hostname/path/mtime |
| Server health records | Parquet | DuckDB | Time-series query for uptime patterns |
| Config (human-edited) | YAML | PyYAML | Human-readable, version-controlled |
| Lockfiles (provenance) | JSON (existing) | stdlib | One-off per file; no aggregation needed |
| Local source spec | YAML | PyYAML | Human-readable, shareable |
| Profiles / job specs | YAML | PyYAML | Human-readable, version-controlled |

**On Lance format:** [Lance](https://lancedb.github.io/lance/) offers better random-access than Parquet for large datasets and is designed for ML workflows. For this package, Parquet + DuckDB covers all use cases with better ecosystem support. Lance is worth revisiting if PPP result datasets exceed 100GB.

**On Arrow IPC:** Arrow IPC (`feather` format, v2) is faster than Parquet for in-process or short-lived exchange (e.g., passing manifests between a planning process and a worker on the same machine). It does not compress as well as Parquet. Use Parquet for persistent storage; consider Arrow IPC for ephemeral inter-process exchange on HPC where speed matters more than file size.

**On Zarr:** Not applicable here. Zarr is for multi-dimensional array data (rasters, time cubes). PPP output is tabular.

---

## 8. Dependency Analysis

### New dependencies required

| Package | Size | Purpose | Already present? |
|---|---|---|---|
| `polars` | ~30 MB | Tabular I/O and lazy manifests | No |
| `pyarrow` | ~80 MB (shared) | Arrow format, Parquet I/O | Transitive via geopandas |
| `duckdb` | ~30 MB | SQL over Parquet | No |
| `anyio` | ~1 MB | Async compatibility layer | No |
| `httpx` | ~3 MB | Async HTTP for station APIs | No |
| `geoarrow-rust` | ~5 MB | GeoPolars bridge (optional) | No |

### Packages that can be removed or demoted

| Package | Current role | Can be replaced by |
|---|---|---|
| `haversine` | Distance calculations in IGS protocol | Polars expression / Shapely |
| `pandas` (direct uses) | CORS loader, Pride output | Polars (with GeoPandas bridge for spatial) |

### Existing dependencies that remain essential

- `geopandas` — GeoParquet read/write, STRtree spatial indexing
- `shapely` — geometry operations
- `fsspec` — filesystem abstraction (local, S3, GCS, SFTP)
- `pydantic` — model validation (keep for config and API surface)
- `yaml` — config parsing (YAML stays as human-editable source)

---

## 9. Implementation Roadmap

These changes are independent enough to be delivered in sequence without large rewrites:

### Phase 0a: Compilation layer — static specs (1–2 days)
- `gnss-etl compile --specs-only` subcommand
- Serialize `_build_match_table()` output to Arrow IPC with version tag in metadata
- Load from Arrow on startup; fall back to YAML rebuild if version mismatch or missing
- Zero API changes; purely internal optimization

### Phase 0b: Compilation layer — managed catalogs (1–2 days)
- Write `compile_catalog()` utility that reads station YAML → writes GeoParquet
- Update `IGSProtocol`, `NOAACORSProtocol`, `GAProtocol`, `RBMCProtocol` to load from Parquet with YAML mtime fallback
- Gate on `geopandas>=0.14` (already a declared dependency)
- Zero API changes; purely internal optimization

### Phase 0c: Compilation layer — protocol catalog sync (2–3 days)
- `gnss-etl sync-catalogs` subcommand
- `CatalogSyncer` class: calls each registered `NetworkProtocol` once globally (not per spatial query), saves result as GeoParquet
- Staleness warning in `GNSSClient.__init__()` when TTL exceeded
- `live_catalog()` builder method to override cached catalog for one query
- `gnss-etl compile --status` to inspect freshness of all tiers

### Phase 1: Polars manifest + `.plan()` (3–5 days)
- Add `Manifest` Pydantic model that wraps Polars DataFrame
- Add `.plan()` method to `StationQuery` and `ProductQuery` — calls `.search()` internally, wraps results in Manifest
- Add `.save()` / `.load()` on Manifest (Parquet I/O)
- Add `Downloader` class as an alias for the existing download pipeline accepting a Manifest
- Zero breakage to existing `.search()` / `.download()` — they continue to work unchanged

### Phase 2: `LocalDataSource` protocol (3–5 days)
- `LocalDataSource` YAML spec model + Pydantic validation
- `LocalSourceDiscoverer` for auto-discovery from filenames
- Parquet manifest cache in `.gnss_sources/`
- `GNSSClient.register_local_source()` method
- Update `WorkSpace` to query the Parquet manifest instead of listing directories
- `gnss-etl register-source` CLI command

### Phase 3: DuckDB audit log (1–2 days)
- `AuditLogger` class that appends download results to partitioned Parquet
- Called at the end of every successful/failed download in `WormHole`
- `gnss-etl audit` CLI command with DuckDB queries as subcommands

### Phase 4: Quality presets + unified PPP query (2–3 days)
- `quality()` and `prefer_quality()` methods on `ProductQuery`
- `PPPQuery` compositor class over `StationQuery` + `ProductQuery`
- `PPPManifest` result type
- `GNSSClient.ppp_query()` entry point

### Phase 5: Async query engine (5–10 days)
- `AsyncConnectionPool` with per-host semaphores
- `AsyncWormHole` using `anyio` + `httpx` + `asyncssh`
- `asyncio.run()` wrapper in terminal methods (`.search()`, `.download()`)
- Backward-compatible: synchronous API unchanged

### Phase 6: Named profiles + CLI (2–3 days)
- Profile YAML serialization/deserialization
- `GNSSClient.save_profile()` / `.load_profile()`
- `gnss-etl run profile.yaml` CLI entry point
- `gnss-etl submit profile.yaml --array-size N` SLURM integration

---

## 10. User Stories

### Story 1: Field campaign data analysis (Geophysicist)

> "I ran a 3-week campaign with 12 portable GNSS receivers in the Aleutians. The data is on a hard drive. I want to process it with PPP using IGS final orbits and also download any permanent IGS stations within 200 km for comparison."

**Today:** Register `WorkSpace`, write a custom `local_config.yaml` matching the field laptop's directory layout (requires reading source code), call `station_query()` and `product_query()` separately, manually combine results.

**After Phase 2 + Phase 4:**
```bash
# One-time: describe the drive layout (30-second edit)
cat > field_drive.yaml << EOF
id: field_drive
base_dir: /Volumes/AleutiansDrive/gnss
layout:
  type: rinex3_standard
  extract_coordinates: true    # read headers for precise positions
EOF
gnss-etl register-source field_drive.yaml

# Python: one query for everything
result = (
    client.ppp_query()
    .spatial(lat=52.5, lon=-174.2, radius_km=200)
    .sources("field_drive", "IGS")           # local first, IGS fallback
    .on_range("2025-06-01", "2025-06-21")
    .observations(version="3", fallback_version="2")
    .products(quality="final", centers=["COD", "ESA"])
    .execute("local", max_workers=30)
)
```

### Story 2: HPC batch run for a network velocity field (Geophysicist + HPC Operator)

> "I need to process 3 years of daily RINEX data for 400 CORS stations to compute a velocity field. I have a SLURM cluster with 32 nodes. The data needs to come from NOAA S3 and CDDIS."

**Today:** Write a Python script that loops over stations and dates, submit as an array job, manually track which jobs succeeded/failed, re-run failures manually.

**After Phase 1 + Phase 3 + Phase 6:**
```bash
# On login node: plan the job (no compute allocation needed)
gnss-etl plan velocity_field.yaml --output manifest.parquet
# → "Planned: 438,000 files from 400 stations × 1095 days"
# → "Servers: NOAA_S3 (320,000 files), CDDIS (118,000 files)"

# Preview before submitting
gnss-etl inspect manifest.parquet --by-server
# → Shows file count and GB per server

# Submit as 32-way array job
gnss-etl submit velocity_field.yaml \
    --manifest manifest.parquet \
    --array-size 32 \
    --partition data \
    --time 04:00:00
# → Generates and submits SLURM batch script
# → Workers receive row-group slice of manifest.parquet

# After completion: check results
gnss-etl audit query \
    "SELECT station_code, COUNT(*) as days, SUM(success::int) as ok \
     FROM '.gnss_audit/downloads/**/*.parquet' \
     WHERE run_id = '...' GROUP BY station_code HAVING ok < days"
# → Lists stations with partial failures → resubmit as small follow-up job
```

### Story 3: Adding a new GNSS network (Software Engineer / Network Operator)

> "I want to add TrigNet (South African GNSS network) to the package. The data is hosted on an SFTP server at trignet.co.za. There's no M3G registration yet."

**Today:** Write a Python `NetworkProtocol` class, write a YAML config, register the protocol in `GNSSNetworkRegistry`, rebuild the package.

**After Phase 2:**

Option A — Static catalog (no Python):
```yaml
# configs/networks/trignet_config.yaml
id: TrigNet
name: TrigNet GNSS Network (South Africa)
type: static_catalog
stations_file: trignet_stations.yaml     # simple list of site_code, lat, lon
servers:
  - id: TRIGNET_SFTP
    hostname: "sftp://trignet.co.za"
    protocol: sftp
    auth_required: true
products:
  - product_name: RINEX_OBS
    server_id: TRIGNET_SFTP
    directory: {pattern: "data/rinex/{YYYY}/{DDD}/"}
```

Option B — API-driven (configurable, still no new Python class):
```yaml
# configs/networks/trignet_config.yaml
id: TrigNet
type: api_catalog
api:
  url: "https://api.trignet.co.za/stations/nearby"
  method: GET
  params:
    lat: "{lat}"
    lon: "{lon}"
    radius_km: "{radius_km}"
  response:
    format: json
    stations_path: "$.stations[*]"
    field_map:
      site_code: "code"
      lat: "latitude"
      lon: "longitude"
      start_date: "installation_date"
```

A `GenericAPIProtocol` (new class, written once) handles any network using the `api_catalog` type — no per-network Python code needed.

### Story 4: Reproducible science (Geophysicist)

> "A reviewer asked me to reprocess one month of data using only final (not rapid) orbits. I need to document exactly what data was used and from which archive."

**After Phase 1 + Phase 3:**
```python
# Original run saved the manifest
manifest = StationManifest.load("run_2025_jan.parquet")

# Reprocess with final orbits only
result = (
    client.ppp_query()
    .from_manifest(manifest)              # reuse same stations and dates
    .products(quality="final")            # override: final only
    .execute("local_final_run")
)

# Audit log provides exact provenance
import duckdb
duckdb.query("""
    SELECT station_code, date, uri, local_path, server_id, param_TTT
    FROM '.gnss_audit/downloads/**/*.parquet'
    WHERE run_id = 'final_reprocess_001'
    ORDER BY date, station_code
""").write_csv("data_provenance.csv")
# → Attach to paper submission
```

---

## 11. Open Questions

1. **Async compatibility with fsspec:** `fsspec` is synchronous. The async WormHole would need either `asyncio.to_thread()` wrappers (simple but defeats the purpose) or direct `asyncssh`/`aiohttp` implementations for FTP/HTTPS. Which servers are highest priority for async? (CDDIS FTPS and NOAA HTTPS together account for ~80% of downloads.)

2. **GeoPolars maturity threshold:** At what point is GeoPolars mature enough to replace GeoPandas for the STRtree step? Track [geoarrow-rust](https://github.com/geoarrow/geoarrow-rs) spatial index support.

3. **Manifest size ceiling:** A 400-station × 1095-day manifest has 438,000 rows. Parquet handles this easily. But the planning phase (directory listing) requires 438,000 directory listing calls. Should planning batch by date (list one directory, match all stations) rather than by station?

4. **RINEX header extraction cost:** Reading the first ~50 lines of every RINEX file for coordinates during `LocalSourceDiscoverer` is I/O-intensive for large archives. Should this be opt-in, async, or replaced by a faster RINEX index library?

5. **Profile versioning:** If a saved profile references a network (e.g., `TrigNet`) that is later removed or renamed, how should `load_profile()` handle the mismatch? Schema migration via `version:` field in the YAML, or explicit error?

6. **Lockfile migration:** The existing JSON sidecar lockfiles provide per-file provenance. The new Parquet audit log provides cross-run provenance. Should they coexist, or should the audit log replace lockfiles entirely? (Keeping both avoids a breaking change but creates two sources of truth.)
