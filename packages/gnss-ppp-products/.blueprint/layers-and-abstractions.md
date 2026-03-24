# gnss-ppp-products: Layers & Abstractions

> Architecture blueprint for `packages/gnss-ppp-products/src/gnss_ppp_products/`

---

## Application Boundaries

| Boundary | Direction | Modules | Operations |
|---|---|---|---|
| **Network** (FTP/FTPS) | Outbound | `server/ftp.py` | List directories, download files |
| **Network** (HTTP/HTTPS) | Outbound | `server/http.py` | List directories (HTML parsing), download files |
| **Filesystem** (bundled configs) | Read | `configs/` | Load YAML specs at startup |
| **Filesystem** (user workspace) | Read/Write | `LocalResourceFactory`, `DependencyResolver` | Search/store product files |
| **User input** | Inbound | `ProductEnvironment`, `QueryFactory`, `DependencyResolver` | Date, product name, constraints |

---

## Layer Definitions

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 4: INTERFACE                                          │
│  ProductEnvironment — unified entry point                    │
│  (factories/environment.py, factories/models.py)             │
├──────────────────────────────────────────────────────────────┤
│  Layer 3: ORCHESTRATION                                      │
│  QueryFactory, DependencyResolver, ResourceFetcher           │
│  (factories/query_factory.py, resource_fetcher.py,           │
│   specifications/dependencies/dependency_resolver.py)        │
├──────────────────────────────────────────────────────────────┤
│  Layer 2: CATALOG (Resolution + Registry)                    │
│  FormatCatalog, ProductCatalog, ResourceCatalog,             │
│  RemoteResourceFactory, LocalResourceFactory                 │
│  (specifications/format/format_spec.py,                      │
│   specifications/products/catalog.py,                        │
│   specifications/remote/resource.py,                         │
│   factories/remote_factory.py,                               │
│   specifications/local/factory.py)                           │
├──────────────────────────────────────────────────────────────┤
│  Layer 1: SPECIFICATION (Data Models + YAML Loading)         │
│  ParameterCatalog, FormatSpec, ProductSpec, ResourceSpec,     │
│  LocalResourceSpec, DependencySpec, AxisDef                  │
│  (specifications/parameters/, specifications/format/spec.py, │
│   specifications/products/product.py,                        │
│   specifications/remote/resource.py,                         │
│   specifications/local/local.py,                             │
│   specifications/dependencies/dependencies.py,               │
│   specifications/queries/query.py)                           │
├──────────────────────────────────────────────────────────────┤
│  Layer 0: CONFIGURATION (Static Data + I/O Adapters)         │
│  Bundled YAML files, path constants, protocol handlers       │
│  (configs/, server/ftp.py, server/http.py,                   │
│   utilities/helpers.py, utilities/metadata_funcs.py)         │
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
| `configs/__init__.py` | Path constants (META_SPEC_YAML, PRODUCT_SPEC_YAML, etc.) | Filesystem (package resources) |
| `configs/meta/` | Parameter definitions YAML | — |
| `configs/products/` | Format + product spec YAML | — |
| `configs/centers/` | Remote center spec YAML | — |
| `configs/local/` | Local storage spec YAML | — |
| `configs/dependencies/` | Dependency spec YAML | — |
| `configs/query/` | Query axis spec YAML | — |
| `server/protocol.py` | `DirectoryAdapter` Protocol interface | — |
| `server/ftp.py` | FTP/FTPS protocol adapter + `FTPAdapter` | Network |
| `server/http.py` | HTTP/HTTPS protocol adapter + `HTTPAdapter` | Network |
| `server/local.py` | Local filesystem adapter + `LocalAdapter` | Filesystem |
| `utilities/helpers.py` | `_PassthroughDict`, `_listify`, `expand_dict_combinations` | — |
| `utilities/metadata_funcs.py` | Computed field registration (DDD, GPSWEEK, etc.) | — |

