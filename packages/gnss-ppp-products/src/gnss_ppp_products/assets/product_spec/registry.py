"""
Product specification registry.

Wraps :class:`~productspec.ProductSpec` (the Pydantic data layer) with
the :class:`MetaDataRegistry` so that regex building and template
resolution use the canonical metadata definitions.

The module-level ``ProductSpecRegistry`` singleton is loaded from the
bundled ``product_spec.yaml`` at import time.

Usage::

    from gnss_ppp_products.assets.product_spec import ProductSpecRegistry

    templates = ProductSpecRegistry.resolve_filename_templates("ORBIT")
    regexes  = ProductSpecRegistry.to_regex("ORBIT")
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Union

from .productspec import (
    Format,
    FormatVersion,
    Product,
    ProductFormatRef,
    ProductSpec,
)
from gnss_ppp_products.assets.meta_spec import MetaDataRegistry

_DEFAULT_YAML = Path(__file__).resolve().parent / "product_spec.yaml"


class _ProductSpecRegistry:
    """Singleton that pairs a loaded :class:`ProductSpec` with the
    :class:`MetaDataRegistry` for regex / template resolution.

    Mirrors the pattern used by ``_MetadataRegistry``: the YAML is
    loaded once at module level and the instance is importable
    everywhere.
    """

    def __init__(self, spec: ProductSpec) -> None:
        self._spec = spec

    # ------------------------------------------------------------------
    # Forwarded look-ups (thin wrappers over ProductSpec)
    # ------------------------------------------------------------------

    @property
    def campaigns(self) -> List[str]:
        return self._spec.campaigns

    @property
    def solutions(self) -> List[str]:
        return self._spec.solutions

    @property
    def content_types(self) -> List[str]:
        return self._spec.content_types

    @property
    def format_types(self) -> List[str]:
        return self._spec.format_types

    @property
    def formats(self) -> Dict[str, Format]:
        return self._spec.formats

    @property
    def products(self) -> Dict[str, Product]:
        return self._spec.products

    def get_format(self, name: str) -> Format:
        return self._spec.get_format(name)

    def get_product(self, name: str) -> Product:
        return self._spec.get_product(name)

    # ------------------------------------------------------------------
    # Template / constraint resolution (delegates to ProductSpec)
    # ------------------------------------------------------------------

    def resolve_filename_templates(
        self,
        product_name: str,
        ref_index: int = 0,
    ) -> List[str]:
        """Return filename template strings for a product format ref."""
        return self._spec.resolve_filename_templates(product_name, ref_index)

    def resolve_metadata_constraints(
        self,
        product_name: str,
        ref_index: int = 0,
    ) -> Dict[str, str]:
        """Flatten a product format ref's metadata into ``{field: pattern}``."""
        return self._spec.resolve_metadata_constraints(product_name, ref_index)

    # ------------------------------------------------------------------
    # Regex generation — uses MetaDataRegistry for default patterns
    # ------------------------------------------------------------------

    def to_regex(
        self,
        product_name: str,
        ref_index: int = 0,
    ) -> List[str]:
        """Build filename regex(es) for a product format reference.

        Resolution order for each ``{FIELD}`` placeholder:

        1. Product-level constraint (from product YAML metadata).
        2. Format-version override (``default`` key in format metadata).
        3. :data:`MetaDataRegistry` default pattern.
        4. Generic ``".+"`` catch-all.
        """
        templates = self.resolve_filename_templates(product_name, ref_index)
        constraints = self.resolve_metadata_constraints(product_name, ref_index)

        product = self._spec.products[product_name]
        ref = product.formats[ref_index]
        fmt = self._spec.formats[ref.format]
        ver = fmt.versions[ref.version]
        format_overrides = ver.get_metadata_overrides()

        # Pull default patterns from the authoritative MetaDataRegistry
        meta_defaults = MetaDataRegistry.defaults()

        _PLACEHOLDER = re.compile(r"\{([^}]+)\}")
        _WB = re.compile(r"\\b")

        def _ci_get(mapping: Dict[str, str], key: str) -> Optional[str]:
            if key in mapping:
                return mapping[key]
            key_lower = key.lower()
            for k, v in mapping.items():
                if k.lower() == key_lower:
                    return v
            return None

        def _strip_wb(pattern: str) -> str:
            return _WB.sub("", pattern)

        regexes: List[str] = []

        for tmpl in templates:
            parts: List[str] = []
            last_end = 0
            for m in _PLACEHOLDER.finditer(tmpl):
                literal = re.escape(tmpl[last_end : m.start()])
                parts.append(literal.replace(r"\.\*", ".*").replace(r"\*", ".*"))

                field = m.group(1)
                hit = _ci_get(constraints, field)
                if hit is None:
                    hit = _ci_get(format_overrides, field)
                if hit is None:
                    hit = _ci_get(meta_defaults, field)
                parts.append(_strip_wb(hit) if hit is not None else ".+")
                last_end = m.end()

            trailing = re.escape(tmpl[last_end:])
            parts.append(trailing.replace(r"\.\*", ".*").replace(r"\*", ".*"))
            regexes.append("".join(parts))

        return regexes

    # ------------------------------------------------------------------
    # Loader
    # ------------------------------------------------------------------

    @classmethod
    def load_from_yaml(
        cls, yaml_path: Union[str, Path] = _DEFAULT_YAML
    ) -> "_ProductSpecRegistry":
        spec = ProductSpec.from_yaml(yaml_path)
        return cls(spec)


# ===================================================================
# Canonical singleton — import this everywhere
# ===================================================================
ProductSpecRegistry = _ProductSpecRegistry.load_from_yaml()
