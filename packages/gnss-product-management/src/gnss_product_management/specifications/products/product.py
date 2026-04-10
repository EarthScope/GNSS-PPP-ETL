"""Author: Franklyn Dunbar

Core product models — PathTemplate, Product, and catalog hierarchies.
"""

import re
from typing import Generic, TypeVar

from gnss_product_management.specifications.parameters.parameter import (
    Parameter,
    ParameterCatalog,
)
from pydantic import BaseModel, Field


class PathTemplate(BaseModel):
    """A template pattern with ``{NAME}``-style placeholders, resolved via :meth:`derive`."""

    pattern: str = Field(description="A template pattern with {NAME}-style placeholders.")
    value: str | None = Field(None, description="The resolved value after derivation.")
    description: str | None = Field(None, description="A description of the path template.")

    def derive(self, parameters: list[Parameter]) -> None:
        """Replace ``{PARAM}`` placeholders in *pattern* with parameter values.

        Args:
            parameters: List of parameters to substitute.
        """
        if self.value is not None:
            return

        for param in parameters:
            if f"{{{param.name}}}" in self.pattern:
                if param.value is not None:
                    self.pattern = self.pattern.replace(f"{{{param.name}}}", param.value)

        return None

    def to_regex(self, parameter_catalog: ParameterCatalog) -> str:
        """Convert the template pattern into a regex with named capture groups.

        Each ``{PARAM}`` placeholder is replaced with ``(?P<PARAM>pattern)``
        using the parameter's regex from *parameter_catalog*.  Literal
        characters outside placeholders are escaped.

        Args:
            parameter_catalog: Catalog supplying regex patterns for each
                parameter name.

        Returns:
            A regex string suitable for :func:`re.fullmatch`.
        """
        template = self.pattern
        # Split the template into placeholder tokens and literal segments
        tokens = re.split(r"(\{(\w+)\})", template)
        regex_parts: list[str] = []
        i = 0
        while i < len(tokens):
            # re.split with 2 groups produces [literal, full_match, group_name, ...]
            if i + 2 < len(tokens) and tokens[i + 1] is not None and tokens[i + 1].startswith("{"):
                # Literal segment before this placeholder
                literal = tokens[i]
                if literal:
                    regex_parts.append(re.escape(literal))
                # Named group for the parameter
                param_name = tokens[i + 2]
                param = parameter_catalog.get(param_name)
                param_pattern = param.pattern if param and param.pattern else r".+"
                regex_parts.append(f"(?P<{param_name}>{param_pattern})")
                i += 3
            else:
                # Trailing literal or segment with no placeholder
                literal = tokens[i]
                if literal:
                    # Preserve .* as regex wildcard (common suffix for compression)
                    literal = re.sub(r"\.\*", "\x00DOTSTAR\x00", literal)
                    escaped = re.escape(literal)
                    escaped = escaped.replace("\x00DOTSTAR\x00", ".*")
                    regex_parts.append(escaped)
                i += 1
        return "".join(regex_parts)


def infer_from_regex(
    regex: str,
    filename: str,
    parameters: list[Parameter],
) -> list[Parameter] | None:
    """Infer parameter values from *filename* using a pre-built *regex*.

    After ``derive()`` and the query-factory's "fill in patterns" step,
    each parameter's ``.value`` is either a concrete literal or its regex
    pattern.  This function reconstructs a named-group regex by replacing
    each parameter's contribution with ``(?P<name>pattern)``, then
    matches *filename* and updates every parameter's ``.value``.

    Args:
        regex: Pre-built regex string (values already substituted).
        filename: Product filename to match.
        parameters: Ordered list of parameters (template order,
            left-to-right).

    Returns:
        The updated parameter list on match, or ``None``.
    """
    # Single left-to-right pass: find each param.value at its expected
    # position and wrap it with a named capture group.
    pos = 0
    parts: list[str] = []
    for param in parameters:
        if param.value is None or param.pattern is None:
            continue
        idx = regex.find(param.value, pos)
        if idx == -1:
            continue
        # Literal regex text between the previous param and this one
        parts.append(regex[pos:idx])
        parts.append(f"(?P<{param.name}>{param.pattern})")
        pos = idx + len(param.value)
    # Remaining suffix (e.g. ``.*`` for compression)
    parts.append(regex[pos:])
    named_regex = "".join(parts)

    m = re.fullmatch(named_regex, filename)
    if m is None:
        return None

    for param in parameters:
        extracted = m.groupdict().get(param.name)
        if extracted is not None:
            param.value = extracted
    return parameters


class Product(BaseModel):
    """A resolved product with its parameters and file/directory templates."""

    name: str = Field(..., description="The name of the product.")
    parameters: list[Parameter] = Field(..., description="A list of parameters for the product.")
    directory: PathTemplate | None = Field(
        default=None, description="The directory where the product is located."
    )
    filename: PathTemplate | None = Field(
        default=None, description="The filename pattern for the product."
    )


T = TypeVar("T")


class VariantCatalog(BaseModel, Generic[T]):
    """Collection of named variants for a single version.

    Attributes:
        variants: Mapping of variant name to product instance.
    """

    variants: dict[str, T]


class VersionCatalog(BaseModel, Generic[T]):
    """Collection of named versions, each containing variants.

    Attributes:
        versions: Mapping of version name to :class:`VariantCatalog`.
    """

    versions: dict[str, VariantCatalog[T]]
