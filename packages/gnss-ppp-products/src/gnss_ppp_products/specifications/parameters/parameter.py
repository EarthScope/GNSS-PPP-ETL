"""Author: Franklyn Dunbar

Parameter model and ParameterCatalog — replaces MetadataField + MetadataCatalog.
"""

import datetime
import re
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field


class DerivationMethod(str, Enum):
    """How a parameter value is obtained."""

    ENUM = "enum"
    COMPUTED = "computed"


class Parameter(BaseModel):
    """A single metadata parameter with optional regex pattern and compute function."""

    name: str = Field(..., description="The name of the parameter.")
    value: Optional[str] = Field(None, description="The value of the parameter.")
    pattern: Optional[str] = Field(
        None, description="A regex pattern to match the parameter value."
    )
    description: Optional[str] = Field(
        None, description="A description of the parameter."
    )
    derivation: Optional[DerivationMethod] = Field(
        DerivationMethod.ENUM,
        description="The method used to derive the parameter value.",
    )
    compute: Optional[Callable[[datetime.datetime], str]] = Field(
        None,
        description="A callable that computes the parameter value from a datetime.",
        exclude=True,
    )

    class Config:
        arbitrary_types_allowed = True


def _extract_template_fields(template: str) -> list[str]:
    """Extract parameter names from ``{NAME}``-style placeholders."""
    return re.findall(r"{(\w+)}", template)


class ParameterCatalog:
    """Registry of parameters with pattern defaults and computed-field support.

    Replaces ``MetadataCatalog``.  Compatible with
    :func:`~gnss_ppp_products.utilities.metadata_funcs.register_computed_fields`.
    """

    def __init__(self, parameters: List[Parameter]):
        self.parameters = {parameter.name: parameter for parameter in parameters}

    def get(self, name: str, default=None) -> Optional[Parameter]:
        """Retrieve a parameter by name.

        Args:
            name: Parameter name.
            default: Value returned when *name* is not found.

        Returns:
            The :class:`Parameter` or *default*.
        """
        return self.parameters.get(name, default)

    def __contains__(self, item):
        return item in self.parameters

    def __getitem__(self, key):
        return self.parameters[key]

    # -- registration (compatible with register_computed_fields) -----

    def register(
        self,
        name: str,
        pattern: Optional[str] = None,
        *,
        compute: Optional[Callable[[datetime.datetime], str]] = None,
        description: Optional[str] = None,
    ) -> Parameter:
        """Register or update a parameter, optionally adding a compute function.

        Args:
            name: Parameter name.
            pattern: Regex pattern for the parameter value.
            compute: Callable that derives the value from a datetime.
            description: Human-readable description.

        Returns:
            The newly created or updated :class:`Parameter`.
        """
        existing = self.parameters.get(name)
        if existing is not None:
            updates: Dict[str, Any] = {}
            if pattern is not None:
                updates["pattern"] = pattern
            if compute is not None:
                updates["compute"] = compute
            if description is not None:
                updates["description"] = description
            p = existing.model_copy(update=updates, deep=True)
        else:
            p = Parameter(
                name=name,
                pattern=pattern,
                compute=compute,
                description=description,
                derivation=DerivationMethod.COMPUTED
                if compute
                else DerivationMethod.ENUM,
            )
        self.parameters[name] = p
        return p

    def computed(
        self,
        name: str,
        pattern: Optional[str] = None,
        *,
        description: Optional[str] = None,
    ):
        """Decorator that registers a computed parameter field.

        Args:
            name: Parameter name.
            pattern: Regex pattern for the parameter value.
            description: Human-readable description.

        Returns:
            A decorator that wraps the compute function.
        """

        def decorator(fn: Callable[[datetime.datetime], str]):
            self.register(name, pattern, compute=fn, description=description)
            return fn

        return decorator

    # -- bulk operations --------------------------------------------

    def defaults(self) -> Dict[str, str]:
        """Return ``{name: pattern}`` for every parameter with a pattern.

        Returns:
            Mapping of parameter names to their regex patterns.
        """
        return {
            p.name: p.pattern for p in self.parameters.values() if p.pattern is not None
        }

    def resolve_params(
        self,
        params: List[Any],
        date: datetime.datetime,
    ) -> Any:
        """Set ``.value`` on computed parameters from *date*.

        Args:
            params: List of :class:`Parameter`-like objects.
            date: Reference datetime for computed fields.

        Returns:
            The same *params* list with computed values filled in.
        """
        for param in params:
            p = self.parameters.get(param.name)
            if p is not None and p.compute is not None:
                param.value = p.compute(date)
        return params

    def interpolate(
        self,
        template: str,
        date: datetime.datetime,
        *,
        computed_only: bool = False,
    ) -> str:
        """Substitute ``{NAME}`` placeholders in *template*.

        Args:
            template: String containing ``{NAME}``-style placeholders.
            date: Reference datetime for computed fields.
            computed_only: If ``True``, only replace computed parameters.

        Returns:
            The interpolated string.
        """
        fields = _extract_template_fields(template)
        values: Dict[str, str] = {}
        for key in fields:
            p = self.parameters.get(key)
            if p is None:
                continue
            if p.compute is not None:
                values[key] = p.compute(date)
            elif not computed_only and p.pattern is not None:
                values[key] = p.pattern
        for key, value in values.items():
            template = template.replace("{" + key + "}", value)
        return template

    # -- YAML loader ------------------------------------------------

    @classmethod
    def from_yaml(cls, yaml_path: Union[str, Path]) -> "ParameterCatalog":
        """Load parameter definitions from a meta-spec YAML file.

        Does **not** register computed fields — call
        :func:`~gnss_ppp_products.utilities.metadata_funcs.register_computed_fields`
        separately after loading.
        """
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
        params: List[Parameter] = []
        for name, entries in data.items():
            kw: Dict[str, Any] = {"name": name}
            for entry in entries:
                if isinstance(entry, dict):
                    kw.update(entry)
            params.append(Parameter(**kw))
        return cls(parameters=params)

    def merge(self, other: "ParameterCatalog") -> "ParameterCatalog":
        """Merge another catalog into this one.

        Duplicate names are overwritten by *other* with a warning.

        Args:
            other: Catalog to merge.

        Returns:
            A new :class:`ParameterCatalog` with combined parameters.
        """
        merged = self.parameters.copy()
        for name, param in other.parameters.items():
            if name in merged:
                print(
                    f"Warning: Duplicate parameter name '{name}' found. Overwriting with new value."
                )
            merged[name] = param
        return ParameterCatalog(parameters=list(merged.values()))
