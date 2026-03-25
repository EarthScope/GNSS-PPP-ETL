# ProductEnvironment Public API

## Problem Statement

The `gnss-ppp-products` package has a fully built internal layer — catalogs, query factories, resource fetchers, dependency resolvers, local/remote factories — but no stable public interface for callers. Pipeline developers (e.g. `pride-ppp`) and researchers writing one-off scripts must reach into internals, wire up multiple factories, and manage query construction manually. There is no single entry point that encapsulates the five core operations every caller needs: find a product, download it, classify a filename, resolve task dependencies, and discover what's available.

## Solution

Split the public surface into two concepts:

1. **`ProductEnvironment`** — immutable state container holding all catalogs, factories, the resource fetcher, spec file locations, and caches. The only behavioral method is `classify()` (pure computation, no I/O).
2. **Pipelines** — classes in `factories/pipelines/` that own orchestration logic. Each pipeline takes an environment at construction and exposes a `run()` method. Pipelines compose other pipelines.

### Vocabulary

- **Environment** — the knowledge container (specifications, catalogs, factories, caches).
- **Pipeline** — a multi-step orchestration recipe that reads from the environment and interacts with the outside world (network, filesystem).
- **Task** — an instance of a software package performing a specific job (e.g. PRIDE-PPP kinematic processing, GypsyX-PPP static processing). A task's product requirements are described by a `DependencySpec` YAML.

```python
from datetime import date
from gnss_ppp_products import ProductEnvironment
from gnss_ppp_products.pipelines import FindPipeline, ResolvePipeline

env = ProductEnvironment(workspace="/data/pride-2025")

# Classify a filename (pure computation — stays on env)
info = env.classify("WUM0MGXFIN_20250150000_01D_05M_ORB.SP3.gz")

# Find best product (local-first, quality-ranked)
find = FindPipeline(env)
best = find.run(product="ORBIT", date=date(2025, 1, 15))

# Resolve all deps for a task (find + download + lockfile)
resolve = ResolvePipeline(env)
resolution = resolve.run(task="pride-pppar", date=date(2025, 1, 15))
```

## User Stories

1. As a pipeline developer, I want to create an environment with just a workspace path, so that I don't have to understand or configure internal specifications.
2. As a pipeline developer, I want to find the best available orbit product for a given date, so that I can use it in PPP processing.
3. As a researcher, I want to find all candidate products (not just the best), so that I can compare what's available across centers and quality tiers.
4. As a pipeline developer, I want to download a found remote resource to my workspace, so that the file is available locally for processing.
5. As a pipeline developer, I want to download a list of found resources in bulk, so that I can efficiently fetch multiple files.
6. As a researcher, I want to classify an arbitrary GNSS product filename, so that I can identify what product, center, quality tier, and date it represents.
7. As a pipeline developer, I want to resolve all dependencies for a task (e.g. pride-pppar) for a given date, so that every required file is downloaded and a lockfile is produced.
8. As a pipeline developer, I want resolve to raise an exception when any dependency is missing, so that I fail fast rather than proceeding with incomplete data.
9. As a researcher, I want to discover what products are available for a date without downloading, so that I can plan my processing.
10. As a pipeline developer, I want to filter queries by parameter constraints (e.g. quality=FIN, sampling=05M), so that I narrow results to exactly what I need.
11. As a pipeline developer, I want to specify a subset of centers per call, so that I can target specific data sources without rebuilding the environment.
12. As a researcher, I want the environment to default centers to "all registered" when I don't specify, so that I get the broadest search with minimal effort.
13. As a pipeline developer, I want the workspace alias to default from the directory name, so that I don't have to specify it explicitly.
14. As a pipeline developer, I want to provide an explicit alias for my workspace, so that lockfiles and logs use a meaningful identifier.
15. As a pipeline developer, I want base_dir validated at construction time, so that I get an immediate error if the workspace directory doesn't exist.
16. As a pipeline developer, I want the environment to be immutable after creation, so that I can safely share it across threads or pipeline stages.
17. As a pipeline developer, I want resolve to produce a lockfile capturing URIs and hashes, so that I can reproduce the exact same set of files later.
18. As a researcher, I want to provide a lockfile as input to download, so that I can reproduce a colleague's exact file set with hash validation.
19. As a pipeline developer, I want local-first searching (check workspace before querying remotes), so that I avoid unnecessary network calls.
20. As a pipeline developer, I want quality preferences to come from configuration, so that find returns FIN > RAP > ULT by default without per-call specification.
21. As a researcher, I want to override quality preference via filters, so that I can pin a specific tier when the default doesn't suit my analysis.
22. As a pipeline developer, I want all universal specs (parameter, format, product, local folder structure) to be bundled, so that I never manually configure them.
23. As a pipeline developer, I want every product to have a validated sink path in the local spec at build time, so that downloads always know where to write.

