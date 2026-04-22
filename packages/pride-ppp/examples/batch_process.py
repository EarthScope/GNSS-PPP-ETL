"""Batch-process multiple RINEX files through PRIDE-PPPAR.

PrideProcessor.process_batch() groups RINEX files by date so that
product resolution (the expensive network step) happens only once per
unique date, then runs pdp3 for each file.
"""

import logging
from pathlib import Path

from pride_ppp import PrideProcessor

logging.basicConfig(level=logging.INFO)

# --- 1. Configure the processor -----------------------------------------
processor = PrideProcessor(
    pride_dir=Path(
        "/Volumes/DunbarSSD/Project/SeafloorGeodesy/SFGMain/Pride"
    ),  # update for your environment
    output_dir=Path(
        "/Volumes/DunbarSSD/Project/SeafloorGeodesy/SFGMain/cascadia-gorda/GCC1/2022_A_1065/intermediate"
    ),  # update for your environment
)

# --- 2. Collect RINEX files ----------------------------------------------
rinex_dir = Path(
    "/Volumes/DunbarSSD/Project/SeafloorGeodesy/SFGMain/cascadia-gorda/GCC1/2022_A_1065/intermediate"
)  # update for your environment
rinex_files = sorted(rinex_dir.glob("*.22o"))
logging.info(f"Found {len(rinex_files)} RINEX files")

# --- 3. Batch process ----------------------------------------------------
# Sites are inferred from filenames.  Set max_workers > 1 for parallel
# pdp3 runs (each in its own temp directory, thread-safe).
results = processor.process_batch(rinex_files, max_workers=15, override=True)

# --- 4. Summarise results ------------------------------------------------
for r in results:
    status = "OK" if r.success else "FAIL"
    logging.info(f"  [{status}] {r.rinex_path.name}  site={r.site}  date={r.date}")

succeeded = [r for r in results if r.success]
failed = [r for r in results if not r.success]
logging.info(f"\n{len(succeeded)} succeeded, {len(failed)} failed")
