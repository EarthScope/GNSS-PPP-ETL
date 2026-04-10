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

### 1. Search (no local storage needed)

```python
from datetime import datetime, timezone
from gnss_product_management import GNSSClient

date = datetime(2025, 1, 2, tzinfo=timezone.utc)

# Build client from bundled specs — no base_dir means search-only mode
client = GNSSClient.from_defaults()

results = (
    client.query()
    .for_product("ORBIT")
    .on(date)
    .where(TTT="FIN")              # final solution
    .sources("COD", "ESA", "IGS") # restrict to these centers
    .prefer(TTT=["FIN", "RAP", "ULT"])
    .search()
)

for r in results:
    print(r.center, r.quality, r.filename)
```

### 2. Download products

```python
from pathlib import Path

client = GNSSClient.from_defaults(base_dir=Path.home() / "gnss_data")

# search() + download() in one fluent chain
paths = (
    client.query()
    .for_product("ORBIT")
    .on(date)
    .where(TTT="FIN")
    .sources("COD")
    .download(sink_id="local")
)

for p in paths:
    print(p)
```

### 3. Resolve all processor dependencies

```python
resolution, lockfile_path = client.resolve_dependencies(
    "path/to/pride_pppar.yaml",
    date,
    sink_id="local",
)

print(resolution.summary())
print(resolution.table())

if resolution.all_required_fulfilled:
    for spec_name, path in resolution.product_paths().items():
        print(f"{spec_name}: {path}")
```

See [examples/](examples/) for runnable scripts with full explanations.

## Core concepts

### Product parameters

Every GNSS product file is identified by a set of parameters.  The two most
important are:

| Parameter | Meaning | Common values |
|---|---|---|
| `TTT` | Solution type / timeliness | `FIN` (final), `RAP` (rapid), `ULT` (ultra-rapid) |
| `AAA` | Analysis center | `COD`, `ESA`, `GFZ`, `WUM`, `IGS`, … |

Chain `.where(TTT="FIN")` on a query to filter, and `.prefer(TTT=["FIN", "RAP"])` to
rank results without hard-filtering.

### FoundResource

`search()` returns a list of `FoundResource` objects.  Each one represents a single
candidate file — either on a remote server or in local storage — with convenience
properties:

| Property | Description |
|---|---|
| `r.center` | Analysis center (e.g. `"COD"`) |
| `r.quality` | Solution tier (e.g. `"FIN"`) |
| `r.filename` | File name only |
| `r.uri` | Full remote URL or local path |
| `r.protocol` | `"ftp"`, `"https"`, or `"file"` |
| `r.hostname` | Server hostname |
| `r.local_path` | Set after a successful download |
| `r.downloaded` | `True` if `local_path` is set |

### DependencySpec

A YAML file that lists every product a processor needs, the centers to prefer, and the
solution tier cascade.  Pass the path directly to `resolve_dependencies()`:

```python
resolution, _ = client.resolve_dependencies("pride_pppar.yaml", date, sink_id="local")
```

The resolver checks the local workspace first (fast-path via lockfile), then downloads
missing files.  Subsequent calls with the same date return immediately.

## Architecture

The package is organized into four layers (see [docs/architecture.md](../../docs/architecture.md) for full details):

```
Layer 3 — Client          GNSSClient (single user-facing entry point)
Layer 2 — Pipelines       ProductQuery, DownloadPipeline, ResolvePipeline
Layer 1 — Factories       SearchPlanner, WormHole, ConnectionPoolFactory
Layer 0 — Specifications  ProductSpec, FormatSpec, DependencySpec, YAML configs
```

Each layer depends only on layers below it.  All user code should go through
`GNSSClient`.

## API overview

| Symbol | Purpose |
|---|---|
| `GNSSClient` | Single entry point — search, download, resolve |
| `GNSSClient.query()` | Returns a fluent `ProductQuery` builder |
| `GNSSClient.search()` | Direct search without the builder |
| `GNSSClient.download()` | Download pre-searched `FoundResource` objects |
| `GNSSClient.resolve_dependencies()` | Full spec-driven dependency resolution |
| `GNSSClient.display()` | Rich tables showing loaded products and centers |
| `ProductQuery` | Fluent builder: `.for_product()`, `.on()`, `.where()`, `.sources()`, `.prefer()`, `.search()`, `.download()` |
| `FoundResource` | Single discovered file — remote URI or local path with metadata properties |
| `DependencySpec` | Parsed YAML dependency specification |
| `DependencyResolution` | Result of `resolve_dependencies()` — `.summary()`, `.table()`, `.product_paths()`, `.missing` |

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