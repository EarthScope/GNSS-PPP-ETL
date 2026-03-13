"""
Backward-compatible re-export shim.

All models have been moved to the ``models`` sub-package:
    - models.server    → Server, ServerProtocol, TimeIndex
    - models.products  → ProductFileQuery, config schemas, RemoteProductAddress
    - models.rinex     → RinexFileQuery, RINEX config schemas
    - models.config    → GNSSCenterConfig

Existing ``from .resource import X`` imports continue to work.
"""

# Server models
from .models.server import Server, ServerProtocol

# Product models
from ..assets.products.products import (
    ProductFileQuery,
    QualityConfig,
    CampaignConfig,
    SampleIntervalConfig,
    DurationConfig,
    ProductConfig,
    RemoteProductAddress,
)

# RINEX models
from .models.rinex import (
    RinexFileQuery,
    StationConfig,
    MonumentConfig,
    ReceiverConfig,
    RegionConfig,
    SatelliteSystemConfig,
    RinexConfig,
)

# Top-level center config
from .models.config import GNSSCenterConfig