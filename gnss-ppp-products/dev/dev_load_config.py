import re
from typing import List, Optional, Union
from gnss_ppp_products.resources.models.products import ProductFileQuery
from gnss_ppp_products.resources.models.rinex import RinexFileQuery
from gnss_ppp_products.resources.resource import GNSSCenterConfig
from datetime import datetime
from gnss_ppp_products.resources.remote.utils import ftp_list_directory,find_best_match_in_listing
from gnss_ppp_products.server import ftp,http
from pathlib import Path



def ftp_protocol(
    ftpserver: str,
    directory: str,
    filename: str,
    use_tls: bool = False
) -> List[str]:
        try:
            listing = ftp.ftp_list_directory(ftpserver, directory,use_tls=use_tls)
        except Exception as e:
            print(f"Error listing FTP directory {ftpserver}/{directory}: {e}")
            return []
        matches = list(ftp.ftp_find_best_match_in_listing(listing, filename))
        if not matches:
            print(f"No matches found for {filename} in FTP directory {ftpserver}/{directory}")
        return matches

def http_protocol(
    httpserver:str,
    directory:str,
    filequery:str
) -> List[str]:
    out = []
    listing = http.http_list_directory(
        server=httpserver,
        directory=directory
    )
    for filename in http.extract_filenames_from_html(listing):
        if re.match(filequery, filename):
    
            print(f"Best match for {filequery}: {filename}")
            out.append(filename)
    return filename


def process_product_query(product_query) -> Optional[List[Union[ProductFileQuery, RinexFileQuery]]]:
    out = []
    match product_query.server.protocol.value.upper():
        case "FTP" | "FTPS":
            try:
                best_match = ftp_protocol(
                    ftpserver=product_query.server.hostname,
                    directory=product_query.directory,
                    filename=product_query.filename,
                    use_tls=(product_query.server.protocol.value.upper() == "FTPS")
                )
                for match in best_match:
                    updated_query = product_query.copy(update={"filename": match})
                    print(updated_query.model_dump_json(indent=2))
                    out.append(updated_query)
            except Exception as e:
                print(f"Error querying FTP: {e}")
        case "HTTP" | "HTTPS":
            try:
                matches = http_protocol(
                    httpserver=product_query.server.hostname,
                    directory=product_query.directory,
                    filequery=product_query.filename
                )
                for match in matches:
                    updated_query = product_query.copy(update={"filename": match})
                    print(updated_query.model_dump_json(indent=2))
                    out.append(updated_query)
            except Exception as e:
                print(f"Error querying HTTP: {e}")
    return out

config_dir = Path(
    "/Users/franklyndunbar/Project/SeaFloorGeodesy/GNSS-PPP-ETL/gnss-ppp-products/src/gnss_ppp_products/resources/config/"
)


date = datetime(2025, 1, 15)
wuhan = GNSSCenterConfig.from_yaml(config_dir / "wuhan.yaml")
cddis = GNSSCenterConfig.from_yaml(config_dir / "cddis.yaml")
igs = GNSSCenterConfig.from_yaml(config_dir / "igs.yaml")
found_products = []
for center in [wuhan, cddis, igs]:
    for product in center.build_product_queries(date):
        found_products.extend(process_product_query(product))
    

    for rnx in center.build_rinex_queries(date):
        found_products.extend(process_product_query(rnx))

with open("found_products.json", "w") as f:
    import json
    json.dump([p.model_dump_json() for p in found_products], f, indent=2)
