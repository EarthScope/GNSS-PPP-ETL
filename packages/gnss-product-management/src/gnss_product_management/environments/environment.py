"""Author: Franklyn Dunbar

ProductRegistry — builds the full catalog chain and remote search planner.

Loads parameter, format, product, and resource specification YAMLs, then
builds derived catalogs (``ParameterCatalog`` → ``FormatCatalog`` →
``ProductCatalog`` → ``RemoteSearchPlanner``).  Also provides
:meth:`~ProductRegistry.classify` for parsing product filenames back
into structured metadata.
"""

from pathlib import Path

from typing import Any, Dict, NamedTuple, Optional, List
import re


from gnss_product_management.specifications.remote.resource import ResourceSpec
from pydantic import BaseModel


from gnss_product_management.specifications.format.format_spec import (
    FormatCatalog,
    FormatSpecCatalog,
)
from gnss_product_management.specifications.parameters.parameter import (
    Parameter,
    ParameterCatalog,
)
from gnss_product_management.specifications.products.catalog import (
    ProductCatalog,
    ProductSpecCatalog,
)
from gnss_product_management.factories.remote_search_planner import (
    RemoteSearchPlanner,
)
from gnss_product_management.utilities.metadata_funcs import register_computed_fields


class _MatchEntry(NamedTuple):
    """Pre-compiled regex entry for filename classification.

    Sorted by template length (longest first) so that more specific
    patterns take precedence during :meth:`ProductRegistry.classify`.
    """

    template_len: int
    compiled_regex: re.Pattern
    product_name: str
    format_name: str
    version: str
    variant: str
    fixed_params: dict


def _merged_parameter_catalog(
    base: ParameterCatalog,
    product_params: List[Parameter],
) -> ParameterCatalog:
    """Merge product-specific parameter patterns into the global catalog.

    Args:
        base: The global :class:`ParameterCatalog`.
        product_params: Product-level parameter overrides.

    Returns:
        A new :class:`ParameterCatalog` with overrides applied.
    """
    merged = {
        name: param.model_copy(deep=True) for name, param in base.parameters.items()
    }
    for p in product_params:
        if p.name in merged:
            updates = {}
            if p.pattern is not None:
                updates["pattern"] = p.pattern
            if updates:
                merged[p.name] = merged[p.name].model_copy(update=updates, deep=True)
        else:
            merged[p.name] = p.model_copy(deep=True)
    return ParameterCatalog(list(merged.values()))


def _build_match_table(
    product_spec_catalog: ProductSpecCatalog,
    product_catalog: ProductCatalog,
    parameter_catalog: ParameterCatalog,
) -> list[_MatchEntry]:
    """Pre-compile a regex match table sorted by template specificity.

    Longer filename templates are checked first so that more specific
    patterns take precedence over generic ones during classification.

    Args:
        product_spec_catalog: The raw product spec definitions.
        product_catalog: The resolved product catalog.
        parameter_catalog: The global parameter catalog.

    Returns:
        A list of :class:`_MatchEntry` tuples sorted longest-first.
    """
    entries: list[_MatchEntry] = []
    for prod_name, ver_cat in product_catalog.products.items():
        for ver_name, var_cat in ver_cat.versions.items():
            for var_name, product in var_cat.variants.items():
                if product.filename is None:
                    continue
                spec = (
                    product_spec_catalog.products[prod_name]
                    .versions[ver_name]
                    .variants[var_name]
                )
                merged = _merged_parameter_catalog(
                    parameter_catalog, product.parameters
                )
                regex_str = product.filename.to_regex(merged)
                entries.append(
                    _MatchEntry(
                        template_len=len(product.filename.pattern),
                        compiled_regex=re.compile(regex_str),
                        product_name=prod_name,
                        format_name=spec.format,
                        version=ver_name,
                        variant=var_name,
                        fixed_params={
                            p.name: p.value
                            for p in product.parameters
                            if p.value is not None
                        },
                    )
                )
    entries.sort(key=lambda e: -e.template_len)
    return entries


class LoadedSpecs(BaseModel):
    """Record of a loaded specification file and its parsed result."""

    filename: Path | str
    built: Any


