#from gnss_ppp_products.queries.remote import query,ProductQuality,SampleInterval,TemporalCoverage,ProductType
from datetime import datetime
from typing import List
from gnss_ppp_products.data_query import (
    query, ProductQuality, SampleInterval, TemporalCoverage, ProductType,RemoteProductAddress
)
date = datetime(2025, 1, 15)

SOURCE = "WUHAN"

results: List[RemoteProductAddress] = query(
    source=SOURCE,
    product_quality=ProductQuality.FINAL,
    product_type=ProductType.SP3,   
  
    date=date
)

for results in results:
    print(f"hostname: {results.server.hostname}, directory: {results.directory}, filename: {results.filename},")
    print(f"product_type: {results.type}, quality: {results.quality}")