## Implementation Decisions

### Environment Model

- **`ProductEnvironment`** is the immutable state container callers construct first.
- Construction: `ProductEnvironment(workspace="/path/to/dir")` or `ProductEnvironment(workspace=("/path/to/dir", "my-alias"))`.
- `workspace` is the only required argument. It is a `str` (path only, alias defaults from stem) or `tuple[str, str]` (path, alias).
- `base_dir` must exist at construction time; the constructor raises `FileNotFoundError` if it doesn't.
- The environment is **frozen/immutable** after `__init__` completes. No mutation methods.
- The environment owns: catalogs, factories, `ResourceFetcher` (with its connection/listing caches), spec file locations, and the precompiled classify match table.
- The only behavioral method is `classify()` — pure regex computation, no I/O.

### What the Environment Holds

| Component | Purpose |
|---|---|
| `parameter_catalog` | Global parameter definitions + computed date fields |
| `format_catalog` | File format templates |
| `product_catalog` | Products × versions × variants |
| `remote_factory` | Remote center registry (FTP/HTTP server → product mapping) |
| `local_factory` | Local directory registry (workspace → product paths) |
| `resource_fetcher` | Protocol-agnostic search with connection + listing caches |
| `dependency_specs` | Registered task dependency specifications |
| `_match_table` | Precompiled regex table for `classify()` |

### Universal Specifications (auto-loaded, bundled)

- `parameter_catalog` — built from `meta_spec.yaml`
- `format_catalog` — built from `product_spec.yaml` + resolved parameters
- `product_catalog` — built from `product_spec.yaml` + resolved formats
- `local_spec` — built from `local_config.yaml` (folder structure spec)
- At build time: validate that every Product in the catalog has a corresponding sink path in the local spec.

### Remote Centers (auto-registered)

- All center YAMLs in `configs/centers/` are loaded: WUM, COD, CDDIS, IGS, ESA, GFZ, VMF.
- Center selection is a **call-level** concern (the `centers` parameter on pipeline `run()`).

### Dependency Specs (auto-registered)

- All dependency YAMLs in `configs/dependencies/` are loaded (e.g. `pride_pppar.yaml`).
- A `DependencySpec` describes what a **task** (software package instance) needs — not the task itself.
- Referenced by name in `ResolvePipeline.run(task="pride-pppar")`.

### Local Factory Architecture

The `LocalResourceFactory` is a registry of named local storage layouts. Each registered spec defines a set of **collections** (groups of product names → directory template). The factory provides two core capabilities:

1. **Source** (`source_product`): Given a product + resource ID, return `ResourceQuery` objects for searching local disk.
2. **Sink** (`sink_product`): Given a product + resource ID + date, return a `ResourceQuery` pointing to the local write path.

**Construction chain:**
- `ProductEnvironment` creates a `LocalResourceFactory` with `product_catalog` + `parameter_catalog`
- For each YAML in `configs/local/`, loads a `LocalResourceSpec` and calls `factory.register(spec, base_dir)`
- `register()` creates a `Server` (protocol="file"), builds `item_to_dir` mapping, stores as `RegisteredLocalResource`

**Key invariant:** Every product in `product_catalog` must appear in at least one registered local collection's `items` list. This is validated at build time so that `find()` and `download()` always know the local sink path for any product.

### Pipelines Architecture

Pipelines live in `factories/pipelines/` and are **classes that own orchestration, not state**. Each pipeline:
- Takes a `ProductEnvironment` at construction
- Reads catalogs/factories/fetcher from the environment (does not duplicate them)
- Exposes a `run()` method with typed parameters and return value
- May compose other pipelines

