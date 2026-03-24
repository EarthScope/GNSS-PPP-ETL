# ProductEnvironment Public API

## Problem Statement

The `gnss-ppp-products` package has a fully built internal layer — catalogs, query factories, resource fetchers, dependency resolvers, local/remote factories — but no stable public interface for callers. Pipeline developers (e.g. `pride-ppp`) and researchers writing one-off scripts must reach into internals, wire up multiple factories, and manage query construction manually. There is no single entry point that encapsulates the five core operations every caller needs: find a product, download it, classify a filename, resolve task dependencies, and discover what's available.

## Solution

Expose **`ProductEnvironment`** as the sole public dependency. Construction requires only a workspace path (a local directory that must already exist). All specifications (parameter catalog, format catalog, product catalog, local folder spec) are bundled and auto-loaded. All remote centers and dependency specs are registered automatically. The five atomic operations are methods directly on the environment object.

```python
from datetime import date
from gnss_ppp_products import ProductEnvironment

env = ProductEnvironment(workspace="/data/pride-2025")

# Find best product (local-first, quality-ranked)
best = env.find(product="ORBIT", date=date(2025, 1, 15))

# Download it
path = env.download(best)

# Classify a filename
info = env.classify("WUM0MGXFIN_20250150000_01D_05M_ORB.SP3.gz")

# Resolve all deps for a task (find + download + lockfile)
resolution = env.resolve(task="pride-pppar", date=date(2025, 1, 15))

# Discover what's available (dry-run)
report = env.discover(date=date(2025, 1, 15))
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

- **`ProductEnvironment`** is the single public class callers depend on.
- Construction: `ProductEnvironment(workspace="/path/to/dir")` or `ProductEnvironment(workspace=("/path/to/dir", "my-alias"))`.
- `workspace` is the only required argument. It is a `str` (path only, alias defaults from stem) or `tuple[str, str]` (path, alias).
- `base_dir` must exist at construction time; the constructor raises `FileNotFoundError` if it doesn't.
- The environment is **frozen/immutable** after `__init__` completes. No mutation methods.

### Universal Specifications (auto-loaded, bundled)

- `parameter_catalog` — built from `meta_spec.yaml`
- `format_catalog` — built from `product_spec.yaml` + resolved parameters
- `product_catalog` — built from `product_spec.yaml` + resolved formats
- `local_spec` — built from `local_config.yaml` (folder structure spec)
- At build time: validate that every Product in the catalog has a corresponding sink path in the local spec.

### Remote Centers (auto-registered)

- All center YAMLs in `configs/centers/` are loaded: WUM, COD, CDDIS, IGS, ESA, GFZ, VMF.
- Center selection is a **call-level** concern (the `centers` parameter on find/resolve/discover).

### Dependency Specs (auto-registered)

- All dependency YAMLs in `configs/dependencies/` are loaded (e.g. `pride_pppar.yaml`).
- Referenced by name in `resolve(task="pride-pppar")`.

### Local Factory Architecture

The `LocalResourceFactory` is a registry of named local storage layouts. Each registered spec defines a set of **collections** (groups of product names → directory template). The factory provides two core capabilities:

1. **Directory resolution** (`resolve_directory`): Given a product name + date, return the local `Path` where that product's files live.
2. **Product resolution** (`resolve_product`): Given a local resource name + product + date, return a `(Server, ProductPath)` tuple for query construction.
3. **File search** (`find_local_files`): Given a `ResourceQuery`, find matching files on disk.

**Construction chain:**
- `ProductEnvironment` creates a `LocalResourceFactory` with `product_catalog` + `parameter_catalog`
- For each YAML in `configs/local/`, loads a `LocalResourceSpec` and calls `factory.register(spec, base_dir)`
- `register()` creates a `Server` (protocol="file"), builds `item_to_dir` mapping, stores as `RegisteredLocalResource`
- All registered base directories must be non-overlapping (enforced at registration time)

**Key invariant:** Every product in `product_catalog` must appear in at least one registered local collection's `items` list. This is validated at build time so that `find()` and `download()` always know the local sink path for any product.

### Operations API

All five operations are methods on `ProductEnvironment`:

**`find(product, date, *, centers=None, filters=None, all=False)`**
- `product`: `str` — product name (e.g. `"ORBIT"`, `"CLOCK"`, `"IONEX"`)
- `date`: `datetime.date` — single date
- `centers`: `list[str] | None` — optional subset of centers; `None` means all
- `filters`: `dict[str, str] | None` — parameter constraints applied at query level (e.g. `{"TTT": "FIN", "SMP": "05M"}`)
- `all`: `bool` — if `False` (default), return single best `FoundResource`; if `True`, return `list[FoundResource]` ranked by preference
- Search order: local workspace first, then remote centers
- Ranking: local > remote; within each layer, quality preference from config (FIN > RAP > ULT)

**`download(resource)`**
- `resource`: `FoundResource | list[FoundResource]`
- Returns `Path | list[Path]` — files written into the workspace according to the local folder structure spec
- If resource is already local, returns existing path (no-op)

**`classify(filename)`**
- `filename`: `str` — a GNSS product filename (optionally with path prefix and/or compression extension)
- Returns `dict | None` — `{"product", "format", "version", "variant", "parameters": {...}}` on match, `None` if no template matches
- Uses a precompiled regex match table sorted by template specificity (longest template first), with per-product merged `ParameterCatalog` for regex generation
- Strips directory prefix and compression extensions before matching
- Accepts optional `parameters: List[Parameter]` for hard constraints that filter candidates

**`resolve(task, date, *, centers=None, filters=None)`**
- `task`: `str` — dependency spec name (e.g. `"pride-pppar"`)
- `date`: `datetime.date`
- `centers`, `filters`: same as `find()`
- Internally: finds all required products, downloads missing ones, produces lockfile
- Returns `Resolution(lockfile=Lockfile, paths=list[Path])`
- Raises `MissingProductError` if any dependency cannot be found

**`discover(date, *, centers=None, filters=None, products=None)`**
- Dry-run: lists what's available without downloading
- Returns `DiscoveryReport` — human-readable summary of available products

### Return Types (Pydantic models)

- `FoundResource`: URI (local Path or remote URL), product name, center, quality, parameters, source type (local/remote)
- `Resolution`: lockfile (Lockfile model), paths (list of local Paths)
- `DiscoveryReport`: structured summary of available products by center/quality
- `Lockfile`: list of locked entries with URI, hash, product, date metadata

### Lockfile

- Produced by `resolve()` as a side-effect
- Accepted as input to `download()` for reproducible fetching with hash validation
- Scope: per-task (one lockfile per resolve call) AND per-file sidecar (future)
- Contains: URI, file hash, product name, center, date, parameters

### Filters

- Filters are `dict[str, str]` mapping parameter names to values (e.g. `{"TTT": "FIN"}`)
- Applied at the query level before search begins
- Use the raw parameter names from the specification (TTT, SMP, AAA, etc.)

### Internal Delegation

The public methods delegate to existing internal components:
- `find()` → `QueryFactory` (build query) → `LocalResourceFactory` (local search) → `RemoteResourceFactory` + `ResourceFetcher` (remote search)
- `download()` → `ResourceFetcher` (fetch + write to local spec path)
- `classify()` → precompiled `_MatchEntry` regex table (built at construction from `ProductSpecCatalog` + `ProductCatalog` + `ParameterCatalog`)
- `resolve()` → `DependencyResolver` (walk dep graph) → `find()` + `download()` per product
- `discover()` → `find(..., all=True)` across all products without download

## Known Bugs (must fix before Phase 2)

These bugs exist in the current codebase and block the `find()` / `download()` / `resolve()` phases. They do NOT affect `classify()` (Phase 1, already working).

### Bug 1: `RegisteredLocalResource` missing `server` field

**Location:** `specifications/local/factory.py` lines 31–36

The `RegisteredLocalResource` Pydantic model does not include a `server` field, but `resolve_product()` (line 189) returns `registered_spec.server` and `find_local_files()` (line 203) compares `registered_spec.server.id`. Both crash with `AttributeError` at runtime.

**Fix:** Add `server: Server` field to `RegisteredLocalResource`.

### Bug 2: Server object created but never stored

**Location:** `specifications/local/factory.py` `register()` method (lines 101–112, 132–139)

The `register()` method creates a `Server` object but does not pass it to the `RegisteredLocalResource` constructor. The server is discarded.

**Fix:** Pass `server=server` when constructing `RegisteredLocalResource`.

### Bug 3: `QueryFactory` → `LocalResourceFactory.resolve_product()` signature mismatch

**Location:** `factories/query_factory.py` line 168 vs `specifications/local/factory.py` line 177

`QueryFactory` calls:
```python
self._local.resolve_product(to_update, date)  # 2 args: Product, datetime
```

But `resolve_product()` expects:
```python
def resolve_product(self, local_resource_name: str, product: Product, date: datetime.datetime)  # 3 args
```

This raises `TypeError: resolve_product() missing 1 required positional argument: 'date'` at runtime.

**Fix:** `QueryFactory` must determine the correct `local_resource_name` to pass. Since the factory may have multiple registered specs, QueryFactory should iterate all registered specs and try each one for the given product, using `item_to_dir` membership to determine applicability. Add a method like `resolve_product_any(product, date) -> Tuple[Server, ProductPath]` that searches all registered specs, or restructure the `QueryFactory._local` call site to iterate.

## Testing Decisions

### What Makes a Good Test
- Tests exercise the public interface only (the 5 methods + construction)
- No testing of internal wiring, factory construction, or catalog internals
- Assert on return types, values, and error conditions

### Modules to Test

**`ProductEnvironment` construction:**
- Valid workspace path → environment created, specs loaded
- Missing workspace path → `FileNotFoundError`
- Alias defaulting from path stem
- Explicit alias override
- All products have sink paths validated

**`find()`:**
- Single best result for known product + date
- `all=True` returns ranked list
- Center filtering narrows results
- Parameter filters narrow results
- Local results preferred over remote
- Unknown product name raises

**`download()`:**
- Remote resource → file written to correct workspace path
- Already-local resource → returns existing path (no-op)
- Bulk download (list input)

**`classify()`:**
- Known PRODUCT filename → correct dict with product, format, version, variant, parameters
- RINEX v2 filename (e.g. `NCC12500.25o`) → correct RINEX_OBS match with regex constraints
- RINEX v3 filename → correct RINEX_OBS/NAV/MET match
- Orography filename (e.g. `orography_ell_1x1`) → correct OROGRAPHY match
- VMF filename → correct VMF match
- ATX filename → correct ATTATX match
- Unknown filename → returns `None`
- Compression extensions stripped before matching
- Directory paths stripped before matching
- Parameter hard constraints filter candidates
- Conflicting hard constraints → returns `None`

**`resolve()`:**
- Task with all deps available → Resolution with paths and lockfile
- Task with missing dep → `MissingProductError`
- Filters applied to dependency queries

**`discover()`:**
- Returns structured report for date/center combo
- Filters narrow discovery

### Prior Art
- Existing tests in `test/` follow the pattern: build environment from fixtures, call methods, assert on returned Pydantic models. The `test_orbit_resources.py`, `test_ionosphere_resources.py` etc. files demonstrate the fixture + assertion pattern.
- `test_product_environment.py` has a `TestClassify` class with 13 parametrized tests covering the classify() method.

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