### Abstractions

- **DirectoryAdapter** (`server/protocol.py`): `typing.Protocol` defining `can_connect()`, `list_directory()`, `download_file()`. Implemented by `FTPAdapter`, `HTTPAdapter`, `LocalAdapter`.
- **Config Paths**: Constants provide stable entry points for YAML loading.

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
| `ProductPath` | `specifications/products/product.py` | Template string with `{PARAM}` placeholders |
| `VariantCatalog[T]` | `specifications/products/product.py` | Generic: variant name → T |
| `VersionCatalog[T]` | `specifications/products/product.py` | Generic: version name → VariantCatalog[T] |
| `ProductSpec` | `specifications/products/catalog.py` | Abstract binding: product name + format ref + parameter overrides |
| `ProductSpecCatalog` | `specifications/products/catalog.py` | Loaded product specs from YAML |
| `Server` | `specifications/remote/resource.py` | Server endpoint (hostname, protocol, auth) |
| `ResourceProductSpec` | `specifications/remote/resource.py` | Product offering at a center (product_name, parameters, directory) |
| `ResourceSpec` | `specifications/remote/resource.py` | Root center spec: servers + product offerings |
| `ResourceQuery` | `specifications/remote/resource.py` | Concrete query target: product + server + directory |
| `LocalCollection` | `specifications/local/local.py` | Group of product specs sharing a directory template |
| `LocalResourceSpec` | `specifications/local/local.py` | Root local storage spec |
| `Dependency` | `specifications/dependencies/dependencies.py` | Single product dependency (spec name, required, constraints) |
| `SearchPreference` | `specifications/dependencies/dependencies.py` | Sort preference for a search axis |
| `DependencySpec` | `specifications/dependencies/dependencies.py` | Full dependency declaration for a task |
| `ResolvedDependency` | `specifications/dependencies/dependencies.py` | Resolution result (status, path, URL) |
| `DependencyResolution` | `specifications/dependencies/dependencies.py` | Aggregated resolution results |
| `AxisDef` | `specifications/queries/query.py` | Global search axis definition |
| `ProductQueryProfile` | `specifications/queries/query.py` | Per-product query configuration |

### Interfaces

Each spec type exposes a `from_yaml(path) -> Self` classmethod for loading. All models are Pydantic BaseModel subclasses exposing standard `.model_dump()`, `.model_validate()`, `.model_copy()`.

### Key Rule
Layer 1 models are **declarative data**. They define *what exists*, not how to build or query it. The `from_yaml()` classmethods are the only I/O allowed (reading config files).

---

## Layer 2: Catalog (Resolution + Registry)

**Responsibility:** Transform abstract specifications into concrete, queryable objects. Maintain registries for lookup. This is where specs *become* usable products.

### Modules & Key Abstractions

| Abstraction | Module | Input → Output |
|---|---|---|
| `Catalog` (ABC) | `specifications/catalog.py` | Base class enforcing `@classmethod resolve()` on all catalogs |
| `FormatCatalog` | `specifications/format/format_spec.py` | FormatSpecCatalog + ParameterCatalog → resolved Products per format/version/variant |
| `ProductCatalog` | `specifications/products/catalog.py` | ProductSpecCatalog + FormatCatalog → resolved Products per product/version/variant |
| `ResourceCatalog` | `specifications/remote/resource_catalog.py` | ResourceSpec + ProductCatalog → expanded ResourceQuery list |
| `RemoteResourceFactory` | `factories/remote_factory.py` | Registry of ResourceCatalogs per center; resolves products against centers |
| `LocalResourceFactory` | `factories/local_factory.py` | Registry of local storage specs; resolves products to filesystem paths |

### Resolution Chain

```
ParameterCatalog ──┐
                   ├──► FormatCatalog ──► ProductCatalog ──┬──► RemoteResourceFactory
FormatSpecCatalog ─┘    ProductSpecCatalog ─┘              │        ↑ ResourceSpec[]
                                                           └──► LocalResourceFactory
                                                                    ↑ LocalResourceSpec[]
```