```
factories/
  pipelines/
    __init__.py
    find.py              # FindPipeline
    download.py          # DownloadPipeline
    resolve.py           # ResolvePipeline  (replaces dependency_resolver.py)
    lockfile_writer.py   # LockfileWriter   (extracted from DependencyResolver)
```

#### `FindPipeline` — query → search → rank

The core building block. Builds queries via `QueryFactory`, searches via the environment's `ResourceFetcher`, ranks results by preference cascade.

```python
class FindPipeline:
    def __init__(self, env: ProductEnvironment) -> None: ...

    def run(
        self,
        date: datetime,
        product: str,
        *,
        centers: list[str] | None = None,
        filters: dict[str, str] | None = None,
        preferences: list[SearchPreference] | None = None,
        all: bool = False,
    ) -> FoundResource | list[FoundResource]: ...
```

- `product`: `str` — product name (e.g. `"ORBIT"`, `"CLOCK"`, `"IONEX"`)
- `date`: `datetime.datetime` — target date (timezone-aware)
- `centers`: optional subset of centers; `None` means all registered
- `filters`: parameter constraints applied at query level (e.g. `{"TTT": "FIN", "SMP": "05M"}`)
- `preferences`: explicit preference cascade; `None` uses default quality ranking
- `all`: if `False` (default), return single best `FoundResource`; if `True`, return `list[FoundResource]` ranked by preference
- Search order: local workspace first, then remote centers
- Internally constructs a `QueryFactory` from the environment's factories/catalogs

#### `DownloadPipeline` — found resource → local path

Fetches remote resources to the local workspace using the environment's `ResourceFetcher` and `LocalResourceFactory` for sink path resolution.

```python
class DownloadPipeline:
    def __init__(self, env: ProductEnvironment) -> None: ...

    def run(
        self,
        resources: FoundResource | list[FoundResource],
        date: datetime,
    ) -> Path | list[Path]: ...
```

- Already-local resources return existing path (no-op)
- Remote resources are downloaded to the workspace path determined by `local_factory.sink_product()`
- Uses the environment's shared `ResourceFetcher` (preserves connection/listing caches)

#### `ResolvePipeline` — walk dependency spec, find + download + lockfile

Replaces `DependencyResolver`. Composes `FindPipeline` + `DownloadPipeline` + `LockfileWriter`.

```python
class ResolvePipeline:
    def __init__(self, env: ProductEnvironment) -> None: ...

    def run(
        self,
        task: str,
        date: datetime,
        *,
        centers: list[str] | None = None,
        filters: dict[str, str] | None = None,
        download: bool = True,
    ) -> DependencyResolution: ...
```

- `task`: dependency spec name (e.g. `"pride-pppar"`) — identifies what a software package instance needs
- Walks each `Dependency` in the spec, calls `FindPipeline.run()` with the spec's preference cascade
- Downloads missing products via `DownloadPipeline` when `download=True`
- Writes lockfile automatically via `LockfileWriter` (implicit, always happens)
- Raises `MissingProductError` if any required dependency cannot be found
- Returns `DependencyResolution` with resolved paths, statuses, and lockfile reference

#### `LockfileWriter` — serialize resolution to disk

Extracted responsibility — not a pipeline itself, but a collaborator used by `ResolvePipeline`.

```python
class LockfileWriter:
    def __init__(self, base_dir: Path) -> None: ...

    def write(
        self, resolution: DependencyResolution, date: datetime
    ) -> Path: ...
```

- Writes to `{base_dir}/.locks/{spec_name}_{date:%Y%j}.lock.json`
- Builds `ProductLockfile` model from resolved dependencies (URLs, hashes, sizes)
- Lockfile writing is implicit in `ResolvePipeline` — callers don't invoke it directly
- The `ProductLockfile` model already exists in `specifications/dependencies/lockfile.py`

### classify() — stays on ProductEnvironment

`classify()` is the only behavioral method on the environment because it's purely computational:
- No I/O, no network, no orchestration
- Uses the precompiled `_MatchEntry` regex table built at construction
- Returns `dict | None` — `{"product", "format", "version", "variant", "parameters": {...}}`
- Strips directory prefix and compression extensions before matching
- Accepts optional `parameters: List[Parameter]` for hard constraints

