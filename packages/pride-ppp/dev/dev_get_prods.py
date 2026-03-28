"""Resolve GNSS products for RINEX files and run PRIDE-PPPAR processing."""

import logging
from pathlib import Path

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)-8s %(name)s — %(message)s",
)

from pride_ppp import PrideProcessor, PrideCLIConfig

pride_dir = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/SFGMain/Pride")
output_dir = Path(
    "/Volumes/DunbarSSD/Project/SeafloorGeodesy/SFGMain/cascadia-gorda/NCC1/2025_A_1126/intermediate"
)

processor = PrideProcessor(
    pride_dir=pride_dir,
    output_dir=output_dir,
    cli_config=PrideCLIConfig(),
)

rinex_files = list(output_dir.glob("*.25o"))
for rinex_file in rinex_files:
    result = processor.process(rinex_file, site="NCC1")
    print(f"{rinex_file.name}: success={result.success}, kin={result.kin_path}")
