"""Pure Pydantic models for remote resource specifications."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field


class ServerSpec(BaseModel):
    """A remote server definition."""

    id: str
    name: str = ""
    hostname: str
    protocol: str = "ftp"
    auth_required: bool = False
    notes: str = ""


class RemoteProductSpec(BaseModel):
    """A product hosted by a data center."""

    id: str
    spec: str
    format: Optional[int] = None
    server_id: str
    available: bool = True
    description: str = ""
    metadata: Dict[str, List[str]] = Field(default_factory=dict)
    directory: str

    @property
    def spec_name(self) -> str:
        return self.spec

    @property
    def format_indices(self) -> Optional[list[int]]:
        """Return explicit format index list, or None to use all formats."""
        if self.format is not None:
            return [self.format]
        return None

    def metadata_combinations(self) -> list[dict[str, str]]:
        """Expand center metadata lists into every combination."""
        if not self.metadata:
            return [{}]
        keys = list(self.metadata.keys())
        value_lists = [self.metadata[k] for k in keys]
        return [dict(zip(keys, combo)) for combo in itertools.product(*value_lists)]

    def get_server(self, spec: "RemoteResourceSpec") -> "ServerSpec":
        """Look up the server for this product within its parent spec."""
        for s in spec.servers:
            if s.id == self.server_id:
                return s
        raise KeyError(f"Server {self.server_id!r} not found in {spec.id}")


class RemoteResourceSpec(BaseModel):
    """Root model for a center's remote resource specification."""

    id: str
    name: str = ""
    description: str = ""
    website: str = ""
    servers: List[ServerSpec] = Field(default_factory=list)
    products: List[RemoteProductSpec] = Field(default_factory=list)

    def get_server(self, server_id: str) -> ServerSpec:
        for s in self.servers:
            if s.id == server_id:
                return s
        raise KeyError(f"Server {server_id!r} not found in {self.id}")

    def get_product(self, product_id: str) -> RemoteProductSpec:
        for p in self.products:
            if p.id == product_id:
                return p
        raise KeyError(f"Product {product_id!r} not found in {self.id}")

    def products_for_spec(self, spec_name: str) -> list[RemoteProductSpec]:
        return [p for p in self.products if p.spec_name == spec_name]

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "RemoteResourceSpec":
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate(raw)
