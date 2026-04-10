"""Process a single RINEX file through PRIDE-PPPAR.

PrideProcessor handles the full pipeline: resolves all required GNSS
products (orbits, clocks, biases, ERP, etc.) from remote analysis
centers, writes the pdp3 config file, runs the binary in an isolated
temp directory, and returns a ProcessingResult with paths to the
kinematic (.kin) and residual (.res) output files.

Prerequisites:
    - pdp3 must be on $PATH (see https://github.com/PrideLab/PRIDE-PPPAR)
"""

from pathlib import Path

from pride_ppp import PrideCLIConfig, PrideProcessor

# --- 1. Configure the processor -----------------------------------------
# pride_dir:  local product storage (orbits, clocks, etc.)
# output_dir: where .kin and .res files are written
processor = PrideProcessor(
    pride_dir=Path("/data/pride"),
    output_dir=Path("/data/output"),
    cli_config=PrideCLIConfig(),  # defaults: kinematic mode, 30s interval
)

# --- 2. Process a RINEX file --------------------------------------------
# Site and date are inferred from the filename/header if not provided.
rinex = Path("SITE00USA_R_20250020000_01D_30S_MO.rnx")

result = processor.process(rinex, site="SITE")

# --- 3. Inspect results --------------------------------------------------
print(f"RINEX:   {result.rinex_path.name}")
print(f"Site:    {result.site}")
print(f"Date:    {result.date}")
print(f"Success: {result.success}")
print()

# Show product resolution summary
print(result.resolution.summary())
print(result.resolution.table())
print()

if result.success:
    # Lazy-load the kinematic positions as a DataFrame
    df = result.positions()
    if df is not None:
        print(f"Positions: {len(df)} epochs")
        print(df.head())
    print(f"\nKin file: {result.kin_path}")

    # Residuals (if available)
    res_df = result.residuals()
    if res_df is not None:
        print(f"\nResiduals: {len(res_df)} rows")
        print(res_df.head())
else:
    print(f"Processing failed (returncode={result.returncode})")
    if result.stderr:
        print(result.stderr[:500])
