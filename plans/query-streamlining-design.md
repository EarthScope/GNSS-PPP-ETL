# GNSS Query Streamlining: Design Options

**Status:** Draft for discussion
**Context:** The current system has a working fluent API for station and product queries, but as networks and HPC use cases grow, several architectural pain points are becoming visible.

---

## Current Architecture in Brief

The system has two main query paths:

- **`StationQuery`** — spatial/temporal search → RINEX file discovery → parallel download. Each network has a concrete Python `NetworkProtocol` class plus a YAML config.
- **`ProductQuery`** — product search (ORBIT, CLOCK, etc.) → ranked candidates → download. Purely config-driven (YAML center specs + product catalog).

Servers (hostnames, protocols, credentials) are currently **embedded inside** network and center YAML configs. The query and transport layers are **interleaved** in the fluent builders.

---

## Pain Points Being Addressed

1. Server config (e.g., CDDIS hostname) is duplicated across multiple network/center files.
2. Adding a new GNSS network requires both a YAML file *and* a new Python class.
3. No serializable representation of a planned download — makes HPC job splitting awkward.
4. No dry-run or pre-flight mode before committing to a large download.
5. Station query and product query feel like separate systems even when a single workflow needs both.

---

## Design Option A: Global Server Registry

### Core Idea

Extract server definitions into their own dedicated config layer. Network and center configs reference servers by ID rather than embedding them.

**Current (server embedded in network config):**
```yaml
# igs_config.yaml
id: IGS
servers:
  - id: CDDIS
    hostname: "ftp://gdc.cddis.eosdis.nasa.gov"
    protocol: ftps
    auth_required: false
products:
  - server_id: CDDIS
    ...
```

**Proposed (server defined once, referenced everywhere):**
```yaml
# servers/cddis.yaml
id: CDDIS
hostname: "ftp://gdc.cddis.eosdis.nasa.gov"
protocol: ftps
auth_required: false
connection_limits:
  max_connections: 4
  timeout_seconds: 30
  retry_attempts: 3
health_check:
  path: "/pub/"
  interval_minutes: 5
```

```yaml
# igs_config.yaml
id: IGS
servers: [CDDIS, IGN]       # reference by ID — no hostname/protocol here
products:
  - server_id: CDDIS
    ...
```

### Trade-offs

**Senior SE perspective:**
Clean separation of concerns. Connection pool sizing, retry policy, and timeout config all live in one place per server. If CDDIS migrates from FTPS to HTTPS, you change one file. You can write a `ServerRegistry` class with health-check logic, a `client.servers()` introspection API, and server-level circuit-breakers. Aligns with the existing `ResourceSpec` / `Server` models — this is a natural split along an existing seam.

**Geophysicist perspective:**
Largely invisible day-to-day. The upside appears when something breaks: "CDDIS is down" is now diagnosable by checking `servers/cddis.yaml` health status rather than hunting through five different network configs. A `client.server_status()` method becomes possible.

**HPC perspective:**
Pre-flight connectivity checks become first-class. Before submitting a 1000-station array job, run `gnss-etl check-servers` to verify CDDIS, IGN, and NOAA S3 are reachable and responsive. A single bad server config can be patched without touching network logic.

### Implementation Scope

- New `ServerRegistry` class in `environments/`
- New `gpm-specs/configs/servers/` directory with per-server YAML files
- Update `ResourceSpec` loader to resolve server IDs against the registry
- Backward-compatible: embedded server dicts still work during transition

---

## Design Option B: Manifest-Based Two-Layer Model

### Core Idea

Split each query type into two explicit phases: **Catalog** (pure discovery, no I/O) and **Transport** (pure download, no logic). The output of the catalog phase is a serializable **Manifest** — a complete snapshot of what will be downloaded and from where.

```
Phase 1: Catalog
  StationQuery.plan()  →  StationManifest (JSON/Parquet)
  ProductQuery.plan()  →  ProductManifest (JSON/Parquet)

Phase 2: Transport
  Downloader.execute(manifest, sink, max_workers)  →  DownloadResult
```

**Manifest structure (conceptual):**
```python
class StationManifest(BaseModel):
    query_params: StationQueryParams    # what was asked
    stations: list[GNSSStation]         # resolved station metadata
    candidates: list[SearchTarget]      # pre-resolved remote URLs, ranked
    generated_at: datetime
    checksum: str                       # reproducibility fingerprint

class DownloadResult(BaseModel):
    manifest: StationManifest
    succeeded: list[FoundResource]
    failed: list[tuple[SearchTarget, str]]   # (target, error_message)
    duration_seconds: float
```

