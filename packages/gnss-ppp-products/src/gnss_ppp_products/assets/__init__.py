from .center import (
    GNSSCenterConfig,
    RinexFileQuery,
    ProductFileQuery,
    AntennaeFileQuery,
    TroposphereFileQuery,
    OrographyFileQuery,
    LEOFileQuery,
    ReferenceTableFileQuery,
)
from pathlib import Path
config_files = Path(__file__).parent / "config_files"

WuhanCenterConfig = GNSSCenterConfig.from_yaml(config_files/"wuhan.yaml")
IGSCenterConfig = GNSSCenterConfig.from_yaml(config_files/"igs.yaml")
CDDISCenterConfig = GNSSCenterConfig.from_yaml(config_files/"cddis.yaml")

__all__ = [
    "GNSSCenterConfig",
    "RinexFileQuery",
    "ProductFileQuery",
    "AntennaeFileQuery",
    "TroposphereFileQuery",
    "OrographyFileQuery",
    "LEOFileQuery",
    "ReferenceTableFileQuery",
    "WuhanCenterConfig",
    "IGSCenterConfig",
    "CDDISCenterConfig",
]