"""
GNSS Product Types
==================

Exhaustive collection of all product types downloaded by remote resources.
"""



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
]   