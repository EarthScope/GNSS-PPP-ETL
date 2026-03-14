from __future__ import annotations

import re
import datetime
from pydantic import BaseModel
import yaml
from pathlib import Path
from typing import Callable, Dict, List, Optional

_GPS_EPOCH = datetime.date(1980, 1, 6)

def extract_template_fields(template: str) -> list[str]:
    """Extract all metadata field names from a template string.

    E.g. "orography_ell_{RESOLUTION}" -> ["RESOLUTION"]
    """


    return re.findall(r"{(\w+)}", template)

class MetadataField(BaseModel):
    """A single registered metadata key."""

    name: str  # canonical key, e.g. "YYYY"
    pattern: Optional[str] = None  # default regex for matching
    compute: Optional[Callable[[datetime.date], str]] = None  # derive a concrete value
    description: Optional[str] = None


class _MetadataRegistry:
    """Central registry of all metadata keys.

    Register fields either declaratively or via the ``@computed``
    decorator.
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

    @property
    def fields(self) -> Dict[str, MetadataField]:
        return dict(self._fields)

    # -- bulk operations ---------------------------------------------

    def defaults(self) -> Dict[str, str]:
        """Return ``{name: pattern}`` for every registered field.

        Drop-in replacement for ``metadata_defaults`` in ProductSpec.
        """
        return {f.name: f.pattern for f in self._fields.values() if f.pattern is not None}

    def resolve(
        self,
        template: str,
        date: datetime.datetime,
        *,
        computed_only: bool = False,
    ) -> str:
        """Substitute metadata placeholders in *template*.

        Parameters
        ----------
        template : str
            A string containing ``{FIELD}`` placeholders.
        date : datetime.datetime
            The date/time used to evaluate computed fields.
        computed_only : bool
            When ``True``, only fields that have a ``compute`` function
            are substituted — non-computable placeholders are left
            untouched (useful for directory templates where patterns
            would be meaningless).  When ``False`` (default), non-
            computable fields fall back to their regex ``pattern``.
        """
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
    def load_from_yaml(cls,yaml_path: str|Path) -> '_MetadataRegistry':
        """Load metadata field definitions from a YAML file."""

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
# ===================================================================
# Canonical registry instance  (import this everywhere)
# ===================================================================
MetaDataRegistry = _MetadataRegistry.load_from_yaml(
    yaml_path=Path(__file__).parent / "meta_spec.yaml"
)
