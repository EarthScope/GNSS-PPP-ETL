"""Server, ResourceSpec, ResourceQuery — remote resource models (Layer 1)."""

from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field

from gnss_ppp_products.specifications.parameters.parameter import Parameter
from gnss_ppp_products.specifications.products.product import Product, ProductPath
from gnss_ppp_products.utilities.helpers import _PassthroughDict
import yaml


class Server(BaseModel):
    """A remote or local server endpoint."""
    id: str
    hostname: str
    protocol: Optional[str] = None
    auth_required: Optional[bool] = False
    description: Optional[str] = None


class ResourceProductSpec(BaseModel):
    """A product offering within a resource/center — maps a catalog product to a server with parameter overrides."""
    id: str
    server_id: str
    available: bool = True
    product_name: str
    product_version: Optional[List[str] | str] = None
    description: Optional[str] = None
    parameters: List[Parameter]
    directory: ProductPath


class ResourceSpec(BaseModel):
    """Root resource specification for a data center."""
    id: str
    name: str
    description: Optional[str] = None
    website: Optional[str] = None
    servers: List[Server] = []
    products: List[ResourceProductSpec] = []

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "ResourceSpec":
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate(raw)


class ResourceQuery(BaseModel):
    """A single concrete query target — one combination of parameter values."""

    product: Product
    server: Server
    directory: ProductPath


    def narrow(self) -> 'ResourceQuery':
        """Substitute already-known parameter values into directory/filename patterns."""
        to_keep = [p for p in self.product.parameters if p.value is None]
        to_update = {p.name: p for p in self.product.parameters if p.value is not None}
        format_dict = _PassthroughDict({k: p.value for k, p in to_update.items()})

        if self.product.filename:
            self.product = self.product.model_copy(deep=True, update={
                "filename": ProductPath(pattern=self.product.filename.pattern.format_map(format_dict))
            })
        self.directory = ProductPath(pattern=self.directory.pattern.format_map(format_dict))

        return self
