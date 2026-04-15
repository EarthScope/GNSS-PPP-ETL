# Documentation Index

Master table of contents for the GNSSommelier repository.

---

## Top-level

| Document | Description |
|---|---|
| README | Project overview, quick start, supported products and centers |
| INSTALL | Installation instructions |
| LICENSE | Project license |

## Reference docs (`docs/`)

| Document | Description |
|---|---|
| [Architecture](architecture.md) | Five-layer architecture of `gnss-product-management` (boundaries, abstractions, resolution chain) |
| [PPP Products](ppp-products.md) | GNSS product naming conventions, file formats, and product type catalogue |
| [Config Reference](config-reference.md) | Guide to the YAML configuration system (metadata, products, centers, local storage, dependencies, queries) |

## Package READMEs

| Package | README | Description |
|---|---|---|
| `gnss-product-management` | [README](../packages/gnss-product-management/README.md) | Core library — YAML-driven product discovery, query expansion, dependency resolution (includes bundled YAML specs) |
| `pride-ppp` | [README](../packages/pride-ppp/README.md) | PRIDE-PPPAR integration — RINEX in, kinematic positions out |

## Inline source READMEs

These READMEs live next to the code they describe (all under `packages/gnss-product-management/src/gnss_product_management/`):

| Path | Topic |
|---|---|
| `environments/` | `ProductEnvironment` and `WorkSpace` usage |
| `factories/` | Factory classes (query, resource, dependency) |
| `lockfile/` | Lock-file tracking system |
| `specifications/` | Pydantic domain models |
| `utilities/` | Date math, decompression, naming helpers |

## Examples

| Package | Script | Description |
|---|---|---|
| gnss-product-management | [`search_products.py`](../packages/gnss-product-management/examples/search_products.py) | Search all centers for a product type |
| gnss-product-management | [`download_from_center.py`](../packages/gnss-product-management/examples/download_from_center.py) | Download from a single center |
| pride-ppp | [`process_rinex.py`](../packages/pride-ppp/examples/process_rinex.py) | Process one RINEX file end-to-end |
| pride-ppp | [`batch_process.py`](../packages/pride-ppp/examples/batch_process.py) | Batch-process multiple RINEX files |
