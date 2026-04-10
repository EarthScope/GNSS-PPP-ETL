# Class Reference — gnss-product-management

Every class, dataclass, Protocol, NamedTuple, Enum, and Exception in the package,
grouped by architectural layer.

---

## Layer 0 — Configuration & Utilities

Layer 0 contains no standalone classes — only module-level helpers and bundled YAML data. Low-level network I/O is handled at Layer 3 by `ConnectionPoolFactory` (via `fsspec`). See [Layer 6 — Utilities](#layer-6--utilities) for the utility classes (`_PassthroughDict`, `IGSAntexReferenceFrameType`) and [Layer 3 — Factories, Planners & Transport](#layer-3--factories-planners--transport) for `ConnectionPool` / `ConnectionPoolFactory`.

---

## Layer 1 — Specifications (Data Models)

Immutable data models parsed from YAML. Everything here is a Pydantic `BaseModel`
unless noted otherwise.

### Parameters

| Class | File | Base | Key Fields |
|---|---|---|---|
| `DerivationMethod` | `specifications/parameters/parameter.py` | `str, Enum` | `ENUM`, `COMPUTED` |
| `Parameter` | `specifications/parameters/parameter.py` | `BaseModel` | `name`, `value`, `pattern`, `derivation`, `compute` |
| `ParameterCatalog` | `specifications/parameters/parameter.py` | — | `parameters: Dict[str, Parameter]` |

### Formats

| Class | File | Base | Key Fields |
|---|---|---|---|
| `FormatFieldDef` | `specifications/format/spec.py` | `BaseModel` | `pattern`, `default`, `description` |
| `FormatVersionSpec` | `specifications/format/spec.py` | `BaseModel` | `description`, `notes`, `metadata`, `file_templates`, `compression` |
| `FormatSpec` (raw) | `specifications/format/spec.py` | `BaseModel` | `description`, `versions`, `compression` |
| `FormatSpecCollection` | `specifications/format/spec.py` | `BaseModel` | `formats: Dict[str, FormatSpec]` |
| `FormatSpec` (resolved) | `specifications/format/format_spec.py` | `BaseModel` | `name`, `version`, `variant`, `parameters`, `filename` |
| `FormatSpecCatalog` | `specifications/format/format_spec.py` | `BaseModel` | `formats: dict[str, VersionCatalog[FormatSpec]]` |
| `FormatCatalog` | `specifications/format/format_spec.py` | `Catalog` | `formats: dict[str, VersionCatalog[Product]]` |
| `FormatRegistry` | `specifications/format/spec.py` | `BaseModel` | `formats: Dict[str, FormatSpec]` (reusable definitions) |

### Products

| Class | File | Base | Key Fields |
|---|---|---|---|
| `PathTemplate` | `specifications/products/product.py` | `BaseModel` | `pattern`, `value`, `description` |
| `Product` | `specifications/products/product.py` | `BaseModel` | `name`, `parameters: List[Parameter]`, `filename: PathTemplate` |
| `VariantCatalog[T]` | `specifications/products/product.py` | `BaseModel, Generic[T]` | `variants: Dict[str, T]` |
| `VersionCatalog[T]` | `specifications/products/product.py` | `BaseModel, Generic[T]` | `versions: Dict[str, T]` |
| `ProductSpec` | `specifications/products/catalog.py` | `BaseModel` | `name`, `format`, `version`, `variant`, `parameters`, `filename` |
| `ProductSpecCatalog` | `specifications/products/catalog.py` | `BaseModel` | `products: dict[str, VersionCatalog[ProductSpec]]` |
| `ProductCatalog` | `specifications/products/catalog.py` | `Catalog` | `products: dict[str, VersionCatalog[Product]]` |

### Remote Resources

| Class | File | Base | Key Fields |
|---|---|---|---|
| `Server` | `specifications/remote/resource.py` | `BaseModel` | `id`, `hostname`, `protocol`, `auth_required` |
| `ResourceProductSpec` | `specifications/remote/resource.py` | `BaseModel` | `id`, `server_id`, `product_name`, `product_version`, `parameters`, `directory` |
| `ResourceSpec` | `specifications/remote/resource.py` | `BaseModel` | `id`, `name`, `servers: List[Server]`, `products: List[ResourceProductSpec]` |
| `SearchTarget` | `specifications/remote/resource.py` | `BaseModel` | `product: Product`, `server: Server`, `directory: PathTemplate` |
| `ResourceCatalog` | `specifications/remote/resource_catalog.py` | `Catalog` | `id`, `name`, `servers`, `queries: List[SearchTarget]` |

### Local Resources

| Class | File | Base | Key Fields |
|---|---|---|---|
| `LocalCollection` | `specifications/local/local.py` | `BaseModel` | `directory`, `description`, `items` |
| `LocalResourceSpec` | `specifications/local/local.py` | `BaseModel` | `name`, `description`, `collections: List[LocalCollection]` |

### Dependencies

| Class | File | Base | Key Fields |
|---|---|---|---|
| `SearchPreference` | `specifications/dependencies/dependencies.py` | `BaseModel` | `parameter`, `sorting`, `description` |
| `Dependency` | `specifications/dependencies/dependencies.py` | `BaseModel` | `spec`, `required`, `constraints: Dict[str, str]` |
| `DependencySpec` | `specifications/dependencies/dependencies.py` | `BaseModel` | `name`, `preferences`, `dependencies`, `package`, `task` |
| `ResolvedDependency` | `specifications/dependencies/dependencies.py` | `BaseModel` | `spec`, `required`, `status`, `local_path`, `remote_url` |
| `DependencyResolution` | `specifications/dependencies/dependencies.py` | `@dataclass` | `spec_name`, `resolved: List[ResolvedDependency]` |

### Abstract Base

| Class | File | Base | Key Fields |
|---|---|---|---|
| `Catalog` | `specifications/catalog.py` | `BaseModel` | Abstract `build()` classmethod — base for all resolved catalogs |

### Relationships

```
Catalog (abstract BaseModel)
 ├── FormatCatalog
 ├── ProductCatalog
 └── ResourceCatalog

Parameter ──used-by──► PathTemplate
Parameter ──used-by──► Product
Parameter ──used-by──► FormatSpec
Parameter ──used-by──► ResourceProductSpec

PathTemplate ──field-of──► Product
PathTemplate ──field-of──► SearchTarget (directory)

Product ──field-of──► SearchTarget
Server  ──field-of──► SearchTarget

VersionCatalog[T] / VariantCatalog[T]
 └── wraps FormatSpec, ProductSpec, Product

FormatSpec ──resolved-into──► Product (via FormatCatalog.build)
ProductSpec ──resolved-into──► Product (via ProductCatalog.build)
ResourceSpec ──resolved-into──► ResourceCatalog (queries: List[SearchTarget])

SearchPreference ──used-by──► DependencySpec
Dependency ──used-by──► DependencySpec
ResolvedDependency ──used-by──► DependencyResolution
```

---

## Layer 2 — Environments & Registry

Load YAML specs, build catalogs, and register local storage layouts.

| Class | File | Base | Key Fields |
|---|---|---|---|
| `_MatchEntry` | `environments/environment.py` | `NamedTuple` | `template_len`, `compiled_regex`, `product_name`, `format_name`, `version`, `variant`, `fixed_params` |
| `LoadedSpecs` | `environments/environment.py` | `BaseModel` | Holds raw spec models before catalog build |
| `ProductRegistry` | `environments/environment.py` | — | Central registry: loads YAML → builds `FormatCatalog`, `ProductCatalog`, `ParameterCatalog`, `ResourceCatalog` objects; satisfies `SourcePlanner` Protocol for remote queries |
| `RegisteredLocalResource` | `environments/workspace.py` | `BaseModel` | `name`, `base_dir`, `spec: LocalResourceSpec`, `server: Server` |
| `WorkSpace` | `environments/workspace.py` | — | Registry of local storage directories and layout specs |

### Relationships

```
ProductRegistry  (implements SourcePlanner Protocol — remote resources)
 ├── owns FormatCatalog
 ├── owns ProductCatalog
 ├── owns ParameterCatalog
 └── owns ResourceCatalog[] (built from ResourceSpec files)

WorkSpace  (implements SourcePlanner Protocol — local resources)
 └── owns RegisteredLocalResource[]
      ├── references LocalResourceSpec
      └── references Server
```

---

## Layer 3 — Factories, Planners & Transport

Query construction, remote search, download, ranking, and dependency resolution.

### Protocols

| Class | File | Base | Description |
|---|---|---|---|
| `SourcePlanner` | `factories/source_planner.py` | `Protocol` | Common interface: `resource_ids`, `source_product()`, `sink_product()`, `register()` |

### Connection Management

| Class | File | Base | Key Fields |
|---|---|---|---|
| `ConnectionPool` | `factories/connection_pool.py` | — | `hostname`, `protocol`, `max_connections`, `_pool`, `_semaphore` |
| `ConnectionPoolFactory` | `factories/connection_pool.py` | — | `_pools: Dict[str, ConnectionPool]` |

### Search Planners

| Class | File | Base | Key Fields |
|---|---|---|---|
| `SearchPlanner` | `factories/search_planner.py` | — | `_product_registry: ProductRegistry`, `_workspace: WorkSpace` |

`SearchPlanner` delegates remote lookups to `ProductRegistry` and local lookups to `WorkSpace` — both satisfy the `SourcePlanner` Protocol (`resource_ids`, `source_product()`, `sink_product()`).

### Transport

| Class | File | Base | Key Fields |
|---|---|---|---|
| `WormHole` | `factories/remote_transport.py` | — | `_connection_pool_factory: ConnectionPoolFactory`, `_env: ProductRegistry` |

### Dependency Resolution

Dependency resolution is handled by `ResolvePipeline` (see Pipelines below). There is no separate `DependencyResolver` class.

### Models & Exceptions

| Class | File | Base | Key Fields |
|---|---|---|---|
| `FoundResource` | `factories/models.py` | `BaseModel` | `product`, `source`, `uri`, `center`, `quality`, `parameters`, `_query` (private) |
| `Resolution` | `factories/models.py` | `BaseModel` | `task`, `paths: List[Path]`, `lockfile` |
| `DiscoveryEntry` | `factories/models.py` | `BaseModel` | `product`, `center`, `quality`, `source`, `uri` |
| `DiscoveryReport` | `factories/models.py` | `BaseModel` | `entries: List[DiscoveryEntry]` |
| `MissingProductError` | `factories/models.py` | `Exception` | `missing: List[str]`, `task: str` |

### Pipelines

| Class | File | Base | Key Fields |
|---|---|---|---|
| `DownloadPipeline` | `factories/pipelines/download.py` | — | `_planner: SearchPlanner`, `_transport: WormHole` |
| `LockfileWriter` | `factories/pipelines/lockfile_writer.py` | — | `_manager: LockfileManager`, `_package: str` |
| `ResolvePipeline` | `factories/pipelines/resolve.py` | — | `_query: ProductQuery`, `_downloader: DownloadPipeline` |

### Ranking (module-level functions, no classes)

| Function | File | Signature |
|---|---|---|
| `sort_by_protocol` | `factories/ranking.py` | `(targets: List[SearchTarget]) -> List[SearchTarget]` |
| `sort_by_preferences` | `factories/ranking.py` | `(targets, preferences) -> List[SearchTarget]` |

### Relationships

```
SourcePlanner (Protocol)
 ├── ProductRegistry  implements SourcePlanner (remote resources)
 └── WorkSpace        implements SourcePlanner (local resources)

SearchPlanner
 ├── uses ProductRegistry (_product_registry) — remote resource_ids / source_product
 └── uses WorkSpace (_workspace)              — local resource_ids / source_product

WormHole
 ├── owns ConnectionPoolFactory
 ├── reads SearchTarget[]  → search()       → SearchTarget[] (expanded)
 └── reads SearchTarget    → download_one() → Path

DownloadPipeline
 ├── owns SearchPlanner
 ├── owns WormHole
 ├── reads FoundResource._query → WormHole.download_one()
 └── produces Path

LockfileWriter
 ├── owns LockfileManager
 ├── reads DependencyResolution
 └── produces Path (lockfile)

ResolvePipeline
 ├── owns ProductQuery  (_query)
 ├── owns DownloadPipeline
 ├── calls ranking.sort_by_protocol / sort_by_preferences (via ProductQuery)
 ├── reads DependencySpec
 └── produces (DependencyResolution, Path)
```

---

## Layer 4 — Client API

High-level entry points consumed by application code.

| Class | File | Base | Key Fields |
|---|---|---|---|
| `GNSSClient` | `client/gnss_client.py` | — | `_env: ProductRegistry`, `_qf: SearchPlanner`, `_fetcher: WormHole` |
| `ProductQuery` | `client/product_query.py` | — | `_fetcher: WormHole`, `_qf: SearchPlanner`, `_product`, `_date`, `_parameters`, `_source_ids`, `_preferences` |

Search results are returned as `FoundResource` objects (see Layer 3 — Models & Exceptions).

### Relationships

```
GNSSClient
 ├── owns ProductRegistry
 ├── owns SearchPlanner
 ├── owns WormHole
 ├── creates ProductQuery (fluent builder)
 ├── delegates to ResolvePipeline (dependency resolution)
 └── produces FoundResource[], DependencyResolution

ProductQuery (fluent builder)
 ├── uses WormHole
 ├── uses SearchPlanner
 └── produces FoundResource[]
```

---

## Layer 5 — Lockfile Management

Persist reproducible product manifests as JSON sidecar files.

| Class | File | Base | Key Fields |
|---|---|---|---|
| `LockProductAlternative` | `lockfile/models.py` | `BaseModel` | `url` |
| `LockProduct` | `lockfile/models.py` | `BaseModel` | `name`, `timestamp`, `url`, `hash`, `size`, `sink`, `alternatives` |
| `DependencyLockFile` | `lockfile/models.py` | `BaseModel` | `date`, `package`, `task`, `version`, `products: List[LockProduct]` |
| `HashMismatchMode` | `lockfile/operations.py` | `Enum` | `WARN`, `STRICT` |
| `LockfileManager` | `lockfile/manager.py` | — | `_dir: Path` — facade for load/save/build operations |

### Relationships

```
DependencyLockFile
 └── contains LockProduct[]
      └── contains LockProductAlternative[]

LockfileManager
 ├── reads/writes DependencyLockFile
 ├── uses LockProduct
 └── uses HashMismatchMode (via operations)
```

---

## Layer 6 — Utilities

| Class | File | Base | Description |
|---|---|---|---|
| `_PassthroughDict` | `utilities/helpers.py` | `dict` | Returns `'{key}'` for missing keys (used in template formatting) |
| `IGSAntexReferenceFrameType` | `utilities/metadata_funcs.py` | `Enum` | IGS ANTEX reference frame identifiers (`IGS05`, `IGS08`, …) |

---

## Module-Level Singletons

| Name | File | Type | Description |
|---|---|---|---|
| `DefaultProductEnvironment` | `defaults/__init__.py` | `ProductRegistry` | Pre-configured registry built from bundled YAML |
| `DefaultWorkSpace` | `defaults/__init__.py` | `WorkSpace` | Pre-configured workspace built from bundled YAML |

---

## Full Dependency Graph (simplified)

```
┌─────────────────────────────────────────────────────────────────┐
│  Client API                                                     │
│  GNSSClient ──► ProductQuery ──► FoundResource[]                │
└──────┬──────────────────────────────────────────────────────────┘
       │ uses
┌──────▼──────────────────────────────────────────────────────────┐
│  Pipelines                                                      │
│  ResolvePipeline ──► ProductQuery ──► DownloadPipeline          │
│                  └──► LockfileWriter                            │
└──────┬──────────────────────────────────────────────────────────┘
       │ uses
┌──────▼──────────────────────────────────────────────────────────┐
│  Factories                                                      │
│  SearchPlanner ──► ProductRegistry (remote, via SourcePlanner)  │
│                └──► WorkSpace (local, via SourcePlanner)        │
│  WormHole ──► ConnectionPoolFactory ──► ConnectionPool          │
│  ranking.sort_by_protocol / sort_by_preferences                 │
└──────┬──────────────────────────────────────────────────────────┘
       │ uses
┌──────▼──────────────────────────────────────────────────────────┐
│  Environments                                                   │
│  ProductRegistry ──► builds catalogs from specs                 │
│  WorkSpace ──► RegisteredLocalResource[]                        │
└──────┬──────────────────────────────────────────────────────────┘
       │ uses
┌──────▼──────────────────────────────────────────────────────────┐
│  Specifications (BaseModel data layer)                          │
│  Parameter, PathTemplate, Product, Server, SearchTarget         │
│  FormatCatalog, ProductCatalog, ResourceCatalog                 │
│  DependencySpec, DependencyResolution, SearchPreference         │
│  LocalResourceSpec, LocalCollection                             │
└──────┬──────────────────────────────────────────────────────────┘
       │ uses
┌──────▼──────────────────────────────────────────────────────────┐
│  Utilities / Configuration (Layer 0)                            │
│  as_path(), hash_file(), decompress_gzip(), bundled YAMLs       │
└─────────────────────────────────────────────────────────────────┘

  Lockfile Management (cross-cutting)
  LockfileManager ──► DependencyLockFile ──► LockProduct
```
