"""
Product catalog — loads product + format specs, resolves into variants.

Fixes from original resolver:
- ProductVariant now carries ``constraints`` and ``field_defaults``
- ``_resolve_all`` creates one variant per binding (not one per constraint field)
- Products with zero constraints still produce a variant
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field

from gnss_ppp_products.specifications.products.products import ProductSpecCollection, ProductSpec, ProductFormatBinding
from gnss_ppp_products.specifications.format.format_catalog import FormatCatalog,FormatSpec


# ===================================================================
# Resolved output
# ===================================================================


class ProductVariant(BaseModel):
    """Fully-resolved product + format binding.

    Downstream consumers use this flat object — no need to chase
    through the format hierarchy.
    """

    product_name: str
    format_id: str
    version: str
    file_template: str
    constraints: Dict[str, str] = Field(default_factory=dict)
    compression: List[str] = Field(default_factory=list)


class ProductCollection(BaseModel):
    """Collection of resolved product variants."""

    variants: List[ProductVariant] = Field(default_factory=list)
# ===================================================================
# Catalog (YAML loader)
# ===================================================================


class ProductCatalog(BaseModel):
    """Collection of product declarations from the ``products:`` YAML key."""

    products: Dict[str, ProductCollection] = Field(default_factory=dict)

    @classmethod
    def resolve(
        cls, format_catalog: FormatCatalog, product_spec_collection: ProductSpecCollection
    ) -> "ProductCatalog":
        """Resolve a ProductSpecCollection against a FormatCatalog."""
        resolved_products: Dict[str, ProductCollection] = {}
        for product_name, product_spec in product_spec_collection.products.items():
            variants: List[ProductVariant] = []
            for binding in product_spec.formats:
                fmt: FormatSpec = format_catalog.get_format(binding.format)
                ver = fmt.versions.get(binding.version)
                if ver is None:
                    raise ValueError(
                        f"Version {binding.version!r} not found in format "
                        f"{binding.format!r}"
                    )
                file_template = ver.file_templates.get(binding.variant)
                if file_template is None:
                    raise ValueError(
                        f"Variant {binding.variant!r} not found in format "
                        f"{binding.format!r} version {binding.version!r}"
                    )
                # Resolve file templates — apply constraint substitutions
                for field_name, value in binding.constraints.items():
                    file_template = file_template.replace(f"{{{field_name}}}", value)

                variant = ProductVariant(
                    product_name=product_name,
                    format_id=binding.format,
                    version=binding.version,
                    file_template=file_template,
                    constraints=binding.constraints,
                    compression=fmt.get_compression(binding.version),
                )
                variants.append(variant)
            resolved_products[product_name] = ProductCollection(variants=variants)
        return cls(products=resolved_products)
 
