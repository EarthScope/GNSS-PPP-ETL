from gnss_ppp_products.resources import ( 
    WuhanNavFileFTPProductSource, CLSIGSNavFileFTPProductSource,CDDISNavFileFTPProductSource,
    ConstellationCode, FTPFileResult
)
import datetime

source = CDDISNavFileFTPProductSource()
date = datetime.date(2025, 1, 1)
result = source.query(
    product="rinex_3_nav",
    date=date
)
print(result)