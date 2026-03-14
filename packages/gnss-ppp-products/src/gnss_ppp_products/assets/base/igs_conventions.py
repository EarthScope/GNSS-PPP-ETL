'''
igs conventions:
https://files.igs.org/pub/resource/guidelines/Guidelines_for_Long_Product_Filenames_in_the_IGS_v2.1.pdf
https://igs.git-pages.gfz-potsdam.de/igs-cors-guidelines/en/data/filename/
'''

from enum import Enum
class AnalysisCenter(str, Enum):
    """
    Analysis centers that produce GNSS products.
    
    Used for identifying product sources and applying center-specific
    processing configurations.

    See https://igs.org/acc/#analysis-centers
    """
    
    # IGS Analysis Centers
    COD = "COD"    # CODE (Center for Orbit Determination in Europe)
    EMR = "EMR"    # Natural Resources Canada
    ESA = "ESA"    # European Space Agency
    GFZ = "GFZ"    # Helmholtz center for geosciences (GFZ)
    GRG = "GRG"    # CNES/CLS (GRGS)
    IGS = "IGS"    # IGS combined solution
    JPL = "JPL"    # Jet Propulsion Laboratory
    MIT = "MIT"    # MIT
    NGS = "NGS"    # NOAA/NGS
    SIO = "SIO"    # Scripps Institution of Oceanography
    UPC = "UPC"    # Universitat Politècnica de Catalunya
    WHU = "WHU"    # Wuhan University
    WMC = "WMC"    # Wuhan University MGEX Analysis Center
    # MGEX Analysis Centers
    CNE = "CNE"    # CNES (MGEX)
    GBM = "GBM"    # GFZ (MGEX)
    JAX = "JAX"    # JAXA (MGEX)
    SHA = "SHA"    # Shanghai Observatory (MGEX)
    WUM = "WUM"    # Wuhan University (MGEX)
    # Pseudo-centers (broadcast, reference tables, etc.)
    BRD = "BRD"    # Broadcast navigation (pseudo-center)

class ProductCampaignSpec(Enum):
    """Enumeration of campaign specifications for GNSS products."""
    DEM = "DEM" # Demonstration campaign
    MGX = "MGX" # Multi-GNSS Project product
    OPS = "OPS" # Operational IGS product
    R01 = "R01" # IGS Reprocessing campaign 1
    Rnn = "Rnn" # Reprocessing Campaign nn (where nn is a zero-padded integer)
    TGA = "TGA" # Tide Gauge Benchmark Monitoring campaign
    TST = "TST" # Test campaign (used for testing and validation)
    STATIC = "STATIC" # Static product (not associated with a specific campaign, used for reference products like antenna calibrations)

class ProductSolutionType(Enum):

    FIN = "FIN"
    NRT = "NRT"
    PRD = "PRD"
    RAP = "RAP"
    RTS = "RTS"
    SNX = "SNX"
    ULR = "ULR"
    ULT = "ULT"

class ProductSampleInterval(str, Enum):
    S_30 = "30S"
    M_5 = "05M"
    M_15 = "15M"
    H_1 = "01H"
    H_2 = "02H"
    D_1 = "01D"

class ProductDuration(str, Enum):
    D_1 = "01D"

class ProductFileFormat(str, Enum):
    """
    File formats (FMT) defined by the IGS long product filename convention.

    Reference: IGS Guidelines for Long Product Filenames, Version 2.1, Section 2.5.
    """

    BIA  = "BIA"   # Bias SINEX
    CLK  = "CLK"   # Clock RINEX
    ERP  = "ERP"   # IGS ERP format
    INX  = "INX"   # IONEX ionospheric TEC grid product format
    JSON = "JSON"  # JavaScript Object Notation
    OBX  = "OBX"   # ORBEX satellite orbit/attitude format
    SNX  = "SNX"   # Solution INdependent EXchange (SINEX) format
    SP3  = "SP3"   # Standard Product 3 orbit format
    SUM  = "SUM"   # Summary of the indicated product / combination summary
    TRO  = "TRO"   # SINEX_TRO troposphere product format
    YAML = "YAML"  # YAML Ain't Markup Language
    ATX  = "ATX"   # ANTEX antenna calibration format

class ProductContentType(str, Enum):
    """
    Content types agreed upon within IGS analysis centers.

    Reference: IGS Guidelines for Long Product Filenames, Version 2.1.
    """

    # -------------------------------------------------------------------------
    # General content types
    # -------------------------------------------------------------------------

    ATT = "ATT"  # Attitude information
    CLK = "CLK"  # Receiver and/or satellite clock parameters
    CLS = "CLS"  # Summary of clock combination
    CMP = "CMP"  # Comparison summary files
    CRD = "CRD"  # Station coordinates/velocities in SINEX
    DSC = "DSC"  # Epochs of station position/velocity discontinuities
    ERP = "ERP"  # Earth rotation parameters
    ORB = "ORB"  # Satellite orbits
    PSD = "PSD"  # Post-seismic deformation models in SINEX
    RES = "RES"  # Residuals from daily SINEX combination
    SOL = "SOL"  # Variance/covariance information or normal equations in SINEX
    SUM = "SUM"  # Summary of orbit or SINEX combination
    TRO = "TRO"  # Troposphere ZPD product

    # -------------------------------------------------------------------------
    # Bias products
    # -------------------------------------------------------------------------

    DCB = "DCB"  # Differential code biases
    DPB = "DPB"  # Differential phase biases
    DSB = "DSB"  # Differential signal biases (code and phase)
    OCB = "OCB"  # Observable-specific code biases
    OPB = "OPB"  # Observable-specific phase biases
    OSB = "OSB"  # Observable-specific signal biases (code and phase)

    # -------------------------------------------------------------------------
    # Ionosphere products
    # -------------------------------------------------------------------------

    GIM = "GIM"  # Global Ionosphere (TEC) Maps
    ROT = "ROT"  # Rate of TEC Index Maps (ROTI Maps)

'''
Rinex V3/V4 Observation,Meterological and Navigation Conventions
'''
class Rinex3DataSource(str, Enum):

    R = "R"  # From receiver using vendor software
    S = "S"  # RTCM or another stream format 

class Rinex3DataType(str, Enum):

    OBS = "O"  # RINEX Observation file
    NAV = "N"  # RINEX Navigation file
    MET = "M"  # RINEX Meteorological file

class RinexSatelliteSystem(str, Enum):

    GPS = "G"
    GLONASS = "R"
    GALILEO = "E"
    BEIDOU = "C"
    QZSS = "J"
    IRNSS = "I"
    LEO = "L"
    MIXED = "M"  # Mixed satellite systems in a single RINEX file

class Rinex2FileInterval(str, Enum):
    DAILY = "0"
    HOURLY = "a"
    HIGHRATE = "a00"

class Rinex2DataType(str, Enum):
    OBS = "o"         # Observation file
    GPS_NAV = "n"     # GPS Navigation file
    MET = "m"         # Meteorological data file
    GLONASS_NAV = "g" # GLONASS Navigation file
    GALILEO_NAV = "l" # Galileo Navigation file (future)
    GEO_PAYLOAD = "h" # Geostationary GPS payload nav message file
    SBAS = "b"        # Geo SBAS broadcast data file
    CLOCK = "c"       # Clock file
    SUMMARY = "s"     # Summary file (IGS, not standard)
    HATANAKA = "d"    # Hatanaka compressed observation file (not in standard, but used)
   
class RinexVersion(str, Enum):
    V2 = "2"
    V3 = "3"
    V4 = "4"
  
class ProductType(Enum):
    """
    Internal product types used for resource configuration and querying.
    """

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
