from gnss_ppp_products.resources.remote.ionosphere_resources import (
    WuhanGIMProductSource,
    CODEGIMProductSource,
    CDDISGIMProductSource,
    IonosphereAnalysisCenter,
    IonosphereProductQuality,
    IonosphereFileResult,
)

import datetime

date = datetime.date(2025, 1, 1)

wuhan_source = WuhanGIMProductSource()
wuhan_result: IonosphereFileResult = wuhan_source.query(
    date=date,
    center=IonosphereAnalysisCenter.ESA,
    quality=IonosphereProductQuality.RAPID,
)
print("Wuhan GIM result:", wuhan_result)

codegim_source = CODEGIMProductSource()
codegim_result: IonosphereFileResult = codegim_source.query(
    date=date,
    center=IonosphereAnalysisCenter.COD,
    quality=IonosphereProductQuality.RAPID,
)
print("CODE GIM result:", codegim_result)
cddisgim_source = CDDISGIMProductSource()
cddisgim_result: IonosphereFileResult = cddisgim_source.query(
    date=date,
    center=IonosphereAnalysisCenter.IGS,
    quality=IonosphereProductQuality.FINAL,
)
print("CDDIS GIM result:", cddisgim_result)

