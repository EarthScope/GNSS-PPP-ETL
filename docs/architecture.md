# gnss-product-management: Layers & Abstractions

> Architecture blueprint for [`packages/gnss-product-management/src/gnss_product_management/`](../packages/gnss-product-management/src/gnss_product_management/)

---

## Application Boundaries

| Boundary | Direction | Modules | Operations |
|---|---|---|---|
| **Network** (FTP/FTPS) | Outbound | `server/ftp.py`, `ConnectionPoolFactory` | List directories, download files |
| **Network** (HTTP/HTTPS) | Outbound | `server/http.py`, `ConnectionPoolFactory` | List directories (HTML parsing), download files |
| **Filesystem** (bundled configs) | Read | `gnss-management-specs` package | Load YAML specs at startup |
| **Filesystem / Cloud** (user workspace) | Read/Write | `WorkSpace`, `LocalSearchPlanner`, `LockfileManager` | Search/store product files (local paths or `s3://` URIs) |
| **User input** | Inbound | `GNSSClient`, `ProductQuery` | Date, product name, constraints |

---

## Layer Definitions

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 4: INTERFACE                                          │
│  GNSSClient, ProductQuery — user-facing entry point          │
│  ProductRegistry, WorkSpace — environment setup              │
│  (client/, environments/)                                    │
├──────────────────────────────────────────────────────────────┤
│  Layer 3: ORCHESTRATION                                      │
│  SearchPlanner, LocalSearchPlanner, WormHole,                │
│  ConnectionPoolFactory, DependencyResolver, LockfileManager  │
│  Pipelines: FindPipeline, DownloadPipeline,                  │
│             LockfileWriter, ResolvePipeline                  │
│  (factories/)                                                │
├──────────────────────────────────────────────────────────────┤
│  Layer 2: CATALOG (Resolution + Registry)                    │
│  FormatCatalog, ProductCatalog, ResourceCatalog,             │
│  RemoteSearchPlanner, SourcePlanner (Protocol)               │
│  (specifications/format/, specifications/products/,          │
│   specifications/remote/, factories/remote_search_planner.py)│
├──────────────────────────────────────────────────────────────┤
│  Layer 1: SPECIFICATION (Data Models + YAML Loading)         │
│  ParameterCatalog, FormatSpec, ProductSpec, SearchTarget,    │
│  LocalResourceSpec, DependencySpec, LockProduct              │
│  (specifications/, lockfile/models.py)                       │
├──────────────────────────────────────────────────────────────┤
│  Layer 0: CONFIGURATION (Static Data + I/O Adapters)         │
│  Bundled YAML files, DirectoryAdapter implementations,       │
│  as_path(), hash_file(), decompress_gzip()                   │
│  (server/, utilities/, gnss-management-specs)                │
└──────────────────────────────────────────────────────────────┘
```

### Dependency Rule

Each layer may depend only on layers **below** it. No upward or lateral dependencies.

```
Layer 4 → Layer 3 → Layer 2 → Layer 1 → Layer 0
```

---

## Layer 0: Configuration (Static Data + I/O Adapters)

**Responsibility:** Provide static bundled data, path constants, protocol-level I/O, and shared utility functions. No business logic.

### Modules

| Module | Concern | Boundary |
|---|---|---|
| `gnss-management-specs` | Path constants (META_SPEC_YAML, etc.) and all bundled YAML files | Filesystem (package resources) |
| `server/protocol.py` | `DirectoryAdapter` Protocol interface | — |
| `server/ftp.py` | FTP/FTPS protocol adapter (`FTPAdapter`) | Network |
| `server/http.py` | HTTP/HTTPS protocol adapter (`HTTPAdapter`) | Network |
| `server/local.py` | Local filesystem adapter (`LocalAdapter`) | Filesystem |
| `utilities/helpers.py` | `hash_file`, `decompress_gzip`, `_PassthroughDict`, `_listify`, `expand_dict_combinations`, `_ensure_datetime` | — |
| `utilities/metadata_funcs.py` | Computed field registration (DDD, GPSWEEK, etc.) | — |
| `utilities/paths.py` | `as_path(uri) -> Path \| CloudPath`, `AnyPath` type alias | — |

### Abstractions

- **`DirectoryAdapter`** (`server/protocol.py`): `typing.Protocol` defining `can_connect()`, `list_directory()`, `download_file()`. Implemented by `FTPAdapter`, `HTTPAdapter`, `LocalAdapter`.
- **`as_path(uri)`** (`utilities/paths.py`): Single dispatch point for path construction. Returns `cloudpathlib.CloudPath` for `s3://`, `gs://`, `az://` URIs and `pathlib.Path` for everything else. All filesystem operations throughout the package flow through this helper.
- **`AnyPath`**: `Union[Path, CloudPath]` type alias used in signatures throughout layers 2–4.

