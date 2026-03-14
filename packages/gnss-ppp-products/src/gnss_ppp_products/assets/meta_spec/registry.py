from __future__ import annotations
from calendar import c
import re
import datetime
from turtle import st
from pydantic import BaseModel,field
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
        return {f.name: f.pattern for f in self._fields.values()}

    def resolve(self, template:str,date:datetime.datetime) -> str:
        """Compute concrete values for all datetime-derived fields.

        Returns ``{name: value}`` only for fields that have a
        ``compute`` function.  Non-computable fields are omitted.
        """
        # find all template fields that have a compute function, call it with the date, and return the results as a dict
        # f"{YYYY}_{DDD}" -> ["YYYY","DDD"] -> {"YYYY": compute(YYYY), "DDD": compute(DDD)}
        templates_fields: List[str] = extract_template_fields(template)
        values = {}
        for key in templates_fields:
            if getattr(self._fields[key], "compute", None):
                values[key] = self._fields[key].compute(date)
            else:
                values[key] = self._fields[key].pattern

        # now we update the template with the computed values, replacing {YYYY} with the computed year, etc.
        for key, value in values.items():
            to_replace = "{" + key + "}"
            template = template.replace(to_replace, value)
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
