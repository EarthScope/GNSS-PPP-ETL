
from typing import List, Optional


from ..assets.products import ProductFileQuery
from ..assets.rinex import RinexFileQuery


from .ftp import ftp_protocol
from .http import http_protocol

def process_product_query(product_query:ProductFileQuery) -> Optional[List[ProductFileQuery]]:
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
                return out
        case "HTTP" | "HTTPS":
            try:
                matches = http_protocol(
                    httpserver=product_query.server.hostname,
                    directory=product_query.directory,
                    filequery=product_query.filename
                )
                for match in matches:
                    updated_query = product_query.copy(update={"filename": match})
                    if hasattr(updated_query,"load_date_from_filename"):
                        updated_query.load_date_from_filename()

                    print(updated_query.model_dump_json(indent=2))
                    out.append(updated_query)
            except Exception as e:
                print(f"Error querying HTTP: {e}")
                return out
    return out