### Key Rule
Layer 0 must not import from any other layer. Protocol adapters operate on primitive types (strings, paths), not domain models.

---

## Layer 1: Specification (Data Models + YAML Loading)

**Responsibility:** Define the domain vocabulary as Pydantic models. Load specifications from YAML. No resolution, no query logic, no I/O beyond YAML parsing.

### Modules & Key Abstractions

| Abstraction | Module | Description |
|---|---|---|
| `Parameter` | `specifications/parameters/parameter.py` | Single metadata field (name, value, pattern, derivation) |
| `ParameterCatalog` | `specifications/parameters/parameter.py` | Registry: parameter name → Parameter definition |
| `FormatFieldDef` | `specifications/format/spec.py` | Field definition within a format version |
| `FormatVersionSpec` | `specifications/format/spec.py` | A format version with metadata fields + file templates |
| `FormatSpec` | `specifications/format/spec.py` | Top-level format with versions |
| `FormatSpecCatalog` | `specifications/format/format_spec.py` | Loaded format specs from YAML |
| `FormatRegistry` | `specifications/format/format_catalog.py` | Read-only lookup of raw format specs |
| `Product` | `specifications/products/product.py` | Concrete product: name, parameters, directory/filename templates |
| `PathTemplate` | `specifications/products/product.py` | Template string with `{PARAM}` placeholders + resolved value |
| `VariantCatalog[T]` | `specifications/products/product.py` | Generic: variant name → T |
| `VersionCatalog[T]` | `specifications/products/product.py` | Generic: version name → VariantCatalog[T] |
| `ProductSpec` | `specifications/products/catalog.py` | Abstract binding: product name + format ref + parameter overrides |
| `ProductSpecCatalog` | `specifications/products/catalog.py` | Loaded product specs from YAML |
| `Server` | `specifications/remote/resource.py` | Server endpoint (hostname, protocol, auth) |
| `ResourceSpec` | `specifications/remote/resource.py` | Root center spec: servers + product offerings |
| `SearchTarget` | `specifications/remote/resource.py` | Concrete query target: product + server + directory + filename |
| `ResourceCatalog` | `specifications/remote/resource_catalog.py` | Resolved SearchTargets per center |
| `LocalCollection` | `specifications/local/local.py` | Group of product specs sharing a directory template |
| `LocalResourceSpec` | `specifications/local/local.py` | Root local storage spec |
| `Dependency` | `specifications/dependencies/dependencies.py` | Single product dependency (spec name, required, constraints) |
| `SearchPreference` | `specifications/dependencies/dependencies.py` | Sort preference for a dependency resolution pass |
| `DependencySpec` | `specifications/dependencies/dependencies.py` | Full dependency declaration for a processing task |
| `ResolvedDependency` | `specifications/dependencies/dependencies.py` | Resolution result (status, URI string, remote URL) |
| `DependencyResolution` | `specifications/dependencies/dependencies.py` | Aggregated results for all dependencies in a spec |
| `LockProduct` | `lockfile/models.py` | Per-file lock entry (hash, size, source URL, sink URI) |
| `DependencyLockFile` | `lockfile/models.py` | Aggregate lockfile for one processing day |

### Interfaces

Each spec type exposes a `from_yaml(path) -> Self` classmethod for loading. All models are Pydantic `BaseModel` subclasses.

`ResolvedDependency.local_path` is a `str` URI — pass it through `as_path()` to get a filesystem object for I/O.

### Key Rule
Layer 1 models are **declarative data**. They define *what exists*, not how to build or query it.

---

## Layer 2: Catalog (Resolution + Registry)

**Responsibility:** Transform abstract specifications into concrete, queryable objects. Maintain registries for lookup. This is where specs *become* usable products.

### Modules & Key Abstractions

| Abstraction | Module | Input → Output |
|---|---|---|
| `Catalog` (ABC) | `specifications/catalog.py` | Base class enforcing `@classmethod resolve()` on all catalogs |
| `SourcePlanner` (Protocol) | `factories/source_planner.py` | Shared interface: `resource_ids`, `source_product()` |
| `FormatCatalog` | `specifications/format/format_spec.py` | FormatSpecCatalog + ParameterCatalog → resolved Products per format/version/variant |
| `ProductCatalog` | `specifications/products/catalog.py` | ProductSpecCatalog + FormatCatalog → resolved Products per product/version/variant |
| `ResourceCatalog` | `specifications/remote/resource_catalog.py` | ResourceSpec + ProductCatalog → expanded SearchTarget list |
| `RemoteSearchPlanner` | `factories/remote_search_planner.py` | Registry of ResourceCatalogs per center; satisfies `SourcePlanner` |

### Resolution Chain

