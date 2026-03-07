from gnss_ppp_products.resources.resource import GNSSCenterConfig
from datetime import datetime
def load_wuhan_config() -> GNSSCenterConfig:
    """Load Wuhan University configuration from YAML."""
    return GNSSCenterConfig.from_yaml("/Users/franklyndunbar/Project/SeaFloorGeodesy/GNSS-PPP-ETL/gnss-ppp-products/src/gnss_ppp_products/resources/config/wuhan.yaml")

test = load_wuhan_config()
print(test)

date = datetime(2025, 1, 15)
products = test.list_products(date)
print(products)