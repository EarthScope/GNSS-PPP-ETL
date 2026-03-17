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

from gnss_ppp_products.specifications.formats import FormatSpec, FormatVersionSpec
from gnss_ppp_products.specifications.products import ProductFormatBinding, ProductSpec
from gnss_ppp_products.catalogs.format_catalog import FormatCatalog


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
    variant: str
    file_template: str
    constraints: Dict[str, str] = Field(default_factory=dict)
    field_defaults: Dict[str, str] = Field(default_factory=dict)
    compression: List[str] = Field(default_factory=list)


# ===================================================================
# Catalog (YAML loader)
# ===================================================================


class ProductSpecCatalog(BaseModel):
    """Collection of product declarations from the ``products:`` YAML key."""

    products: Dict[str, ProductSpec] = Field(default_factory=dict)


    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "ProductSpecCatalog":
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate({"products": raw.get("products", {})})


# ===================================================================
# Resolver
# ===================================================================


class ProductCatalog:
    """Resolves product bindings against a format catalog into
    :class:`ProductVariant` objects.
    """

    def __init__(
        self,
        format_catalog: FormatCatalog,
        product_catalog: ProductSpecCatalog,
    ) -> None:
        self._format_specs = format_catalog
        self._product_specs = product_catalog
        self._variants: Dict[str, List[ProductVariant]] = defaultdict(list)
        self._resolve_all()

    def _resolve_all(self) -> None:
        """Walk every product binding and resolve it."""
        for product_name, product in self._product_specs.products.items():
            for binding in product.formats:
                fmt: FormatSpec = self._format_specs.get_format(binding.format)
                ver: FormatVersionSpec = fmt.versions[binding.version]
                file_template: Optional[str] = ver.file_templates.get(
                    binding.variant, None
                )
                if file_template is None:
                    raise ValueError(
                        f"Variant {binding.variant!r} not found in format "
                        f"{binding.format!r} version {binding.version!r}"
                    )
                # Resolve file templates — apply constraint substitutions

                for field_name, value in binding.constraints.items():
                    file_template = file_template.replace(f"{{{field_name}}}", value)

                pv = ProductVariant(
                    product_name=product_name,
                    format_id=binding.format,
                    version=binding.version,
                    variant=binding.variant,
                    file_template=file_template,
                    compression=fmt.get_compression(binding.version),
                )
                self._variants[product_name].append(pv)

    # -- access ------------------------------------------------------

    @property
    def products(self) -> Dict[str, ProductSpec]:
        return self._product_specs.products

    @property
    def format_catalog(self) -> FormatCatalog:
        return self._format_specs

    def get_variants(self, product_name: str) -> List[ProductVariant]:
        try:
            return self._variants[product_name]
        except KeyError:
            raise KeyError(
                f"Product {product_name!r} not found. "
                f"Available: {sorted(self._variants)}"
            )

    def get_variant(self, product_name: str, index: int = 0) -> ProductVariant:
        variants = self.get_variants(product_name)
        if index >= len(variants):
            raise IndexError(
                f"Product {product_name!r} has {len(variants)} variant(s), "
                f"requested index {index}"
            )
        return variants[index]

    # -- loader ------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "ProductCatalog":
        """Load both catalogs from a single YAML and resolve."""
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        format_catalog = FormatCatalog.model_validate(
            {"formats": raw.get("formats", {})}
        )
        product_spec_catalog = ProductSpecCatalog.model_validate(
            {"products": raw.get("products", {})}
        )
        return cls(format_catalog, product_spec_catalog)