**Usage:**
```python
# Laptop: plan the job, inspect, then commit
manifest = (
    client.station_query()
    .within(64.978, -147.499, 1000)
    .networks("IGS", "CORS")
    .on(date)
    .plan()                              # new — no I/O beyond station catalog
)
manifest.save("/scratch/job_001/manifest.json")

# Review before downloading
print(f"Planned: {len(manifest.candidates)} files from {len(manifest.stations)} stations")

# HPC: worker receives manifest slice, downloads its portion
result = Downloader.execute(
    manifest.slice(worker_id=3, total_workers=16),
    sink_id="local",
    max_workers=50,
)
result.save("/scratch/job_001/result_worker_3.json")

# Combine results, identify failures, retry
combined = DownloadResult.merge(result_files)
retry_manifest = combined.failed_as_manifest()
```

### Trade-offs

**Senior SE perspective:**
The fluent builders become pure query planners — testable without any network access. Transport is a separate, swappable component. Clear SRP. The manifest is the system boundary between "planning" (runs anywhere) and "execution" (runs wherever data needs to land). Enables mocking the catalog phase in tests while using real transport in integration tests.

Concern: Two-phase adds conceptual overhead. Users already familiar with `.search()` / `.download()` need to learn `.plan()` / `Downloader.execute()`. The existing API should remain as syntactic sugar over the two-phase model.

**Geophysicist perspective:**
The manifest is the "shopping list" — you can review it before anything is downloaded. Share manifests with collaborators so they can replicate exactly what data was used in an analysis. The manifest becomes part of the scientific record alongside the processed data. Intermediate state is preserved: if a download fails halfway through, resume from the manifest rather than re-querying.

**HPC perspective:**
This is the most HPC-friendly design. A manifest is naturally an array-job input: worker N processes `manifest.stations[N::total_workers]`. Checkpointing is trivial — persist the manifest plus a set of completed station codes. Failed stations can be extracted as a new manifest and resubmitted as a small follow-up job. Works cleanly with SLURM array jobs, PBS, or cloud batch systems.

### Implementation Scope

- New `StationManifest` and `ProductManifest` models (extend existing `FoundResource`)
- `.plan()` method on `StationQuery` and `ProductQuery`
- `Downloader` class wrapping existing `WormHole` + connection pool logic
- `.slice(worker_id, total_workers)` and `.save()` / `.load()` on manifests
- Existing `.search()` / `.download()` remain unchanged (call `.plan()` internally)

---

## Design Option C: Declarative Query Specs (YAML-Driven Batches)

### Core Idea

Extend the YAML config system to support *query specifications* — complete descriptions of a data retrieval job that can be submitted to a CLI or HPC scheduler without writing Python.

**Query spec format:**
```yaml
# jobs/alaska_2026_jan.yaml
description: "Alaska CORS + IGS stations, Jan 2026"
version: 1

spatial:
  lat: 64.978
  lon: -147.499
  radius_km: 1000

networks: [IGS, CORS, ERT]

date_range:
  start: "2026-01-01"
  end: "2026-01-31"
  step: "1D"

products:
  - type: RINEX_OBS
    rinex_version: ["3", "2"]    # try in order
    variant: OBS
  - type: ORBIT
    preference: [FIN, RAP, ULT]
    sources: [COD, ESA, GFZ]
  - type: CLOCK
    preference: [FIN, RAP]
    sources: [COD, ESA]

execution:
  sink: local
  max_workers: 50
  retry_count: 3
  checkpoint_dir: /scratch/alaska_jan/checkpoints
```

**CLI usage:**
```bash
# Run interactively
gnss-etl run jobs/alaska_2026_jan.yaml

# Dry run — resolve manifest only, no download
gnss-etl plan jobs/alaska_2026_jan.yaml --output manifest.json

# Submit to SLURM
gnss-etl submit jobs/alaska_2026_jan.yaml --array-size 32 --partition data

# Check status
gnss-etl status jobs/alaska_2026_jan.yaml
```

**Programmatic usage (Python):**
```python
from gnss_product_management import GNSSJobSpec

spec = GNSSJobSpec.from_yaml("jobs/alaska_2026_jan.yaml")
client = GNSSClient.from_defaults(base_dir="/data/gnss")
result = client.run(spec)
```

### Trade-offs

**Senior SE perspective:**
YAML query specs are a layer on top of the existing fluent API, not a replacement. Implementation is a thin serialization/deserialization wrapper around the existing builders. The risk is YAML expressiveness: complex fallback logic (e.g., "try v3, but for stations X, Y, Z prefer v2") is awkward in YAML. Keep the Python API as the power-user escape hatch. Versioning the spec format matters — use `version:` field and migrate deliberately.

The spec format should be validated with JSON Schema or Pydantic to give early, clear error messages rather than cryptic runtime failures.