```
ParameterCatalog ──┐
                   ├──► FormatCatalog ──► ProductCatalog ──┬──► RemoteSearchPlanner
FormatSpecCatalog ─┘    ProductSpecCatalog ─┘              │        ↑ ResourceSpec[]
                                                           └──► LocalSearchPlanner
                                                                    ↑ LocalResourceSpec[]
```

### Interfaces

- `FormatCatalog.resolve(format_spec_catalog, parameter_catalog) -> FormatCatalog`
- `ProductCatalog.resolve(product_spec_catalog, format_catalog) -> ProductCatalog`
- `ResourceCatalog.resolve(resource_spec, product_catalog) -> ResourceCatalog`

Both `RemoteSearchPlanner` and `LocalSearchPlanner` satisfy the `SourcePlanner` Protocol:
- `resource_ids -> List[str]`
- `source_product(product, resource_id) -> List[SearchTarget]`

### Key Rule
Catalogs are **immutable after construction**. Resolution happens once; the result is cached as data. No network I/O, no filesystem writes.

---

## Layer 3: Orchestration (Query Building + Transport + Resolution)

**Responsibility:** Combine catalogs with user constraints to build, execute, and resolve queries. Touches external boundaries (network, filesystem, cloud storage).

### Modules & Key Abstractions

| Abstraction | Module | Responsibility |
|---|---|---|
| `SearchPlanner` | `factories/search_planner.py` | Date + product + constraints → `List[SearchTarget]` |
| `LocalSearchPlanner` | `factories/local_search_planner.py` | Local/cloud file search, sink resolution, lockfile directory |
| `WormHole` | `factories/remote_transport.py` | Directory listing + filename matching + file download |
| `ConnectionPoolFactory` | `factories/connection_pool.py` | fsspec-backed connection pools per host (FTP, FTPS, HTTP, HTTPS, file) |
| `DependencyResolver` | `factories/dependency_resolver.py` | Two-phase local+remote resolution with preference cascade |
| `LockfileManager` | `lockfile/manager.py` | Lockfile lifecycle: check, load, save, import/export |
| `FindPipeline` | `factories/pipelines/find.py` | Pipeline: search → ranked SearchResult list |
| `DownloadPipeline` | `factories/pipelines/download.py` | Pipeline: SearchResult → downloaded local/cloud path |
| `LockfileWriter` | `factories/pipelines/lockfile_writer.py` | Pipeline: write sidecar + aggregate lockfiles |
| `ResolvePipeline` | `factories/pipelines/resolve.py` | Pipeline: DependencySpec → DependencyResolution + lockfile |

### Data Flow

```
User constraints (date, product, parameters...)
        │
        ▼
   SearchPlanner
   ├── Resolve product templates (ProductCatalog)
   ├── Compute date fields (ParameterCatalog)
   ├── Narrow parameters (user constraints)
   ├── Expand combinations (cartesian product)
   ├── Local targets (LocalSearchPlanner.source_product)
   └── Remote targets (RemoteSearchPlanner.source_product)
        │
        ▼
   List[SearchTarget]  (directory pattern + filename pattern)
        │
        ▼
   WormHole
   ├── Group by (hostname, directory)
   ├── List directories in parallel (ConnectionPoolFactory)
   ├── Match filename patterns (regex)
   └── Optionally download (ConnectionPoolFactory.download_file)
        │
        ▼
   List[SearchTarget]  (filename.value populated)
```

### Cloud / Local Filesystem Transparency

`LocalSearchPlanner` and `LockfileManager` accept base directories as URI strings, dispatched through `as_path()`:

- Local path: `/data/gnss` → `pathlib.Path`
- S3 URI: `s3://bucket/gnss` → `cloudpathlib.S3Path`

All path operations (`.exists()`, `.iterdir()`, `.read_text()`, `.write_text()`, `.mkdir()`, `/` operator) are identical across backends. The `LockfileManager` stores aggregate lockfiles at the resource's `base_dir / "dependency_lockfiles"`, enabling distributed workers to coordinate via shared cloud storage.

### Interfaces

- `SearchPlanner.get(date, product, parameters, ...) -> List[SearchTarget]`
- `WormHole.search(List[SearchTarget]) -> List[SearchTarget]`  (one per matched file)
- `WormHole.download_one(query, local_resource_id, local_factory, date) -> AnyPath | None`
- `LocalSearchPlanner.find_local_files(query, date) -> List[AnyPath]`
- `LocalSearchPlanner.lockfile_dir(resource_id) -> AnyPath`
- `DependencyResolver.resolve(date, local_sink_id) -> Tuple[DependencyResolution, AnyPath | None]`
- `LockfileManager(lockfile_dir: str | Path | CloudPath)` — storage-agnostic

### Key Rule
Orchestration modules coordinate between catalogs and I/O adapters. They **do not define** domain models — they consume them. Network/filesystem operations are delegated to Layer 0 adapters or `cloudpathlib`.

