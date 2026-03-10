import datetime
import re
from typing import List, Optional

from gnss_ppp_products.resources.remote.antennae_resources import _extract_filenames_from_html
import requests

from ..resources.resource import RemoteProductAddress,ServerProtocol
from ..resources.products import ProductType, TemporalCoverage,SampleInterval,ProductQuality
from ..resources import RESOURCE_COLLECTIONS
from gnss_ppp_products.resources.remote.utils import ftp_list_directory,find_best_match_in_listing

def query(
        date: datetime.datetime | datetime.date,
        product_type: ProductType = None,
        product_quality: Optional[ProductQuality] = None,
        sample_interval: Optional[SampleInterval] = None,
        temporal_coverage: Optional[TemporalCoverage] = None,
        source: Optional[str] = None
):
    
    # Solve for a matching solution based on the provided parameters
    # For simplicity, we will just search through all products and find the best match 
    # based on the provided parameters. In a real implementation, we would likely want to optimize this search.
    valid_candidates: List[RemoteProductAddress] = []

    for resource_name, resource in RESOURCE_COLLECTIONS.items():
        if source and resource_name != source:
            continue
        products: List[RemoteProductAddress] = resource.list_products(
            date,
            product_type=product_type,
            product_quality=product_quality,
            sample_interval=sample_interval,
            temporal_coverage=temporal_coverage
        )
        
        for product in products:
            if product_type and product.type != product_type:
                continue
            match product.server.protocol:
                case ServerProtocol.FTP:
                    try:
                        listing = ftp_list_directory(product.server.hostname, product.directory)
                    except Exception as e:
                        print(f"Error listing FTP directory {product.server.hostname}/{product.directory}: {e}")
                        continue
                    best_match = find_best_match_in_listing(listing, product.filename)
                    if best_match:
                        product.filename = best_match  # Update the product filename to the best match found in the listing
                        valid_candidates.append(product
                        )
                case ServerProtocol.HTTP | ServerProtocol.HTTPS:
                    try:
                        response = requests.get(f"{product.server.hostname}/{product.directory}")
                        response.raise_for_status()
                        # Parse HTML to extract filenames
                        filenames = _extract_filenames_from_html(response.text)
                        matches = [f for f in filenames if re.match(product.filename, f)]
                        if matches:
                            valid_candidates.append(RemoteProductAddress(
                                server=product.server,
                                directory=product.directory,
                                filename=matches[0],  # Assuming the first match is the best match; this can be improved
                                file_id=product.file_id,
                                type=product.type,
                                quality=product.quality,
                                solution=product.solution
                            )
                            )
                    except Exception as e:
                        # Directory listing not available - use the filename pattern directly
                        # Remove regex escapes to get actual filename (e.g., "ngs20\.atx" -> "ngs20.atx")
                        actual_filename = product.filename.replace('\\', '')
                        print(f"Directory listing not available for {product.server.hostname}/{product.directory}, using direct filename: {actual_filename}")
                        valid_candidates.append(RemoteProductAddress(
                            server=product.server,
                            directory=product.directory,
                            filename=actual_filename,
                            file_id=product.file_id,
                            type=product.type,
                            quality=product.quality,
                            solution=product.solution
                        )
                        )

    # Sort candidates by quality and return the best one
    sort_order = [ProductQuality.FINAL, ProductQuality.RAPID, ProductQuality.ULTRA_RAPID, ProductQuality.REAL_TIME, ProductQuality.PREDICTED]
    valid_candidates.sort(key=lambda x: sort_order.index(x.quality) if x.quality in sort_order else len(sort_order))
    return valid_candidates 