**Geophysicist perspective:**
This is the highest-impact option for non-programmers. A postdoc can write a YAML spec, commit it to git, and run `gnss-etl run spec.yaml` — no Python knowledge required. Specs are self-documenting job descriptions that travel with the data. Sharing a job spec with a collaborator gives them everything needed to replicate the exact data collection.

The spec format should have sensible defaults (e.g., `networks: all`, `preference: [FIN, RAP, ULT]`) so minimal config is needed for common cases.

**HPC perspective:**
YAML specs map directly to SLURM job scripts. The `gnss-etl submit` command can auto-generate a SLURM batch script from the spec, with array parallelism over dates or stations. The `checkpoint_dir` field enables fault-tolerant execution: already-downloaded files are skipped on restart. This is the pattern used by large data pipeline tools (Snakemake, Nextflow) — the spec is the workflow definition.

### Implementation Scope

- `GNSSJobSpec` Pydantic model with JSON Schema export
- YAML loader for job specs
- `GNSSClient.run(spec)` method
- CLI entry point: `gnss-etl` with `run`, `plan`, `submit`, `status` subcommands
- SLURM/PBS template generator for `submit`
- HPC-aware checkpoint tracking (SQLite or file-based)

---

## Design Option D: Unified Station + Product Query

### Core Idea

Currently, station RINEX and analysis-center products (ORBIT, CLOCK) are queried via entirely separate builders. A workflow that needs both for PPP processing requires two separate query chains that must be mentally composed. Provide a unified `GNSSJobQuery` that handles both in a single chain.

```python
job = (
    client.job_query()
    .spatial(lat=64.978, lon=-147.499, radius_km=1000)
    .networks("IGS", "CORS")
    .on(date)
    # Station observations
    .observations(rinex_version="3", fallback="2")
    # Analysis center products (for PPP)
    .orbits(preference=["FIN", "RAP"], sources=["COD", "ESA"])
    .clocks(preference=["FIN", "RAP"], sources=["COD", "ESA"])
    .download("local", max_workers=50)
)

# Result is a structured bundle
job.observations    # list[FoundResource] for RINEX_OBS
job.orbits          # list[FoundResource] for ORBIT
job.clocks          # list[FoundResource] for CLOCK
```

### Trade-offs

**Senior SE perspective:**
Ergonomic improvement for the common PPP workflow, but adds coupling between the station and product query systems which are otherwise cleanly independent. The unified builder is best implemented as a thin compositor over the existing separate builders, not as a new merged implementation. Risk: if either sub-query fails, the whole job fails — need careful error handling with partial results.

**Geophysicist perspective:**
This is the most natural representation of a PPP job. When running PPP, you need observations *and* products for the same date — they are conceptually one request. Not having to write two separate query chains (and remember to keep dates synchronized) reduces errors. The `job.observations`, `job.orbits`, `job.clocks` result structure maps directly to what a PPP processor expects.

**HPC perspective:**
Bundling the two queries allows intelligent co-scheduling: station obs and center products can be fetched in parallel since they come from different servers. A unified job also gives a single checkpoint granularity (date + station set) rather than having to manage two separate checkpoint streams.

### Implementation Scope

- `GNSSJobQuery` as a thin compositor class
- `GNSSJobResult` with typed sub-results
- Hook into existing `StationQuery` and `ProductQuery` internally
- Optional: serialize to/from `GNSSJobSpec` YAML (ties to Option C)

---

## Recommendation: Staged Implementation

These options are not mutually exclusive. A pragmatic ordering:

| Phase | Option | Effort | Impact |
|-------|--------|--------|--------|
| 1 | **A — Server Registry** | Low | Medium — fixes config fragmentation |
| 2 | **B — Manifest Model** | Medium | High — unlocks HPC, reproducibility |
| 3 | **C — Declarative Specs** | Medium | High — accessibility for non-programmers |
| 4 | **D — Unified Query** | Low | Medium — ergonomics for PPP workflow |

**Phase 1** is a pure refactor with no user-facing API changes — do it first to clean up the config layer.

**Phase 2** is the highest-leverage change for HPC use and scientific reproducibility — do it before the CLI to give the CLI something solid to wrap.

**Phase 3** depends on Phase 2 (manifest is the intermediate representation) and gives a clean CLI entry point for the HPC scheduler integration.

**Phase 4** is an ergonomic nicety that can be added at any phase since it's a thin compositor.

---

## Open Questions

1. Should server health-check state be stored locally (SQLite) or queried fresh each time?
2. What format should manifests use for HPC array jobs — JSON (human-readable) or Parquet (fast for large station counts)?
3. Should the YAML job spec support Jinja templating for date ranges, or keep it strictly declarative?
4. For the unified query (Option D), should partial failures (obs downloaded but orbits failed) return a partial result or raise?
5. Is there a need to support cloud-native manifest storage (S3) for distributed HPC workflows where workers don't share a filesystem?
