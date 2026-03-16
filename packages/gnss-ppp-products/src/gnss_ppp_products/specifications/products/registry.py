"""
Product specification registry — pure spec code.

Wraps :class:`ProductSpec` with a metadata registry for regex building.
No singleton created at import time; callers use ``load_from_yaml(path)``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Union

from .models import (
    Format,
    FormatVersion,
    Product,
    ProductFormatRef,
    ProductSpec,
)


class _ProductSpecRegistry:
    """Pairs a loaded :class:`ProductSpec` with a metadata registry
    for regex / template resolution.
    """

    def __init__(self, spec: ProductSpec, *, meta_registry=None) -> None:
        self._spec = spec
        self._meta_registry = meta_registry


    # ------------------------------------------------------------------
    # Template / constraint resolution
    # ------------------------------------------------------------------

    def resolve_filename_templates(
        self,
        product_name: str,
        ref_index: int = 0,
    ) -> List[str]:
        return self._spec.resolve_filename_templates(product_name, ref_index)

    def resolve_metadata_constraints(
        self,
        product_name: str,
        ref_index: int = 0,
    ) -> Dict[str, str]:
        return self._spec.resolve_metadata_constraints(product_name, ref_index)

    # ------------------------------------------------------------------
    # Regex generation
    # ------------------------------------------------------------------

    def to_regex(
        self,
        product_name: str,
        ref_index: int = 0,
    ) -> List[str]:
        """Build filename regex(es) for a product format reference.

        Uses the attached metadata registry for default patterns when
        available; otherwise falls back to ``ProductSpec.metadata_defaults``.
        """
        if self._meta_registry is None:
            return self._spec.to_regex(product_name, ref_index)

        templates = self.resolve_filename_templates(product_name, ref_index)
        constraints = self.resolve_metadata_constraints(product_name, ref_index)

        product = self._spec.products[product_name]
        ref = product.formats[ref_index]
        fmt = self._spec.formats[ref.format]
        ver = fmt.versions[ref.version]
        format_overrides = ver.get_metadata_overrides()

        meta_defaults = self._meta_registry.defaults()

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
    def from_yaml(
        cls,
        yaml_path: Union[str, Path],
        *,
        meta_registry=None,
    ) -> "_ProductSpecRegistry":
        """Load from YAML. No default path — caller must supply one."""
        spec = ProductSpec.from_yaml(yaml_path)
        return cls(spec, meta_registry=meta_registry)