class ProductRegistry:
    """Unified container for the specification / factory layer.

    Incrementally loads YAML specs via ``add_*()`` methods, then calls
    :meth:`build` to derive the full catalog chain::

        ParameterCatalog → FormatCatalog → ProductCatalog → RemoteSearchPlanner

    After building, :meth:`classify` parses a product filename into
    structured metadata (product name, format, version, variant, parameters).

    Attributes:
        _parameter_catalog: Built parameter catalog (available after :meth:`build`).
        _format_catalog: Built format catalog (available after :meth:`build`).
        _product_catalog: Built product catalog (available after :meth:`build`).
        _remote_resource_factory: Built remote planner (available after :meth:`build`).
    """

    def __init__(self) -> None:
        """Initialise an empty registry with no specs loaded."""

        self._parameter_specs: Dict[str, LoadedSpecs] = {}
        self._format_specs: Dict[str, LoadedSpecs] = {}
        self._product_specs: Dict[str, LoadedSpecs] = {}
        self._resource_specs: Dict[str, LoadedSpecs] = {}

        self._parameter_catalog: Optional[ParameterCatalog] = None
        self._format_catalog: Optional[FormatCatalog] = None
        self._product_spec_catalog: Optional[ProductSpecCatalog] = None
        self._product_catalog: Optional[ProductCatalog] = None
        self._remote_resource_factory: Optional[RemoteSearchPlanner] = None

    def add_parameter_spec(self, path: Path | str, id: str = "default") -> None:
        """Load and register a parameter specification YAML file.

        Args:
            path: Filesystem path to the YAML file.
            id: Unique identifier for this spec (default ``'default'``).
        """
        path = Path(path)
        assert path.exists(), f"Parameter spec file not found: {path}"
        assert path.is_file(), f"Parameter spec path must be a file: {path}"
        assert id not in self._parameter_specs, (
            f"Parameter spec with id '{id}' already exists. Please choose a unique id."
        )
        parameter_spec_catalog = ParameterCatalog.from_yaml(path)
        self._parameter_specs[id] = LoadedSpecs(
            filename=path, built=parameter_spec_catalog
        )

    def add_format_spec(self, path: Path | str, id: str = "default") -> None:
        """Load and register a format specification YAML file.

        Args:
            path: Filesystem path to the YAML file.
            id: Unique identifier for this spec (default ``'default'``).
        """
        path = Path(path)
        assert path.exists(), f"Format spec file not found: {path}"
        assert path.is_file(), f"Format spec path must be a file: {path}"
        assert id not in self._format_specs, (
            f"Format spec with id '{id}' already exists. Please choose a unique id."
        )

        format_spec_catalog = FormatSpecCatalog.from_yaml(path)
        self._format_specs[id] = LoadedSpecs(filename=path, built=format_spec_catalog)

    def add_product_spec(self, path: Path | str, id: str = "default") -> None:
        """Load and register a product specification YAML file.

        Args:
            path: Filesystem path to the YAML file.
            id: Unique identifier for this spec (default ``'default'``).
        """
        path = Path(path)
        assert path.exists(), f"Product spec file not found: {path}"
        assert path.is_file(), f"Product spec path must be a file: {path}"
        assert id not in self._product_specs, (
            f"Product spec with id '{id}' already exists. Please choose a unique id."
        )
        product_spec: ProductSpecCatalog = ProductSpecCatalog.from_yaml(path)
        self._product_specs[id] = LoadedSpecs(filename=path, built=product_spec)
        if self._product_spec_catalog is None:
            self._product_spec_catalog = product_spec
        else:
            self._product_spec_catalog = self._product_spec_catalog.merge(product_spec)

    def add_resource_spec(self, path: Path | str) -> None:
        """Load and register a remote resource specification YAML file.

        Args:
            path: Filesystem path to the YAML file.
        """
        path = Path(path)
        assert path.exists(), f"Resource spec file not found: {path}"
        assert path.is_file(), f"Resource spec path must be a file: {path}"

        resource_spec = ResourceSpec.from_yaml(path)
        id = resource_spec.id
        assert id not in self._resource_specs, (
            f"Resource spec with id '{id}' already exists. Please choose a unique id."
        )
        self._resource_specs[id] = LoadedSpecs(filename=path, built=resource_spec)

    def _build_parameter_catalog(self) -> None:
        """Build the merged :class:`ParameterCatalog` from loaded specs."""
        for id, spec in self._parameter_specs.items():
            if self._parameter_catalog is None:
                self._parameter_catalog = ParameterCatalog.from_yaml(spec.filename)
            else:
                new_cat = ParameterCatalog.from_yaml(spec.filename)
                self._parameter_catalog = self._parameter_catalog.merge(new_cat)
        register_computed_fields(self._parameter_catalog)

    def _build_format_catalog(self) -> None:
        """Build the :class:`FormatCatalog` from loaded format specs."""
        assert self._parameter_catalog is not None, (
            "Parameter catalog must be built before building format catalog"
        )
        for id, spec in self._format_specs.items():
            format_catalog_new = FormatCatalog.build(
                format_spec_catalog=spec.built,
                parameter_catalog=self._parameter_catalog,
            )
            if self._format_catalog is None:
                self._format_catalog = format_catalog_new
            else:
                self._format_catalog = self._format_catalog.merge(format_catalog_new)

    def _build_product_catalog(self) -> None:
        """Build the :class:`ProductCatalog` and classification match table."""
        assert self._format_catalog is not None, (
            "Format catalog must be built before building product catalog"
        )
        assert self._product_spec_catalog is not None, (
            "Product spec catalog must be built before building product catalog"
        )
        assert self._parameter_catalog is not None, (
            "Parameter catalog must be built before building product catalog"
        )
        for id, spec in self._product_specs.items():
            product_catalog_new = ProductCatalog.build(
                product_spec_catalog=spec.built, format_catalog=self._format_catalog
            )
            if self._product_catalog is None:
                self._product_catalog = product_catalog_new
            else:
                self._product_catalog = self._product_catalog.merge(product_catalog_new)
        assert self._product_catalog is not None, "Product catalog failed to build"
        self._match_table = _build_match_table(
            product_spec_catalog=self._product_spec_catalog,
            product_catalog=self._product_catalog,
            parameter_catalog=self._parameter_catalog,
        )

    def _build_remote_resource_factory(self) -> None:
        """Build the :class:`RemoteSearchPlanner` from loaded resource specs."""
        assert self._product_catalog is not None, (
            "Product catalog must be built before building remote search planner"
        )
        assert self._parameter_catalog is not None, (
            "Parameter catalog must be built before building remote search planner"
        )
        factory = RemoteSearchPlanner(
            product_catalog=self._product_catalog,
            parameter_catalog=self._parameter_catalog,
        )
        for id, spec in self._resource_specs.items():
            factory.register(spec.built)
        self._remote_resource_factory = factory

    def build(self) -> None:
        """Build the full catalog chain from loaded specs.

        Must be called after all ``add_*()`` methods.  Builds:
        ``ParameterCatalog`` → ``FormatCatalog`` → ``ProductCatalog`` →
        ``RemoteSearchPlanner``.
        """
        self._build_parameter_catalog()
        self._build_format_catalog()
        self._build_product_catalog()
        self._build_remote_resource_factory()

    def classify(
        self,
        filename: str,
        parameters: Optional[List[Parameter]] = None,
    ) -> Optional[Dict[str, str]]:
        """Parse a product filename and return its metadata.

        Args:
            filename: A product filename, optionally including a directory
                path and/or compression extension.
            parameters: Optional hard constraints.  Products whose fixed
                parameters conflict with a supplied value are skipped.

        Returns:
            A dict with keys ``product``, ``format``, ``version``,
            ``variant``, and ``parameters`` on match, or ``None`` if
            no product template matches.
        """
        name = Path(filename).name
        constraints = {
            p.name: p.value for p in (parameters or []) if p.value is not None
        }

        for entry in self._match_table:
            if any(
                k in entry.fixed_params and entry.fixed_params[k] != v
                for k, v in constraints.items()
            ):
                continue

            m = entry.compiled_regex.fullmatch(name)
            if m is None:
                continue

            extracted = {k: v for k, v in m.groupdict().items() if v is not None}

            if any(
                k in extracted and extracted[k] != v for k, v in constraints.items()
            ):
                continue

            return {
                "product": entry.product_name,
                "format": entry.format_name,
                "version": entry.version,
                "variant": entry.variant,
                "parameters": {**entry.fixed_params, **extracted},
            }

        return None
