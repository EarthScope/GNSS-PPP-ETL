"""
Environment — unified container for GNSS product spec registries.

Holds non-singleton instances of every registry, validates cross-
references at construction time, and provides convenience methods
for querying and resolving dependencies.

The environment can be built from a YAML manifest file or constructed
programmatically.  All existing code continues to work via the global
singletons; the Environment is an opt-in upgrade path.

Manifest YAML schema::

    name: pride_ppp_kinematic
    base_dir: ~/gnss_products        # expanded at load time

    specs:
      meta: meta_spec.yaml           # relative to assets/<subpackage>/
      products: product_spec.yaml
      query: query_v2.yaml
      local: local_v2.yml
      centers:                        # list of center YAML files
        - igs_v2.yml
        - wuhan_v2.yml
        - code_v2.yml
      dependencies: pride_ppp_kin.yml # optional

    defaults:                         # optional axis defaults
      solution: FIN
      campaign: MGX
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from gnss_ppp_products.assets.meta_spec.registry import _MetadataRegistry
from gnss_ppp_products.assets.product_spec.registry import _ProductSpecRegistry
from gnss_ppp_products.assets.remote_resource_spec.registry import (
    _RemoteResourceRegistry,
)
from gnss_ppp_products.assets.local_resource_spec.registry import (
    _LocalResourceRegistry,
)
from gnss_ppp_products.assets.query_spec.query import QuerySpec
from gnss_ppp_products.assets.dependency_spec.models import DependencySpec

logger = logging.getLogger(__name__)


# ===================================================================
# Well-known asset directories (default YAML locations)
# ===================================================================

_ASSETS = Path(__file__).resolve().parent.parent  # .../assets/
_META_DIR = _ASSETS / "meta_spec"
_PRODUCT_DIR = _ASSETS / "product_spec"
_REMOTE_DIR = _ASSETS / "remote_resource_spec"
_LOCAL_DIR = _ASSETS / "local_resource_spec"
_QUERY_DIR = _ASSETS / "query_spec"
_DEP_DIR = _ASSETS / "dependency_spec"


# ===================================================================
# Validation
# ===================================================================


class EnvironmentValidationError(Exception):
    """Raised when cross-validation of an Environment fails."""

    def __init__(self, errors: List[str]) -> None:
        self.errors = errors
        msg = f"{len(errors)} validation error(s):\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        super().__init__(msg)


# ===================================================================
# Environment
# ===================================================================


class Environment:
    """Unified container holding all GNSS product spec registries.

    Parameters
    ----------
    name : str
        Human-readable environment name.
    base_dir : Path or str
        Root of local product storage.
    meta : _MetadataRegistry
        Metadata field definitions.
    products : _ProductSpecRegistry
        Product specifications (filename templates, constraints).
    remote : _RemoteResourceRegistry
        Remote data center definitions.
    local : _LocalResourceRegistry
        Local storage layout.
    query : QuerySpec
        Query axis definitions and product profiles.
    dependencies : DependencySpec or None
        Optional task dependency declaration.
    defaults : dict
        Optional default axis values (e.g. ``{"solution": "FIN"}``).
    """

    def __init__(
        self,
        *,
        name: str,
        base_dir: Union[str, Path],
        meta: _MetadataRegistry,
        products: _ProductSpecRegistry,
        remote: _RemoteResourceRegistry,
        local: _LocalResourceRegistry,
        query: QuerySpec,
        dependencies: Optional[DependencySpec] = None,
        defaults: Optional[Dict[str, str]] = None,
    ) -> None:
        self.name = name
        self.base_dir = Path(base_dir).expanduser()
        self.meta = meta
        self.products = products
        self.remote = remote
        self.local = local
        self.query_spec = query
        self.dependencies = dependencies
        self.defaults = dict(defaults) if defaults else {}

        # Wire base_dir into local registry
        self.local.base_dir = self.base_dir

    # ------------------------------------------------------------------
    # Manifest loader
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "Environment":
        """Load an Environment from a manifest YAML file.

        Relative paths in the ``specs`` section are resolved against
        the default asset directories.
        """
        path = Path(path)
        with open(path) as fh:
            raw = yaml.safe_load(fh)

        specs = raw.get("specs", {})

        # ---- meta ----
        meta_path = _resolve_spec_path(
            specs.get("meta", "meta_spec.yaml"), _META_DIR
        )
        meta = _MetadataRegistry.load_from_yaml(meta_path)
        # Re-register computed fields (they are tied to the module-level
        # singleton by the @computed decorator in funcs.py — we need to
        # replay them on this new instance).
        _replay_computed_fields(meta)

        # ---- products ----
        prod_path = _resolve_spec_path(
            specs.get("products", "product_spec.yaml"), _PRODUCT_DIR
        )
        products = _ProductSpecRegistry.load_from_yaml(prod_path)

        # ---- remote centers ----
        center_files = specs.get("centers", [])
        remote = _RemoteResourceRegistry()
        if center_files:
            for cf in center_files:
                p = _resolve_spec_path(cf, _REMOTE_DIR)
                from gnss_ppp_products.assets.remote_resource_spec.remote_resource import (
                    RemoteResourceSpec,
                )
                center = RemoteResourceSpec.from_yaml(p)
                remote._register(center)
        else:
            # Default: load all *_v2.yml from the standard directory
            remote = _RemoteResourceRegistry.load_from_directory()

        # ---- local ----
        local_path = _resolve_spec_path(
            specs.get("local", "local_v2.yml"), _LOCAL_DIR
        )
        local = _LocalResourceRegistry.load_from_yaml(local_path)

        # ---- query ----
        query_path = _resolve_spec_path(
            specs.get("query", "query_v2.yaml"), _QUERY_DIR
        )
        query = QuerySpec.from_yaml(query_path)

        # ---- dependencies (optional) ----
        dep = None
        dep_file = specs.get("dependencies")
        if dep_file:
            dep_path = _resolve_spec_path(dep_file, _DEP_DIR)
            dep = DependencySpec.from_yaml(dep_path)

        # ---- base_dir ----
        base_dir = Path(raw.get("base_dir", "~/gnss_products")).expanduser()

        # ---- defaults ----
        defaults = raw.get("defaults", {})

        env = cls(
            name=raw.get("name", path.stem),
            base_dir=base_dir,
            meta=meta,
            products=products,
            remote=remote,
            local=local,
            query=query,
            dependencies=dep,
            defaults=defaults,
        )

        return env

    # ------------------------------------------------------------------
    # Programmatic builder (all defaults)
    # ------------------------------------------------------------------

    @classmethod
    def default(
        cls,
        *,
        name: str = "default",
        base_dir: Union[str, Path] = "~/gnss_products",
        center_files: Optional[List[str]] = None,
        dependency_file: Optional[str] = None,
        defaults: Optional[Dict[str, str]] = None,
    ) -> "Environment":
        """Build an Environment using the standard built-in spec files.

        This is the simplest constructor — it loads everything from the
        default asset directories, optionally restricting which centers
        are included.
        """
        meta = _MetadataRegistry.load_from_yaml(_META_DIR / "meta_spec.yaml")
        _replay_computed_fields(meta)

        products = _ProductSpecRegistry.load_from_yaml()
        local = _LocalResourceRegistry.load_from_yaml()
        query = QuerySpec.from_yaml()

        if center_files:
            remote = _RemoteResourceRegistry()
            from gnss_ppp_products.assets.remote_resource_spec.remote_resource import (
                RemoteResourceSpec,
            )
            for cf in center_files:
                p = _resolve_spec_path(cf, _REMOTE_DIR)
                center = RemoteResourceSpec.from_yaml(p)
                remote._register(center)
        else:
            remote = _RemoteResourceRegistry.load_from_directory()

        dep = None
        if dependency_file:
            dep_path = _resolve_spec_path(dependency_file, _DEP_DIR)
            dep = DependencySpec.from_yaml(dep_path)

        return cls(
            name=name,
            base_dir=base_dir,
            meta=meta,
            products=products,
            remote=remote,
            local=local,
            query=query,
            dependencies=dep,
            defaults=defaults,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> List[str]:
        """Cross-validate all spec references.

        Returns a list of error strings.  An empty list means the
        environment is consistent.

        Checks performed:

        1. Every product name in remote center specs exists in product_spec.
        2. Every product name in local specs exists in product_spec.
        3. Every product name in query profiles exists in product_spec.
        4. Every local_collection referenced in query profiles exists.
        5. Every center referenced in dependency preferences exists.
        6. Every dependency spec name exists in product_spec.
        7. Every dependency spec name has a query profile.
        """
        errors: List[str] = []
        product_names = set(self.products.products.keys())
        center_ids = set(self.remote.centers.keys())
        local_collections = set(self.local.collections.keys())
        query_specs = set(self.query_spec.products.keys())
        local_specs = set(self.local.all_specs)

        # 1. Remote product specs → product_spec
        for cid, center in self.remote.centers.items():
            for rp in center.products:
                if rp.spec_name not in product_names:
                    errors.append(
                        f"remote center '{cid}' product '{rp.id}' references "
                        f"unknown spec '{rp.spec_name}'"
                    )

        # 2. Local specs → product_spec
        for s in local_specs:
            if s not in product_names:
                errors.append(
                    f"local spec '{s}' not found in product_spec "
                    f"(known: {sorted(product_names)})"
                )

        # 3. Query profile names → product_spec
        for s in query_specs:
            if s not in product_names:
                errors.append(
                    f"query profile '{s}' not found in product_spec"
                )

        # 4. Query local_collection → local_resource_spec
        for s, profile in self.query_spec.products.items():
            coll = profile.local_collection
            if coll and coll not in local_collections:
                errors.append(
                    f"query profile '{s}' references local_collection "
                    f"'{coll}' not found in local spec "
                    f"(known: {sorted(local_collections)})"
                )

        # 5-7. Dependency spec validation
        if self.dependencies:
            for pref in self.dependencies.preferences:
                if pref.center not in center_ids:
                    errors.append(
                        f"dependency preference center '{pref.center}' "
                        f"not found in remote centers "
                        f"(known: {sorted(center_ids)})"
                    )
            for dep in self.dependencies.dependencies:
                if dep.spec not in product_names:
                    errors.append(
                        f"dependency spec '{dep.spec}' not found "
                        f"in product_spec"
                    )
                if dep.spec not in query_specs:
                    errors.append(
                        f"dependency spec '{dep.spec}' has no "
                        f"query profile"
                    )

        return errors

    def validate_or_raise(self) -> None:
        """Run :meth:`validate` and raise if any errors are found."""
        errors = self.validate()
        if errors:
            raise EnvironmentValidationError(errors)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def query(self, date: datetime.date) -> "ProductQuery":
        """Build a :class:`ProductQuery` scoped to this environment."""
        from gnss_ppp_products.assets.query_spec.engine import ProductQuery

        return ProductQuery(
            date,
            query_registry=self.query_spec,
            remote_registry=self.remote,
            local_registry=self.local,
            meta_registry=self.meta,
            product_registry=self.products,
        )

    # ------------------------------------------------------------------
    # Dependency resolution API
    # ------------------------------------------------------------------

    def resolve(
        self,
        date: datetime.date,
        *,
        download: bool = False,
    ) -> "DependencyResolution":
        """Resolve dependencies using this environment's registries.

        Requires :attr:`dependencies` to have been set (either via
        the manifest or programmatically).

        Returns a :class:`DependencyResolution` with the outcome for
        every declared dependency.
        """
        if self.dependencies is None:
            raise RuntimeError(
                "No dependency spec configured in this environment. "
                "Set env.dependencies or include 'dependencies' in the manifest."
            )
        from gnss_ppp_products.assets.dependency_spec.resolver import (
            DependencyResolver,
        )

        resolver = DependencyResolver(
            self.dependencies,
            base_dir=self.base_dir,
            environment=self,
        )
        return resolver.resolve(date, download=download)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        n_centers = len(self.remote.centers)
        n_products = len(self.products.products)
        n_remote = sum(
            len(c.products) for c in self.remote.centers.values()
        )
        dep_name = self.dependencies.name if self.dependencies else "(none)"
        return (
            f"Environment({self.name!r}, "
            f"centers={n_centers}, "
            f"product_specs={n_products}, "
            f"remote_products={n_remote}, "
            f"dep={dep_name})"
        )

    def summary(self) -> str:
        """Return a multi-line summary of the environment."""
        lines = [
            f"Environment: {self.name}",
            f"  base_dir: {self.base_dir}",
            f"  product specs: {sorted(self.products.products.keys())}",
            f"  centers: {sorted(self.remote.centers.keys())}",
            f"  local collections: {sorted(self.local.collections.keys())}",
            f"  query profiles: {sorted(self.query_spec.products.keys())}",
        ]
        if self.dependencies:
            lines.append(f"  dependencies: {self.dependencies.name}")
            lines.append(
                f"    {len(self.dependencies.dependencies)} deps, "
                f"{len(self.dependencies.preferences)} preferences"
            )
        if self.defaults:
            lines.append(f"  defaults: {self.defaults}")
        return "\n".join(lines)


# ===================================================================
# Helpers
# ===================================================================


def _resolve_spec_path(filename: str, default_dir: Path) -> Path:
    """Resolve a spec filename to an absolute path.

    If *filename* is already absolute, return it.  Otherwise, look
    in *default_dir*.
    """
    p = Path(filename).expanduser()
    if p.is_absolute():
        return p
    candidate = default_dir / p
    if candidate.exists():
        return candidate
    return p  # let the caller handle FileNotFoundError


def _replay_computed_fields(meta: _MetadataRegistry) -> None:
    """Re-register the @computed fields from funcs.py on a new instance.

    The ``funcs.py`` module registers computed fields on the global
    singleton at import time.  When we create a fresh registry we need
    to copy them over.
    """
    from gnss_ppp_products.assets.meta_spec import MetaDataRegistry as _global

    for name, field in _global.fields.items():
        if field.compute is not None and name not in meta:
            meta.register(
                name,
                field.pattern,
                compute=field.compute,
                description=field.description,
            )
