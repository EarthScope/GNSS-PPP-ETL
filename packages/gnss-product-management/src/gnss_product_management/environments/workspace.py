"""Author: Franklyn Dunbar

Workspace management for local GNSS product storage.

Maps :class:`LocalResourceSpec` definitions (loaded from YAML) to concrete
base directories on disk so that local resources can be queried through the
same :class:`ResourceQuery` interface used for remote servers.

Base directories may be local filesystem paths (``/data/gnss``) or cloud
URIs (``s3://bucket/prefix``).  Path operations are dispatched through
:func:`~gnss_product_management.utilities.paths.as_path` so that all
filesystem interactions work uniformly regardless of backend.
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from gnss_product_management.specifications.local.local import LocalResourceSpec
from gnss_product_management.specifications.parameters.parameter import ParameterCatalog
from gnss_product_management.specifications.products.catalog import ProductCatalog
from gnss_product_management.specifications.products.product import (
    PathTemplate,
    Product,
)
from gnss_product_management.specifications.remote.resource import SearchTarget, Server
from gnss_product_management.utilities.helpers import _ensure_datetime
from gnss_product_management.utilities.paths import AnyPath, as_path

if TYPE_CHECKING:
    from gnss_product_management.environments.environment import ProductRegistry

logger = logging.getLogger(__name__)


def paths_overlap(p1: AnyPath | str, p2: AnyPath | str) -> bool:
    """Check whether two paths share a common ancestor-descendant relationship.

    For local paths, checks the resolved filesystem hierarchy.  For cloud
    URIs, falls back to string prefix comparison (cloud paths have no
    symlinks to resolve).

    Args:
        p1: First path or URI.
        p2: Second path or URI.

    Returns:
        ``True`` if either path is a parent of (or equal to) the other.
    """
    s1 = str(p1).rstrip("/")
    s2 = str(p2).rstrip("/")

    # Cloud paths — use string prefix comparison
    if "://" in s1 or "://" in s2:
        return s1.startswith(s2) or s2.startswith(s1)

    # Local paths — resolve symlinks before comparing
    r1 = Path(s1).resolve()
    r2 = Path(s2).resolve()
    return r1.is_relative_to(r2) or r2.is_relative_to(r1)


class RegisteredLocalResource(BaseModel):
    """A local resource spec that has been bound to a base directory.

    ``base_dir`` is stored as a URI string so that it can represent both
    local paths (``/data/gnss``) and cloud locations
    (``s3://bucket/prefix``).  Use the :attr:`base_path` property to
    obtain the appropriate :class:`~pathlib.Path` or
    :class:`~cloudpathlib.CloudPath` object for filesystem operations.

    Attributes:
        name: Human-readable identifier for this resource.
        base_dir: Base directory URI (local path or cloud URI).
        spec: The underlying local resource specification.
        item_to_dir: Mapping of item names to their subdirectory.
        server: A ``file``-protocol :class:`Server` wrapping *base_dir*.
    """

    name: str
    base_dir: str
    spec: LocalResourceSpec
    item_to_dir: dict[str, str]
    server: Server

    @property
    def base_path(self) -> AnyPath:
        """The base directory as a :class:`~pathlib.Path` or cloud path."""
        return as_path(self.base_dir)


class WorkSpace:
    """Registry of local storage directories and their layout specifications.

    Manages the mapping between ``LocalResourceSpec`` definitions (loaded from
    YAML) and concrete base directories on disk or in cloud storage.  Each
    registered spec gets a ``Server(protocol='file')`` so that local resources
    can be queried with the same ``ResourceQuery`` interface used for remote
    servers.

    Also provides product-resolution methods (``source_product``,
    ``sink_product``, ``lockfile_dir``, ``find_local_files``) once bound to a
    :class:`ProductRegistry` via :meth:`bind`.

    Attributes:
        _registered_specs: Mapping of spec names to registered resources.
        _alias_map: Mapping of aliases to canonical spec names.
        _resource_specs: Loaded but not-yet-registered spec objects.
        _product_catalog: Product catalog (available after :meth:`bind`).
        _parameter_catalog: Parameter catalog (available after :meth:`bind`).

    Usage::

        ws = WorkSpace()
        ws.add_resource_spec('local_config.yaml')
        ws.register_spec(base_dir='/data/gnss', spec_ids=['local_config'], alias='local')
    """

    def __init__(self):
        """Initialise an empty workspace with no specs loaded."""

        self._registered_specs: dict[str, RegisteredLocalResource] = {}
        self._alias_map: dict[str, str] = {}  # alias → spec name
        self._resource_specs: dict[str, LocalResourceSpec] = {}
        self._product_catalog: ProductCatalog | None = None
        self._parameter_catalog: ParameterCatalog | None = None

    def bind(self, product_registry: ProductRegistry) -> None:
        """Inject catalog references from a built :class:`ProductRegistry`.

        Must be called before using :meth:`source_product`,
        :meth:`sink_product`, or :meth:`find_local_files`.

        Args:
            product_registry: A fully built registry with catalogs.
        """
        self._product_catalog = product_registry._product_catalog
        self._parameter_catalog = product_registry._parameter_catalog

    def add_resource_spec(self, path: Path | str, id: str | None = None) -> None:
        """Load a :class:`LocalResourceSpec` from a YAML file.

        Args:
            path: Path to the YAML specification file.
            id: Optional override for the spec name.  Defaults to the
                name declared inside the YAML file.

        Raises:
            AssertionError: If *path* does not exist or a spec with
                the same name is already registered.
        """
        path = Path(path)
        assert path.exists(), f"Resource spec file not found: {path}"
        assert path.is_file(), f"Resource spec path must be a file: {path}"
        spec = LocalResourceSpec.from_yaml(path)
        spec = spec.model_copy(update={"source_file": path})
        name = spec.name
        if id is not None:
            name = id
        assert name not in self._resource_specs, (
            f"Resource spec with name '{name}' already exists. Please choose a unique name."
        )
        self._resource_specs[name] = spec

    def register_spec(
        self, base_dir: AnyPath | str, spec_ids: list[str], alias: str | None = None
    ) -> None:
        """Bind loaded spec(s) to a base directory and register the result.

        *base_dir* may be a local filesystem path or a cloud URI such as
        ``s3://bucket/prefix``.  When multiple *spec_ids* are given they are
        merged into a single :class:`LocalResourceSpec`.

        Args:
            base_dir: Root directory for the resource (local path or cloud URI).
            spec_ids: One or more previously loaded spec identifiers.
            alias: Optional alias that also maps to this resource.

        Raises:
            AssertionError: If *base_dir* does not exist or any
                *spec_id* has not been loaded.
            ValueError: If *alias* is already in use or *base_dir* overlaps
                with an existing registration.
        """
        base_path = as_path(str(base_dir))
        assert base_path.exists(), f"Base directory not found: {base_dir}"
        assert base_path.is_dir(), f"Base directory must be a directory: {base_dir}"

        specs_to_register: list[LocalResourceSpec] = []
        for spec_id in spec_ids:
            assert spec_id in self._resource_specs, (
                f"Spec id '{spec_id}' not found. Available specs: {list(self._resource_specs.keys())}"
            )
            built_spec = self._resource_specs[spec_id]
            specs_to_register.append(built_spec)

        spec_to_register = LocalResourceSpec.merge(specs_to_register)
        server = Server(
            id=spec_to_register.name,
            hostname=str(base_path),
            protocol="file",
            auth_required=False,
            description=specs_to_register[-1].description,
        )
        if alias:
            if alias in self._alias_map:
                alias_mapped_spec = self._alias_map[alias]
                if alias_mapped_spec != spec_to_register.name:
                    raise ValueError(
                        f"Alias {alias!r} is already in use for spec {self._alias_map[alias]!r}."
                    )
            self._alias_map[alias] = spec_to_register.name

        item_to_dir: dict[str, str] = {}
        for coll_name, coll in spec_to_register.collections.items():
            for item in coll.items:
                if item in item_to_dir:
                    raise ValueError(
                        f"Spec {item!r} is in multiple collections: "
                        f"{item_to_dir[item]!r} and {coll_name!r}"
                    )
                item_to_dir[item] = coll.directory

        local_resource = RegisteredLocalResource(
            name=spec_to_register.name,
            base_dir=str(base_path),
            spec=spec_to_register,
            item_to_dir=item_to_dir,
            server=server,
        )

        # Check for overlapping base directories with existing registered resources
        for registered_spec in self._registered_specs.values():
            if paths_overlap(registered_spec.base_dir, str(base_path)):
                raise ValueError(
                    f"Base directory {base_dir!r} overlaps with existing base directory "
                    f"{registered_spec.base_dir!r} for spec {registered_spec.name!r}. "
                    f"Please choose non-overlapping base directories for local resources."
                )
        self._registered_specs[spec_to_register.name] = local_resource

    def register(
        self,
        spec: LocalResourceSpec | Path | str,
        base_dir: Path | str,
        alias: str | None = None,
    ) -> None:
        """Register a local resource specification in one step.

        Convenience alternative to :meth:`add_resource_spec` +
        :meth:`register_spec`.  Accepts a :class:`LocalResourceSpec`
        object or a path to a YAML file.

        Args:
            spec: A :class:`LocalResourceSpec`, or a path to a YAML file.
            base_dir: Root directory on disk for the resource.
            alias: Optional alias that also maps to this resource.

        Raises:
            ValueError: If *base_dir* overlaps with an existing
                registration or *alias* is already taken.
        """
        if isinstance(base_dir, str):
            base_dir = Path(base_dir)

        if isinstance(spec, (Path, str)):
            spec = LocalResourceSpec.from_yaml(str(spec))

        base_path = as_path(str(base_dir)) if base_dir else None
        server = Server(
            id=spec.name,
            hostname=str(base_path) if base_path else spec.name,
            protocol="file",
            auth_required=False,
            description=spec.description,
        )

        name = spec.name
        if name in self._registered_specs:
            raise ValueError(f"Local resource {name!r} is already registered.")
        for registered_spec in self._registered_specs.values():
            if paths_overlap(registered_spec.base_dir, base_dir):
                raise ValueError(
                    f"Base directory {base_dir!r} for spec {name!r} overlaps with "
                    f"existing base directory {registered_spec.base_dir!r} for spec "
                    f"{registered_spec.name!r}. Please choose non-overlapping base "
                    f"directories for local resources."
                )
        if alias:
            if alias in self._alias_map:
                raise ValueError(
                    f"Alias {alias!r} is already in use for spec {self._alias_map[alias]!r}."
                )
            self._alias_map[alias] = name

        item_to_dir: dict[str, str] = {}
        for coll_name, coll in spec.collections.items():
            for item in coll.items:
                if item in item_to_dir:
                    raise ValueError(
                        f"Spec {item!r} is in multiple collections: "
                        f"{item_to_dir[item]!r} and {coll_name!r}"
                    )
                item_to_dir[item] = coll.directory

        self._registered_specs[name] = RegisteredLocalResource(
            name=name,
            base_dir=str(as_path(str(base_dir))),
            spec=spec,
            item_to_dir=item_to_dir,
            server=server,
        )

    @property
    def resource_ids(self) -> list[str]:
        """Identifiers for all registered local resources."""
        return list(self._registered_specs.keys())

    def _get_registered_spec(self, name_or_alias: str) -> RegisteredLocalResource:
        """Look up a registered local resource by name or alias.

        Args:
            name_or_alias: Resource name or alias.

        Returns:
            The registered local resource.

        Raises:
            KeyError: If *name_or_alias* is not found.
        """
        if name_or_alias in self._alias_map:
            name_or_alias = self._alias_map[name_or_alias]
        registered_spec = self._registered_specs.get(name_or_alias)
        if registered_spec is None:
            raise KeyError(
                f"Local resource {name_or_alias!r} not found. "
                f"Known resources: {list(self._registered_specs.keys())}"
            )
        return registered_spec

    def source_product(self, product: Product, resource_id: str) -> list[SearchTarget]:
        """Resolve a product into SearchTarget objects for a local resource.

        Args:
            product: Product to resolve.
            resource_id: Local resource identifier.

        Returns:
            A list of :class:`SearchTarget` objects.

        Raises:
            KeyError: If *resource_id* or *product.name* is not found.
        """
        registered_spec = self._get_registered_spec(resource_id)
        directory_template = registered_spec.item_to_dir.get(product.name)
        if directory_template is None:
            raise KeyError(
                f"Product {product.name!r} not found in resource {resource_id!r}. "
                f"Known products: {sorted(registered_spec.item_to_dir.keys())}"
            )
        directory = PathTemplate(pattern=directory_template)
        directory.derive(product.parameters)
        return [
            SearchTarget(
                product=product,
                server=registered_spec.server,
                directory=directory,
            )
        ]

    def sink_product(
        self,
        product: Product,
        resource_id: str,
        date: datetime.date,
    ) -> SearchTarget:
        """Resolve the local directory for a product on a given date.

        Args:
            product: Product to locate.
            resource_id: Local resource identifier.
            date: Target date for computed template fields.

        Returns:
            A :class:`SearchTarget` with resolved directory path.

        Raises:
            KeyError: If *resource_id* or *product.name* is not found.
        """
        assert self._parameter_catalog is not None, "Call bind() before sink_product()"
        dt = _ensure_datetime(date)
        registered_spec = self._get_registered_spec(resource_id)

        directory_template = registered_spec.item_to_dir.get(product.name)
        if directory_template is None:
            raise KeyError(
                f"Spec {product.name!r} not found in any local collection. "
                f"Known specs: {list(registered_spec.item_to_dir.keys())}"
            )
        resolved = self._parameter_catalog.interpolate(directory_template, dt, computed_only=True)

        out_query = SearchTarget(
            product=product,
            server=registered_spec.server,
            directory=PathTemplate(pattern=directory_template, value=resolved),
        )
        return out_query

    def lockfile_dir(
        self,
        resource_id: str,
    ) -> AnyPath:
        """Return the dependency lockfile directory for a resource.

        For local resources this is a subdirectory of the base directory.
        For cloud resources (e.g. ``s3://bucket/prefix``) it is an
        equivalent cloud path, enabling distributed workers to share
        lockfile state via cloud storage.

        Args:
            resource_id: Local resource identifier.

        Returns:
            Path to the lockfile directory (created if needed).
        """
        registered_spec = self._get_registered_spec(resource_id)
        dep_lockfile_dir = registered_spec.base_path / "dependency_lockfiles"
        dep_lockfile_dir.mkdir(parents=True, exist_ok=True)
        return dep_lockfile_dir

    def find_local_files(
        self,
        query: SearchTarget,
        date: datetime.date | None = None,
    ) -> list[AnyPath]:
        """Search local or cloud storage for files matching a query.

        Works identically for local :class:`~pathlib.Path` and cloud
        :class:`~cloudpathlib.CloudPath` base directories.

        Args:
            query: SearchTarget with directory and filename patterns.
            date: Optional date for interpolating computed fields.

        Returns:
            Sorted list of matching paths (local or cloud).

        Raises:
            KeyError: If the query's server is not registered.
        """
        assert self._parameter_catalog is not None, "Call bind() before find_local_files()"
        dir_pattern = query.directory.pattern
        if date:
            date = _ensure_datetime(date)
            dir_pattern = self._parameter_catalog.interpolate(dir_pattern, date, computed_only=True)

        # Find the registered spec that owns this query's server.
        registered_spec = None
        for candidate in self._registered_specs.values():
            if candidate.server.id == query.server.id:
                registered_spec = candidate
                break

        if registered_spec is None:
            raise KeyError(
                f"Server {query.server.id!r} not found in any registered local resource. "
                f"Known servers: {[s.server.id for s in self._registered_specs.values()]}"
            )

        file_pattern = query.product.filename.pattern if query.product.filename else None
        if date and file_pattern:
            date = _ensure_datetime(date)
            file_pattern = self._parameter_catalog.interpolate(
                file_pattern, date, computed_only=True
            )

        search_dir = registered_spec.base_path / dir_pattern

        if file_pattern:
            return sorted(
                p
                for p in search_dir.iterdir()
                if p.is_file() and re.search(file_pattern, p.name, re.IGNORECASE)
            )
        return sorted(p for p in search_dir.iterdir() if p.is_file())

    # ---- Rich display -------------------------------------------------------

    def display(self) -> None:
        """Print a rich summary of loaded specs and registered local resources.

        Prints two tables:

        - **Loaded Specs** — every spec loaded via :meth:`add_resource_spec`,
          with its name and product list.
        - **Registered Resources** — every resource bound to a base directory
          via :meth:`register_spec`, with its alias(es), base directory, and
          the products it covers.

        Requires the ``rich`` package (bundled as a project dependency).
        """
        from rich import box
        from rich.console import Console
        from rich.table import Table

        console = Console()

        # Reverse the alias map: spec_name → [alias, ...]
        spec_aliases: dict[str, list[str]] = {}
        for alias, spec_name in self._alias_map.items():
            spec_aliases.setdefault(spec_name, []).append(alias)

        if self._resource_specs:
            st = Table(
                title="[bold]Loaded Local Specs[/bold]",
                box=box.ROUNDED,
                show_lines=False,
                header_style="bold white",
            )
            st.add_column("Spec Name", style="bold cyan", no_wrap=True)
            st.add_column("Collections", style="dim")

            for spec_name, spec in sorted(self._resource_specs.items()):
                collections = sorted(spec.collections.keys())
                st.add_row(spec_name, ", ".join(collections))
            console.print(st)

        if self._registered_specs:
            rt = Table(
                title="[bold]Registered Local Resources[/bold]",
                box=box.ROUNDED,
                show_lines=True,
                header_style="bold white",
            )
            rt.add_column("Name", style="bold green", no_wrap=True)
            rt.add_column("Alias(es)", style="dim", no_wrap=True)
            rt.add_column("Spec", style="dim", no_wrap=True)
            rt.add_column("Spec File", style="dim")
            rt.add_column("Base Directory", style="dim")
            rt.add_column("Products", style="dim")

            for name, resource in sorted(self._registered_specs.items()):
                aliases = ", ".join(sorted(spec_aliases.get(name, [])))
                products = sorted(resource.item_to_dir.keys())
                spec = self._resource_specs.get(name) or resource.spec
                spec_file = str(spec.source_file) if spec.source_file else ""
                rt.add_row(
                    name,
                    aliases,
                    spec.name,
                    spec_file,
                    resource.base_dir,
                    "\n".join(products),
                )
            console.print(rt)
