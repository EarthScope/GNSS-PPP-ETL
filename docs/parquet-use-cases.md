# Parquet in GNSS-PPP-ETL: Use Cases and Benefits

Parquet is an open columnar storage format that pairs naturally with this package's data model. Every major data structure in the pipeline — station catalogs, search manifests, download histories, PPP results — is a table of records with typed columns. That shape is exactly what Parquet is designed for.

This document describes six concrete use cases, with notes on who benefits and how each fits the existing architecture.

---

## Background: Why Columnar Storage Fits GNSS Data

The package's core data types share a common structure: many records, fixed schema, repeated queries against subsets of columns.

| Current format | Data | Rows (typical) | Pain today |
|---|---|---|---|
| YAML | Station catalogs (IGS, CORS, GA, RBMC) | 150–1800 | Re-parsed from disk on every process startup; no geometry column for spatial tools |
| Python `list[FoundResource]` | Search/download results | 10–10,000 | Discarded after each run; JSON export has no schema |
| JSON sidecar files | Download lockfiles | One per file | Auditing across a run requires scanning hundreds of files |
| `.kin` text files → `pd.DataFrame` | PPP kinematic positions | 86,400/day/station | No cross-station aggregation without manual concatenation |
| In-memory dict | WormHole directory listings | 100–50,000 entries/host | Re-fetched from FTP/HTTPS every run; no caching |

Parquet eliminates each of these pain points with a single format that is readable by pandas, GeoPandas, DuckDB, Spark, QGIS, and most HPC data tools.

---

## Use Case 1: Station Catalogs as GeoParquet

### The current state

Station catalogs are stored as YAML (IGS, GA, RBMC) or CSV (NOAA CORS). On startup, each protocol class reads the file, parses it into Python dicts, constructs `GNSSStation` Pydantic models, and builds an `STRtree` spatial index from scratch. For CORS this involves `pd.read_csv()` → `gpd.GeoDataFrame()` — the most expensive pattern at startup.

```
cors_stations.yaml  (228 KB, 1,796 rows)
  ↓ yaml.safe_load()  →  list[dict]
  ↓ GNSSStation(...)  →  list[GNSSStation]
  ↓ STRtree(points)   →  spatial index   [rebuilt every time]
```

### The Parquet alternative

