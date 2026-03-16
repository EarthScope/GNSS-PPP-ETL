"""
Metadata registry — pure spec code.

Defines :class:`MetadataField` and :class:`_MetadataRegistry` with no
hardcoded YAML paths and no global singleton created at import time.
Callers create instances via ``_MetadataRegistry.load_from_yaml(path)``.
"""

import re
import datetime
from pydantic import BaseModel
import yaml
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .models import MetadataField

def extract_template_fields(template: str) -> list[str]:
    """Extract all metadata field names from a template string.

    E.g. ``"orography_ell_{RESOLUTION}"`` → ``["RESOLUTION"]``
    """
    return re.findall(r"{(\w+)}", template)


class _MetadataRegistry:
    """Central registry of all metadata keys.

    Register fields either declaratively (from YAML) or via the
    ``@computed`` decorator.

    This class is intentionally agnostic — it knows nothing about
    where YAML files live.  Callers provide the path explicitly.
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
        """Decorator that registers a computed metadata field.

        Usage::

            @registry.computed("YYYY", r"\\d{4}")
            def _yyyy(dt: datetime.date) -> str:
                return f"{dt.year:04d}"
        """

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
        """Return ``{name: pattern}`` for every registered field."""
        return {f.name: f.pattern for f in self._fields.values() if f.pattern is not None}

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
            if field.compute is not None:
                values[key] = field.compute(date)
            elif not computed_only and field.pattern is not None:
                values[key] = field.pattern

        for key, value in values.items():
            template = template.replace("{" + key + "}", value)
        return template

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> '_MetadataRegistry':
        """Load metadata field definitions from a YAML file.

        Does **not** register computed fields — call
        :func:`~gnss_ppp_products.utilities.metadata_funcs.register_computed_fields`
        separately after loading.
        """
        metadata_registry = cls()

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
                metadata_registry.register(name, pattern, description=description)
        return metadata_registry
