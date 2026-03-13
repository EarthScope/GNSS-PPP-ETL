#from gnss_ppp_products.queries.remote import query,ProductQuality,SampleInterval,TemporalCoverage,ProductType
from datetime import datetime
from typing import List
from gnss_ppp_products.data_query import (
    query, ProductQuality, SampleInterval, TemporalCoverage, ProductType,RemoteProductAddress
)
date = datetime(2025, 1, 15)

SOURCES = ["WUHAN", "CDDIS", "IGS", "NGS", "ESA", "CODE"]
PRODUCTS = [ProductType.ATX,ProductType.SP3,ProductType.CLK,ProductType.RINEX3_NAV]

SOURCES = ["IGS"]
PRODUCTS = [ProductType.ATX]
for SOURCE in SOURCES:
    for PRODUCT in PRODUCTS:
   
        print(f"Querying for source: {SOURCE}, product type: {PRODUCT}")
        results: List[RemoteProductAddress] = query(
            center=SOURCE,
            product_quality=ProductQuality.FINAL,
            product_type=PRODUCT,
            date=date
        )

        for results in results:
            print(f"hostname: {results.server.hostname}, directory: {results.directory}, filename: {results.filename},")
            print(f"product_type: {results.type}, quality: {results.quality}\n")
        print(f"{'='*80}\n")
