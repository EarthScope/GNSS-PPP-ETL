from enum import Enum
import datetime
from dataclasses import dataclass

class TemporalCoverage(Enum):
    DAILY = "daily"
    GPSWEEKLY = "gpsweekly"
    EPOCH = "epoch" # For products that are generated at non-regular intervals, e.g. when a new solution is available
    YEARLY = "yearly" # For products that are generated on a yearly basis, e.g. annual reference frames

class ProductQuality(Enum):
    FINAL = "final"
    RAPID = "rapid"
    RTS = "rts"

@dataclass
class ATX:
    """
    Class representing an ATX antenna calibration file.
    """
    __name__: str = "ATX"
    temporal_coverage: TemporalCoverage = TemporalCoverage.EPOCH

@dataclass
class VMF:
    """
    Class representing a VMF troposphere mapping function product.
    """
    __name__: str = "VMF"
    temporal_coverage: TemporalCoverage = TemporalCoverage.EPOCH

@dataclass
class IONEX:
    """
    Class representing an IONEX ionosphere map product.
    """
    __name__: str = "IONEX"
    temporal_coverage: TemporalCoverage = TemporalCoverage.DAILY

@dataclass
class CLK:
    """
    Class representing a satellite clock product.
    """
    __name__: str = "CLK"
    temporal_coverage: TemporalCoverage = TemporalCoverage.DAILY

@dataclass
class SP3:
    """
    Class representing a satellite orbit product in SP3 format.
    """
    __name__: str = "SP3"
    temporal_coverage: TemporalCoverage = TemporalCoverage.DAILY

@dataclass
class ERP:
    """
    Class representing Earth Rotation Parameters (ERP) product.
    """
    __name__: str = "ERP"
    temporal_coverage: TemporalCoverage = TemporalCoverage.DAILY

@dataclass
class OBX:
    """
    Class representing ocean loading coefficients product.
    """
    __name__: str = "OBX"
    temporal_coverage: TemporalCoverage = TemporalCoverage.YEARLY
    