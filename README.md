![Architecture diagram](image.png)
# GNSS-PPP-ETL

Automated retrieval and management of [IGS](https://igs.org/) analysis center
products for Precise Point Positioning, with an integrated
[PRIDE-PPPAR](https://pride.whu.edu.cn/pppar/) processing pipeline for
kinematic PPP-AR solutions.

## Motivation

Running PPP or PPP-AR requires a constellation of auxiliary products — precise
orbits (SP3), satellite clocks (CLK), code/phase biases (BIA), Earth rotation
parameters (ERP), ionosphere maps (GIM/IONEX), troposphere models, and antenna
calibrations (ATX). These files are scattered across FTP/FTPS/HTTP servers
maintained by different IGS analysis centers, each with its own directory
layout, naming convention, and update cadence.

**GNSS-PPP-ETL** eliminates the manual bookkeeping. Given a date and a
processing task definition, it resolves every required product across all
registered centers, downloads and decompresses the files into a structured
local workspace, and tracks what was fetched in reproducible lock files. For
PRIDE-PPPAR users, a second package wraps `pdp3` in a Python pipeline that
handles product resolution, config-file generation, and output parsing in a
single call.

## Packages

This is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/)
containing two packages:

| Package | Purpose |
|---|---|
| [`gnss-product-management`](packages/gnss-product-management/) | YAML-driven product discovery, query expansion, dependency resolution, and download from IGS analysis centers |
| [`pride-ppp`](packages/pride-ppp/) | Concurrent-safe PRIDE-PPPAR integration — RINEX in, kinematic positions out |

### gnss-product-management

The core library. Bundles YAML specifications for products, file-naming
formats, center server layouts, and local storage trees. A five-layer
architecture (Configuration → Specification → Catalog → Orchestration →
Interface) keeps concerns separated so adding a new center or product type
requires only a new YAML file.

### pride-ppp

A processing facade built on top of `gnss-product-management`. Resolves all
dependencies for a PRIDE-PPPAR run, writes the `pdp3` config file, executes
the binary in an isolated temp directory, and returns structured
`ProcessingResult` objects with lazy DataFrame access to `.kin` positions and
`.res` residuals.

## Documentation

See [`docs/INDEX.md`](docs/INDEX.md) for a full table of contents. Key docs:

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | Five-layer design of `gnss-product-management` |
| [PPP Products](docs/ppp-products.md) | GNSS product naming conventions and file formats |
| [Config Reference](docs/config-reference.md) | Guide to the YAML configuration system |

## Supported products

Product types currently defined in the bundled specifications:

| Product | Format | Description |
|---|---|---|
| **Orbit** | SP3 | Precise satellite ephemerides (15 min) |
| **Clock** | CLK | Satellite & station clock corrections (30 s / 5 min) |
| **Bias** | BIA | Code and phase bias (OSB/DSB) for ambiguity resolution |
| **ERP** | ERP | Polar motion, UT1-UTC, LOD |
| **GIM** | IONEX | Global ionosphere TEC maps |
| **Navigation** | RINEX NAV | Broadcast ephemerides (merged BRDC) |
| **ATX** | ANTEX | Satellite & receiver antenna phase center calibrations |
| **OBX** | OBX | Satellite attitude quaternions |
| **Troposphere** | VMF1/VMF3 | Vienna Mapping Functions (gridded) |
| **Orography** | GRID | Orography grids for VMF |
| **Leap seconds** | — | IERS leap second table |
| **Sat parameters** | — | Satellite metadata (mass, geometry, SRP) |

## Supported analysis centers & servers

| Center | Institution | Server | Protocol |
|---|---|---|---|
| **CDDIS** | [NASA GSFC](https://cddis.nasa.gov/) | `gdc.cddis.eosdis.nasa.gov` | FTPS |
| **COD** | [AIUB, Univ. of Bern](http://www.aiub.unibe.ch/research/code___analysis_center/) | `ftp.aiub.unibe.ch` | FTP |
| **ESA** | [ESA/ESOC](https://gssc.esa.int/) | `gssc.esa.int` | FTP |
| **GFZ** | [GFZ Potsdam](https://www.gfz-potsdam.de/) | `isdcftp.gfz-potsdam.de` | FTP |
| **IGS** | [IGN France](https://igs.org/) / [IGS](https://files.igs.org/) | `igs.ign.fr` / `files.igs.org` | FTP / HTTPS |
| **VMF** | [TU Wien](https://vmf.geo.tuwien.ac.at/) | `vmf.geo.tuwien.ac.at` | HTTPS |
| **WUM** | [Wuhan University](http://www.igs.gnsswhu.cn/) | `igs.gnsswhu.cn` | FTP |

## Quick start

```bash
# Clone and install
git clone https://github.com/EarthScope/GNSS-PPP-ETL.git
cd GNSS-PPP-ETL
uv sync --all-packages
```

### Search for products across all centers

```python
from datetime import datetime, timezone
from gnss_product_management import QueryFactory, ResourceFetcher
from gnss_product_management.defaults import DefaultProductEnvironment, DefaultWorkSpace

qf = QueryFactory(product_environment=DefaultProductEnvironment, workspace=DefaultWorkSpace)
queries = qf.get(date=datetime(2025, 1, 2, tzinfo=timezone.utc), product={"name": "ORBIT"})

fetcher = ResourceFetcher()
results = fetcher.search(queries)
for r in results:
    if r.found:
        print(r.query.server.hostname, r.matched_filenames)
```

### Resolve & download all dependencies

```python
from datetime import datetime, timezone
from pathlib import Path
from gnss_product_management import QueryFactory, ResourceFetcher, DependencyResolver
from gnss_product_management.defaults import DefaultProductEnvironment, DefaultWorkSpace
from gnss_product_management.specifications.dependencies.dependencies import DependencySpec

workspace = DefaultWorkSpace
workspace.register_spec(base_dir=Path("/data/gnss-products"), spec_ids=["local_config"], alias="local")

dep_spec = DependencySpec.from_yaml("path/to/your/dependency_spec.yaml")
qf = QueryFactory(product_environment=DefaultProductEnvironment, workspace=workspace)
resolver = DependencyResolver(
    dep_spec=dep_spec,
    product_environment=DefaultProductEnvironment,
    query_factory=qf,
    fetcher=ResourceFetcher(),
)
resolution, lockfile = resolver.resolve(date=datetime(2025, 1, 2, tzinfo=timezone.utc), local_sink_id="local")
print(resolution.table())
```

### Run PRIDE-PPPAR processing

```python
from pathlib import Path
from pride_ppp import PrideProcessor

processor = PrideProcessor(
    pride_dir=Path("/data/pride"),
    output_dir=Path("/data/output"),
)
result = processor.process(Path("SITE00USA_R_20250010000_01D_30S_MO.rnx"))

if result.success:
    print(result.positions().head())
```

> **Prerequisite:** The `pdp3` binary from
> [PRIDE-PPPAR](https://github.com/PrideLab/PRIDE-PPPAR) must be on `$PATH`.

## Examples

Runnable scripts in each package's `examples/` directory:

| Package | Script | Description |
|---|---|---|
| gnss-product-management | [search_products.py](packages/gnss-product-management/examples/search_products.py) | Search all centers for a product type on a given date |
| gnss-product-management | [resolve_dependencies.py](packages/gnss-product-management/examples/resolve_dependencies.py) | Resolve and download all PRIDE-PPPAR dependencies |
| gnss-product-management | [download_from_center.py](packages/gnss-product-management/examples/download_from_center.py) | Download a specific product from a single center |
| pride-ppp | [process_rinex.py](packages/pride-ppp/examples/process_rinex.py) | Process one RINEX file end-to-end |
| pride-ppp | [batch_process.py](packages/pride-ppp/examples/batch_process.py) | Batch-process multiple RINEX files |

## Project structure

```
GNSS-PPP-ETL/
├── pyproject.toml                  # Workspace root
├── packages/
│   ├── gnss-product-management/          # Product discovery & download
│   │   ├── src/gnss_product_management/
│   │   │   ├── configs/            # Bundled YAML specs (centers, products, formats)
│   │   │   ├── environments/       # ProductEnvironment, WorkSpace
│   │   │   ├── factories/          # QueryFactory, ResourceFetcher, DependencyResolver
│   │   │   ├── specifications/     # Pydantic models (Parameter, FormatSpec, ProductSpec)
│   │   │   ├── server/             # FTP, HTTP, local filesystem adapters
│   │   │   └── utilities/          # Date math, decompression, naming helpers
│   │   └── test/
│   └── pride-ppp/                  # PRIDE-PPPAR integration
│       └── src/pride_ppp/
│           ├── processor.py        # PrideProcessor — main entry point
│           ├── cli.py              # pdp3 command-line builder
│           ├── config.py           # PRIDE config-file I/O
│           ├── output.py           # .kin/.res parsing
│           └── rinex.py            # RINEX utilities

```

## Requirements

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- `gfortran` + `gcc` + `make` if building PRIDE-PPPAR from source

## References

- [International GNSS Service — Products](https://igs.org/products/)
- [IGS Product Access](https://igs.org/products-access/)
- [PRIDE-PPPAR (Wuhan University)](https://pride.whu.edu.cn/pppar/)
- [IGS Long Product Filenames](https://igs.org/formats-and-standards/)
- [Vienna Mapping Functions](https://vmf.geo.tuwien.ac.at/)

## License

See [LICENSE](LICENSE) for details.
