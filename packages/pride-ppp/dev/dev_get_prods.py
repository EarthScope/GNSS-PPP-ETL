"""Resolve GNSS products for a RINEX file and generate a PRIDE config."""

import datetime
import logging
from pathlib import Path
from typing import override

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)-8s %(name)s — %(message)s",
)

from pride_ppp import get_gnss_products, rinex_to_kin,PrideCLIConfig

pride_dir = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/SFGMain/Pride")

# Option 1: resolve from a RINEX file
rinex_dir = Path(
    "/Volumes/DunbarSSD/Project/SeafloorGeodesy/SFGMain/cascadia-gorda/NCC1/2025_A_1126/intermediate"
)
rinex_files = rinex_dir.glob("*.25o")
for rinex_file in rinex_files:
    config_path = get_gnss_products(rinex_path=rinex_file, pride_dir=pride_dir)
    print(f"Config path for {rinex_file.name}: {config_path}")
    cli_config = PrideCLIConfig(pride_configfile_path=Path(config_path))
    rinex_to_kin(
        site="NCC1",
        source=rinex_file, pridedir=pride_dir, writedir=rinex_dir, pride_cli_config=cli_config,override=True)
