# Installation

## Requirements

- Python 3.10 – 3.14
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Development install (full workspace)

Clone the repository and sync all packages in one step:

```bash
git clone https://github.com/EarthScope/GNSSommelier.git
cd GNSSommelier
uv sync
```

This installs both workspace packages in editable mode along with their dependencies.

## Installing individual packages

### gnss-product-management

GNSS product discovery, query expansion, dependency resolution, and download.
Includes bundled YAML specifications for centers, products, formats, and local storage.

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

## Package dependency graph

```
pride-ppp
└── gnss-product-management
```

## Running tests

```bash
# All non-integration tests for gnss-product-management
uv run pytest packages/gnss-product-management/test/ -m "not integration" -q

# pride-ppp tests
uv run pytest packages/pride-ppp/tests/ -q
```

## Verifying the install

```python
from gnss_product_management import GNSSClient
from gnss_management_specs.configs import PRODUCT_SPEC_YAML

print(PRODUCT_SPEC_YAML)  # path to bundled product spec

client = GNSSClient.from_defaults()
client.display()  # lists loaded products and centers
```
