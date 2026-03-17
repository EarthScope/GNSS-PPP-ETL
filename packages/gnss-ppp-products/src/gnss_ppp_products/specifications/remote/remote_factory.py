"""
Remote resource factory — loads center specs, indexes products and servers.
"""

from __future__ import annotations

import datetime
from pathlib import Path
import re
from typing import Dict, List, Optional

import yaml

from gnss_ppp_products.specifications.remote.remote import (
    RemoteProductSpec,
    RemoteResourceSpec,
    ServerSpec,
)
from gnss_ppp_products.specifications.metadata.metadata_catalog import MetadataCatalog
from gnss_ppp_products.specifications.products.product_catalog import ProductCatalog

class RemoteResourceCatalog(RemoteResourceSpec):

    @classmethod
    def resolve(cls, 
                remote_resource_catalog: RemoteResourceSpec,
                product_catalog: ProductCatalog,
                metadata_catalog: MetadataCatalog) -> "RemoteResourceCatalog":
        '''
        Check that the metadata constraints match the metadata catalog, the product specs are valid, and resolve the directory templates.
        
        '''

        for product in remote_resource_catalog.products:
            if product_catalog.products.get(product.spec) is None:
                raise ValueError(f"Product spec {product.spec_name!r} not found in product catalog.")
            for key, values in product.metadata.items():
                metadata_spec = metadata_catalog.get(key)
                if metadata_spec is None:
                    raise ValueError(f"Metadata key {key!r} not found in metadata catalog.")
                if metadata_spec.pattern is not None:
                    for value in values:
                        match_ = re.match(metadata_spec.pattern, value)
                        assert match_ is not None, f"Metadata value {value!r} for key {key!r} does not match pattern {metadata_spec.pattern!r}"
        return cls(**remote_resource_catalog.model_dump())
             
class RemoteResourceFactory:
    """Registry of remote data centers and their products.

    Replaces ``_RemoteResourceRegistry``.
    """

    def __init__(self, product_catalog: ProductCatalog, metadata_catalog: MetadataCatalog) -> None:
        self._centers: Dict[str, RemoteResourceCatalog] = {}
        self._products_by_id: Dict[str,  RemoteProductSpec] = {}
        self._servers_by_id: Dict[str,ServerSpec] = {}
        self._product_catalog = product_catalog
        self._metadata_catalog = metadata_catalog




    def _register(self, spec: RemoteResourceSpec) -> None:
        resolved_spec = RemoteResourceCatalog.resolve(spec, self._product_catalog, self._metadata_catalog)
        self._centers[resolved_spec.id] = resolved_spec
        for srv in resolved_spec.servers:
            assert srv.id not in self._servers_by_id, f"Duplicate server ID {srv.id!r} found in center {resolved_spec.id!r}"
            self._servers_by_id[srv.id] = srv
        for prod in resolved_spec.products:
            assert prod.id not in self._products_by_id, f"Duplicate product ID {prod.id!r} found in center {resolved_spec.id!r}"
            self._products_by_id[prod.id] = prod

    def get_server_for_product(self, product_id: str) -> ServerSpec:
        prod = self._products_by_id[product_id]
        return self._servers_by_id[prod.server_id]



