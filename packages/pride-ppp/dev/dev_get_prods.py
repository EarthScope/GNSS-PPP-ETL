import logging
from pathlib import Path

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)-8s %(name)s — %(message)s",
)

from pride_ppp import get_gnss_products

rinex_path = Path(
    "/Volumes/DunbarSSD/Project/SeafloorGeodesy/SFGMain/cascadia-gorda/NCC1/2025_A_1126/intermediate/NCC12500.25o"
)
pride_dir = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/SFGMain/Pride")

config_path = get_gnss_products(rinex_path=rinex_path, pride_dir=pride_dir)
print(f"Config path: {config_path}")