---

## Layer 4: Interface (Entry Point)

**Responsibility:** Provide user-facing APIs that wire all layers together. Hide internal complexity behind clean, fluent interfaces.

### Modules & Key Abstractions

| Abstraction | Module | Responsibility |
|---|---|---|
| `GNSSClient` | `client/gnss_client.py` | Primary entry point: search, download, resolve dependencies |
| `ProductQuery` | `client/product_query.py` | Fluent query builder (`.on()`, `.where()`, `.sources()`, `.prefer()`) |
| `SearchResult` | `client/search_result.py` | User-facing search result (hostname, filename, parameters, local_path) |
| `ProductRegistry` | `environments/environment.py` | Loads YAML specs, builds catalog chain, holds `RemoteSearchPlanner` |
| `WorkSpace` | `environments/workspace.py` | Registers local/cloud storage directories against `LocalResourceSpec` layouts |
| `RegisteredLocalResource` | `environments/workspace.py` | Bound spec + `base_dir` URI (local path or cloud URI) + `base_path` property |

### Interfaces

```python
# Construct from bundled defaults
client = GNSSClient.from_defaults(base_dir="/data/gnss")          # local
client = GNSSClient.from_defaults(base_dir="s3://bucket/gnss")   # S3

# Fluent query builder
results = (
    client.query("ORBIT")
          .on(date)
          .where(TTT="FIN")
          .sources("COD", "WUM")
          .prefer(TTT=["FIN", "RAP"])
          .search()
)

# Download
paths = client.download(results, sink_id="local", date=date)

# Full dependency resolution
resolution, lockfile_path = client.resolve_dependencies(dep_spec, date, sink_id="local")
```

For advanced use, construct manually:

```python
registry = ProductRegistry()
registry.add_parameter_spec(META_SPEC_YAML)
registry.add_format_spec(FORMAT_SPEC_YAML)
registry.add_product_spec(PRODUCT_SPEC_YAML)
registry.add_resource_spec(center_yaml)
registry.build()

workspace = WorkSpace()
workspace.add_resource_spec(local_spec_yaml)
workspace.register_spec(base_dir="s3://my-bucket/gnss", spec_ids=["local_config"])

client = GNSSClient(env=registry, workspace=workspace)
```

### Key Rule
All standard user code should interact through `GNSSClient` or `ProductQuery`. `ProductRegistry` and `WorkSpace` are setup objects; the pipelines and planners are internal implementation details.

---

## Abstraction Inventory by Layer

```
Layer 0 (Configuration)         Layer 1 (Specification)
─────────────────────           ───────────────────────
DirectoryAdapter (Protocol)     Parameter
FTPAdapter                      ParameterCatalog
HTTPAdapter                     FormatFieldDef
LocalAdapter                    FormatVersionSpec
as_path() / AnyPath             FormatSpec
hash_file()                     FormatSpecCatalog
decompress_gzip()               FormatRegistry
_ensure_datetime()              Product
register_computed_fields()      PathTemplate
gnss-management-specs YAMLs     VariantCatalog[T]
                                VersionCatalog[T]
                                ProductSpec
                                ProductSpecCatalog
                                Server
                                ResourceSpec
                                SearchTarget
                                ResourceCatalog
                                LocalCollection
                                LocalResourceSpec
                                Dependency
                                SearchPreference
                                DependencySpec
                                ResolvedDependency
                                DependencyResolution
                                LockProduct
                                DependencyLockFile

Layer 2 (Catalog)               Layer 3 (Orchestration)
─────────────────               ───────────────────────
Catalog (ABC base)              SearchPlanner
SourcePlanner (Protocol)        LocalSearchPlanner
FormatCatalog                   WormHole
ProductCatalog                  ConnectionPoolFactory
RemoteSearchPlanner             DependencyResolver
                                LockfileManager
                                FindPipeline
                                DownloadPipeline
                                LockfileWriter
                                ResolvePipeline

Layer 4 (Interface)
───────────────────
GNSSClient
ProductQuery
SearchResult
ProductRegistry
WorkSpace
RegisteredLocalResource
```

---

## Summary

| Layer | Purpose | Depends On | Boundary |
|---|---|---|---|
| 0 — Configuration | Static data, I/O adapters, path utilities | Nothing | Filesystem, Network, Cloud |
| 1 — Specification | Domain models, YAML loading | Layer 0 | Filesystem (YAML reads) |
| 2 — Catalog | Resolve specs → concrete objects, registries | Layer 1 | None (pure computation) |
| 3 — Orchestration | Build queries, execute fetches, resolve deps, manage lockfiles | Layers 0, 1, 2 | Network, Filesystem, Cloud |
| 4 — Interface | User-facing API, environment wiring | Layers 1, 2, 3 | User input |
