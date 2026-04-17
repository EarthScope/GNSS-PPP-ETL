# PRD: GNSS Station Network Query & RINEX Access

**Date:** 2026-04-15
**Status:** Draft
**Package:** `gnss-product-management`

---

## Problem Statement

`gnss-product-management` currently handles precision product retrieval (orbits, clocks,
biases, ERP) from IGS analysis centers — but has no concept of GNSS *stations* or
observation data networks. A user processing a site in Alaska cannot ask
"give me all stations within 150 km of this volcano and download their RINEX files";
they must look up station codes manually, hard-wire them into configs, and deal with
network-specific authentication (e.g. EarthScope GAGE's OAuth2) entirely outside the
library. Station metadata is not modelled anywhere in the system, so spatial searches,
availability checks, and per-network protocol variations are all left to the user.

Dependency specs (`DependencySpec`) that drive PPP pipelines cannot express "I need a
RINEX observation file for a station matching these criteria" — the station identity must
be resolved upstream and baked in as a literal file path, making specs inflexible and
non-portable.

---

## Solution

Extend `gnss-product-management` with a **Station Query subsystem** that models GNSS
networks and their stations, supports spatial and temporal queries, exposes a fluent API
consistent with the existing `ProductQuery` interface, integrates a pluggable auth layer,
and allows `DependencySpec` to express station requirements declaratively.

New networks are registered through YAML network configs and decorator-registered
functions on a `NetworkRegistry` instance — no new classes required for standard cases.
Auth credentials are resolved through env vars declared in the network YAML.

---

## Coding Philosophy

These principles govern all implementation decisions in this PRD. They are derived from
the project's behavioral guidelines in `.github/skills/CLAUDE.md`. When in doubt, the
simpler approach wins.

**Think before coding — surface tradeoffs, don't assume.**
Before implementing any component, state assumptions explicitly. If multiple
interpretations exist, present them. If a simpler approach exists, take it. If something
is unclear, stop and ask rather than guessing and refactoring later.

**Minimum code that solves the problem — nothing speculative.**
Every class, protocol, and method must be required by a concrete use case in this PRD.
No features beyond what was asked. No abstractions for single-use code. No
"flexibility" or "configurability" that wasn't requested. No error handling for
impossible scenarios. If an implementation can be 50 lines, it should not be 200.
Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

**Reuse before extending, extend before creating.**
Prefer wiring existing classes (`WormHole`, `SearchPlanner`, `ConnectionPool`,
`LockfileWriter`) over building new ones. When a class must be extended, add the minimum
required — a new method, a new parameter — rather than a new subclass. Only create new
classes when the abstraction genuinely cannot live anywhere else.

**YAML-driven configuration over code.**
New networks that fit the standard patterns (`remote_api` or `local_index`) require only
a YAML file. Code is written only for what YAML cannot express: custom response mapping,
custom filesystem construction, custom credential resolution. The bar for writing a new
registered function is "YAML cannot express this" — not "this might vary someday."

**Decorator registration over class inheritance.**
Network-specific logic is registered as functions (`@registry.station_query`,
`@registry.response_adapter`, `@registry.credential`, `@registry.filesystem`) against a
`NetworkRegistry` instance. This mirrors `ParameterCatalog.computed()` and avoids deep
inheritance hierarchies. A new network adds a registration module — no base class to
subclass, no interface to implement.

**Surgical changes only — touch only what you must.**
Existing classes (`ProductRegistry`, `ConnectionPool`, `ResolvePipeline`, etc.) are
modified only where this PRD explicitly requires it. Adjacent code, comments, and
formatting are left untouched. Every changed line must trace directly to a requirement
in this PRD. Remove imports/variables/functions that your changes made unused — don't
remove pre-existing dead code unless asked.

**Validate at boundaries, trust internals.**
Input validation (spatial filter parameters, dep spec structure, YAML schema) happens at
the public API boundary — Pydantic models and explicit validators. Internal plumbing
trusts that upstream validation has already run. Do not add defensive checks inside
`SearchPlanner`, `WormHole`, or `LockfileWriter` for conditions that the query layer
already enforces.

**Goal-driven execution — define success criteria before writing code.**
Transform each task into a verifiable goal before starting:
- "Add `StationQuery`" → "Write builder tests, then make them pass"
- "Add `RINEX_OBS` dispatch" → "Write a `ResolvePipeline` test that reproduces the
  missing path, then make it pass"

For multi-step tasks, state a brief plan with explicit verify steps before
implementing. Strong success criteria allow independent progress; weak criteria
("make it work") require constant clarification.

---

## Extensibility Model

Adding a new GNSS network in the future should require only:

1. **A network YAML** in `configs/networks/` declaring the network ID, server, spatial
   protocol type, and credential names.
2. **A registration module** (only if the network needs custom query logic, response
   mapping, credential resolution, or filesystem construction) with functions decorated
   against the `NetworkRegistry` instance.
3. **A call to `register_network_handlers()`** to wire the module into
   `DefaultNetworkEnvironment`.

No modifications to `StationQuery`, `SearchPlanner`, `ConnectionPool`, `ResolvePipeline`,
or any other core class. The four decorator registration points are the only extension
surface:

| Decorator | When needed |
|---|---|
| `@registry.station_query` | Network has non-standard spatial query logic |
| `@registry.response_adapter` | Network response schema differs from `GNSSStation` fields |
| `@registry.credential` | Network requires custom token resolution beyond env var lookup |
| `@registry.filesystem` | Network requires custom fsspec filesystem (auth headers, query params) |

A network that fits standard patterns (public remote API with a URL template, response
keys matching `GNSSStation` fields, no auth) needs only a YAML file — no Python code.

---

## User Stories

1. As a geodesist, I want to find all GNSS stations within a given radius of a
   lat/lon point, so that I can select stations relevant to a volcanic deformation study.

2. As a geodesist, I want to find all GNSS stations within a bounding box, so that I can
   select stations covering a geographic region without specifying a centre point.

3. As a geodesist, I want to download RINEX observation files for a set of discovered
   stations to my local filesystem for a given date, so that I can run my PPP processing
   pipeline on them.

4. As a geodesist, I want to see which networks contain stations matching my spatial
   query, so that I know which data providers to engage with.

5. As a geodesist, I want to access station metadata (4-char code, lat/lon, network,
   data availability start/end dates) for stations matching a spatial query, so that I
   can filter stations by temporal coverage before downloading anything.

6. As a geodesist, I want to filter spatial or network queries by a date range, so that
   I only receive stations that were active during my processing period.

7. As a geodesist, I want to specify a RINEX version (2 or 3) for station RINEX
   retrieval, so that I can use the format compatible with my processing software.

8. As a geodesist, I want to specify a target network (e.g. `ERT`, a future `CORS`)
   within a spatial query, so that I can restrict retrieval to a trusted or preferred
   data provider.

9. As a PPP pipeline operator, I want to express a RINEX station dependency in a
   `DependencySpec` as either a concrete station code list or a spatial query that
   resolves at runtime, so that my processing specs are portable and do not require
   manual station lookup.

10. As a PPP pipeline operator, I want the dependency resolution pipeline to
    automatically resolve a spatial station query against the appropriate network,
    download the RINEX files, and record them in the lockfile, so that station data is
    treated like any other dependency.

11. As a PPP pipeline operator, I want to specify the required RINEX version inside a
    dependency spec, so that the resolver always fetches the correct format for my
    processing tool.

12. As a user with restricted data access, I want to provide my EarthScope GAGE
    credentials once (via environment variable or the EarthScope SDK token cache) and
    have all subsequent RINEX queries and downloads use them transparently, so that I do
    not have to handle authentication manually in my scripts.

13. As a user, I want authentication failures to produce clear, actionable error
    messages that tell me which credential is missing and how to supply it, so that I
    can unblock myself without reading source code.

14. As a developer, I want to register a new GNSS network by adding a YAML center
    config, so that adding public anonymous networks requires only configuration, not
    code.

15. As a developer, I want to register a custom `NetworkHandler` Python class for a
    network with a non-standard API, so that I can implement OAuth token injection,
    metadata endpoint queries, or other protocol details in an isolated, testable unit.

16. As a developer, I want the `NetworkHandler` interface to expose spatial query,
    metadata fetch, and RINEX download as separate, independently testable methods, so
    that I can mock or stub individual capabilities during testing.

17. As a developer, I want the `StationCatalog` to be loadable from the existing
    center YAML directory without breaking backward compatibility with existing
    product-only center configs, so that network configs are additive.

18. As a developer, I want the auth credential abstraction (`TokenProvider`) to be
    independently testable with a simple mock implementation, so that network handler
    tests do not require live OAuth flows.

19. As a developer, I want the `StationQuery` builder to follow the same fluent,
    immutable-clone pattern as `ProductQuery`, so that the API is familiar and
    predictable.

20. As a developer, I want `GNSSClient` to expose a `station_query()` method that
    returns a `StationQuery` builder, so that station and product queries share a single
    entry point and can be composed in the same script.

---

## Implementation Decisions

### New Modules

**`GNSSStation` model**
A Pydantic model representing the minimal metadata for a station. Required fields:
`site_code` (4-char), `lat`, `lon`. Optional fields: `network_id`, `start_date`,
`end_date`. `None` for `end_date` means the station is currently active; `None` for
`start_date` means unknown — such stations are included rather than excluded by temporal
filters. No hardware fields (receiver, antenna) in v1; they are out of scope.

**`SpatialFilter`**
A Pydantic model representing *what* to query, not *how* to execute it. Supports two
shapes (discriminated union):
- `PointRadius(lat, lon, radius_km)` — great-circle query
- `BoundingBox(min_lat, min_lon, max_lat, max_lon)` — rectangular query

`SpatialFilter` is a pure data model. It carries no logic for communicating with any
server. How the filter is executed against a specific network is the responsibility of
the registered `SpatialQueryProtocol` (see below).

**`ResponseAdapter` protocol**
A `Protocol` with a single method: `adapt(raw: dict) -> GNSSStation | None`. Returns
`None` for records missing required fields (`site_code`, `lat`, `lon`); the calling
protocol silently skips `None` results. A `PassthroughAdapter` (default) assumes
response keys match `GNSSStation` field names exactly. Custom adapters (e.g.
`EarthScopeResponseAdapter`) are registered against a `NetworkRegistry` instance using
the `@registry.response_adapter("ERT")` decorator.

**`SpatialQueryProtocol` + `SpatialQueryContext`**
A Python `Protocol` that abstracts spatial query execution. The single method:

```python
def query(filter: SpatialFilter, context: SpatialQueryContext) -> list[GNSSStation]
```

`SpatialQueryContext` carries: `server: Server`, `token: str | None`, and
`cache_dir: Path | None` (only consumed by `LocalIndexProtocol`; configured per-network
in YAML via `spatial_protocol_config.cache_dir`).

Two v1 implementations:

1. **Remote spatial API** (`RemoteSpatialAPIProtocol`, key `"remote_api"`) — the
   network exposes an endpoint that accepts spatial parameters and returns only matching
   stations. Configured via `spatial_protocol_config.url_template` in the network YAML.
   Response is mapped to `GNSSStation` via the registered `ResponseAdapter`. Example:
   ```
   https://web-services.unavco.org/gsac/site?lat={lat}&lon={lon}&radius={radius_km}
   ```

2. **Local index** (`LocalIndexProtocol`, key `"local_index"`) — queries a plain CSV
   station index stored at `spatial_protocol_config.cache_dir`. Applies pure-Python
   haversine / bbox filtering in-process. Raises a clear error if the CSV is absent —
   index building is always explicit (via a dev script), never automatic. The index is a
   tracked artifact that may be committed to the repository. `spatial_protocol_config.ttl_days`
   controls staleness warnings (default: 7 days); `.refresh_index()` currently no-ops
   with a warning log on all protocol types (reserved for future cache invalidation).

`StationQuery` calls `NetworkRegistry.protocol_for(center_id)` to select the correct
protocol at query time — no conditional branching in the query layer.

**`IndexBuilder` protocol**
A separate `Protocol` for building the `LocalIndexProtocol` CSV, with one implementation
per network registered in YAML via `spatial_protocol_config.index_builder_module`. Index
building is an explicit dev/ops operation, never triggered automatically at query time.

**`NetworkRegistry`**
A new registry (consistent with `ProductRegistry`) that maps network IDs to their
configured `SpatialQueryProtocol` instance, built from network YAML configs. Loaded
independently from `ProductRegistry` — `GNSSClient` constructs both from their
respective config directories (`configs/centers/` and `configs/networks/`).

Network-specific functions are registered against a `NetworkRegistry` instance using
four decorator types:
- `@registry.station_query("ERT")` — spatial metadata query function
- `@registry.response_adapter("ERT")` — response dict → `GNSSStation` mapping
- `@registry.credential("earthscope_token")` — token resolver function
- `@registry.filesystem("ERT")` — fsspec `AbstractFileSystem` factory for authenticated download

This mirrors the `ParameterCatalog.computed()` decorator pattern. A
`DefaultNetworkEnvironment` singleton is built at import time (same as
`DefaultProductEnvironment`), with EarthScope functions registered against it in a
`register_network_handlers()` call. `GNSSClient.from_defaults()` picks up the
pre-built `DefaultNetworkEnvironment`.

`ConnectionPool` accepts an optional fsspec filesystem instance at construction.
`NetworkEnvironment` constructs the appropriate filesystem via `@registry.filesystem`
and passes it to `ConnectionPool` — keeping `ConnectionPool` fully unaware of auth,
tokens, or server-specific query parameters (e.g. `?list` for EarthScope directory
listings).

**Network YAML schema** (`configs/networks/<id>.yaml`):
```yaml
id: ERT
description: EarthScope GAGE network
server:
  hostname: data.earthscope.org
  protocol: https
  auth_required: true
spatial_protocol: remote_api
spatial_protocol_config:
  url_template: "https://web-services.unavco.org/gsac/site?..."
  cache_dir: null          # only for local_index
  ttl_days: 7              # only for local_index
credentials:
  - name: earthscope_token
    env_var: EARTHSCOPE_TOKEN
```

Note: `web-services.unavco.org` (spatial metadata API) is public and requires no auth.
`data.earthscope.org` (RINEX download) requires `EARTHSCOPE_TOKEN`. These are separate
servers with separate auth concerns handled by separate registered functions.

Centers providing only precision products (COD, ESA, etc.) have no network YAML and are
not loaded by `NetworkRegistry`. Product center configs in `configs/centers/` are
untouched.

**`CredentialStore` + `TokenProvider`**
`TokenProvider` is a `Protocol` with a single method: `get_token(credential_name: str) -> str | None`.
Credential resolver functions are registered via `@registry.credential(name)` and
resolve env var names declared in the network YAML `credentials` list. Auth is lazy —
triggered on first `.metadata()`, `.search()`, or `.download()` call. If no token can
be resolved, a hard error is raised naming the missing env var and how to set it.
`EarthScopeSDKTokenProvider` is out of scope for v1.

**`StationQuery`**
Fluent immutable-clone builder, mirroring `ProductQuery`. Wired with `WormHole`,
extended `SearchPlanner`, and `NetworkRegistry` — same construction pattern as
`ProductQuery`.

Builder methods:
- `.within(lat, lon, radius_km)` — set `PointRadius` spatial filter (last-wins with `.in_bbox()`)
- `.in_bbox(min_lat, min_lon, max_lat, max_lon)` — set `BoundingBox` filter (last-wins with `.within()`)
- `.from_stations(*codes)` — explicit 4-char station codes; requires `.centers()` to be set (enforced at execution time)
- `.centers(*ids)` — restrict to these center IDs, mirroring `ProductQuery.sources()`; optional for spatial queries, required for `.from_stations()`
- `.on(date)` — single date; serves as both station availability filter and RINEX retrieval date. `.on_range()` is not supported for station queries.
- `.rinex_version(v)` — pin RINEX version; defaults to `"3"`; filters at `.metadata()`, `.search()`, and `.download()`
- `.refresh_index()` — force `LocalIndexProtocol` centers to re-fetch their station index regardless of TTL; silently no-ops with a warning log on `remote_api` centers

Execution methods:
- `.metadata() -> list[GNSSStation]` — query station metadata; requires a spatial filter or `.from_stations()`; returns partial results with a warning log if a center is unreachable
- `.search() -> list[FoundResource]` — discover matching RINEX files across centers; results sorted by station code ascending, then RINEX version descending; multi-center duplicates for the same station code are both returned as a ranked fallback chain
- `.download(sink_id) -> list[FoundResource]` — search + download; auto-falls back to next center entry if a download fails; returns `list[FoundResource]` with `local_path` populated on the winning entry so the caller can see which center served the file

**`GNSSClient` extension**
`GNSSClient.station_query() -> StationQuery` — returns a fresh builder wired to the
client's `WormHole`, extended `SearchPlanner`, and `NetworkRegistry`.

**`SearchPlanner` extension**
`SearchPlanner` is extended to handle `RINEX_OBS` products. `NetworkHandler.resolve_rinex()`
produces `SearchTarget` objects that feed into the existing planner pipeline, allowing
`WormHole` to handle RINEX observation downloads unchanged.

**`CredentialStore` + `TokenProvider`**
`TokenProvider` is a `Protocol` with a single method: `get_token(network_id: str) -> str | None`.
Auth is lazy — triggered on first `.metadata()`, `.search()`, or `.download()` call, not
at construction time. This allows browser-based OAuth flows (e.g. EarthScope GAGE) to
be initiated on first use.

`EnvVarTokenProvider` ships in v1, reading `EARTHSCOPE_TOKEN` (or a configurable env
var name per network). If no provider can supply a token, a hard error is raised with an
actionable message naming the missing env var and how to set it.

`EarthScopeSDKTokenProvider` is out of scope for v1.

**`DependencySpec` extension**
`Dependency` gains two new optional fields:
- `stations: list[str] | None` — explicit 4-char codes; center must be specified via the
  existing `constraints` dict (e.g. `constraints: {AAA: ERT}`)
- `station_spatial: SpatialFilter | None` — GeoJSON `Point` geometry + required `radius_km`
  field; date is taken from `ResolvePipeline.run(date=...)` at runtime. `BoundingBox` is
  not expressible in YAML (bbox remains available on the `StationQuery` builder API only).

Station dependencies must set `spec: RINEX_OBS`. A Pydantic validator enforces that a
`RINEX_OBS` dep has exactly one of `stations` or `station_spatial` set. A non-`RINEX_OBS`
dep with either field set raises a validation error at load time. `rinex_version` defaults
to `"3"` and can be overridden per-dependency.

`ResolvePipeline` dispatches on `dep.spec == "RINEX_OBS"` to route to `StationQuery`.
Center resolution order for station deps: `dep.constraints["AAA"]` → `run(centers=...)`
→ all registered networks. Lockfile entries for station deps follow the same per-file
keying as product deps (`product="RINEX_OBS"`, filename as key, `parameters` carries
`SSSS` and `V`). `LockfileWriter` is reused unchanged.

### Architectural decisions

- **No new top-level package.** Everything lives in `gnss-product-management`. A future
  `gnss-station-management` package could be spun off if the module grows, but that is
  out of scope.
- **No `NetworkHandler` class.** `NetworkHandler` is replaced by decorator-registered
  functions (`@registry.station_query`, `@registry.response_adapter`) on the
  `NetworkRegistry` instance, following the `ParameterCatalog.computed()` pattern.
  EarthScope-specific logic lives in a `register_network_handlers()` function called
  during `DefaultNetworkEnvironment` construction.
- **Networks and centers are separated.** Product centers (`configs/centers/`) and
  station networks (`configs/networks/`) are distinct config directories loaded by
  independent registries. `ProductRegistry` and `NetworkRegistry` are constructed
  independently by `GNSSClient`.
- **No GeoPandas / Shapely dependency.** `LocalIndexProtocol` uses pure haversine math
  for radius queries and coordinate comparisons for bbox. External geospatial libs are
  optional (an extras group `geo` may wrap Shapely for polygon support later).
- **`SpatialQueryProtocol` dispatch mirrors `ConnectionPool` dispatch.** Just as
  `ConnectionPool._connect()` dispatches on `Server.protocol`, `NetworkRegistry` maps
  the `spatial_protocol` field in a network YAML to a `SpatialQueryProtocol` instance.
  `StationQuery` is fully decoupled from how filtering is performed.
- **Local index building is always explicit.** `LocalIndexProtocol` raises if the CSV
  is absent — no silent fetching. The index is a tracked artifact managed by a separate
  `IndexBuilder` protocol, potentially committed to the repository.
- **Local index TTL is configurable per network.** `spatial_protocol_config.ttl_days`
  controls staleness warnings. `.refresh_index()` currently no-ops with a warning log,
  reserved for future cache invalidation across all protocol types.
- **`SearchPlanner` is extended for `RINEX_OBS`.** The registered station query
  function calls `StationQuery` to resolve station metadata, then produces `SearchTarget`
  objects that flow through the existing `SearchPlanner` → `WormHole` pipeline. No new
  download infrastructure is needed.
- **Auth is lazy and env-var-first.** `EnvVarTokenProvider` reads the env var name from
  the network YAML `credentials.token_env_var` field. Auth is triggered on first query
  call. Hard error with actionable message if the env var is unset.
  `EarthScopeSDKTokenProvider` is out of scope for v1.
- **EarthScope station metadata is sourced from the web services API**
  (`https://web-services.unavco.org/gsac/site`), not by scraping the RINEX directory.
  Response mapping is handled by a registered `EarthScopeResponseAdapter`. Fallback: a
  bundled station CSV in `gpm-specs/src/gpm_specs/configs/stations/earthscope_stations.csv`
  can be used if the API is unreachable (loaded via `LocalIndexProtocol`).
- **`FoundResource` is reused unchanged.** RINEX observation files returned by
  `StationQuery.search()` are `FoundResource` objects with `product="RINEX_OBS"` and
  a `parameters` dict that includes `SSSS` (station code) and `V` (RINEX version).
- **`StationQuery.download()` returns `list[FoundResource]`, not `list[Path]`.**
  This diverges intentionally from `ProductQuery.download()` to give the caller
  visibility into which center served each file after fallback resolution.

---

## Testing Decisions

A good test:
- Tests only externally observable behaviour (return values, raised exceptions, written
  files) — not internal implementation details or call counts on mocks.
- Is deterministic and does not require network access unless marked `integration`.
- Uses real `GNSSStation` / `SpatialFilter` / `StationQuery` instances rather than
  inspecting private state.

### Modules to test

**`ProductQuery` builder (pure unit)** ← written first as the model for `StationQuery` tests
Test that each chained method returns a new immutable instance and that state is set
correctly. Prior art: `test_infer_parameters.py`. These tests are in scope for this work.

**`SpatialFilter` (pure unit)**
Test that `PointRadius` and `BoundingBox` round-trip through Pydantic validation and that
invalid inputs (e.g. `radius_km <= 0`, `min_lat > max_lat`) raise `ValidationError`. No
mocks required. Geometry correctness (haversine, bbox containment) tested in
`RemoteSpatialAPIProtocol` unit tests.

**`StationQuery` builder (pure unit)**
Test that each chained method returns a new immutable instance and that state is set
correctly. Verify that calling `.metadata()` or `.search()` without a spatial filter or
`.from_stations()` raises a clear `ValueError`. Verify that `.from_stations()` without
`.centers()` raises at execution time. Mirrors `ProductQuery` builder tests written above.

**`RemoteSpatialAPIProtocol` (pure unit)**
Test `.query()` with a mocked HTTP response (using `responses` library) and a fixture URL
template. Verify correct `GNSSStation` mapping via a fixture `ResponseAdapter`. Test that
stations with missing required fields (`site_code`, `lat`, `lon`) are silently skipped.
Test boundary conditions (station exactly on radius edge via haversine). No live network.

**`NetworkRegistry` loading**
Test that a minimal network YAML fixture (real file in `configs/networks/`) is loaded
correctly. Test that an unknown `spatial_protocol` key raises an informative error. Test
that `spatial_protocol` defaults to `local_index` when omitted. Prior art:
`test_product_environment.py` — loads real bundled YAML fixtures.

**`CredentialStore` + `TokenProvider`**
Test that a registered credential function reads the correct env var and returns `None`
when unset. Test that `CredentialStore` tries registered providers in order. No real
tokens required.

**`EarthScopeResponseAdapter` (pure unit)**
Test that a mocked `web-services.unavco.org` JSON response is correctly mapped to
`list[GNSSStation]`. Test that records missing `site_code`, `lat`, or `lon` return `None`.
Test that missing optional fields (`start_date`, `end_date`) are tolerated. HTTP responses
mocked with `responses` library.

**`DependencySpec` extension (unit)**
Test that a YAML dep spec with `spec: RINEX_OBS` and `stations: [FAIR]` parses correctly.
Test that `RINEX_OBS` with both `stations` and `station_spatial` set raises a validation
error. Test that a non-`RINEX_OBS` dep with `stations` set raises a validation error.
Test that `rinex_version` defaults to `"3"`. Prior art: `test_lockfile.py`.

**`ResolvePipeline` with station dependencies (unit)**
Test that a `RINEX_OBS` dependency with `stations: [FAIR]` dispatches to the `StationQuery`
path and returns a `ResolvedDependency` with `status="downloaded"`. Test that center
resolution order is respected (`dep.constraints["AAA"]` → `run(centers=...)` → all
networks). Use a mocked `NetworkRegistry` returning a fixed `list[FoundResource]`.
Prior art: `test_dependency_resolution.py`.

**Not tested in v1:**
`LocalIndexProtocol` (deferred until used by a real network), `@registry.filesystem`
factory (deferred until EarthScope integration tests).

---

## Out of Scope

- **Polygon spatial queries** — only point+radius and bounding box in v1.
- **Station hardware metadata** — receiver type, antenna type, monument type, and site
  logs are not modelled. `GNSSStation` stores only code, coords, network, and
  availability window.
- **Real-time / NTRIP streams** — this PRD covers archived RINEX files only.
- **High-rate RINEX** (1 Hz) — only standard-rate daily/hourly files are in scope.
- **Campaign / non-continuous stations** — only continuously operating stations via
  the standard archive directory structure.
- **CORS (NOAA NGS) network integration** — identified as a future network; the decorator
  registration pattern makes it additive (new YAML + `register_network_handlers()` call),
  but the CORS implementation is not shipped in v1.
- **A new `gnssommelier` CLI sub-command for station search** — out of scope for this
  PRD; a `gnssommelier stations` command may follow in a separate PRD.
- **Position time-series or velocity products** — even though EarthScope GAGE hosts
  them, they are not station *observation* data and are not addressed here.

---

## Further Notes

- The EarthScope GAGE `data.earthscope.org` hostname is used for RINEX downloads (network
  ID `ERT`). The spatial metadata API at `web-services.unavco.org` is public and requires
  no auth. These are separate servers registered under the same network ID.
- The EarthScope web services metadata API base URL is
  `https://web-services.unavco.org/gsac/site`. The response format is JSON; the
  `EarthScopeResponseAdapter` should tolerate missing optional fields gracefully (some
  older campaign stations have incomplete records).
- A bundled station CSV fallback (for offline use) should be stored in
  `gpm-specs/src/gpm_specs/configs/stations/earthscope_stations.csv` and regenerated
  periodically by a dev script via the `IndexBuilder` protocol. The CSV is not
  auto-updated at query time.
- The `CredentialStore` should be configurable via the existing `gnssommelier` user
  config (`~/.config/gnssommelier/config.yaml`), specifically a `credentials:` block
  that maps network IDs to env var names or SDK token cache paths.
- Haversine distance calculation should use the WGS-84 mean Earth radius
  (6371.0088 km) and operate in double precision throughout.
