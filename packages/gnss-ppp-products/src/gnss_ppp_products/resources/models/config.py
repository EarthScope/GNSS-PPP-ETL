"""
Top-level GNSS center configuration model.

Separated into its own module to avoid circular imports between
products.py and rinex.py (GNSSCenterConfig references both
ProductConfig and RinexConfig).
"""

import datetime
from typing import List, Optional

from ..types import ProductQuality
from .server import Server
from ...assets.products.products import ProductConfig, ProductFileQuery
from .rinex import RinexConfig, RinexFileQuery
from .base import BaseConfig

from .antennae_calibration import AntennaeCalibrationConfig, AntennaeCalibrationQuery

class GNSSCenterConfig(BaseConfig):
    """Configuration for a GNSS product center."""
    name: str
    code: str
    description: Optional[str] = None
    website: Optional[str] = None
    servers: List[Server]
    products: List[ProductConfig]
    rinex: Optional[List[RinexConfig]] = None
    antennae: Optional[List[AntennaeCalibrationConfig]] = None

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "GNSSCenterConfig":
        import yaml
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def build_product_queries(
        self,
        date: datetime.datetime | datetime.date,
        product_quality: Optional[ProductQuality] = None,
    ) -> List[ProductFileQuery]:
        """
        Expand all product configs into file queries for the given date.

        Parameters
        ----------
        date : datetime.datetime | datetime.date
            The date to query products for.
        product_quality : ProductQuality, optional
            If given, only include queries matching this quality level.
        """
        queries: list[ProductFileQuery] = []
        for product in self.products:
            if not product.available:
                continue
            for query in product.build(date):
                if product_quality and query.quality != product_quality.value:
                    continue
                query.server = next((s for s in self.servers if s.id == product.server_id), None)
                assert query.server is not None, f"No matching server for product query: {query}"
                queries.append(query)
        return queries

    def build_rinex_queries(
        self,
        date: datetime.datetime | datetime.date,
    ) -> List[RinexFileQuery]:
        """Expand all rinex configs into file queries for the given date."""
        queries: list[RinexFileQuery] = []
        if not self.rinex:
            return queries
        for rinex in self.rinex:
            if not rinex.available:
                continue
            for query in rinex.build(date):
                query.server = next((s for s in self.servers if s.id == rinex.server_id), None)
                assert query.server is not None, f"No matching server for RINEX query: {query}"
                queries.append(query)
        return queries

    def build_antennae_queries(
        self,
        date: datetime.datetime | datetime.date,
    ) -> List[AntennaeCalibrationQuery]:
        """Expand all antennae calibration configs into file queries for the given date."""
        queries: list[AntennaeCalibrationQuery] = []
        if not self.antennae:
            return queries
        for ant in self.antennae:
            if not ant.available:
                continue
            for query in ant.build(date):
                query.server = next((s for s in self.servers if s.id == ant.server_id), None)
                assert query.server is not None, f"No matching server for antennae calibration query: {query}"   
            queries.append(query)
        return queries