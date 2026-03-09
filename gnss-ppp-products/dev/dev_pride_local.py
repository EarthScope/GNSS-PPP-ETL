from gnss_ppp_products.resources.local import PrideDataSource
from gnss_ppp_products.resources._products import ProductType, TemporalCoverage
from datetime import datetime

PRIDE_ROOT = "/Volumes/DunbarSSD/Project/SeafloorGeodesy/SFGMain/Pride"
PRIDE_TABLE = "/Users/franklyndunbar/Project/SeaFloorGeodesy/PRIDE-PPPAR/table"

date = datetime(2025, 8, 15)
product_to_find = ProductType.SP3
regex = None  # Use default regex based on product type extensions

pride_source = PrideDataSource(PRIDE_ROOT, PRIDE_TABLE)
result = pride_source.query(date, product_to_find, regex)
print(result)