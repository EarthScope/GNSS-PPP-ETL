from typing import Optional

from gnss_ppp_products.assets.base.igs_conventions import ProductContentType
from ..base import (
    AssetBase,
    ProductCampaignSpec,
    ProductSolutionType,
    ProductSampleInterval,
    ProductDuration, ProductType,
    ProductFileFormat,
    AnalysisCenter,
    )


# ---------------------------------------------------------------------------
# Regex fallback patterns for IGS long-form filename placeholders.
# When a field value is not provided, the corresponding pattern is
# substituted into the template so the result can be used as a regex.
# ---------------------------------------------------------------------------

_PRODUCT_PLACEHOLDER_REGEX: dict[str, str] = {
    "center":    r"[A-Z]{3}",
    "version":   r"\d",
    "campaign":  r"[A-Z]{3}",
    "quality":   r"[A-Z]{3}",
    "year":      r"\d{4}",
    "doy":       r"\d{3}",
    "duration":  r"\d{2}[SMHD]",
    "interval":  r"\d{2}[SMHD]",
    "content":   r"[A-Z]{3}",
    "format":    r"[A-Z]{3,4}",
    "gps_week":  r"\d{4}",
    "yy":        r"\d{2}",
    "month":     r"\d{2}",
    "day":       r"\d{2}",
}


class _RegexFallbackDict(dict):
    """Dict that returns regex patterns for unknown placeholder keys."""

    def __missing__(self, key: str) -> str:
        return _PRODUCT_PLACEHOLDER_REGEX.get(key, ".+")



class ProductBase(AssetBase):
    """Base class for all product configurations."""
    content : Optional[ProductContentType] = None
    format: Optional[ProductFileFormat] = None
    version: Optional[str] = "0"
    interval: Optional[ProductSampleInterval] = None 
    solution: Optional[ProductSolutionType] = None  # Solution quality code (FIN, RAP, ULR, …)
    duration: Optional[ProductDuration] = None
    # for querying
    filename: Optional[str] = None
    directory: Optional[str] = None