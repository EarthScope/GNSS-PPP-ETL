"""
Top-level GNSS center configuration model.

Separated into its own module to avoid circular imports between
products.py and rinex.py (GNSSCenterConfig references both
ProductConfig and RinexConfig).
"""

from pydantic import BaseModel
import datetime
from typing import List, Optional

from ..products import ProductConfig, ProductFileQuery
from ..antennae import AntennaeFileQuery, AntennaeConfig
from ..rinex import RinexFileQuery, RinexConfig
from ..troposphere import TroposphereConfig, TroposphereFileQuery
from ..orography import OrographyConfig, OrographyFileQuery
from ..leo import LEOConfig, LEOFileQuery
from ..reference_tables import ReferenceTableConfig, ReferenceTableFileQuery
from ..server import Server

class GNSSCenterConfig(BaseModel):
    """Configuration for a GNSS product center."""
    name: str
    code: str
    description: Optional[str] = None
    website: Optional[str] = None
    servers: List[Server]
    products: List[ProductConfig]
    rinex: Optional[List[RinexConfig]] = None
    antennae: Optional[List[AntennaeConfig]] = None
    troposphere: Optional[List[TroposphereConfig]] = None
    orography: Optional[List[OrographyConfig]] = None
    leo: Optional[List[LEOConfig]] = None
    reference_tables: Optional[List[ReferenceTableConfig]] = None

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "GNSSCenterConfig":
        import yaml
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def build_product_queries(
        self,
        date: datetime.datetime | datetime.date,
    ) -> List[ProductFileQuery]:
        """
        Expand all product configs into file queries for the given date.

        Parameters
        ----------
        date : datetime.datetime | datetime.date
            The date to query products for.
        """
        queries: list[ProductFileQuery] = []
        for product in self.products:
            if not product.available:
                continue
            for query in product.build(date):
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
    ) -> List[AntennaeFileQuery]:
        """Expand all antennae calibration configs into file queries for the given date."""
        queries: list[AntennaeFileQuery] = []
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

    def build_troposphere_queries(
        self,
        date: datetime.datetime | datetime.date,
    ) -> List[TroposphereFileQuery]:
        """Expand all troposphere configs into file queries for the given date."""
        queries: list[TroposphereFileQuery] = []
        if not self.troposphere:
            return queries
        for tropo in self.troposphere:
            if not tropo.available:
                continue
            for query in tropo.build(date):
                query.server = next((s for s in self.servers if s.id == tropo.server_id), None)
                assert query.server is not None, f"No matching server for troposphere query: {query}"
                queries.append(query)
        return queries

    def build_orography_queries(self) -> List[OrographyFileQuery]:
        """Expand all orography configs into file queries (static, no date)."""
        queries: list[OrographyFileQuery] = []
        if not self.orography:
            return queries
        for orog in self.orography:
            if not orog.available:
                continue
            for query in orog.build():
                query.server = next((s for s in self.servers if s.id == orog.server_id), None)
                assert query.server is not None, f"No matching server for orography query: {query}"
                queries.append(query)
        return queries

    def build_leo_queries(
        self,
        date: datetime.datetime | datetime.date,
    ) -> List[LEOFileQuery]:
        """Expand all LEO configs into file queries for the given date."""
        queries: list[LEOFileQuery] = []
        if not self.leo:
            return queries
        for leo_cfg in self.leo:
            if not leo_cfg.available:
                continue
            for query in leo_cfg.build(date):
                query.server = next((s for s in self.servers if s.id == leo_cfg.server_id), None)
                assert query.server is not None, f"No matching server for LEO query: {query}"
                queries.append(query)
        return queries

    def build_reference_table_queries(self) -> List[ReferenceTableFileQuery]:
        """Expand all reference table configs into file queries (static, no date)."""
        queries: list[ReferenceTableFileQuery] = []
        if not self.reference_tables:
            return queries
        for ref in self.reference_tables:
            if not ref.available:
                continue
            for query in ref.build():
                query.server = next((s for s in self.servers if s.id == ref.server_id), None)
                assert query.server is not None, f"No matching server for reference table query: {query}"
                queries.append(query)
        return queries