### Interfaces

All three catalog classes inherit from `Catalog(BaseModel)` (in `specifications/catalog.py`), which enforces an abstract `@classmethod resolve()`. Concrete signatures:

- `FormatCatalog.resolve(format_spec_catalog, parameter_catalog) -> FormatCatalog`
- `ProductCatalog.resolve(product_spec_catalog, format_catalog) -> ProductCatalog`
- `ResourceCatalog.resolve(resource_spec, product_catalog) -> ResourceCatalog`

Factory registries follow a `register()` + query pattern:

- `RemoteResourceFactory.register(ResourceSpec) -> ResourceCatalog`
- `RemoteResourceFactory.get(center_id) -> ResourceCatalog`
- `LocalResourceFactory.register(LocalResourceSpec, base_dir)`
- `LocalResourceFactory.resolve_product(Product, date) -> (Server, ProductPath)`

### Key Rule
Catalogs are **immutable after construction**. Resolution happens once; the result is cached as data. No network I/O, no filesystem writes.

---

## Layer 3: Orchestration (Query Building + Fetching + Resolution)

**Responsibility:** Combine catalogs with user constraints to build, execute, and resolve queries. This layer touches external boundaries (network, filesystem).

### Modules & Key Abstractions

| Abstraction | Module | Responsibility |
|---|---|---|
| `QueryFactory` | `factories/query_factory.py` | Lazy narrowing: date + product + constraints → List[ResourceQuery] |
| `ResourceFetcher` | `factories/resource_fetcher.py` | Execute queries against remote servers (FTP/HTTP) |
| `DependencyResolver` | `specifications/dependencies/dependency_resolver.py` | Two-phase local+remote resolution with preference cascade |

### Data Flow

```
User constraints (date, product, center, quality...)
        │
        ▼
   QueryFactory
   ├── Resolve product templates (via ProductCatalog)
   ├── Compute date fields (via ParameterCatalog)
   ├── Narrow parameters (user constraints)
   ├── Expand combinations (cartesian product)
   ├── Resolve local paths (via LocalResourceFactory)
   └── Resolve remote queries (via RemoteResourceFactory)
        │
        ▼
   List[ResourceQuery]
        │
        ▼
   ResourceFetcher
   ├── List remote directories (via server/ftp.py, server/http.py)
   ├── Match filenames against regex patterns
   └── Optionally download matched files
        │
        ▼
   List[FoundResource]
```

### Interfaces

- `QueryFactory.get(date, product, parameters, ...) -> List[ResourceQuery]`
- `ResourceFetcher.search(List[ResourceQuery]) -> List[FetchResult]`
- `ResourceFetcher.download(List[FetchResult], local_factory, date)`
- `DependencyResolver.resolve(date, download=False) -> DependencyResolution`

### Key Rule
Orchestration modules coordinate between catalogs and I/O adapters. They **do not define** domain models — they consume them. Network/filesystem operations are delegated to Layer 0 adapters.

---

## Layer 4: Interface (Entry Point)

**Responsibility:** Provide a single, user-facing API that wires all layers together. Hide internal complexity.

### Modules & Key Abstractions

| Abstraction | Module | Responsibility |
|---|---|---|
| `ProductEnvironment` | `factories/environment.py` | Unified container: loads specs, builds catalogs, exposes factories |
| `FoundResource` | `factories/models.py` | User-facing result type |
| `Resolution` | `factories/models.py` | Aggregated resolution result |
| `DiscoveryReport` | `factories/models.py` | Summary of available products |

### Interfaces

- `ProductEnvironment(workspace=path)` — Primary constructor (auto-loads bundled specs)
- `ProductEnvironment.from_yaml(...)` — Explicit constructor
- `.product_catalog` — Access resolved product catalog
- `.remote_factory` — Access remote center registry
- `.local_factory` — Access local storage factory
- `.query_factory` — Access query builder
- `.classify(filename) -> dict` — Identify a product from its filename

