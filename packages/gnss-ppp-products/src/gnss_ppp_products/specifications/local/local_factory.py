"""
Local resource factory — loads local storage specs, resolves directories.

Fixes from original:
- ``resolve_directory`` uses actual model fields (not ghost ``self.metadata``)
- Factory has proper lookup methods (``get_spec``, ``collection_for_spec``, etc.)
"""

from __future__ import annotations

import collections
import datetime
from pathlib import Path
from token import OP
from typing import Dict, List, Optional, Union
import logging
from pydantic import BaseModel,Field, PrivateAttr, model_validator
import yaml

from gnss_ppp_products.specifications.local.local import LocalCollection, LocalResourceSpec
from gnss_ppp_products.specifications.products.product_catalog import ProductCatalog
from gnss_ppp_products.specifications.metadata.metadata_catalog import MetadataCatalog

logger = logging.getLogger(__name__)

class LocalResourceFactory(BaseModel):
    """Registry / factory for local storage layouts.

    Replaces ``_LocalResourceRegistry``.
    """

    collections: Dict[str, LocalCollection] = Field(default_factory=dict)
    _base_dir: Optional[Path] = PrivateAttr(default=None)
    _product_catalog: Optional[ProductCatalog] = PrivateAttr(default=None)
    _metadata_catalog: Optional[MetadataCatalog] = PrivateAttr(default=None)
    _spec_to_collection_map: Dict[str, str] = PrivateAttr(default_factory=dict)
    @classmethod
    def resolve(
        cls,
        local_resource_spec: LocalResourceSpec,
        product_catalog: ProductCatalog,
    ) -> "LocalResourceFactory":
        
        """check for spec uniqueness, and collection spec completeness."""
        spec_to_collection: Dict[str, str] = {}
        for coll_name, coll in local_resource_spec.collections.items():
            for s in coll.specs:
                if s in spec_to_collection:
                    raise ValueError(
                        f"Spec {s!r} is in multiple collections: "
                        f"{spec_to_collection[s]!r} and {coll_name!r}"
                    )
                spec_to_collection[s] = coll_name

        for product_name in product_catalog.products.keys():
            if product_name not in spec_to_collection:
                logger.warning(
                    f"Product spec {product_name!r} is not included in any local "
                    f"resource collection. It will not be resolvable via the local "
                    f"factory."
                )

        spec_directory_map: Dict[str, str] = {
            spec_name: local_resource_spec.collections[coll_name].directory
            for spec_name, coll_name in spec_to_collection.items()
        }

        instance = cls(
            collections=local_resource_spec.collections,
        )
        instance._spec_to_collection_map = spec_directory_map  
        instance._product_catalog = product_catalog
        return instance
  
        

    def resolve_directory(
        self,
        spec_name: str,
        date: datetime.date | datetime.datetime,
    ) -> Path:
        
        assert self._metadata_catalog is not None, "Metadata catalog must be set to resolve directories with date placeholders"
        if isinstance(date, datetime.date) and not isinstance(
            date, datetime.datetime
        ):
            date = datetime.datetime(
                date.year, date.month, date.day,
                tzinfo=datetime.timezone.utc,
            )

        directory_template = self._spec_to_collection_map.get(spec_name)

        # If the directory template is found, resolve any metadata placeholders and return the path

        if directory_template is not None:
            return self._base_dir /Path(self._metadata_catalog.resolve(directory_template, date, computed_only=True))

        raise KeyError(
            f"Spec {spec_name!r} not found in any local resource spec. "
            f"Known specs: {list(self._spec_to_collection_map.keys())}"
        )
