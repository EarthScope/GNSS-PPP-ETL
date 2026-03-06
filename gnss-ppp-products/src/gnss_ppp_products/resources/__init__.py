
from .remote.local_resources import PRIDEGNSSOutputResource
from .remote.ionosphere_resources import (
    IonosphereProductQuality,
    IonosphereProductType,
    IonosphereFileResult,
    IonosphereAnalysisCenter,
    IonosphereProductSource,  # Alias for IonosphereAnalysisCenter
    CODEGIMProductSource,
    CDDISGIMProductSource,
    WuhanGIMProductSource,
)
from .remote.troposphere_resources import (
    AtmosphericProductQuality,
    AtmosphericFileResult,
    VMFHTTPProductSource,
  
)
from .remote.orography_resources import (
    OrographyGridResolution,
    OrographyFileResult,
    VMFOrographyHTTPSource,
)
from .remote.orbit_clock_resources import (
    WuhanFTPProductSource,
    CLSIGSFTPProductSource,
    KASIFTPProductSource,
    CDDISFTPProductSource,
    ProductTypes as OrbitClockProductTypes,
    OrbitClockFTPProductSource,
)
from .remote.navigation_resources import (
    WuhanNavFileFTPProductSource,
    CLSIGSNavFileFTPProductSource,
    CDDISNavFileFTPProductSource,
)
from .remote.reference_tables import (
    ReferenceTableType,
    ReferenceTableResult,
    WuhanProductTableFTPSource,
    CDDISProductTableFTPSource,
)
from .remote.antennae_resources import (
    IGSAntexReferenceFrameType,
    AntexFileResult,
    NGSNOAAAntexHTTPSource,
    IGSAntexHTTP,
    IGSAntexHTTP as IGSAntexHTTPSource,  # Alias for backward compatibility
    determine_frame,
    AstroInstMGEXAntexFTPSource
)
from .remote.leo_resources import (
    GRACEMission,
    GRACEInstrument,
    GRACEFileResult,
    GFZGRACEFTPProductSource,
)
from .remote.base import (
    ProductQuality,
    FTPFileResult,
    ConstellationCode,
    ResourceQueryResult,
    DownloadProtocol,
)

# Local resource imports
from .local import (
    DirectoryStrategy,
    ProductCategory,
    LocalDirectoryBuilder,
    LocalFileFinder,
    LocalFileResult,
    LocalOrbitClockResult,
    LocalNavigationResult,
    LocalAntexResult,
    LocalAtmosphericResult,
    LocalProductSource,
    LocalDataSource,
    PrideDataSource,
)