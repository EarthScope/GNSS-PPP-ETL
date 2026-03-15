
import datetime


from gnss_ppp_products.assets.query_spec import QuerySpecRegistry, ProductQuery
from gnss_ppp_products.assets.remote_resource_spec import RemoteResourceRegistry
from gnss_ppp_products.assets.local_resource_spec import LocalResourceRegistry

# ── target date ────────────────────────────────────────────────────
date = datetime.date(2025, 1, 15)

q = ProductQuery(date=date)
q.narrow(spec="ATTATX")
for result in q.results:
   
    print(result)