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
    file_templates: List[str]
    constraints: Dict[str, str] = Field(default_factory=dict)
    field_defaults: Dict[str, str] = Field(default_factory=dict)
    compression: List[str] = Field(default_factory=list)


# ===================================================================
# Catalog (YAML loader)
# ===================================================================


class ProductCatalog(BaseModel):
    """Collection of product declarations from the ``products:`` YAML key."""

    products: Dict[str, ProductSpec] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "ProductCatalog":
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate({"products": raw.get("products", {})})


# ===================================================================
# Resolver
# ===================================================================


class ProductResolver:
    """Resolves product bindings against a format catalog into
    :class:`ProductVariant` objects.
    """

    def __init__(
        self,
        format_catalog: FormatCatalog,
        product_catalog: ProductCatalog,
    ) -> None:
        self._formats = format_catalog
        self._products = product_catalog
        self._variants: Dict[str, List[ProductVariant]] = defaultdict(list)
        self._resolve_all()

    def _resolve_all(self) -> None:
        """Walk every product binding and resolve it."""
        for product_name, product in self._products.products.items():
            for binding in product.formats:
                fmt: FormatSpec = self._formats.get_format(binding.format)
                ver: FormatVersionSpec = fmt.versions[binding.version]

                # Resolve file templates — apply constraint substitutions
                raw_templates: List[str] = ver.file_templates.get(
                    binding.variant, []
                )
                resolved_templates: List[str] = []
                for tmpl in raw_templates:
                    t = tmpl
                    for field_name, value in binding.constraints.items():
                        t = t.replace(f"{{{field_name}}}", value)
                    resolved_templates.append(t)

                pv = ProductVariant(
                    product_name=product_name,
                    format_id=binding.format,
                    version=binding.version,
                    variant=binding.variant,
                    file_templates=resolved_templates,
                    constraints=dict(binding.constraints),
                    field_defaults=ver.get_field_defaults(),
                    compression=fmt.get_compression(binding.version),
                )
                self._variants[product_name].append(pv)

    # -- access ------------------------------------------------------

    @property
    def products(self) -> Dict[str, ProductSpec]:
        return self._products.products

    @property
    def format_catalog(self) -> FormatCatalog:
        return self._formats

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

    # -- regex generation --------------------------------------------

    def to_regex(
        self,
        product_name: str,
        variant_index: int = 0,
        *,
        meta_defaults: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """Build filename regexes for a resolved product variant.

        Resolution priority for each ``{FIELD}`` placeholder:
        1. ``variant.constraints``
        2. ``variant.field_defaults``
        3. ``meta_defaults`` (global metadata patterns)
        4. ``.+`` fallback
        """
        variant = self.get_variant(product_name, variant_index)

        _PLACEHOLDER = re.compile(r"\{([^}]+)\}")
        _WB = re.compile(r"\\b")

        def _ci_get(mapping: Dict[str, str], key: str) -> Optional[str]:
            if key in mapping:
                return mapping[key]
            for k, v in mapping.items():
                if k.lower() == key.lower():
                    return v
            return None

        regexes: List[str] = []

        for tmpl in variant.file_templates:
            parts: List[str] = []
            last_end = 0
            for m in _PLACEHOLDER.finditer(tmpl):
                literal = re.escape(tmpl[last_end : m.start()])
                parts.append(literal.replace(r"\.\*", ".*").replace(r"\*", ".*"))

                field = m.group(1)
                hit = _ci_get(variant.constraints, field)
                if hit is None:
                    hit = _ci_get(variant.field_defaults, field)
                if hit is None and meta_defaults:
                    hit = _ci_get(meta_defaults, field)
                parts.append(_WB.sub("", hit) if hit is not None else ".+")
                last_end = m.end()

            trailing = re.escape(tmpl[last_end:])
            parts.append(trailing.replace(r"\.\*", ".*").replace(r"\*", ".*"))
            regexes.append("".join(parts))

        return regexes

    # -- loader ------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "ProductResolver":
        """Load both catalogs from a single YAML and resolve."""
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        format_catalog = FormatCatalog.model_validate(
            {"formats": raw.get("formats", {})}
        )
        product_catalog = ProductCatalog.model_validate(
            {"products": raw.get("products", {})}
        )
        return cls(format_catalog, product_catalog)


# ===================================================================
# Registry (pairs resolver with metadata catalog)
# ===================================================================


class ProductSpecRegistry:
    """Pairs a :class:`ProductResolver` with a metadata catalog.

    This is the main entry point downstream code interacts with.
    """

    def __init__(
        self, resolver: ProductResolver, *, meta_catalog=None
    ) -> None:
        self._resolver = resolver
        self._meta_catalog = meta_catalog

    @property
    def products(self) -> Dict[str, ProductSpec]:
        return self._resolver.products

    @property
    def formats(self) -> Dict[str, FormatSpec]:
        return self._resolver.format_catalog.formats

    def get_variant(self, product_name: str, variant_index: int = 0) -> ProductVariant:
        return self._resolver.get_variant(product_name, variant_index)

    def get_variants(self, product_name: str) -> List[ProductVariant]:
        return self._resolver.get_variants(product_name)

    def to_regex(
        self,
        product_name: str,
        variant_index: int = 0,
    ) -> List[str]:
        """Build regexes using the paired metadata catalog defaults."""
        meta_defaults = self._meta_catalog.defaults() if self._meta_catalog else None
        return self._resolver.to_regex(
            product_name, variant_index, meta_defaults=meta_defaults
        )

    @classmethod
    def from_yaml(
        cls,
        yaml_path: Union[str, Path],
        *,
        meta_catalog=None,
    ) -> "ProductSpecRegistry":
        resolver = ProductResolver.from_yaml(yaml_path)
        return cls(resolver, meta_catalog=meta_catalog)
