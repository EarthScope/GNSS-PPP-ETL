# Documentation Index

Master table of contents for the GNSSommelier repository.

---

## Top-level

| Document | Description |
|---|---|
| [README](../README.md) | Project overview, quick start, supported products and centers |
| [INSTALL](../INSTALL.md) | Installation instructions |
| [LICENSE](../LICENSE) | Project license |

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
| [`environments/README.md`](../packages/gnss-product-management/src/gnss_product_management/environments/README.md) | `ProductEnvironment` and `WorkSpace` usage |
| [`factories/README.md`](../packages/gnss-product-management/src/gnss_product_management/factories/README.md) | Factory classes (query, resource, dependency) |
| [`lockfile/README.md`](../packages/gnss-product-management/src/gnss_product_management/lockfile/README.md) | Lock-file tracking system |
| [`server/README.md`](../packages/gnss-product-management/src/gnss_product_management/server/README.md) | FTP/HTTP/Local protocol adapters |
| [`specifications/README.md`](../packages/gnss-product-management/src/gnss_product_management/specifications/README.md) | Pydantic domain models |
| [`utilities/README.md`](../packages/gnss-product-management/src/gnss_product_management/utilities/README.md) | Date math, decompression, naming helpers |

## Examples

| Package | Script | Description |
|---|---|---|
| gnss-product-management | [`search_products.py`](../packages/gnss-product-management/examples/search_products.py) | Search all centers for a product type |
| gnss-product-management | [`resolve_dependencies.py`](../packages/gnss-product-management/examples/resolve_dependencies.py) | Resolve & download all dependencies |
| gnss-product-management | [`download_from_center.py`](../packages/gnss-product-management/examples/download_from_center.py) | Download from a single center |
| pride-ppp | [`process_rinex.py`](../packages/pride-ppp/examples/process_rinex.py) | Process one RINEX file end-to-end |
| pride-ppp | [`batch_process.py`](../packages/pride-ppp/examples/batch_process.py) | Batch-process multiple RINEX files |
