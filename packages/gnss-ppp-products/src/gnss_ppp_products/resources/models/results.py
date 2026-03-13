"""
Unified result dataclass re-exports.

Every remote resource module defines a specialization of ``ResourceQueryResult``.
This module re-exports them all from a single location for convenience.
"""

from ..remote.base import (
    ResourceQueryResult,
    FTPFileResult,
    DownloadProtocol,
    ProductQuality,
)
from ..remote.ionosphere_resources import (
    IonosphereFileResult,
    IonosphereProductQuality,
    IonosphereProductType,
)
from ..remote.troposphere_resources import (
    AtmosphericFileResult,
    AtmosphericProductQuality,
)
from ..remote.antennae_resources import (
    AntexFileResult,
    IGSAntexReferenceFrameType,
)
from ..remote.orography_resources import (
    OrographyFileResult,
    OrographyGridResolution,
)
from ..remote.leo_resources import (
    GRACEFileResult,
    GRACEMission,
)
from ..remote.reference_tables import (
    ReferenceTableResult,
    ReferenceTableType,
)
