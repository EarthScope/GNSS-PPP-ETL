"""
Top-level GNSS center configuration model.

Separated into its own module to avoid circular imports between
products.py and rinex.py (GNSSCenterConfig references both
ProductConfig and RinexConfig).
"""

import datetime
from typing import List, Optional

from pydantic import BaseModel

from ..products import Solution, ProductQuality, TemporalCoverage
from ..igs_conventions import ProductSampleInterval, ProductType
from .server import Server
from .products import ProductConfig, RemoteProductAddress
from .rinex import RinexConfig


class GNSSCenterConfig(BaseModel):
    """Configuration for a GNSS product center."""
    name: str
    code: str
    description: Optional[str] = None
    website: Optional[str] = None
    servers: List[Server]
    products: List[ProductConfig]
    rinex: Optional[List[RinexConfig]] = None

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "GNSSCenterConfig":
        import yaml
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def list_products(
            self,
            date: datetime.datetime | datetime.date,
            product_type: Optional[ProductType] = None,
            product_quality: Optional[ProductQuality] = None,
            sample_interval: Optional[ProductSampleInterval] = None,
            temporal_coverage: Optional[TemporalCoverage] = None,
            file_id: Optional[str] = None
    ) -> List[RemoteProductAddress]:
        """
        Get product addresses matching the specified criteria.
        
        Parameters
        ----------
        date : datetime.datetime | datetime.date
            The date to query products for
        file_id : str, optional
            Specific file ID to filter (e.g., "current", "archive")
        product_type : ProductType, optional
            Specific product type to filter
        product_quality : ProductQuality, optional
            Specific product quality to filter
        sample_interval : SampleInterval, optional
            Specific sample interval to filter
        temporal_coverage : TemporalCoverage, optional
            Specific temporal coverage to filter
        """
        product_addresses: list[RemoteProductAddress] = []
        for product in self.products:
            if not product.available:
                continue
                
            server = next((s for s in self.servers if s.id == product.server_id), None)
            if server is None:
                raise ValueError(f"Product {product.type} references unknown server_id {product.server_id}")
            
            # Filter files by file_id if specified
            files_to_use = product.files
            if file_id:
                files_to_use = [f for f in product.files if f.id == file_id]
            
            # Filter files by date validity
            files_to_use = [f for f in files_to_use if f.is_valid_for_date(date)]
            
            # Build each combination of quality/solution/intervals/files
            qualities = [x for x in product.qualities if not product_quality or x == product_quality] or [None]
            solutions = product.solutions or [None]
 
            for file_config in files_to_use:
                for quality in qualities:
                    for solution in solutions:
            
                        filename = file_config.filename.build(
                            date=date,
                            solution=solution,
                            quality=quality
                            
                        )
                        directory = file_config.build_directory(date)

                        address = RemoteProductAddress(
                            server=server,
                            directory=directory,
                            filename=filename,
                            file_id=file_config.id,
                            type=product.type,
                            quality=quality,
                            solution=solution
                        )
                        product_addresses.append(address)

        return product_addresses
