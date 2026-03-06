
from .local_resources import PRIDEGNSSOutputResource
from .ionosphere_resources import (
    IonosphereProductQuality,
    IonosphereProductType,
    IonosphereFileResult,
    IonosphereAnalysisCenter,
    IonosphereProductSource,  # Alias for IonosphereAnalysisCenter
    CODEGIMProductSource,
    CDDISGIMProductSource,
    WuhanGIMProductSource,
)
from .troposphere_resources import (
    AtmosphericProductQuality,
    AtmosphericFileResult,
    VMFHTTPProductSource,
  
)
from .orography_resources import (
    OrographyGridResolution,
    OrographyFileResult,
    VMFOrographyHTTPSource,
)
from .orbit_clock_resources import (
    WuhanFTPProductSource,
    CLSIGSFTPProductSource,
    KASIFTPProductSource,
    CDDISFTPProductSource
)
from .navigation_resources import (
    WuhanNavFileFTPProductSource,
    CLSIGSNavFileFTPProductSource,
    CDDISNavFileFTPProductSource,
)
from .reference_tables import (
    WuhanProductTableFTPSource,
    CDDISProductTableFTPSource,
)
from .antennae_resources import (
    IGSAntexReferenceFrameType,
    AntexFileResult,
    NGSNOAAAntexHTTPSource,
    IGSAntexHTTPSource,
    determine_frame,
    AstroInstMGEXAntexFTPSource
)
from .base import (
    ProductQuality,
    FTPFileResult,
    ConstellationCode,
    ResourceQueryResult,
    DownloadProtocol,
)