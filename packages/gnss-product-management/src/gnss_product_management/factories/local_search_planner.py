"""Author: Franklyn Dunbar

LocalSearchPlanner — collections-based local file-system product archives.
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from gnss_product_management.environments import ProductRegistry
from gnss_product_management.environments import (
    WorkSpace,
    RegisteredLocalResource,
    paths_overlap,
)

from gnss_product_management.specifications.local.local import LocalResourceSpec
from gnss_product_management.specifications.products.product import (
    Product,
    PathTemplate,
)
from gnss_product_management.specifications.remote.resource import SearchTarget, Server
from gnss_product_management.utilities.helpers import _ensure_datetime
from gnss_product_management.utilities.paths import AnyPath, as_path

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class LocalSearchPlanner:
    """Registry of local file-system product archives using collections-based layout.

    Loads a ``LocalResourceSpec`` (from ``local_config.yaml``) plus the
    ``ProductCatalog`` to produce one ``SearchTarget`` per locally-known
    product type, using the collection's directory template and the catalog's
    filename pattern.

    Attributes:
        _workspace: The workspace providing registered local specs.
        _product_registry: The product registry with built catalogs.

    Usage::

        spec = LocalResourceSpec.from_yaml("local_config.yaml")
        local = LocalSearchPlanner(spec, product_catalog, parameter_catalog, base_dir=Path("/data/gnss"))
    """

    def __init__(
        self,
        workspace: WorkSpace,
        product_registry: ProductRegistry,
    ) -> None:
        """Initialise from a workspace and product registry.

        Args:
            workspace: Workspace with registered local resource specs.
            product_registry: Built product registry with catalogs.
        """

        self._workspace = workspace
        self._product_registry = product_registry

        self._product_catalog = product_registry._product_catalog
        self._parameter_catalog = product_registry._parameter_catalog
        self._registered_specs: Dict[str, RegisteredLocalResource] = (
            workspace._registered_specs
        )
        self._alias_map: Dict[str, str] = workspace._alias_map

    def register(
        self,
        spec: LocalResourceSpec | Path | str,
        base_dir: Path | str,
        alias: Optional[str] = None,
    ) -> None:
        """Register a local resource specification.

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
            # Check if any existing base directories overlap with the new spec's base directory
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

        item_to_dir: Dict[str, str] = {}
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
        if alias:
            self._alias_map[alias] = name

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
        dt = _ensure_datetime(date)
        registered_spec = self._get_registered_spec(resource_id)

        directory_template = registered_spec.item_to_dir.get(product.name)
        if directory_template is None:
            raise KeyError(
                f"Spec {product.name!r} not found in any local collection. "
                f"Known specs: {list(registered_spec.item_to_dir.keys())}"
            )
        resolved = self._parameter_catalog.interpolate(
            directory_template, dt, computed_only=True
        )

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

    @property
    def resource_ids(self) -> List[str]:
        """Return identifiers for all registered local resources."""
        return list(self._registered_specs.keys())

    def source_product(self, product: Product, resource_id: str) -> List[SearchTarget]:
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

    def find_local_files(
        self,
        query: SearchTarget,
        date: Optional[datetime.date] = None,
    ) -> List[AnyPath]:
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
        dir_pattern = query.directory.pattern
        if date:
            date = _ensure_datetime(date)
            dir_pattern = self._parameter_catalog.interpolate(
                dir_pattern, date, computed_only=True
            )

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

        file_pattern = (
            query.product.filename.pattern if query.product.filename else None
        )
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