### Key Rule
All user code should interact through `ProductEnvironment`. Internal layer details (catalogs, specs, factories) are implementation concerns.

---

## Identified Inconsistencies (Current State)

All 6 inconsistencies have been resolved:

### 1. ~~LocalResourceFactory lives in specifications/~~ ✅ RESOLVED
Moved to `factories/local_factory.py`. Backward-compat re-export in `specifications/local/__init__.py`.

### 2. ~~DependencyResolver lives in specifications/~~ ✅ RESOLVED
Moved to `factories/dependency_resolver.py`. Uses direct module imports to avoid circular deps.

### 3. ~~FormatCatalog uses `__init__` instead of `@classmethod resolve()`~~ ✅ RESOLVED
Refactored to `FormatCatalog.resolve(format_spec_catalog, parameter_catalog)`.

### 4. ~~ResourceCatalog mixes Layer 1 + Layer 2 in one file~~ ✅ RESOLVED
Extracted `ResourceCatalog` + helpers into `specifications/remote/resource_catalog.py`. `resource.py` now contains only Layer 1 models.

### 5. ~~QueryFactory helper models duplicate specification-layer concepts~~ ✅ RESOLVED
Both sets of dead code removed: `AxisAlias`/`SortPreference`/`QueryProfile` from `query_factory.py`, and `AxisDef`/`ExtraAxisDef`/`ProductQueryProfile` from `specifications/queries/query.py` (file deleted). Neither was used in production code.

### 6. ~~Protocol adapters lack a common interface~~ ✅ RESOLVED
`DirectoryAdapter` Protocol defined in `server/protocol.py`. Concrete adapters: `FTPAdapter` (ftp.py), `HTTPAdapter` (http.py), `LocalAdapter` (local.py). `ResourceFetcher` now uses an adapter registry instead of if/elif dispatch.

---

## Abstraction Inventory by Layer

```
Layer 0 (Configuration)         Layer 1 (Specification)
─────────────────────           ───────────────────────
configs/__init__.py             Parameter
server/ftp.py                   ParameterCatalog
server/http.py                  FormatFieldDef
utilities/helpers.py            FormatVersionSpec
utilities/metadata_funcs.py     FormatSpec
                                FormatSpecCatalog
                                FormatRegistry
                                Product
                                ProductPath
                                VariantCatalog[T]
                                VersionCatalog[T]
                                ProductSpec
                                ProductSpecCatalog
                                Server
                                ResourceProductSpec
                                ResourceSpec
                                ResourceQuery
                                LocalCollection
                                LocalResourceSpec
                                Dependency
                                SearchPreference
                                DependencySpec
                                ResolvedDependency
                                DependencyResolution

Layer 2 (Catalog)               Layer 3 (Orchestration)
─────────────────               ───────────────────────
Catalog (ABC base)              QueryFactory
FormatCatalog                   ResourceFetcher
ProductCatalog                  DependencyResolver
ResourceCatalog
RemoteResourceFactory
LocalResourceFactory

Layer 4 (Interface)
───────────────────
ProductEnvironment
FoundResource
Resolution
DiscoveryReport
```

---

## Summary

| Layer | Purpose | Depends On | Boundary |
|---|---|---|---|
| 0 — Configuration | Static data, I/O adapters, utilities | Nothing | Filesystem, Network |
| 1 — Specification | Domain models, YAML loading | Layer 0 | Filesystem (YAML reads) |
| 2 — Catalog | Resolve specs → concrete objects, registries | Layer 1 | None (pure computation) |
| 3 — Orchestration | Build queries, execute fetches, resolve deps | Layers 0, 1, 2 | Network, Filesystem |
| 4 — Interface | User-facing API, container wiring | Layers 1, 2, 3 | User input |
