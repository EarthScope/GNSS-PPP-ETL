"""
GNSS Product Collections
========================

Convenience collections grouping product types by category for easy filtering
and iteration.

Usage
-----
    >>> from gnss_ppp_products.resources.products import ORBIT_CLOCK_PRODUCTS
    >>> for product in ORBIT_CLOCK_PRODUCTS:
    ...     print(product.name)
    SP3
    CLK
    ERP
    BIAS
    OBX
    SUM
"""

from typing import Set

from .types import ProductType


# ---------------------------------------------------------------------------
# Category-based Collections
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

# All atmospheric product types (ionosphere + troposphere)
ATMOSPHERIC_PRODUCTS: Set[ProductType] = {
    ProductType.GIM,
    ProductType.VMF1,
    ProductType.VMF3,
}

# Ionosphere-only products
IONOSPHERE_PRODUCTS: Set[ProductType] = {
    ProductType.GIM,
}

# Troposphere-only products
TROPOSPHERE_PRODUCTS: Set[ProductType] = {
    ProductType.VMF1,
    ProductType.VMF3,
}

# All antenna calibration product types
ANTENNA_PRODUCTS: Set[ProductType] = {
    ProductType.ATX_IGS,
    ProductType.ATX_CODE_MGEX,
    ProductType.ATX_NGS,
}

# All reference/auxiliary product types
REFERENCE_PRODUCTS: Set[ProductType] = {
    ProductType.LEAP_SECONDS,
    ProductType.SAT_PARAMETERS,
}

# Orography products
OROGRAPHY_PRODUCTS: Set[ProductType] = {
    ProductType.OROGRAPHY,
}

# All LEO satellite product types
LEO_PRODUCTS: Set[ProductType] = {
    ProductType.GRACE_GNV,
    ProductType.GRACE_ACC,
    ProductType.GRACE_SCA,
    ProductType.GRACE_KBR,
    ProductType.GRACE_LRI,
    ProductType.GRACE_CLK,
    ProductType.GRACE_THR,
}


# ---------------------------------------------------------------------------
# Temporal Organization Collections
# ---------------------------------------------------------------------------

# Products that require date-based directory organization
DATE_ORGANIZED_PRODUCTS: Set[ProductType] = (
    ORBIT_CLOCK_PRODUCTS | NAVIGATION_PRODUCTS | ATMOSPHERIC_PRODUCTS | LEO_PRODUCTS
)

# Products that are static (date-independent, rarely updated)
STATIC_PRODUCTS: Set[ProductType] = ANTENNA_PRODUCTS | REFERENCE_PRODUCTS | OROGRAPHY_PRODUCTS


# ---------------------------------------------------------------------------
# All Products
# ---------------------------------------------------------------------------

# Complete set of all product types
ALL_PRODUCTS: Set[ProductType] = set(ProductType)
