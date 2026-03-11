from gnss_ppp_products.resources.resource import GNSSCenterConfig
from datetime import datetime
from gnss_ppp_products.resources.remote.utils import ftp_list_directory,find_best_match_in_listing
from pathlib import Path

config_dir = Path(
    "/Users/franklyndunbar/Project/SeaFloorGeodesy/GNSS-PPP-ETL/gnss-ppp-products/src/gnss_ppp_products/resources/config/"
)


wuhan = GNSSCenterConfig.from_yaml(config_dir / "wuhan.yaml")

date = datetime(2025, 1, 15)
# products = wuhan.list_products(date)

# for product in products:

#     listing = ftp_list_directory(
#         ftpserver=product.server.hostname,
#         directory=product.directory
#     )
#     #print(listing)
#     best_match = find_best_match_in_listing(listing, product.filename)
#     if best_match:
#         print(product.model_dump_json(indent=2))
#         print(f"Best match for {product.filename}: {best_match}")

cddis = GNSSCenterConfig.from_yaml(config_dir / "cddis.yaml")
products = cddis.build_product_queries(date)
for product in products:

    listing = ftp_list_directory(
        ftpserver=product.server.hostname,
        directory=product.directory,
        use_tls=True
    )
    #print(listing)
    for best_match in find_best_match_in_listing(listing, product.filename):
        print(product.model_dump_json(indent=2))
        print(f"Best match for {product.filename}: {best_match}")