### Return Types (Pydantic models)

- `FoundResource`: URI (local Path or remote URL), product name, center, quality, parameters, source type (local/remote)
- `DependencyResolution`: spec name, list of `ResolvedDependency` (status, local_path, hash, size, lockfile entry)
- `DiscoveryReport`: structured summary of available products by center/quality
- `ProductLockfile`: list of `LockProduct` entries with URI, hash, product, date metadata

### Lockfile

- Produced by `ResolvePipeline` as an implicit side-effect (always written after successful resolution)
- Accepted as input to `DownloadPipeline` for reproducible fetching with hash validation (future)
- Scope: per-task, per-date (one lockfile per resolve call)
- Contains: URI, file hash, product name, center, date, parameters

### Filters

- Filters are `dict[str, str]` mapping parameter names to values (e.g. `{"TTT": "FIN"}`)
- Applied at the query level before search begins
- Use the raw parameter names from the specification (TTT, SMP, AAA, etc.)

### Internal Delegation

```
classify()        → ProductEnvironment._match_table (pure regex, no delegation)
FindPipeline      → QueryFactory.get() → env.resource_fetcher.search()
DownloadPipeline  → env.resource_fetcher.download() → env.local_factory.sink_product()
ResolvePipeline   → FindPipeline + DownloadPipeline + LockfileWriter
```

### Migration from DependencyResolver

The existing `dependency_resolver.py` is replaced by `ResolvePipeline`:
- Preference sorting logic moves to `FindPipeline._apply_preferences()`
- Local-vs-remote resolution logic moves to `FindPipeline.run()` (local-first search order)
- Download logic moves to `DownloadPipeline.run()`
- Lockfile writing moves to `LockfileWriter.write()`
- The `DependencyResolver` class is deprecated and removed

## Known Bugs ~~(must fix before Phase 2)~~ — ALL FIXED

All three bugs have been resolved. Documented here for reference.

### Bug 1 (FIXED): `RegisteredLocalResource` missing `server` field

**Location:** `specifications/local/factory.py`

Added `server: Server` field to `RegisteredLocalResource`.

### Bug 2 (FIXED): Server object created but never stored

**Location:** `specifications/local/factory.py` `register()`

Added `server=server` when constructing `RegisteredLocalResource`.

### Bug 3 (FIXED): `QueryFactory` → `LocalResourceFactory.resolve_product()` signature mismatch

**Location:** `factories/query_factory.py` vs `specifications/local/factory.py`

Changed `resolve_product()` to accept `(product, date)` and iterate all registered specs to find the one whose `item_to_dir` contains the product name. Also fixed `find_local_files()` loop that used `for x in dict: ... break` pattern which would set `x` to the last item regardless of match.

## Testing Decisions

### What Makes a Good Test
- Tests exercise the public interface: `ProductEnvironment` construction + `classify()`, and pipeline `run()` methods
- No testing of internal wiring, factory construction, or catalog internals
- Assert on return types, values, and error conditions
- Pipeline tests mock the environment's `resource_fetcher` to avoid network I/O

### Modules to Test

**`ProductEnvironment` construction + `classify()`:**
- Valid workspace path → environment created, specs loaded
- Missing workspace path → `FileNotFoundError`
- Alias defaulting from path stem
- Explicit alias override
- `resource_fetcher` is accessible and shared
- classify: Known filenames → correct dict; unknown → `None`; compression/path stripped; parameter constraints

**`FindPipeline`:**
- Single best result for known product + date
- `all=True` returns ranked list
- Center filtering narrows results
- Parameter filters narrow results
- Local results preferred over remote
- Preference cascade applied correctly
- Unknown product name raises

**`DownloadPipeline`:**
- Remote resource → file written to correct workspace path
- Already-local resource → returns existing path (no-op)
- Bulk download (list input)

**`ResolvePipeline`:**
- Task with all deps available → DependencyResolution with paths
- Lockfile written implicitly to `.locks/` directory
- Task with missing required dep → `MissingProductError`
- Filters applied to dependency queries
- `download=False` returns resolution without downloading

**`LockfileWriter`:**
- Writes valid JSON lockfile to expected path
- Round-trips through `ProductLockfile.from_json_file()`

