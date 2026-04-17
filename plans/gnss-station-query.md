# Plan: GNSS Station Network Query & RINEX Access

> Source PRD: [plans/prds/2026-04-15-gnss-station-query.md](prds/2026-04-15-gnss-station-query.md)

## Architectural decisions

Durable decisions that apply across all phases:

- **Key models**: `GNSSStation` (site_code, lat, lon, network_id?, start_date?, end_date?), `SpatialFilter` (discriminated union of `PointRadius` and `BoundingBox`), `SpatialQueryContext` (server, token, cache_dir)
- **Registry pattern**: `NetworkRegistry` loaded from `configs/networks/` YAML independently of `ProductRegistry`. Bundled into `NetworkEnvironment` alongside `CredentialStore`. Mirrors `DefaultProductEnvironment` singleton pattern.
- **Extension surface**: Four decorator registration points on `NetworkRegistry` instance — `@registry.station_query`, `@registry.response_adapter`, `@registry.credential`, `@registry.filesystem`. All EarthScope-specific logic registered in `register_network_handlers()`.
- **Query entry point**: `GNSSClient.station_query() -> StationQuery`, wired with `WormHole` + `SearchPlanner` + `NetworkEnvironment`. Same construction pattern as `ProductQuery`.
- **RINEX_OBS dispatch**: `ResolvePipeline` routes on `dep.spec == "RINEX_OBS"` to `StationQuery`. Center resolution order: `dep.constraints["AAA"]` → `run(centers=...)` → all registered networks.
- **Download return type**: `StationQuery.download()` returns `list[FoundResource]` (not `list[Path]`) to expose which center served each file after fallback. Intentional divergence from `ProductQuery.download()`.
- **Lockfile entries**: Station RINEX entries keyed by filename, `product="RINEX_OBS"`, `parameters` carries `SSSS` and `V`. `LockfileWriter` reused unchanged.
- **Auth**: Lazy, triggered on first query call. `EnvVarTokenProvider` reads env var name from network YAML `credentials[].env_var`. Hard error if unset.
- **No new top-level package**: Everything lives in `gnss-product-management` and `gpm-specs`.

---

## Phase 1: Foundational models + ProductQuery builder tests

**User stories**: 1, 2, 5, 6, 19

### What to build

Introduce the two pure data models — `GNSSStation` and `SpatialFilter` — and write
`ProductQuery` builder tests as the prior art that all `StationQuery` builder tests will
mirror.

`GNSSStation` is a Pydantic model with required fields `site_code`, `lat`, `lon` and
optional `network_id`, `start_date`, `end_date`. `None` end_date means active; `None`
start_date means unknown (included in temporal filters).

`SpatialFilter` is a discriminated union of `PointRadius(lat, lon, radius_km)` and
`BoundingBox(min_lat, min_lon, max_lat, max_lon)`. It is a pure data model — no query
logic.

`ProductQuery` builder tests verify the immutable-clone pattern: each chained call
returns a new instance, original is unchanged, state is set correctly.

### Acceptance criteria

- [ ] `GNSSStation` validates required fields; accepts `None` for optional fields
- [ ] `PointRadius` rejects `radius_km <= 0`; `BoundingBox` rejects `min_lat > max_lat`
- [ ] `SpatialFilter` round-trips through Pydantic validation for both shapes
- [ ] `ProductQuery` builder tests pass: each method returns a new immutable instance
- [ ] `ProductQuery` builder tests verify that chaining `.on(d1).on(d2)` uses `d2`
- [ ] All tests are pure unit — no network, no filesystem, no mocks

---

## Phase 2: NetworkRegistry + EarthScope spatial metadata

**User stories**: 1, 2, 4, 5, 6, 8, 12, 13, 14, 15, 16, 17, 18, 19, 20

### What to build

Wire up the full metadata query path end-to-end: network YAML loading, registry
construction, credential resolution, spatial protocol execution, response mapping, and
the `StationQuery` builder through to `.metadata()`.

`NetworkEnvironment` bundles `NetworkRegistry` + `CredentialStore`. `NetworkRegistry`
loads from `configs/networks/` YAML. `DefaultNetworkEnvironment` is built at import time
with EarthScope functions registered via `register_network_handlers()`.

`RemoteSpatialAPIProtocol` executes unauthenticated HTTP GETs against
`web-services.unavco.org/gsac/site` using a URL template from the network YAML.
`EarthScopeResponseAdapter` maps the JSON response to `list[GNSSStation]`, skipping
records missing required fields.

`StationQuery` builder exposes all chaining methods (`.within`, `.in_bbox`,
`.from_stations`, `.centers`, `.on`, `.rinex_version`, `.refresh_index`). `.metadata()`
raises `ValueError` if neither spatial filter nor `.from_stations()` is set; raises if
`.from_stations()` is set without `.centers()`.

`.metadata()` returns partial results + warning log if a center is unreachable.
`.refresh_index()` no-ops with a warning log on all protocol types.

`GNSSClient.station_query()` returns a fresh `StationQuery` wired to
`DefaultNetworkEnvironment`.

### Acceptance criteria

- [ ] `configs/networks/earthscope_network.yaml` loads into `NetworkRegistry` correctly
- [ ] Unknown `spatial_protocol` key in YAML raises an informative error at load time
- [ ] `EnvVarTokenProvider` returns token when env var is set; raises actionable error when unset
- [ ] `EarthScopeResponseAdapter` maps mocked JSON to `list[GNSSStation]`; skips records missing `site_code`/`lat`/`lon`; tolerates missing optional fields
- [ ] `StationQuery.metadata()` raises `ValueError` without spatial filter or `.from_stations()`
- [ ] `StationQuery.metadata()` raises `ValueError` when `.from_stations()` set without `.centers()`
- [ ] `.within().centers("ERT").on(date).metadata()` returns `list[GNSSStation]` (mocked HTTP via `responses`)
- [ ] `.metadata()` returns partial results + warning when one center is unreachable
- [ ] `.refresh_index()` logs a warning and returns the builder unchanged
- [ ] `StationQuery` builder tests mirror `ProductQuery` builder tests: immutable clone, correct state
- [ ] `GNSSClient.station_query()` returns a `StationQuery` bound to the default environment

