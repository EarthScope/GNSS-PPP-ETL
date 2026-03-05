from gnss_ppp_products.resources import (
    IGSAntexHTTPSource,
    NGSNOAAAntexHTTPSource,
)
import datetime

source = IGSAntexHTTPSource()
date = datetime.date(2025, 1, 1)
result = source.query(date=date)
print(result)

result_current = source.query(date=datetime.datetime.today().astimezone(datetime.timezone.utc))
print(result_current)

source_ngs = NGSNOAAAntexHTTPSource()
result_ngs = source_ngs.query(date=date)
print(result_ngs)