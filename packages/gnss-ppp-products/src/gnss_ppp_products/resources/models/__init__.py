"""
GNSS PPP Product Models
=======================

Pydantic BaseModels organized by domain:
    - server: Server connectivity models
    - products: IGS product filename queries and YAML config schemas
    - rinex: RINEX filename queries and RINEX-specific config schemas
    - config: Top-level center configuration (GNSSCenterConfig)
    - results: Unified result dataclass re-exports
"""

from .server import Server, ServerProtocol
from ...assets.products.products import (
    ProductFileQuery,
    QualityConfig,
    CampaignConfig,
    SampleIntervalConfig,
    DurationConfig,
    ProductConfig,
    RemoteProductAddress,
)
from .rinex import (
    RinexFileQuery,
    StationConfig,
    MonumentConfig,
    ReceiverConfig,
    RegionConfig,
    SatelliteSystemConfig,
    RinexConfig,
)
from .config import GNSSCenterConfig
from .results import (
    ResourceQueryResult,
    FTPFileResult,
    IonosphereFileResult,
    AtmosphericFileResult,
    AntexFileResult,
    OrographyFileResult,
    GRACEFileResult,
    ReferenceTableResult,
)