---

## Phase 3: RINEX file search

**User stories**: 3, 7, 8

### What to build

Extend `SearchPlanner` with `search_stations()` and wire `StationQuery.search()` to
produce a ranked `list[FoundResource]`.

The EarthScope network YAML gains a `RINEX_OBS` product spec: v2 uses a full path
template (`archive/gnss/rinex/obs/{YYYY}/{DDD}/{SSSS}{ddd}0.{yy}o.Z`); v3 uses a
directory template (`archive/gnss/rinex3/obs/{YYYY}/{DDD}/`) and filename glob
(`{SSSS}*.rnx.gz`) resolved via directory listing.

`SearchPlanner.search_stations(stations, date, version)` iterates stations sequentially,
building one `SearchTarget` per station. Directory listing cache in
`ConnectionPoolFactory` prevents redundant network calls for the v3 glob case.

`ConnectionPool` accepts an optional fsspec filesystem instance at construction.
`@registry.filesystem("ERT")` registers a factory that constructs a filesystem with
`EARTHSCOPE_TOKEN` injected as a Bearer header and `?list` appended to directory listing
calls.

`StationQuery.search()` resolves stations via `.metadata()`, calls
`search_stations()`, executes the search, and returns results sorted by station code
ascending then RINEX version descending. Multi-center duplicates for the same station are
both retained as a ranked fallback chain.

### Acceptance criteria

- [ ] `SearchPlanner.search_stations()` returns one `SearchTarget` per station
- [ ] v2 `SearchTarget` directory + filename resolves to correct archive path
- [ ] v3 `SearchTarget` uses directory template + glob; filename resolved via directory listing
- [ ] `StationQuery.search()` requires `.on(date)` to be set; raises `ValueError` otherwise
- [ ] Results sorted: station code ascending, RINEX version descending
- [ ] Multi-center results for same station code are both present in output
- [ ] `@registry.filesystem("ERT")` factory is registered and callable with a dummy credential
- [ ] `.within(...).centers("ERT").on(date).search()` returns `list[FoundResource]` with `product="RINEX_OBS"` and `parameters["SSSS"]` set (mocked HTTP + mocked directory listing)

---

## Phase 4: Download with per-station fallback

**User stories**: 3, 7, 8, 12, 13

### What to build

Implement `StationQuery.download()` with auto-fallback across centers per station.

The sorted `list[FoundResource]` from `.search()` is treated as a ranked fallback chain
per station code. `.download()` iterates by station: tries entries in order, stops on
first successful download for that station, marks the rest as skipped. Returns
`list[FoundResource]` with `local_path` populated on the winner — giving the caller full
visibility into which center served each file.

### Acceptance criteria

- [ ] `.download()` returns `list[FoundResource]`, not `list[Path]`
- [ ] `local_path` is populated on the `FoundResource` that was successfully downloaded
- [ ] If the first center fails, the second center is tried automatically
- [ ] If all centers fail for a station, that station is absent from the return list (not raised)
- [ ] Successfully downloaded files exist on disk at `local_path`
- [ ] `.download()` on a multi-station query returns one winner per station

---

## Phase 5: DependencySpec + ResolvePipeline integration

**User stories**: 9, 10, 11

### What to build

Extend `Dependency` with `stations` and `station_spatial` fields and wire
`ResolvePipeline` to dispatch `RINEX_OBS` deps through `StationQuery`.

`Dependency` gains `stations: list[str] | None` and `station_spatial: SpatialFilter | None`.
Pydantic validators enforce: `spec == "RINEX_OBS"` when either field is set; exactly one
of `stations` or `station_spatial` is set on a `RINEX_OBS` dep; non-`RINEX_OBS` deps
with either field set raise at load time. `rinex_version` defaults to `"3"`.

`station_spatial` in YAML uses GeoJSON `Point` geometry + required `radius_km` field.
`BoundingBox` is not expressible in YAML.

`ResolvePipeline` dispatches on `dep.spec == "RINEX_OBS"`, builds a `StationQuery` with
the resolved center (from `dep.constraints["AAA"]` → `run(centers=...)` → all networks),
calls `.download()`, and writes lockfile entries via `LockfileWriter` unchanged.

### Acceptance criteria

- [ ] `Dependency` with `spec: RINEX_OBS` and `stations: [FAIR]` parses correctly from YAML
- [ ] `station_spatial` with GeoJSON `Point` + `radius_km` parses correctly from YAML
- [ ] `RINEX_OBS` dep with both `stations` and `station_spatial` raises `ValidationError`
- [ ] Non-`RINEX_OBS` dep with `stations` set raises `ValidationError`
- [ ] `rinex_version` defaults to `"3"` when not specified
- [ ] `ResolvePipeline.run()` dispatches `RINEX_OBS` to `StationQuery` path
- [ ] Center resolution order respected: `constraints["AAA"]` wins over `run(centers=...)`
- [ ] Lockfile entries for RINEX_OBS use filename as key, `product="RINEX_OBS"`, `parameters` carries `SSSS` and `V`
- [ ] `ResolvePipeline` fast-path (existing lockfile) still works for `RINEX_OBS` deps
