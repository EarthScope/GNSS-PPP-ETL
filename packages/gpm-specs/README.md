# gpm-specs

Bundled YAML configuration data for GNSSommelier — analysis center endpoints,
product definitions, file format specifications, and local storage layouts.

This package contains no executable code. It ships the specification files that
`gnss-product-management` reads at runtime to know which servers exist, which
products they host, and how IGS long filenames are constructed.

## Installation

From the monorepo (development):

```bash
uv sync
```

Standalone:

```bash
uv add gpm-specs
# or
pip install gpm-specs
```

---

## Configuration files

All YAML files live under `src/gpm_specs/configs/`:

| Directory / File | Description |
|---|---|
| `centers/` | One YAML per analysis center — server hostnames, protocols, product listings |
| `meta/meta_spec.yaml` | IGS parameter catalog (`TTT`, `AAA`, `YYYY`, `DDD`, `GPSWEEK`, …) |
| `products/product_spec.yaml` | Product definitions (ORBIT, CLOCK, BIA, ERP, …) and path templates |
| `products/format_spec.yaml` | File format specs — regex patterns, decompression rules, sampling codes |
| `local/local_config.yaml` | Default local storage layout — directory structure under `base_dir` |
| `query/query_config.yaml` | Default query configuration — connection limits, retry policy |

### Centers

Each file in `centers/` describes one analysis center:

```yaml
id: WUM
servers:
  - id: wuhan_ftp
    hostname: ftp://igs.gnsswhu.cn
    protocol: ftp
    auth_required: false
resources:
  - id: wum_orbit
    product_name: ORBIT
    server_id: wuhan_ftp
    directory: pub/gps/products/{GPSWEEK}/
    available: true
```

See [`docs/data-centers.md`](../../docs/data-centers.md) for the full center
catalog with server endpoints and product listings.

---

## Python API

`gpm_specs` exports `Path` constants that point at the bundled files:

```python
from gpm_specs import (
    CENTERS_RESOURCE_DIR,   # Path to centers/ directory
    DEPENDENCY_SPEC_DIR,    # Path to dependency spec directory
    FORMAT_SPEC_YAML,       # Path to format_spec.yaml
    LOCAL_SPEC_DIR,         # Path to local/ directory
    META_SPEC_YAML,         # Path to meta_spec.yaml
    PRODUCT_SPEC_YAML,      # Path to product_spec.yaml
    QUERY_SPEC_YAML,        # Path to query_config.yaml
)
```

`gnss-product-management` consumes these paths automatically when you call
`GNSSClient.from_defaults()`. You only need to import them directly if you are
loading the specs yourself (e.g. to inspect or extend the catalog).

---

## Adding a new analysis center

1. Create `src/gpm_specs/configs/centers/<id>_config.yaml` following the
   schema of an existing center (e.g. `cod_config.yaml`).
2. Add at least one `servers` entry and one `resources` entry.
3. Run the test suite — `test_catalog_coverage` will pick up the new file
   automatically.
4. Add an entry to [`docs/data-centers.md`](../../docs/data-centers.md).
