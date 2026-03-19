"""
Metadata catalog — registry of metadata fields with template resolution.

Wraps :class:`MetadataField` spec models into a live registry that can
resolve ``{YYYY}``-style placeholders in path and filename templates.
"""

from __future__ import annotations

import re
import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from gnss_ppp_products.specifications.metadata.metadata import MetadataField


def extract_template_fields(template: str) -> list[str]:
    """Extract metadata field names from a template string.

    ``"orography_ell_{RESOLUTION}"`` → ``["RESOLUTION"]``
    """
    return re.findall(r"{(\w+)}", template)


class MetadataCatalog:
    """Registry of metadata keys with pattern and compute support.

    Replaces ``_MetadataRegistry``.
    """

    def __init__(self) -> None:
        self._fields: Dict[str, MetadataField] = {}

    # -- registration ------------------------------------------------

    def register(
        self,
        name: str,
        pattern: Optional[str] = None,
        *,
        compute: Optional[Callable[[datetime.datetime], str]] = None,
        description: Optional[str] = None,
    ) -> MetadataField:
        f = MetadataField(
            name=name, pattern=pattern, compute=compute, description=description
        )
        if name in self._fields:
            updates = {k: v for k, v in f.model_dump().items() if v is not None}
            f = self._fields[name].model_copy(update=updates)

        self._fields[name] = f
        return f

    def computed(
        self,
        name: str,
        pattern: Optional[str] = None,
        *,
        description: Optional[str] = None,
    ):
        """Decorator that registers a computed metadata field."""

        def decorator(fn: Callable[[datetime.datetime], str]):
            self.register(name, pattern, compute=fn, description=description)
            return fn

        return decorator

    # -- lookup ------------------------------------------------------

    def __getitem__(self, name: str) -> MetadataField:
        return self._fields[name]

    def __contains__(self, name: str) -> bool:
        return name in self._fields

    def get(self, name: str) -> Optional[MetadataField]:
        return self._fields.get(name)

    # -- bulk operations ---------------------------------------------

    def defaults(self) -> Dict[str, str]:
        """Return ``{name: pattern}`` for every field with a pattern."""
        return {
            f.name: f.pattern
            for f in self._fields.values()
            if f.pattern is not None
        }

    def resolve_params(self,
                     params: List[Any],
                     date: datetime.datetime,) ->Any:
        for param in params:

            
            if param.name in self._fields:
                field = self._fields[param.name]
                if field.compute is not None:
                    param.value = field.compute(date)
        return params
    
    def resolve(
        self,
        template: str,
        date: datetime.datetime,
        *,
        computed_only: bool = False,
    ) -> str:
        """Substitute metadata placeholders in *template*."""
        template_fields: List[str] = extract_template_fields(template)
        values: Dict[str, str] = {}
        for key in template_fields:
            field = self._fields.get(key)
            if field is None:
                continue
            if field.compute is not None :
                values[key] = field.compute(date)
            elif not computed_only and field.pattern is not None:
                values[key] = field.pattern

        for key, value in values.items():
            template = template.replace("{" + key + "}", value)
        return template

    # -- loader ------------------------------------------------------

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "MetadataCatalog":
        """Load metadata field definitions from a YAML file.

        Does **not** register computed fields — call
        :func:`register_computed_fields` separately after loading.
        """
        catalog = cls()

        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        for name, entries in data.items():
            pattern = None
            description = ""
            for entry in entries:
                if "pattern" in entry:
                    pattern = entry["pattern"]
                if "description" in entry:
                    description = entry["description"]

            if pattern is not None:
                catalog.register(name, pattern, description=description)
        return catalog
