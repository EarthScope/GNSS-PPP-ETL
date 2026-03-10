from enum import Enum

from pydantic import BaseModel

class Solution(BaseModel):
    code: str
    prefix: str
    description: str = ""


class SampleInterval(str, Enum):
    S_30 = "30S"
    M_5 = "05M"
    M_15 = "15M"
    H_1 = "01H"
    H_2 = "02H"

class ProductDuration(str, Enum):
    D_1 = "01D"

class ProductQuality(str, Enum):
    """Quality/latency levels for products."""
    
    FINAL = "FIN"        # Post-processed, highest accuracy (~2 week latency)
    RAPID = "RAP"        # Near real-time (~1 day latency)
    ULTRA_RAPID = "ULR"  # Ultra-rapid products (~3-6 hour latency)
    REAL_TIME = "RTS"      # Real-time streaming

class TemporalCoverage(str, Enum):
    """Temporal coverage/cadence of products."""
    
    EPOCH = "epoch"          # Non-regular intervals (e.g., new solution release)
    HOURLY = "hourly"        # Hourly products (e.g., VMF grids)  
    DAILY = "daily"          # Daily products (most common)
    GPSWEEKLY = "gpsweekly"  # GPS week-based products
    YEARLY = "yearly"        # Annual products (e.g., reference frames)
    STATIC = "static"        # Static files (rarely updated)

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
    
    SP3 = "SP3"
    CLK = "CLK"
    ERP = "ERP"
    BIAS = "BIAS"
    OBX = "OBX"
    SUM = "SUM"
    IONX = "IONX"
    RINEX3_NAV = "RINEX3_NAV"
    RINEX2_NAV = "RINEX2_NAV"  # Generic RINEX 2 navigation
    RINEX2_NAV_GPS = "RINEX2_NAV_GPS"
    RINEX2_NAV_GLONASS = "RINEX2_NAV_GLONASS"
    RINEX2_NAV_MIXED = "RINEX2_NAV_MIXED"  # Mixed GPS+GLONASS RINEX 2.x navigation files
    
    # -------------------------------------------------------------------------
    # Ionosphere Products
    # -------------------------------------------------------------------------
    
    GIM = "GIM"      # Global Ionosphere Maps (e.g., TEC grids)
    
    # -------------------------------------------------------------------------
    # Troposphere Products
    # -------------------------------------------------------------------------
    
    VMF1 = "VMF1"  # Vienna Mapping Functions 1 (legacy troposphere mapping)
    
    VMF3 = "VMF3"  # Vienna Mapping Functions 3 (improved troposphere mapping)
     
    # -------------------------------------------------------------------------
    # Antenna Calibration Products
    # -------------------------------------------------------------------------
    
    ATX = "ATX"      # Generic ANTEX antenna calibration files
    
    
    # -------------------------------------------------------------------------
    # Reference Tables
    # -------------------------------------------------------------------------
    
    LEAP_SECONDS = "LEAP_SECONDS"  # Leap seconds table
    
    SAT_PARAMETERS = "SAT_PARAMETERS"  # Satellite physical parameters (e.g., mass, area)
    
    # -------------------------------------------------------------------------
    # Orography Products
    # -------------------------------------------------------------------------
    
    OROGRAPHY = "OROGRAPHY"  # Digital elevation models (DEMs) for GNSS processing
    
    # -------------------------------------------------------------------------
    # LEO Satellite Products (GRACE/GRACE-FO)
    # -------------------------------------------------------------------------
    
    GRACE_GNV = "GRACE_GNV"  # GRACE/GRACE-FO GPS navigation Level-1B data
    GRACE_ACC = "GRACE_ACC"  # GRACE/GRACE-FO accelerometer data
    GRACE_SCA = "GRACE_SCA"  # GRACE/GRACE-FO star camera data
    GRACE_KBR = "GRACE_KBR"  # GRACE/GRACE-FO K-Band ranging data
    GRACE_LRI = "GRACE_LRI"  # GRACE-FO Laser Ranging Interferometer data
    