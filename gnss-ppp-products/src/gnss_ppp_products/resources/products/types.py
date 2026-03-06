"""
GNSS Product Type Definitions
=============================

Exhaustive collection of all product types downloaded by remote resources.
Provides a unified type system for product classification, temporal coverage,
quality levels, and data categories.

Product Categories
------------------
    - **Orbit/Clock**: Precise satellite orbits, clocks, biases, ERPs
    - **Navigation**: Broadcast ephemeris (RINEX 2/3)
    - **Ionosphere**: Global Ionosphere Maps (GIM/IONEX)
    - **Troposphere**: Vienna Mapping Functions (VMF1/VMF3)
    - **Antenna**: Phase center calibrations (ANTEX)
    - **Reference**: Leap seconds, satellite parameters
    - **Orography**: Terrain height grids
    - **LEO**: Low Earth Orbit satellite products (GRACE)

Usage
-----
    >>> from gnss_ppp_products.resources.products import ProductType, ProductCategory
    >>> 
    >>> # Check product properties
    >>> ProductType.SP3.category  # ProductCategory.ORBIT_CLOCK
    >>> ProductType.SP3.temporal_coverage  # TemporalCoverage.DAILY
    >>>
    >>> # Get all products in a category
    >>> ProductType.by_category(ProductCategory.ORBIT_CLOCK)
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional, Set


# ---------------------------------------------------------------------------
# Temporal and Quality Classifications
# ---------------------------------------------------------------------------


class TemporalCoverage(str, Enum):
    """Temporal coverage/cadence of products."""
    
    EPOCH = "epoch"          # Non-regular intervals (e.g., new solution release)
    HOURLY = "hourly"        # Hourly products (e.g., VMF grids)  
    DAILY = "daily"          # Daily products (most common)
    GPSWEEKLY = "gpsweekly"  # GPS week-based products
    YEARLY = "yearly"        # Annual products (e.g., reference frames)
    STATIC = "static"        # Static files (rarely updated)


class ProductQuality(str, Enum):
    """Quality/latency levels for products."""
    
    FINAL = "final"        # Post-processed, highest accuracy (~2 week latency)
    RAPID = "rapid"        # Near real-time (~1 day latency)
    ULTRA_RAPID = "ultra"  # Ultra-rapid products (~3-6 hour latency)
    REAL_TIME = "rts"      # Real-time streaming
    PREDICTED = "predicted"  # Forecast/predicted products


class ProductCategory(str, Enum):
    """High-level product categories."""
    
    ORBIT_CLOCK = "orbit_clock"   # Precise orbits, clocks, biases
    NAVIGATION = "navigation"     # Broadcast ephemeris
    IONOSPHERE = "ionosphere"     # Ionospheric corrections
    TROPOSPHERE = "troposphere"   # Tropospheric corrections
    ANTENNA = "antenna"           # Antenna calibrations
    REFERENCE = "reference"       # Reference tables (leap sec, etc.)
    OROGRAPHY = "orography"       # Terrain/elevation data
    LEO = "leo"                   # LEO satellite products


class FileFormat(str, Enum):
    """Common file formats for GNSS products."""
    
    SP3 = "sp3"        # SP3 orbit format
    CLK = "clk"        # RINEX clock format
    RINEX_NAV = "rnx"  # RINEX navigation
    IONEX = "ionex"    # Ionosphere map exchange
    SINEX = "snx"      # Solution INdependent EXchange
    ANTEX = "atx"      # Antenna exchange format
    BIAS = "bia"       # Bias-SINEX format
    ERP = "erp"        # Earth rotation parameters
    VMF = "vmf"        # Vienna mapping functions
    ASCII = "txt"      # Plain text


# ---------------------------------------------------------------------------
# Product Type Definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProductTypeInfo:
    """
    Metadata for a product type.
    
    Attributes
    ----------
    name : str
        Short identifier (e.g., "SP3", "CLK").
    description : str
        Human-readable description.
    category : ProductCategory
        High-level category.
    temporal_coverage : TemporalCoverage
        Typical temporal coverage/cadence.
    file_formats : tuple[FileFormat, ...]
        Expected file formats.
    extensions : tuple[str, ...]
        Common file extensions.
    qualities : tuple[ProductQuality, ...]
        Available quality levels.
    """
    
    name: str
    description: str
    category: ProductCategory
    temporal_coverage: TemporalCoverage
    file_formats: tuple = field(default_factory=tuple)
    extensions: tuple = field(default_factory=tuple)
    qualities: tuple = field(default_factory=tuple)


class ProductType(Enum):
    """
    Exhaustive enumeration of all GNSS product types.
    
    Each member contains a ProductTypeInfo with full metadata.
    
    Examples
    --------
    >>> ProductType.SP3.value.category
    <ProductCategory.ORBIT_CLOCK: 'orbit_clock'>
    >>> ProductType.SP3.value.temporal_coverage
    <TemporalCoverage.DAILY: 'daily'>
    """
    
    # -------------------------------------------------------------------------
    # Orbit/Clock Products
    # -------------------------------------------------------------------------
    
    SP3 = ProductTypeInfo(
        name="SP3",
        description="Precise satellite orbit positions in SP3 format",
        category=ProductCategory.ORBIT_CLOCK,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.SP3,),
        extensions=(".sp3", ".sp3.gz", ".SP3.gz"),
        qualities=(ProductQuality.FINAL, ProductQuality.RAPID, ProductQuality.ULTRA_RAPID),
    )
    
    CLK = ProductTypeInfo(
        name="CLK",
        description="Precise satellite and station clock corrections",
        category=ProductCategory.ORBIT_CLOCK,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.CLK,),
        extensions=(".clk", ".clk.gz", ".CLK.gz"),
        qualities=(ProductQuality.FINAL, ProductQuality.RAPID),
    )
    
    ERP = ProductTypeInfo(
        name="ERP",
        description="Earth Rotation Parameters (pole coordinates, UT1-UTC, LOD)",
        category=ProductCategory.ORBIT_CLOCK,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.ERP,),
        extensions=(".erp", ".erp.gz", ".ERP.gz"),
        qualities=(ProductQuality.FINAL, ProductQuality.RAPID),
    )
    
    BIAS = ProductTypeInfo(
        name="BIAS",
        description="Satellite differential code and phase biases (DCB/DSB/OSB)",
        category=ProductCategory.ORBIT_CLOCK,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.BIAS,),
        extensions=(".bia", ".bia.gz", ".BIA.gz", ".BSX.gz"),
        qualities=(ProductQuality.FINAL, ProductQuality.RAPID),
    )
    
    OBX = ProductTypeInfo(
        name="OBX",
        description="ORBEX satellite attitude quaternions and angular velocities",
        category=ProductCategory.ORBIT_CLOCK,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.ASCII,),
        extensions=(".obx", ".obx.gz", ".OBX.gz"),
        qualities=(ProductQuality.FINAL,),
    )
    
    SUM = ProductTypeInfo(
        name="SUM",
        description="Solution summary files",
        category=ProductCategory.ORBIT_CLOCK,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.ASCII,),
        extensions=(".sum", ".SUM.gz"),
        qualities=(ProductQuality.FINAL,),
    )
    
    # -------------------------------------------------------------------------
    # Navigation/Broadcast Products
    # -------------------------------------------------------------------------
    
    RINEX3_NAV = ProductTypeInfo(
        name="RINEX3_NAV",
        description="RINEX 3.x broadcast navigation (multi-GNSS)",
        category=ProductCategory.NAVIGATION,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.RINEX_NAV,),
        extensions=(".rnx", ".rnx.gz", "MN.rnx.gz"),
        qualities=(ProductQuality.FINAL,),
    )
    
    RINEX2_NAV_GPS = ProductTypeInfo(
        name="RINEX2_NAV_GPS",
        description="RINEX 2.x GPS broadcast navigation",
        category=ProductCategory.NAVIGATION,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.RINEX_NAV,),
        extensions=(".n", ".n.Z", ".n.gz"),
        qualities=(ProductQuality.FINAL,),
    )
    
    RINEX2_NAV_GLONASS = ProductTypeInfo(
        name="RINEX2_NAV_GLONASS",
        description="RINEX 2.x GLONASS broadcast navigation",
        category=ProductCategory.NAVIGATION,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.RINEX_NAV,),
        extensions=(".g", ".g.Z", ".g.gz"),
        qualities=(ProductQuality.FINAL,),
    )
    
    RINEX2_NAV_MIXED = ProductTypeInfo(
        name="RINEX2_NAV_MIXED",
        description="RINEX 2.x mixed GPS+GLONASS broadcast navigation",
        category=ProductCategory.NAVIGATION,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.RINEX_NAV,),
        extensions=(".p", ".p.Z", ".p.gz"),
        qualities=(ProductQuality.FINAL,),
    )
    
    # -------------------------------------------------------------------------
    # Ionosphere Products
    # -------------------------------------------------------------------------
    
    GIM = ProductTypeInfo(
        name="GIM",
        description="Global Ionosphere Map (VTEC grids in IONEX format)",
        category=ProductCategory.IONOSPHERE,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.IONEX,),
        extensions=(".i", ".I.Z", ".INX.gz", ".ionex"),
        qualities=(ProductQuality.FINAL, ProductQuality.RAPID, ProductQuality.PREDICTED),
    )
    
    # -------------------------------------------------------------------------
    # Troposphere Products
    # -------------------------------------------------------------------------
    
    VMF1 = ProductTypeInfo(
        name="VMF1",
        description="Vienna Mapping Functions 1 (troposphere mapping coefficients)",
        category=ProductCategory.TROPOSPHERE,
        temporal_coverage=TemporalCoverage.HOURLY,
        file_formats=(FileFormat.VMF,),
        extensions=(".H00", ".H06", ".H12", ".H18"),
        qualities=(ProductQuality.FINAL,),
    )
    
    VMF3 = ProductTypeInfo(
        name="VMF3",
        description="Vienna Mapping Functions 3 (improved troposphere mapping)",
        category=ProductCategory.TROPOSPHERE,
        temporal_coverage=TemporalCoverage.HOURLY,
        file_formats=(FileFormat.VMF,),
        extensions=(".H00", ".H06", ".H12", ".H18"),
        qualities=(ProductQuality.FINAL,),
    )
    
    # -------------------------------------------------------------------------
    # Antenna Calibration Products
    # -------------------------------------------------------------------------
    
    ATX_IGS = ProductTypeInfo(
        name="ATX_IGS",
        description="IGS ANTEX antenna phase center calibrations",
        category=ProductCategory.ANTENNA,
        temporal_coverage=TemporalCoverage.EPOCH,
        file_formats=(FileFormat.ANTEX,),
        extensions=(".atx",),
        qualities=(ProductQuality.FINAL,),
    )
    
    ATX_CODE_MGEX = ProductTypeInfo(
        name="ATX_CODE_MGEX",
        description="CODE MGEX ANTEX antenna calibrations (M14/M20)",
        category=ProductCategory.ANTENNA,
        temporal_coverage=TemporalCoverage.EPOCH,
        file_formats=(FileFormat.ANTEX,),
        extensions=(".ATX",),
        qualities=(ProductQuality.FINAL,),
    )
    
    ATX_NGS = ProductTypeInfo(
        name="ATX_NGS",
        description="NGS/NOAA ANTEX antenna calibrations",
        category=ProductCategory.ANTENNA,
        temporal_coverage=TemporalCoverage.EPOCH,
        file_formats=(FileFormat.ANTEX,),
        extensions=(".atx",),
        qualities=(ProductQuality.FINAL,),
    )
    
    # -------------------------------------------------------------------------
    # Reference Tables
    # -------------------------------------------------------------------------
    
    LEAP_SECONDS = ProductTypeInfo(
        name="LEAP_SECONDS",
        description="UTC-TAI leap second offset table",
        category=ProductCategory.REFERENCE,
        temporal_coverage=TemporalCoverage.STATIC,
        file_formats=(FileFormat.ASCII,),
        extensions=(".sec", ".dat"),
        qualities=(ProductQuality.FINAL,),
    )
    
    SAT_PARAMETERS = ProductTypeInfo(
        name="SAT_PARAMETERS",
        description="Satellite metadata and properties table",
        category=ProductCategory.REFERENCE,
        temporal_coverage=TemporalCoverage.STATIC,
        file_formats=(FileFormat.ASCII,),
        extensions=("",),
        qualities=(ProductQuality.FINAL,),
    )
    
    # -------------------------------------------------------------------------
    # Orography Products
    # -------------------------------------------------------------------------
    
    OROGRAPHY = ProductTypeInfo(
        name="OROGRAPHY",
        description="Ellipsoidal terrain height grids for VMF interpolation",
        category=ProductCategory.OROGRAPHY,
        temporal_coverage=TemporalCoverage.STATIC,
        file_formats=(FileFormat.ASCII,),
        extensions=("_1x1", "_5x5"),
        qualities=(ProductQuality.FINAL,),
    )
    
    # -------------------------------------------------------------------------
    # LEO Satellite Products (GRACE/GRACE-FO)
    # -------------------------------------------------------------------------
    
    GRACE_GNV = ProductTypeInfo(
        name="GRACE_GNV",
        description="GRACE/GRACE-FO GPS navigation Level-1B data",
        category=ProductCategory.LEO,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.ASCII,),
        extensions=(".dat.gz",),
        qualities=(ProductQuality.FINAL,),
    )
    
    GRACE_ACC = ProductTypeInfo(
        name="GRACE_ACC",
        description="GRACE/GRACE-FO accelerometer Level-1B data",
        category=ProductCategory.LEO,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.ASCII,),
        extensions=(".dat.gz",),
        qualities=(ProductQuality.FINAL,),
    )
    
    GRACE_SCA = ProductTypeInfo(
        name="GRACE_SCA",
        description="GRACE/GRACE-FO star camera Level-1B data",
        category=ProductCategory.LEO,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.ASCII,),
        extensions=(".dat.gz",),
        qualities=(ProductQuality.FINAL,),
    )
    
    GRACE_KBR = ProductTypeInfo(
        name="GRACE_KBR",
        description="GRACE/GRACE-FO K-Band ranging Level-1B data",
        category=ProductCategory.LEO,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.ASCII,),
        extensions=(".dat.gz",),
        qualities=(ProductQuality.FINAL,),
    )
    
    GRACE_LRI = ProductTypeInfo(
        name="GRACE_LRI",
        description="GRACE-FO Laser Ranging Interferometer Level-1B data",
        category=ProductCategory.LEO,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.ASCII,),
        extensions=(".dat.gz",),
        qualities=(ProductQuality.FINAL,),
    )
    
    GRACE_CLK = ProductTypeInfo(
        name="GRACE_CLK",
        description="GRACE/GRACE-FO clock Level-1B data",
        category=ProductCategory.LEO,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.ASCII,),
        extensions=(".dat.gz",),
        qualities=(ProductQuality.FINAL,),
    )
    
    GRACE_THR = ProductTypeInfo(
        name="GRACE_THR",
        description="GRACE/GRACE-FO thruster Level-1B data",
        category=ProductCategory.LEO,
        temporal_coverage=TemporalCoverage.DAILY,
        file_formats=(FileFormat.ASCII,),
        extensions=(".dat.gz",),
        qualities=(ProductQuality.FINAL,),
    )
    
    # -------------------------------------------------------------------------
    # Class Methods
    # -------------------------------------------------------------------------
    
    @classmethod
    def by_category(cls, category: ProductCategory) -> List["ProductType"]:
        """
        Get all product types in a given category.
        
        Parameters
        ----------
        category : ProductCategory
            The category to filter by.
            
        Returns
        -------
        List[ProductType]
            All product types belonging to that category.
        """
        return [pt for pt in cls if pt.value.category == category]
    
    @classmethod
    def by_temporal_coverage(cls, coverage: TemporalCoverage) -> List["ProductType"]:
        """Get all product types with a given temporal coverage."""
        return [pt for pt in cls if pt.value.temporal_coverage == coverage]
    
    @classmethod
    def daily_products(cls) -> List["ProductType"]:
        """Get all daily products."""
        return cls.by_temporal_coverage(TemporalCoverage.DAILY)
    
    @classmethod
    def static_products(cls) -> List["ProductType"]:
        """Get all static (rarely updated) products."""
        return cls.by_temporal_coverage(TemporalCoverage.STATIC)
    
    @property
    def info(self) -> ProductTypeInfo:
        """Alias for .value to access ProductTypeInfo."""
        return self.value
    
    @property
    def category(self) -> ProductCategory:
        """Shortcut for .value.category."""
        return self.value.category
    
    @property
    def temporal_coverage(self) -> TemporalCoverage:
        """Shortcut for .value.temporal_coverage."""
        return self.value.temporal_coverage


# ---------------------------------------------------------------------------
# Convenience Collections
# ---------------------------------------------------------------------------

# All orbit/clock product types
ORBIT_CLOCK_PRODUCTS: Set[ProductType] = {
    ProductType.SP3,
    ProductType.CLK,
    ProductType.ERP,
    ProductType.BIAS,
    ProductType.OBX,
    ProductType.SUM,
}

# All navigation product types
NAVIGATION_PRODUCTS: Set[ProductType] = {
    ProductType.RINEX3_NAV,
    ProductType.RINEX2_NAV_GPS,
    ProductType.RINEX2_NAV_GLONASS,
    ProductType.RINEX2_NAV_MIXED,
}

# All atmospheric product types
ATMOSPHERIC_PRODUCTS: Set[ProductType] = {
    ProductType.GIM,
    ProductType.VMF1,
    ProductType.VMF3,
}

# All antenna product types
ANTENNA_PRODUCTS: Set[ProductType] = {
    ProductType.ATX_IGS,
    ProductType.ATX_CODE_MGEX,
    ProductType.ATX_NGS,
}

# All reference/auxiliary product types
REFERENCE_PRODUCTS: Set[ProductType] = {
    ProductType.LEAP_SECONDS,
    ProductType.SAT_PARAMETERS,
    ProductType.OROGRAPHY,
}

# All LEO product types
LEO_PRODUCTS: Set[ProductType] = {
    ProductType.GRACE_GNV,
    ProductType.GRACE_ACC,
    ProductType.GRACE_SCA,
    ProductType.GRACE_KBR,
    ProductType.GRACE_LRI,
    ProductType.GRACE_CLK,
    ProductType.GRACE_THR,
}

# Products that require date-based organization
DATE_ORGANIZED_PRODUCTS: Set[ProductType] = (
    ORBIT_CLOCK_PRODUCTS | NAVIGATION_PRODUCTS | ATMOSPHERIC_PRODUCTS | LEO_PRODUCTS
)

# Products that are static (date-independent)
STATIC_PRODUCTS: Set[ProductType] = ANTENNA_PRODUCTS | REFERENCE_PRODUCTS


# ---------------------------------------------------------------------------
# Analysis Center / Source Enums (for reference)
# ---------------------------------------------------------------------------


class AnalysisCenter(str, Enum):
    """
    Analysis centers that produce GNSS products.
    
    Used for identifying product sources and applying center-specific
    processing configurations.
    """
    
    # IGS Analysis Centers
    COD = "cod"    # CODE (Center for Orbit Determination in Europe)
    EMR = "emr"    # Natural Resources Canada
    ESA = "esa"    # European Space Agency
    GFZ = "gfz"    # GeoForschungsZentrum Potsdam
    GRG = "grg"    # CNES/CLS (GRGS)
    IGS = "igs"    # IGS combined solution
    JPL = "jpl"    # Jet Propulsion Laboratory
    MIT = "mit"    # MIT
    NGS = "ngs"    # NOAA/NGS
    SIO = "sio"    # Scripps Institution of Oceanography
    UPC = "upc"    # Universitat Politècnica de Catalunya
    WHU = "whu"    # Wuhan University
    
    # MGEX Analysis Centers
    CNE = "cne"    # CNES (MGEX)
    GBM = "gbm"    # GFZ (MGEX)
    JAX = "jax"    # JAXA (MGEX)
    SHA = "sha"    # Shanghai Observatory (MGEX)
    WUM = "wum"    # Wuhan University (MGEX)


class ConstellationType(str, Enum):
    """GNSS constellation identifiers."""
    
    GPS = "G"       # GPS (USA)
    GLONASS = "R"   # GLONASS (Russia)
    GALILEO = "E"   # Galileo (EU)
    BEIDOU = "C"    # BeiDou (China)
    QZSS = "J"      # QZSS (Japan)
    IRNSS = "I"     # IRNSS/NavIC (India)
    SBAS = "S"      # SBAS
    MIXED = "M"     # Multi-constellation

