from pydantic import BaseModel

class WuhanProductTableFTPSource(BaseModel):
    ftpserver: str = "ftp://igs.gnsswhu.cn"
    _leap_seconds: str = "pub/whu/phasebias/table/leap.sec"
    _sat_parameters: str = "pub/whu/phasebias/table/sat_parameters"

    def leap_sec(self) -> str:
        return self.ftpserver + "/" + self._leap_seconds
    
    def sat_parameters(self) -> str:
        return self.ftpserver + "/" + self._sat_parameters
    
class CDDISProductTableFTPSource(BaseModel):
    ftpserver: str = "ftp://gdc.cddis.eosdis.nasa.gov"
    _leap_seconds: str = "pub/products/iers/leapsec.dat"

    def leap_sec(self) -> str:
        return self.ftpserver + "/" + self._leap_seconds
    