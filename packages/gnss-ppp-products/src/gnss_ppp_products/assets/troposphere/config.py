from itertools import product
from typing import List, Optional
import datetime

from pydantic import BaseModel

from .base import TroposphereBase, VMFProduct, VMFGridResolution, VMFHour
from .query import TroposphereFileQuery


# ---------------------------------------------------------------------------
# YAML configuration schemas
# ---------------------------------------------------------------------------


class VMFProductConfig(BaseModel):
    product: VMFProduct
    description: Optional[str] = None


class VMFResolutionConfig(BaseModel):
    resolution: VMFGridResolution
    description: Optional[str] = None


class VMFHourConfig(BaseModel):
    hour: VMFHour
    description: Optional[str] = None


class TroposphereConfig(TroposphereBase):
    """Configuration for a troposphere (VMF) product."""
    id: str
    server_id: str
    available: bool = True
    description: Optional[str] = None
    notes: Optional[str] = None
    product_set: List[VMFProductConfig]
    resolution_set: List[VMFResolutionConfig]
    hour_set: List[VMFHourConfig]

    def build(self, date: datetime.datetime | datetime.date) -> List[TroposphereFileQuery]:
        """Expand config into all combinations of product/resolution/hour."""
        assert self.filename is not None, "TroposphereConfig must have a filename template"
        assert self.directory is not None, "TroposphereConfig must have a directory template"

        products = [p.product for p in self.product_set] or [None]
        resolutions = [r.resolution for r in self.resolution_set] or [None]
        hours = [h.hour for h in self.hour_set] or [None]

        queries: list[TroposphereFileQuery] = []
        for vmf_product, resolution, hour in product(products, resolutions, hours):
            query = TroposphereFileQuery(
                date=date,
                product=vmf_product,
                resolution=resolution,
                hour=hour,
            )
            query.build_filename(self.filename)
            query.build_directory(self.directory)
            queries.append(query)
        return queries
