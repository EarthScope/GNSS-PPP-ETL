"""
GNSS Product Types
==================

Exhaustive collection of all product types downloaded by remote resources.
"""

from .types import (
    # Core enums
    TemporalCoverage,
    ProductQuality,
    ProductCategory,
    FileFormat,
    AnalysisCenter,
    ConstellationType,
    # Product type enum with metadata
    ProductType,
    ProductTypeInfo,
)

from .collections import (
    # Category-based collections
    ORBIT_CLOCK_PRODUCTS,
    NAVIGATION_PRODUCTS,
    ATMOSPHERIC_PRODUCTS,
    IONOSPHERE_PRODUCTS,
    TROPOSPHERE_PRODUCTS,
    ANTENNA_PRODUCTS,
    REFERENCE_PRODUCTS,
    OROGRAPHY_PRODUCTS,
    LEO_PRODUCTS,
    # Temporal organization collections
    DATE_ORGANIZED_PRODUCTS,
    STATIC_PRODUCTS,
    # All products
    ALL_PRODUCTS,
)

from .filename import (
    # Filename enums
    AnalysisCenter as FilenameAnalysisCenter,
    SolutionType,
    QualityLevel,
    ContentType,
    FileExtension,
    SamplingInterval,
    DataCoverage,
    # Filename builder classes
    IGSFilename,
    ProductFilenameBuilder,
    filename_builder,
    # Factory functions
    orbit_filename,
    clock_filename,
    erp_filename,
    bias_filename,
    attitude_filename,
    gim_filename,
)

__all__ = [
    # Enums
    "TemporalCoverage",
    "ProductQuality", 
    "ProductCategory",
    "FileFormat",
    "AnalysisCenter",
    "ConstellationType",
    # Product types
    "ProductType",
    "ProductTypeInfo",
    # Category-based collections
    "ORBIT_CLOCK_PRODUCTS",
    "NAVIGATION_PRODUCTS",
    "ATMOSPHERIC_PRODUCTS",
    "IONOSPHERE_PRODUCTS",
    "TROPOSPHERE_PRODUCTS",
    "ANTENNA_PRODUCTS",
    "REFERENCE_PRODUCTS",
    "OROGRAPHY_PRODUCTS",
    "LEO_PRODUCTS",
    # Temporal organization collections
    "DATE_ORGANIZED_PRODUCTS",
    "STATIC_PRODUCTS",
    "ALL_PRODUCTS",
    # Filename generation
    "SolutionType",
    "QualityLevel",
    "ContentType",
    "FileExtension",
    "SamplingInterval",
    "DataCoverage",
    "IGSFilename",
    "ProductFilenameBuilder",
    "filename_builder",
    "orbit_filename",
    "clock_filename",
    "erp_filename",
    "bias_filename",
    "attitude_filename",
    "gim_filename",
]