Compile each catalog once into a **GeoParquet** file — Parquet with a geometry column following the [GeoParquet spec](https://geoparquet.org/). The geometry encodes station coordinates as Point geometry, enabling direct spatial queries.

```
cors_stations.parquet  (compressed, ~30 KB)
  ↓ gpd.read_parquet()  →  GeoDataFrame   [~10x faster than YAML parse]
  ↓ STRtree(gdf.geometry)  →  spatial index
```

**Schema:**
```
site_code    : string
lat          : float64
lon          : float64
geometry     : geometry (Point, CRS: EPSG:4326)
network_id   : string
server_id    : string
rinex_version: list<string>
start_date   : date32
end_date     : date32
```

### Who benefits

**Geophysicist:** Open the catalog directly in QGIS or ArcGIS Pro without any Python. Filter by region, color by network, export to KML. The workflow "which CORS stations have operated continuously since 2010?" becomes a drag-and-drop filter, not a script.

```python
import geopandas as gpd
stations = gpd.read_parquet("cors_stations.parquet")
long_running = stations[
    stations.start_date < "2010-01-01"
].explore()   # interactive Leaflet map in Jupyter
```

**Senior SE:** Startup time drops significantly for protocols that rebuild STRtree on every import. The GeoParquet file is the compiled, ready-to-index form of the YAML source. The YAML remains the authoritative source; a build step (or lazy-compile on first load) produces the Parquet cache.

**HPC:** When 32 array workers all start simultaneously and each loads `cors_stations.parquet`, the OS page cache means the file is read from disk once and served to all workers from memory. YAML parsing at that scale produces 32 redundant parse passes with no sharing.

---

## Use Case 2: Download Manifest as Parquet

### The current state

The planned design (see `plans/query-streamlining-design.md`, Option B) introduces a **Manifest** — a serializable description of all files to be downloaded, produced by `.plan()` before any I/O happens. The manifest needs to be:

- Written to shared storage by a planning process
- Read and sliced by N parallel workers
- Partially updated as workers complete their portions

JSON is a natural first choice, but falls short on all three: write is serial, slicing requires reading the whole file, and concurrent partial updates require locks.

### The Parquet alternative

A manifest is a table. Each row is one candidate download. Parquet handles the rest.

**Schema:**
```
station_code  : string
product       : string            (RINEX_OBS, ORBIT, CLOCK, ...)
date          : date32
uri           : string            (ftp://..., s3://..., file://...)
server_id     : string
priority      : int32             (lower = preferred)
rinex_version : string
parameters    : map<string, string>
estimated_mb  : float32
```

**HPC worker pattern:**
```python
import pyarrow.parquet as pq
import pyarrow.compute as pc

# Worker N of M: read only its partition — no full load needed
manifest = pq.read_table(
    "manifest.parquet",
    filters=[("station_code", "in", my_station_batch)],
)

# Or use row-group-aligned slicing
dataset = pq.ParquetDataset("manifest.parquet")
# Each row group maps to one array job task
```

**Writing results back:**
```python
# Each worker writes its own partition; no coordination needed
result_df.to_parquet(f"results/worker_{worker_id}.parquet")

# Final merge is one read
all_results = pd.read_parquet("results/")   # reads all partitions
```

### Who benefits

**Geophysicist:** Before any download starts, open `manifest.parquet` in pandas or DuckDB and ask "how many files are planned, how many GB, which servers?" Gives confidence before committing to a large job.

```python
import duckdb
duckdb.query("""
    SELECT server_id, COUNT(*) as files, SUM(estimated_mb)/1024 as gb
    FROM 'manifest.parquet'
    GROUP BY server_id
    ORDER BY gb DESC
""").df()
```

**Senior SE:** The manifest is the contract between planning and execution. Parquet enforces schema at the boundary — a worker that receives a malformed manifest will fail fast on read, not silently mid-download.

**HPC:** Parquet row groups map naturally to SLURM array tasks. Set row group size = files per task. Worker $SLURM_ARRAY_TASK_ID reads row group $SLURM_ARRAY_TASK_ID — zero-coordination slice.

```bash
#SBATCH --array=0-31
python download_worker.py --row-group $SLURM_ARRAY_TASK_ID manifest.parquet
```

---

## Use Case 3: Persistent Download Audit Log

### The current state

After a download, `FoundResource` objects exist only in the calling Python process. A CLI flag can serialize them to JSON, but the output has no schema, is not queryable, and is not appended across runs — each export overwrites.

Lockfiles (JSON sidecar files, one per downloaded file) provide some persistence, but auditing requires scanning potentially thousands of `.json` files in subdirectories.

### The Parquet alternative

An **audit log** Parquet table accumulates every download result across all runs. Each row records what was downloaded, when, from where, and whether it succeeded.

**Schema:**
```
run_id         : string           (UUID, stable per gnss-etl invocation)
timestamp      : timestamp[us]
station_code   : string
product        : string
date           : date32
uri            : string
server_id      : string
local_path     : string
success        : bool
bytes_received : int64
duration_ms    : int32
error_message  : string           (null on success)
```

**Location:** `{base_dir}/.gnss_audit/downloads.parquet` — or partitioned by year/month for large histories.

**Appending** is handled by writing new row groups; existing row groups are never rewritten. On read, filter by date or run_id.

### Who benefits

**Geophysicist:** Reproducibility. Six months later, "what data did I use for this PPP run?" is a SQL query over the audit log, not a hunt through directories.

```python
import duckdb
duckdb.query("""
    SELECT station_code, date, uri, local_path
    FROM 'downloads.parquet'
    WHERE run_id = 'abc-123'
      AND product = 'RINEX_OBS'
    ORDER BY date, station_code
""").df()
```

**Senior SE:** The audit log replaces the scattered JSON sidecar lockfiles with a single, queryable source of truth. It enables cache invalidation logic ("this file was downloaded more than 7 days ago from a server that serves rapid products — check for a final solution").

**HPC:** After a 32-worker array job, the audit log aggregates all results — including failures — in one place. Identifying which stations failed and resubmitting only those is a single filter query.

```python
failures = duckdb.query("""
    SELECT station_code, error_message
    FROM 'downloads.parquet'
    WHERE run_id = ? AND success = false
""", parameters=[run_id]).df()

# failures["station_code"].tolist() → input for a retry manifest
```

---

## Use Case 4: PPP Results Table

### The current state

After a batch PPP run, each processed station produces a `.kin` file that `pride_ppp` parses into a `pd.DataFrame` (via `kin_to_kin_position_df()`). In a 100-station batch run, this produces 100 separate DataFrames that must be manually concatenated for any multi-station analysis. There is no persistent storage of parsed results — the DataFrames live only as long as the Python process.

### The Parquet alternative

Write each station's PPP results to a partitioned Parquet dataset at the time of processing. The partition key is date and station code — matching how the data is naturally organized.

**Directory layout:**
```
results/
  year=2026/
    doy=004/
      station=FAIR/
        positions.parquet    (86400 rows × position columns)
        residuals.parquet
      station=BREW/
        positions.parquet
        ...
```

**Schema (positions):**
```
timestamp      : timestamp[us, UTC]
x_ecef         : float64 (meters)
y_ecef         : float64 (meters)
z_ecef         : float64 (meters)
lat            : float64 (degrees)
lon            : float64 (degrees)
height         : float64 (meters)
sigma_x        : float32
sigma_y        : float32
sigma_z        : float32
n_satellites   : int16
pdop           : float32
station_code   : string        (redundant with partition, useful for flat reads)
network_id     : string
```

**Multi-station read (the killer feature):**
```python
import pandas as pd

# Read all stations for a date range in one call
positions = pd.read_parquet(
    "results/",
    filters=[
        ("year", ">=", 2026),
        ("doy", "between", [1, 31]),
    ],
)
# → DataFrame with all stations, all days — ready for WRMS, network analysis, etc.
```

### Who benefits

**Geophysicist:** This is the highest-impact use case. Multi-station time series analysis — computing WRMS, fitting velocity fields, detecting offsets — currently requires a custom aggregation script per project. With a Parquet dataset, it's one `pd.read_parquet()` call followed by standard pandas/scipy operations. The results are also directly loadable into GIS tools (GeoPandas with geometry from lat/lon) or visualization tools (HoloViews, Plotly).

**Senior SE:** Parquet partitioned by date and station enables lazy loading — a notebook analyzing one station reads only that partition. The partition layout also aligns with how PPP is parallelized (one process per station per day), so each worker writes its own file with no coordination.

**HPC:** Post-processing across 1000 stations for 365 days produces 365,000 partition files — awkward for most formats, but normal for Parquet. Reading the full dataset with predicate pushdown (e.g., "only stations within 500 km of a point") skips irrelevant partitions entirely.

---

## Use Case 5: Remote Directory Listing Cache

### The current state

`WormHole` (the download orchestrator in `factories/remote_transport.py`) groups `SearchTarget` objects by `(hostname, directory)` and lists each remote directory once per query. These listings can be expensive: CDDIS FTPS connections have a connection limit of 2–4, and listing a directory of hundreds of daily files takes several seconds. Every new process re-fetches the same directory, even if nothing has changed.

### The Parquet alternative

Cache remote directory listings as Parquet, keyed by hostname, path, and a TTL timestamp. On a cache hit, skip the remote listing entirely.

**Schema:**
```
hostname      : string
path          : string
filename      : string
size_bytes    : int64
mtime         : timestamp[us]
cached_at     : timestamp[us]
ttl_seconds   : int32
```

**Cache lookup pattern:**
```python
import duckdb

def list_directory_cached(hostname, path, ttl=3600):
    cached = duckdb.query("""
        SELECT filename, size_bytes, mtime
        FROM 'dir_cache.parquet'
        WHERE hostname = ?
          AND path = ?
          AND cached_at > now() - INTERVAL (? SECONDS)
    """, parameters=[hostname, path, ttl]).df()

    if len(cached) > 0:
        return cached["filename"].tolist()

    # Cache miss: fetch and write
    files = remote_list(hostname, path)
    _write_cache(hostname, path, files)
    return files
```

### Who benefits

**Geophysicist:** Repeated runs over the same date range (e.g., reprocessing with a different PPP engine) skip remote listing entirely after the first run. What took 5 minutes of FTP requests on first run takes seconds on subsequent runs.

**Senior SE:** The cache is a simple append-and-filter pattern — no cache invalidation logic beyond TTL. The Parquet format means the cache survives process restarts and is inspectable without a special tool.

**HPC:** When 32 array workers all start at the same time and all need to list the same CDDIS directories, without a cache they would simultaneously open 32 FTP connections to CDDIS (which has a limit of 2–4). With a shared Parquet cache on a shared filesystem, one worker populates the cache and the rest hit it — staying within server limits.

---

## Use Case 6: Product Availability Matrix

### The current state

`DiscoveryReport` and `DiscoveryEntry` (in `factories/models.py`) provide an in-memory summary of what products were found for a given query. These are useful for a single date but are not accumulated across dates — there is no persistent record of "which analysis centers have final orbits for every day in 2025?"

### The Parquet alternative

An **availability matrix** is a Parquet table with one row per (product, center, date) combination, recording whether the product was found and from which server.

**Schema:**
```
product        : string    (ORBIT, CLOCK, RINEX_OBS, ...)
center         : string    (COD, ESA, GFZ, ...)
date           : date32
quality        : string    (FIN, RAP, ULT)
found          : bool
server_id      : string
uri            : string
file_size_bytes: int64
checked_at     : timestamp[us]
```

**Example queries:**
```python
import duckdb

# Which centers have final orbits for every day in Jan 2026?
duckdb.query("""
    SELECT center, COUNT(*) as days_available
    FROM 'availability.parquet'
    WHERE product = 'ORBIT'
      AND quality = 'FIN'
      AND date BETWEEN '2026-01-01' AND '2026-01-31'
      AND found = true
    GROUP BY center
    HAVING days_available = 31
    ORDER BY days_available DESC
""").df()

# Which dates have no final orbit from any center?
duckdb.query("""
    SELECT date
    FROM 'availability.parquet'
    WHERE product = 'ORBIT' AND quality = 'FIN' AND found = true
    GROUP BY date
    HAVING COUNT(DISTINCT center) = 0
""").df()
```

### Who benefits

**Geophysicist:** "Which centers reliably have data for my study period?" — answered in seconds rather than a test-download run. The availability matrix can be pre-built and shared as a community resource, so individual researchers don't need to rediscover the same data availability patterns.

**Senior SE:** The availability matrix decouples discovery from download. The `.search()` phase can be run as a lightweight nightly job that populates the matrix; `.download()` then consults the matrix rather than re-querying servers. This is especially valuable for products with known latencies (rapid orbits appear ~1 day after; final orbits appear ~2 weeks after).

**HPC:** Pre-built availability matrices allow jobs to skip centers that are known not to have data for a given date, reducing wasted connection attempts and failed downloads at scale.

---

## Implementation Notes

### Dependencies

Adding Parquet support requires:

```toml
# pyproject.toml
dependencies = [
    "pyarrow>=14.0",        # Parquet read/write, Arrow in-memory format
    "duckdb>=0.10",         # SQL over Parquet without a server
    # geopandas already declared — covers GeoParquet read/write
]
```

`pyarrow` is a transitive dependency of `geopandas` and `pandas` in most environments — it may already be installed.

### GeoParquet

The GeoParquet spec (v1.0) is supported natively by `geopandas.read_parquet()` and `geopandas.GeoDataFrame.to_parquet()`. No additional library is needed beyond the existing `geopandas` dependency.

### DuckDB

DuckDB can read Parquet files directly from local paths, S3, and HTTPS without loading them into memory first. It supports predicate pushdown against Parquet row group statistics, making it fast for filtering large datasets. It requires no server and adds a single small Python dependency.

### Avoiding Over-Engineering

Not every data structure needs Parquet. The existing JSON lockfile sidecars work well for per-file provenance tracking at small scale. The targets for Parquet are places where the current format creates a concrete friction point — startup latency, cross-run aggregation, HPC splitting, or spatial tool interoperability. Start with Use Cases 1 and 2 (station catalogs and download manifests), which have the broadest impact with the least architectural change.
