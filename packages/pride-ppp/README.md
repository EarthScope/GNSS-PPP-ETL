# pride-ppp

PRIDE-PPPAR integration for kinematic Precise Point Positioning with
Ambiguity Resolution (PPP-AR). Wraps the `pdp3` binary in a concurrent-safe
Python pipeline that resolves GNSS products, runs processing, and returns
structured results with lazy DataFrame access.

## Installation

**From the monorepo (development):**

```bash
# From the repository root — uv resolves workspace dependencies automatically
uv sync
```

**Standalone:**

```bash
uv add pride-ppp
# or
pip install pride-ppp
```

> **Prerequisite:** The `pdp3` binary from
> [PRIDE-PPPAR](https://pride.whu.edu.cn/pppar/) must be on `$PATH`.

## Quick start

```python
from pathlib import Path
from pride_ppp import PrideProcessor

processor = PrideProcessor(
    pride_dir=Path("/data/pride"),
    output_dir=Path("/data/output"),
)
result = processor.process(Path("SITE00USA_R_20250020000_01D_30S_MO.rnx"), site="SITE")

if result.success:
    print(result.positions().head())   # kinematic positions
    print(result.residuals().head())   # residuals
```

See [examples/](examples/) for more (single file, batch processing).

## API overview

| Symbol | Module | Role |
|---|---|---|
| `PrideProcessor` | `processor` | Concurrent-safe RINEX → position pipeline |
| `ProcessingResult` | `processor` | Per-file outcome with lazy `.kin_df` / `.res_df` |
| `PrideCLIConfig` | `cli` | Typed pdp3 command-line flag builder |
| `PRIDEPPPFileConfig` | `config` | PRIDE config-file I/O (read/write) |
| `SatelliteProducts` | `config` | Product path resolution for pdp3 |
| `PridePPP` | `output` | Pydantic model for `.kin` file records |
| `validate_kin_file` | `output` | Check `.kin` output integrity |
| `kin_to_kin_position_df` | `output` | `.kin` → position DataFrame |
| `get_wrms_from_res` | `output` | Weighted RMS from residual files |
| `merge_broadcast_files` | `rinex` | Combine multi-hour broadcast RINEX |
| `rinex_get_time_range` | `rinex` | Extract observation time span |

## Architecture

`pride-ppp` delegates all product discovery and fetching to the sibling
[gnss-product-management](../gnss-product-management/) package. Internally it follows a
simple three-stage flow:

1. **Configure** — build `PrideCLIConfig` + `PRIDEPPPFileConfig` from user
   inputs and bundled defaults (`defaults/`, `config_files/`).
2. **Resolve** — use `gnss-product-management` to discover, download, and
   decompress required orbit / clock / bias / ERP / table files.
3. **Execute** — invoke `pdp3` in an isolated temp directory; parse
   `.kin` / `.res` outputs into `ProcessingResult`.

