"""Quick test of build_query regex fallback behavior."""
import datetime
from gnss_ppp_products.resources.models.products import ProductFileQuery
from gnss_ppp_products.resources.models.rinex import RinexFileQuery

TPL = "{center}{version}{campaign}{quality}_{year}{doy}0000_{duration}_{interval}_ORB.SP3.*"
date = datetime.date(2025, 3, 10)

# Fully specified - exact filename
q = ProductFileQuery(content="ORB", format="SP3", center="WUM", quality="FIN", campaign="MGX")
q.date = date
print("Full:          ", q.build_query(TPL))

# Missing center & quality → regex fallback
q2 = ProductFileQuery(content="ORB", format="SP3")
q2.date = date
print("Partial:       ", q2.build_query(TPL))

# No date → date fields become regex
q3 = ProductFileQuery(center="WUM", quality="FIN")
print("No date:       ", q3.build_query(TPL))

# Nothing specified → pure regex
q4 = ProductFileQuery()
print("Empty:         ", q4.build_query(TPL))

# RINEX test
RTPL = "{station}{monument}{receiver}{region}_{data_source}_{year}{doy}0000_{duration}_{satellite_system}{content}.rnx.*"
rq = RinexFileQuery(station="BRDC", monument=0, receiver="0", region="IGN", satellite_system="M", content="N")
rq.date = date
print("RINEX full:    ", rq.build_query(RTPL))

rq2 = RinexFileQuery()
rq2.date = date
print("RINEX partial: ", rq2.build_query(RTPL))
