"""Batch-process multiple RINEX files through PRIDE-PPPAR.

PrideProcessor.process_batch() groups RINEX files by date so that
product resolution (the expensive network step) happens only once per
unique date, then runs pdp3 for each file.
"""

from pathlib import Path
from pride_ppp import PrideProcessor

# --- 1. Configure the processor -----------------------------------------
processor = PrideProcessor(
    pride_dir=Path("/data/pride"),
    output_dir=Path("/data/output"),
)

# --- 2. Collect RINEX files ----------------------------------------------
rinex_dir = Path("/data/rinex")
rinex_files = sorted(rinex_dir.glob("*.rnx"))
print(f"Found {len(rinex_files)} RINEX files")

# --- 3. Batch process ----------------------------------------------------
# Sites are inferred from filenames.  Set max_workers > 1 for parallel
# pdp3 runs (each in its own temp directory, thread-safe).
results = processor.process_batch(rinex_files, max_workers=2)

# --- 4. Summarise results ------------------------------------------------
for r in results:
    status = "OK" if r.success else "FAIL"
    print(f"  [{status}] {r.rinex_path.name}  site={r.site}  date={r.date}")

succeeded = [r for r in results if r.success]
failed = [r for r in results if not r.success]
print(f"\n{len(succeeded)} succeeded, {len(failed)} failed")
