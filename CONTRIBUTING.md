# Contributing

## Contents

- [Setup](#setup)
- [Part 1 — Expanding product and server availability](#part-1--expanding-product-and-server-availability)
  - [Scenario 1 — Add an analysis center](#scenario-1--add-an-analysis-center)
  - [Scenario 2 — Add a product type](#scenario-2--add-a-product-type)
  - [Scenario 3 — Add a metadata parameter](#scenario-3--add-a-metadata-parameter)
  - [Scenario 4 — Add a dependency spec for a new processing task](#scenario-4--add-a-dependency-spec-for-a-new-processing-task)
  - [Spec PR checklist](#spec-pr-checklist)
- [Part 2 — Code contributions](#part-2--code-contributions)
  - [Bug reports](#bug-reports)
  - [Suggesting features](#suggesting-features)
  - [Making a code change](#making-a-code-change)
  - [Code style](#code-style)
  - [Code PR checklist](#code-pr-checklist)

---

## Setup

```bash
git clone https://github.com/EarthScope/GNSS-PPP-ETL.git
cd GNSS-PPP-ETL
uv sync --all-packages
```

Run the test suite:

```bash
uv run pytest packages/gnss-product-management/test/
```

---

## Part 1 — Expanding product and server availability

The four scenarios below cover the vast majority of spec extensions. All live
in `gnss-management-specs` — the core library (`gnss-product-management`)
never needs to change for these cases.

### Scenario 1 — Add an analysis center

**Who needs this:** A geodesist whose preferred center (NRCAN, BKG, JAXA,
Geoscience Australia) is not in the bundled specs, or a developer integrating
a private product server.

The spec lives in
`packages/gnss-management-specs/src/gnss_management_specs/configs/centers/`.
One file per center. The loader picks up every `*_config.yaml` in that
directory automatically — no manifest to update.

#### Step 1: Create the center config

```yaml
# packages/gnss-management-specs/src/gnss_management_specs/configs/centers/nrcan_config.yaml

id: NRC                     # IAG/IGS three-character analysis center code
name: Natural Resources Canada
website: https://natural-resources.canada.ca/maps-tools-publications/data

servers:
  - id: nrcan_ftp
    name: NRCan Products FTP
    hostname: "ftp://pretend.ftp.server"
    protocol: ftp             # ftp | ftps | http | https
    auth_required: false

products:

  - id: nrcan_orbit
    product_name: ORBIT       # must match a key in product_spec.yaml
    server_id: nrcan_ftp
    available: true
    description: Precise orbits from NRCan
    parameters:
      - {name: AAA, value: NRC}
      - {name: TTT, value: FIN}
      - {name: TTT, value: RAP}
      - {name: SMP, value: 15M}
    directory: {pattern: "gnss/products/w{GPSWEEK}/"}

  - id: nrcan_clock
    product_name: CLOCK
    server_id: nrcan_ftp
    available: true
    description: Precise clocks from NRCan
    parameters:
      - {name: AAA, value: NRC}
      - {name: TTT, value: FIN}
      - {name: TTT, value: RAP}
      - {name: SMP, value: 30S}
    directory: {pattern: "gnss/products/w{GPSWEEK}/"}
```

The `parameters` list enumerates every allowed value for each IGS filename
field. The engine generates the Cartesian product of all parameter combinations
and matches filenames against each candidate pattern in the remote directory.
List as many `TTT` or `SMP` values as the center actually publishes.

#### Step 2: Verify

```python
from datetime import datetime, timezone
from gnss_product_management import GNSSClient

client = GNSSClient.from_defaults()
date = datetime(2025, 1, 15, tzinfo=timezone.utc)

results = (
    client.query()
    .for_product("ORBIT")
    .on(date)
    .sources("NRC")
    .search()
)
print(results)
```

---

### Scenario 2 — Add a product type

**Who needs this:** A developer adding SSR corrections, SINEX station
coordinates, troposphere delay products (ZTD), or any other product not in
the current catalog.

Adding a product type requires edits to two files:

1. `format_spec.yaml` — defines the filename template structure
2. `product_spec.yaml` — registers the product in the catalog

#### Step 1: Check `format_spec.yaml`

Most IGS products follow the standard long filename convention and reuse the
existing `PRODUCT` format template:

```
{AAA}{V}{PPP}{TTT}_{YYYY}{DDD}{HH}{MM}_{LEN}_{SMP}_{CNT}.{FMT}.*
```

If your product follows this convention (SP3, CLK, BIA, ERP, IONEX, etc.),
**skip to Step 2**. If it uses a non-standard filename structure, add a new
format entry:

```yaml
# packages/gnss-management-specs/src/gnss_management_specs/configs/products/format_spec.yaml

SSR_STREAM:
  name: SSR_STREAM
  versions:
    "1":
      variants:
        default:
          parameters:
            - name: AAA
            - name: YYYY
            - name: DDD
            - name: CNT
            - name: FMT
          filename: "{AAA}_{YYYY}{DDD}_{CNT}.{FMT}.*"
```

#### Step 2: Add to `product_spec.yaml`

```yaml
# packages/gnss-management-specs/src/gnss_management_specs/configs/products/product_spec.yaml

  TROP:
    description: >
      Troposphere delay products (ZTD/ZWD) at GNSS reference stations.
      ex: COD0OPSFIN_20250150000_01D_01H_TRO.TRO

    formats:
      - format: PRODUCT       # references format_spec.yaml key
        version: "1"
        constraints:
          LEN: "01D"
          CNT: "TRO"
          FMT: "TRO"
        variant: default
```

`constraints` are hard-coded filename field values applied at search time.
Use them to distinguish TROP from ORBIT when both share the `PRODUCT` template.

#### Step 3: Add the product to a center config

Edit the relevant center's `*_config.yaml`:

```yaml
# append to the products list in, e.g., cod_config.yaml

  - id: cod_trop
    product_name: TROP
    server_id: cod_ftp
    available: true
    description: CODE troposphere products (ZTD)
    parameters:
      - {name: AAA, value: COD}
      - {name: TTT, value: FIN}
      - {name: SMP, value: 01H}
    directory: {pattern: "pub/aiub/CODE/{YYYY}/"}
```

#### Step 4: Add to a dependency spec (optional)

If this product should be resolved automatically for a processing task, add it
to the relevant `dependencies/*.yaml`:

```yaml
# append to dependencies list in, e.g., pride_pppar.yaml

  - spec: TROP
    product: TROP
    required: false           # set true if the processor cannot run without it
    timeliness: [FIN, RAP]
    center: [COD, ESA]
```

---

### Scenario 3 — Add a metadata parameter

**Who needs this:** A researcher working with non-standard centers that publish
products with filename fields not currently tracked, or anyone integrating a
LEO-augmented or mission-specific product series where the standard IGS
parameters are insufficient.

Parameters are defined in:
`packages/gnss-management-specs/src/gnss_management_specs/configs/meta/meta_spec.yaml`

#### Existing parameters

| Parameter | Pattern | Derivation | IGS meaning |
|---|---|---|---|
| `AAA` | `[A-Z0-9]{3}` | enum | Analysis center code (WUM, COD, GFZ, …) |
| `TTT` | `[A-Z]{3}` | enum | Timeliness: FIN ≥13 d / RAP ≤17 h / ULT ≤3 h / NRT / PRD |
| `YYYY` | `\d{4}` | computed | 4-digit year |
| `DDD` | `\d{3}` | computed | Day of year (001–366) |
| `GPSWEEK` | `\d{4}` | computed | GPS week number |
| `SMP` | `\d{2}[SMHD]` | enum | Sampling interval (30S, 05M, 01H, 01D) |
| `FMT` | `[A-Z0-9]+` | enum | File format extension (SP3, CLK, BIA, ERP) |
| `CNT` | `[A-Z0-9]+` | enum | File content type (ORB, CLK, OSB, ERP) |
| `LEN` | `\d{2}[SMHD]` | enum | File arc length (01D, 03D) |
| `V` | `\d` | enum | Format version digit |
| `PPP` | `[A-Z0-9]{3}` | enum | Processing type (OPS, MGX) |

#### Adding a new parameter

```yaml
# packages/gnss-management-specs/src/gnss_management_specs/configs/meta/meta_spec.yaml

MISSION:
  - pattern: "[A-Z0-9]{3,6}"   # regex matched against the filename token
  - description: "Mission identifier for LEO-augmented GNSS products (e.g. GRACE, SWARM)"
  - derivation: enum            # enum = explicit values listed in center configs
                                # computed = derived automatically from the date
```

After adding the parameter to `meta_spec.yaml`, reference it in your
`format_spec.yaml` parameters list and in the center config `parameters`
entries, exactly as you would `AAA` or `TTT`.

---

### Scenario 4 — Add a dependency spec for a new processing task

**Who needs this:** A graduate student defining required products for a
processor other than PRIDE-PPPAR, or a pipeline engineer encoding timeliness
requirements for a specific campaign.

```yaml
# packages/gnss-management-specs/src/gnss_management_specs/configs/dependencies/my_processor.yaml

name: my-processor
version: "1"

dependencies:
  - spec: ORBIT
    product: ORBIT
    required: true
    timeliness: [FIN, RAP, ULT]
    center: [WUM, COD, GFZ, ESA]

  - spec: CLOCK
    product: CLOCK
    required: true
    timeliness: [FIN, RAP]
    center: [WUM, COD, GFZ]

  - spec: BIA
    product: BIA
    required: false           # optional for float PPP; set true for PPP-AR
    timeliness: [FIN]
    center: [WUM, COD]
```

Use it directly with `GNSSClient`:

```python
from datetime import datetime, timezone
from pathlib import Path
from gnss_product_management import GNSSClient

client = GNSSClient.from_defaults(base_dir=Path("/data/gnss"))
date = datetime(2025, 1, 15, tzinfo=timezone.utc)

resolution, lockfile_path = client.resolve_dependencies(
    "packages/gnss-management-specs/src/gnss_management_specs/configs/dependencies/my_processor.yaml",
    date,
    sink_id="local",
)

if resolution.all_required_fulfilled:
    for spec, path in resolution.product_paths().items():
        print(f"{spec:<14s}  {path}")
else:
    missing = [r.spec for r in resolution.missing if r.required]
    print(f"Missing required products: {missing}")
```

---

### Spec PR checklist

- [ ] New center config placed in `configs/centers/` named `{id_lowercase}_config.yaml`
- [ ] New product/format entries follow the indentation and field names in existing YAML files
- [ ] Any new parameter added to `meta_spec.yaml` with `pattern` and `derivation` fields
- [ ] `uv run pytest packages/gnss-product-management/test/` passes
- [ ] Manual spot-check: `client.query().for_product(...).on(date).sources(...).search()` returns expected results

---

## Part 2 — Code contributions

### Bug reports

Open an issue at [EarthScope/GNSS-PPP-ETL](https://github.com/EarthScope/GNSS-PPP-ETL/issues)
and include:

- The minimal code that reproduces the problem
- The full traceback
- Python version (`python --version`) and package version (`uv pip show gnss-product-management`)
- For search/download failures: the target date, product name, and center code

If the failure is protocol-specific (FTP timeout, FTPS auth error), capture
debug-level logs:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Suggesting features

Open a discussion or issue describing:

1. **The workflow** — what processing scenario requires this? Reference the
   relevant IGS product, center, or RINEX convention if applicable.
2. **What you tried** — did you attempt a workaround via the existing query
   API, a custom `DependencySpec`, or a spec-layer extension?
3. **The gap** — what specifically cannot be expressed with the current API
   or YAML schemas?

Feature suggestions backed by a concrete geodetic use case (e.g., "MADOCA-PPP
SSR streams for real-time positioning", "SINEX station coordinate ingestion for
network adjustment") move faster than abstract API requests. If you are unsure
whether something belongs in `gnss-management-specs` (a new YAML spec) or
`gnss-product-management` (a code change), describe the use case and we will
help identify the right layer.

### Making a code change

The five-layer architecture means most changes land in a single layer:

| What you are changing | Where it lives |
|---|---|
| New IGS center or product catalog | `gnss-management-specs` YAML specs — no code needed |
| New filename format or parameter | `gnss-management-specs` YAML specs — no code needed |
| Query builder behavior (`.where`, `.prefer`, `.on_range`) | `gnss-product-management/client/product_query.py` |
| Remote directory listing or download logic | `gnss-product-management/factories/remote_transport.py` |
| Dependency resolution or lockfile logic | `gnss-product-management/factories/pipelines/` |
| PRIDE-PPPAR config generation or output parsing | `pride-ppp/` |

Before opening a PR for a code change:

1. **Check the issue tracker** — a related issue may already exist or be in
   progress.
2. **Open an issue first** for non-trivial changes (new pipeline stage, new
   transport protocol, changes to the `DependencySpec` schema). A brief
   discussion upfront avoids wasted effort.
3. **Keep the scope narrow.** A PR that adds FTP retry logic should not also
   refactor the connection pool. Separate concerns into separate PRs.

### Code style

- Formatting: [Ruff](https://docs.astral.sh/ruff/) (`uv run ruff format .`)
- Linting: `uv run ruff check .`
- Type hints required on all public functions and methods
- Docstrings on all public classes and methods; use Google style
- No `print` statements in library code — use `logging.getLogger(__name__)`
- New transport protocols must implement the fsspec-backed path in
  `ConnectionPoolFactory`; do not add protocol-specific branches elsewhere

### Code PR checklist

- [ ] `uv run ruff format .` applied — no formatting diff
- [ ] `uv run ruff check .` passes — no lint errors
- [ ] `uv run pytest packages/gnss-product-management/test/` passes
- [ ] New public functions and classes have docstrings and type hints
- [ ] No changes to existing YAML spec schemas without a corresponding issue
  discussing the migration path
- [ ] For `pride-ppp` changes: `uv run pytest packages/pride-ppp/test/` passes
