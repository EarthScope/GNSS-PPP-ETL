from gnss_ppp_products.resources import ( 
    WuhanNavFileFTPProductSource, CLSIGSNavFileFTPProductSource,
    ConstellationCode, FTPFileResult
)
import datetime

source = WuhanNavFileFTPProductSource()
date = datetime.date(2010, 1, 1)
result = source.query(
    product="rinex_2_nav",
    date=date,
    constellation=ConstellationCode.GPS,
)
print(result)