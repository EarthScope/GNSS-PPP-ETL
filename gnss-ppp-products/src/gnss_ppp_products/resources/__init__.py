
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
from .atmospheric_products import (
    AtmosphericProductQuality,
    AtmosphericFileResult,
    VMFProductSource,
    AtmosphericProductSource,
)
from .orbit_clock_products import (
    WuhanFTPProductSource,
    CLSIGSFTPProductSource,
    KASDIFTPProductSource,
    CDDISFTPProductSource
)
from .navigation_products import (
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
)