### Prior Art
- Existing tests in `test/` follow the pattern: build environment from fixtures, call methods, assert on returned Pydantic models.
- `test_product_environment.py` has a `TestClassify` class with 13 parametrized tests covering the classify() method.
- `test_dependency_resolution.py` tests the current DependencyResolver — these will migrate to test ResolvePipeline.

## Phase 1 Implementation Status

Phase 1 (Environment Construction + classify()) is **complete**. What was built:

### Constructor
- Three construction paths: `workspace=` (preferred), legacy `base_dir=`, `from_yaml()` class method
- Workspace path auto-loads all bundled YAMLs (meta, format, product, local, centers, dependencies)
- `base_dir` existence validated at construction time
- Alias defaults from directory stem or can be overridden via tuple
- Immutable after construction (no register methods, no setters)

### classify()
- Returns `Optional[Dict[str, str]]` — `{"product", "format", "version", "variant", "parameters": {...}}` or `None`
- Uses `_MatchEntry` NamedTuple table precompiled at construction via `_build_match_table()`
- Sorted by template length (most specific first) — first match wins
- Per-product merged `ParameterCatalog` overlays product parameter patterns onto the global catalog for regex generation
- Regex constraints in `product_spec.yaml` (character classes like `[dot]`, `[ONM]`) stored as `pattern` on Parameter (not `value`) to prevent `derive()` from substituting them and `re.escape()` from destroying the regex
- Strips directory prefix and compression extensions
- Accepts optional `parameters: List[Parameter]` hard constraints

### Deviations from original PRD
- `classify()` returns `dict | None` instead of a `ClassifiedProduct` Pydantic model — simpler, avoids premature type ceremony
- `classify()` returns `None` for no-match instead of raising `ValueError` — more ergonomic for pipeline use
- No `ClassifiedProduct` model defined — the plain dict is sufficient for now

## Phase 2 Plan — Pipelines

Phase 2 introduces the `factories/pipelines/` module. Implementation order:

1. **Add `resource_fetcher` to `ProductEnvironment`** — construct a shared `ResourceFetcher` in `__init__`, expose as read-only property
2. **`FindPipeline`** — extract query-build + search + rank logic from `DependencyResolver._resolve_one()` and the `find_and_download.py` example into a standalone pipeline class
3. **`DownloadPipeline`** — extract download-to-sink logic from `DependencyResolver._download_result()` and `ResourceFetcher.download()`
4. **`LockfileWriter`** — extract lockfile construction from `DependencyResolver._write_file_lock()` / `_make_resolved()`
5. **`ResolvePipeline`** — compose Find + Download + LockfileWriter, replacing `DependencyResolver`
6. **Migrate callers** — update `find_and_download.py` example and `pride-ppp/products.py` to use pipelines
7. **Deprecate/remove `DependencyResolver`** — once all callers are migrated

## Out of Scope

- **Multi-local priority search**: searching across multiple workspaces in priority order (noted as future TODO)
- **Date ranges**: all operations are single-date; multi-date iteration is the caller's concern
- **Remote hash checking**: verifying remote file integrity before download (hashes rarely available remotely)
- **CLI**: this PRD covers the Python API only, not command-line tooling
- **Per-file sidecar lockfiles**: the resolve lockfile is per-task; sidecar format is future work
- **Custom/user-provided specifications**: all specs are bundled; there is no mechanism for users to add custom product definitions
- **Streaming/async API**: all operations are synchronous from the caller's perspective (internal concurrency is an implementation detail)

## Further Notes

- The 16 known products are: RINEX_OBS, RINEX_NAV, RINEX_MET, ORBIT, CLOCK, ERP, BIA, ATTOBX, IONEX, RNX3_BRDC, LEAP_SEC, SAT_PARAMS, VMF, OROGRAPHY, LEO_L1B, ATTATX.
- The 7 bundled centers are: WUM, COD, CDDIS, IGS, ESA, GFZ, VMF.
- Quality preference order (from config): FIN > RAP > ULT.
- The `ProductEnvironment` consolidates what was previously split across `ProductEnvironment`, `QueryFactory`, `ResourceFetcher`, and `DependencyResolver` into a single caller-facing object. The internals remain factored; only the public surface changes.
