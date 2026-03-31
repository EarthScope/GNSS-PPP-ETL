# gnss-product-management

Specification-driven discovery, resolution, and download of GNSS Precise Point Positioning products from IGS analysis centers.

## What it does

- **YAML-driven specs** — products, formats, centers, and local storage are defined in bundled YAML configurations. No code changes needed to add a new center or product type.
- **Query engine** — give it a date and product name; it resolves the exact remote path (FTP, FTPS, HTTP) across all registered centers using a parameter catalog and template expansion.
- **Dependency resolver** — declare what a processing task needs (orbit, clock, bias, ERP, …) and the resolver finds, downloads, and caches every product in one call.
- **Local workspace** — resolved products land in a structured local directory tree, tracked by lock files for reproducibility.

## Installation

**From the monorepo (development):**

```bash
# From the repository root — uv resolves workspace dependencies automatically
uv sync
```

**Standalone:**

```bash
uv add gnss-product-management
# or
pip install gnss-product-management
```

## Quick start

```python
from datetime import datetime, timezone
from gnss_product_management import QueryFactory, ResourceFetcher
from gnss_product_management.defaults import DefaultProductEnvironment, DefaultWorkSpace

# Query for orbit products on all registered centers
qf = QueryFactory(product_environment=DefaultProductEnvironment, workspace=DefaultWorkSpace)
queries = qf.get(date=datetime(2025, 1, 2, tzinfo=timezone.utc), product={"name": "ORBIT"})

# Search remote servers for matching files
fetcher = ResourceFetcher()
results = fetcher.search(queries)
for r in results:
    if r.found:
        print(r.query.server.hostname, r.matched_filenames)
```

See [examples/](examples/) for more (dependency resolution, single-center downloads).

## Architecture

The package is organized in five layers (see [docs/architecture.md](../../docs/architecture.md) for full details):

```
Layer 4 — Interface       ProductEnvironment (unified entry point)
Layer 3 — Orchestration   QueryFactory, ResourceFetcher, DependencyResolver
Layer 2 — Catalog         FormatCatalog, ProductCatalog, ResourceCatalog, Factories
Layer 1 — Specification   Parameter, FormatSpec, ProductSpec, DependencySpec (Pydantic models)
Layer 0 — Configuration   Bundled YAML configs, FTP/HTTP/Local adapters, utilities
```

Each layer depends only on layers below it. All user code should interact through `ProductEnvironment` or `DependencyResolver`.

## API overview

| Class | Layer | Purpose |
|---|---|---|
| `ProductEnvironment` | Interface | Loads specs, builds catalogs, exposes factories and `classify()` |
| `QueryFactory` | Orchestration | Date + product + constraints → `List[ResourceQuery]` |
| `ResourceFetcher` | Orchestration | Searches remote directories, matches file patterns, downloads |
| `DependencyResolver` | Orchestration | Resolves a full dependency spec (local-first, then remote) |
| `WorkSpace` | Orchestration | Manages local storage specs and registered directory trees |

## Supported centers

| Center | Products |
|---|---|
| **CDDIS** (NASA) | clock, GIM, leap seconds, navigation, orbit |
| **COD** (AIUB) | bias, clock, ERP, GIM, orbit |
| **ESA** (ESOC) | clock, GIM, orbit |
| **GFZ** (Potsdam) | clock, orbit |
| **IGS** (IGN France) | ATX, bias, clock, ERP, navigation, OBX, orbit |
| **VMF** (TU Wien) | orography, VMF1, VMF3 |
| **WUM** (Wuhan) | bias, clock, ERP, GIM, leap seconds, navigation, OBX, orbit, sat_parameters |