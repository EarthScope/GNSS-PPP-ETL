from gnss_ppp_products.resources.troposphere_resources import (
    VMFHTTPProductSource,
    AtmosphericProductQuality,
    AtmosphericFileResult,
)
import datetime
date = datetime.date(2025, 1, 1)
source = VMFHTTPProductSource()
result = source.query(
    date=date,
    resolution="1x1",
    product="VMF3",
    hour='H00'
)
print(result.url if result else "No product found")
