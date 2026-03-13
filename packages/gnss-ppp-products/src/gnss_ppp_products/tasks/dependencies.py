"""
Product dependency definitions for Tasks.

A :class:`ProductDependency` declares *what* category of GNSS product
is required.  The :class:`DependencyType` enum mirrors the asset
categories already defined by the center configuration builders
(``GNSSCenterConfig.build_*_queries``).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class DependencyType(str, Enum):
    """Categories of GNSS product dependencies.

    Each value maps directly to a ``build_*_queries`` method on
    :class:`~gnss_ppp_products.assets.center.config.GNSSCenterConfig`.
    """

    PRODUCTS = "products"
    RINEX = "rinex"
    ANTENNAE = "antennae"
    TROPOSPHERE = "troposphere"
    OROGRAPHY = "orography"
    LEO = "leo"
    REFERENCE_TABLES = "reference_tables"


class ProductDependency(BaseModel):
    """A single product dependency within a Task.

    Parameters
    ----------
    type : DependencyType
        The category of product needed (e.g. orbits/clocks, RINEX nav).
    required : bool
        If ``True`` the task cannot succeed without fulfilling this
        dependency.  Optional dependencies are resolved on a best-effort
        basis.
    description : str, optional
        Human-readable note about why this dependency exists.
    """

    type: DependencyType
    required: bool = True
    description: Optional[str] = None
