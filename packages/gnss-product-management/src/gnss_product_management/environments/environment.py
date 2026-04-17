"""ProductRegistry — builds the full catalog chain and manages remote resources.

Loads parameter, format, product, and resource specification YAMLs, then
builds derived catalogs (``ParameterCatalog`` → ``FormatCatalog`` →
``ProductCatalog``).  Also registers remote :class:`ResourceCatalog` objects
and provides :meth:`~ProductRegistry.classify` for parsing product filenames
back into structured metadata.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

from pydantic import BaseModel
from rich import box
from rich.console import Console
from rich.table import Table

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
from gnss_product_management.specifications.products.product import Product
from gnss_product_management.specifications.remote.resource import (
    ResourceSpec,
    SearchTarget,
)
from gnss_product_management.specifications.remote.resource_catalog import (
    ResourceCatalog,
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
    product_params: list[Parameter],
) -> ParameterCatalog:
    """Merge product-specific parameter patterns into the global catalog.

    Args:
        base: The global :class:`ParameterCatalog`.
        product_params: Product-level parameter overrides.

    Returns:
        A new :class:`ParameterCatalog` with overrides applied.
    """
    merged = {name: param.model_copy(deep=True) for name, param in base.parameters.items()}
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
                    product_spec_catalog.products[prod_name].versions[ver_name].variants[var_name]
                )
                merged = _merged_parameter_catalog(parameter_catalog, product.parameters)
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
                            p.name: p.value for p in product.parameters if p.value is not None
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

        ParameterCatalog → FormatCatalog → ProductCatalog

    Remote resource specs loaded via :meth:`add_resource_spec` are built
    into :class:`ResourceCatalog` objects that support :meth:`source_product`
    and :meth:`sink_product` for remote query resolution.

    After building, :meth:`classify` parses a product filename into
    structured metadata (product name, format, version, variant, parameters).

    Attributes:
        _parameter_catalog: Built parameter catalog (available after :meth:`build`).
        _format_catalog: Built format catalog (available after :meth:`build`).
        _product_catalog: Built product catalog (available after :meth:`build`).
        _catalogs: Built remote resource catalogs (available after :meth:`build`).
    """

    def __init__(self) -> None:
        """Initialise an empty registry with no specs loaded."""

        self._parameter_specs: dict[str, LoadedSpecs] = {}
        self._format_specs: dict[str, LoadedSpecs] = {}
        self._product_specs: dict[str, LoadedSpecs] = {}
        self._resource_specs: dict[str, LoadedSpecs] = {}

        self._parameter_catalog: ParameterCatalog | None = None
        self._format_catalog: FormatCatalog | None = None
        self._product_spec_catalog: ProductSpecCatalog | None = None
        self._product_catalog: ProductCatalog | None = None
        self._catalogs: dict[str, ResourceCatalog] = {}

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
        self._parameter_specs[id] = LoadedSpecs(filename=path, built=parameter_spec_catalog)

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

    def _build_remote_catalogs(self) -> None:
        """Build :class:`ResourceCatalog` objects from loaded resource specs."""
        assert self._product_catalog is not None, (
            "Product catalog must be built before building remote catalogs"
        )
        for id, spec in self._resource_specs.items():
            cat = ResourceCatalog.build(
                resource_spec=spec.built, product_catalog=self._product_catalog
            )
            self._catalogs[cat.id] = cat

    def build(self) -> None:
        """Build the full catalog chain from loaded specs.

        Must be called after all ``add_*()`` methods.  Builds:
        ``ParameterCatalog`` → ``FormatCatalog`` → ``ProductCatalog`` →
        remote :class:`ResourceCatalog` objects.
        """
        self._build_parameter_catalog()
        self._build_format_catalog()
        self._build_product_catalog()
        self._build_remote_catalogs()

    # ---- Remote resource query interface -----------------------------------

    @property
    def resource_ids(self) -> list[str]:
        """Identifiers for all registered remote resource centers."""
        return list(self._catalogs.keys())

    @property
    def centers(self) -> list[str]:
        """Alias for :attr:`resource_ids`."""
        return self.resource_ids

    @property
    def catalogs(self) -> list[ResourceCatalog]:
        """All registered remote resource catalogs."""
        return list(self._catalogs.values())

    @property
    def all_queries(self) -> list[SearchTarget]:
        """Flattened list of every search target across all remote centers."""
        return [q for cat in self._catalogs.values() for q in cat.queries]

    def get(self, center_id: str) -> ResourceCatalog:
        """Retrieve a remote resource catalog by center identifier.

        Args:
            center_id: Data center identifier.

        Returns:
            The matching :class:`ResourceCatalog`.
        """
        return self._catalogs[center_id]

    @staticmethod
    def match_pinned_query(found: Product, incoming: Product) -> Product | None:
        """Check if a found query matches an incoming product based on pinned parameters.

        Args:
            found: Product from the resource catalog.
            incoming: Product being searched for.

        Returns:
            The *incoming* product with matched values filled in,
            or ``None`` if pinned parameters conflict.
        """
        found_params = {p.name: p.value for p in found.parameters if p.value is not None}
        incoming_params = {p.name: p.value for p in incoming.parameters if p.value is not None}
        matching_keys = set(found_params.keys()) & set(incoming_params.keys())
        for key in matching_keys:
            found_val = found_params[key]
            incoming_val = incoming_params[key]
            if found_val != incoming_val:
                return None

        for p in incoming.parameters:
            if p.value is None and p.name in found_params:
                p.value = found_params.get(p.name)
        return incoming

    def source_product(self, product: Product, resource_id: str) -> list[SearchTarget]:
        """Resolve a product into all matching SearchTargets for a remote resource.

        Args:
            product: Product to resolve.
            resource_id: Remote resource identifier.

        Returns:
            A list of :class:`SearchTarget` objects.

        Raises:
            KeyError: If *resource_id* or *product.name* is not found.
        """
        cat = self._catalogs.get(resource_id)
        if cat is None:
            raise KeyError(
                f"Resource {resource_id!r} not found in remote catalogs. "
                f"Known resources: {list(self._catalogs.keys())}"
            )
        candidates = [q for q in cat.queries if q.product.name == product.name]
        if not candidates:
            raise KeyError(
                f"Product {product.name!r} not found in resource {resource_id!r}. "
                f"Known products: {set(q.product.name for q in cat.queries)}"
            )

        results: list[SearchTarget] = []
        for query in candidates:
            # Deep copy so we never mutate the catalog's original query
            query = query.model_copy(deep=True)
            incoming = product.model_copy(deep=True)

            matched_product: Product | None = self.match_pinned_query(query.product, incoming)
            if matched_product is None:
                continue

            if query.product.filename:
                query.product.filename.derive(incoming.parameters)
            query.directory.derive(incoming.parameters)
            results.append(query)

        return results

    def sink_product(self, product: Product, resource_id: str, date: datetime) -> SearchTarget:
        """Resolve the remote directory/filename for uploading *product*.

        Args:
            product: Product to upload.
            resource_id: Remote resource identifier.
            date: Target date for computed fields.

        Returns:
            A :class:`SearchTarget` with resolved paths.

        Raises:
            KeyError: If no matching entry exists.
        """
        assert self._parameter_catalog is not None, "Call build() before sink_product()"
        queries = self.source_product(product, resource_id)
        if not queries:
            raise KeyError(
                f"Product {product.name!r} has no matching entry in resource {resource_id!r}."
            )
        query = queries[0]
        query.product = product

        resolved_dir = self._parameter_catalog.interpolate(
            query.directory.pattern, date, computed_only=True
        )
        query.directory.value = resolved_dir
        query.product = product
        return query

    # ---- Filename classification --------------------------------------------

    def classify(
        self,
        filename: str,
        parameters: list[Parameter] | None = None,
    ) -> dict[str, str] | None:
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
        constraints = {p.name: p.value for p in (parameters or []) if p.value is not None}

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

            if any(k in extracted and extracted[k] != v for k, v in constraints.items()):
                continue

            return {
                "product": entry.product_name,
                "format": entry.format_name,
                "version": entry.version,
                "variant": entry.variant,
                "parameters": {**entry.fixed_params, **extracted},
            }

        return None

    # ---- Rich display -------------------------------------------------------

    def display(self) -> None:
        """Print a rich summary of loaded products and registered remote centers.

        Prints two tables to the terminal:

        - **Products** — every product name with its versions and variants.
        - **Remote Centers** — every registered data center with its
          available products, protocols, and hostnames.

        Requires the ``rich`` package (bundled as a project dependency).
        """
        console = Console()

        if self._product_catalog is not None:
            pt = Table(
                title="[bold]Registered Products[/bold]",
                box=box.ROUNDED,
                show_lines=False,
                header_style="bold white",
            )
            pt.add_column("Product", style="bold cyan", no_wrap=True)
            pt.add_column("Versions", style="dim")
            pt.add_column("Variants", style="dim")

            for prod_name, ver_cat in sorted(self._product_catalog.products.items()):
                versions = sorted(ver_cat.versions.keys())
                variants: set = set()
                for var_cat in ver_cat.versions.values():
                    variants.update(var_cat.variants.keys())
                pt.add_row(
                    prod_name,
                    ", ".join(versions),
                    ", ".join(sorted(variants)),
                )
            console.print(pt)

        if self._catalogs:
            ct = Table(
                title="[bold]Remote Centers[/bold]",
                box=box.ROUNDED,
                show_lines=True,
                header_style="bold white",
            )
            ct.add_column("ID", style="bold green", no_wrap=True)
            ct.add_column("Name")
            ct.add_column("Products", style="dim")
            ct.add_column("Protocols", style="dim", no_wrap=True)
            ct.add_column("Hostname(s)", style="dim")

            for center_id, cat in sorted(self._catalogs.items()):
                product_names = sorted({q.product.name for q in cat.queries})
                protocols = sorted({s.protocol for s in cat.servers if s.protocol})
                hostnames = sorted({s.hostname for s in cat.servers})
                ct.add_row(
                    center_id,
                    cat.name,
                    "\n".join(product_names),
                    "\n".join(protocols),
                    "\n".join(hostnames),
                )
            console.print(ct)
