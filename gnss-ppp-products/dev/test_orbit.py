from gnss_ppp_products.resources.orbit_clock_resources import (
    WuhanDirectorySourceFTP,
    CLSIGSDirectorySourceFTP,
    ProductTypes,
)

import datetime

date = datetime.date(2025, 1, 1)

wuhan_source = WuhanDirectorySourceFTP()
wuhan_orbit_dir = wuhan_source.directory(product=ProductTypes.ORBIT, date=date)
print("Wuhan Orbit Directory:", wuhan_orbit_dir)