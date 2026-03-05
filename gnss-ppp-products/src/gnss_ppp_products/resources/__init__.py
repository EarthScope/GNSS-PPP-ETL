
from .local_resources import PRIDEGNSSOutputResource
from .atmospheric_products import (
    AtmosphericProductQuality,
    AtmosphericFileResult,
    CODEGIMProductSource as CODEGIMProductSourceAtmospheric,  # Legacy alias
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
from .ionosphere_resources import (
    IonosphereProductQuality,
    IonosphereProductType,
    IonosphereFileResult,
    CODEGIMProductSource,
    CDDISGIMProductSource,
    WuhanGIMProductSource,
    IonosphereProductSource,
)
from .base import (
    ProductQuality,
    FTPFileResult,
    ConstellationCode,
)