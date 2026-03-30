# Installation

## Requirements

- Python 3.10 – 3.14
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Development install (full workspace)

Clone the repository and sync all packages in one step:

```bash
git clone https://github.com/EarthScope/GNSS-PPP-ETL.git
cd GNSS-PPP-ETL
uv sync
```

This installs all three workspace packages in editable mode along with their dependencies.

## Installing individual packages

### gnss-product-management

GNSS product discovery, query expansion, dependency resolution, and download.

```bash
uv add gnss-product-management
# or
pip install gnss-product-management
```

### pride-ppp

PRIDE-PPPAR processing pipeline. Depends on `gnss-product-management`.

```bash
uv add pride-ppp
# or
pip install pride-ppp
```

> **Prerequisite:** The `pdp3` binary from [PRIDE-PPPAR](https://pride.whu.edu.cn/pppar/) must be on `$PATH`.

To include optional plotting support:

```bash
uv add "pride-ppp[plot]"
# or
pip install "pride-ppp[plot]"
```

### gnss-management-specs

Bundled YAML specification files (centers, products, formats, local storage). Installed automatically as a dependency of the other two packages.

```bash
uv add gnss-management-specs
# or
pip install gnss-management-specs
```

## Package dependency graph

```
pride-ppp
├── gnss-product-management
│   └── gnss-management-specs
└── gnss-management-specs
```

## Running tests

```bash
# All non-integration tests for gnss-product-management
cd packages/gnss-product-management
uv run pytest test/ -m "not integration" -q
```

## Verifying the install

```python
from gnss_product_management import QueryFactory, ResourceFetcher
from gnss_management_specs.configs import PRODUCT_SPEC_YAML

print(PRODUCT_SPEC_YAML)  # path to bundled product spec
```
