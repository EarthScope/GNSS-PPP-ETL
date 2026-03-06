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
    # Convenience collections
    ORBIT_CLOCK_PRODUCTS,
    NAVIGATION_PRODUCTS,
    ATMOSPHERIC_PRODUCTS,
    ANTENNA_PRODUCTS,
    REFERENCE_PRODUCTS,
    LEO_PRODUCTS,
    DATE_ORGANIZED_PRODUCTS,
    STATIC_PRODUCTS,
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
    # Collections
    "ORBIT_CLOCK_PRODUCTS",
    "NAVIGATION_PRODUCTS",
    "ATMOSPHERIC_PRODUCTS",
    "ANTENNA_PRODUCTS",
    "REFERENCE_PRODUCTS",
    "LEO_PRODUCTS",
    "DATE_ORGANIZED_PRODUCTS",
    "STATIC_PRODUCTS",
]