"""
Environment — unified container for GNSS product spec registries.

Holds non-singleton instances of every registry, validates cross-
references at construction time, and provides convenience methods
for querying and resolving dependencies.

The environment can be built from a YAML manifest file or constructed
programmatically.

Manifest YAML schema::

    name: pride_ppp_kinematic
    base_dir: ~/gnss_products

    specs:
      meta: meta_spec.yaml
      products: product_spec.yaml
      query: query_v2.yaml
      local: local_v2.yml
      centers:
        - igs_v2.yml
        - wuhan_v2.yml
        - code_v2.yml
      dependencies: pride_ppp_kin.yml

    defaults:
      solution: FIN
      campaign: MGX
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml

from gnss_ppp_products.catalogs import (
    MetadataCatalog,
    ProductCatalog,
    RemoteResourceFactory,
    LocalResourceFactory,
    QuerySpec,
    DependencyResolver,
    ProductQuery,
)
from gnss_ppp_products.specifications.dependencies.dependencies import DependencySpec
from gnss_ppp_products.utilities.metadata_funcs import register_computed_fields

import gnss_ppp_products.configs as _cfg

logger = logging.getLogger(__name__)


# ===================================================================
# Well-known directories (from configs)
# ===================================================================

_META_DIR = _cfg.META_SPEC_YAML.parent
_PRODUCT_DIR = _cfg.PRODUCT_SPEC_YAML.parent
_REMOTE_DIR = _cfg.REMOTE_SPEC_DIR
_LOCAL_DIR = _cfg.LOCAL_SPEC_YAML.parent
_QUERY_DIR = _cfg.QUERY_SPEC_YAML.parent
_DEP_DIR = _cfg.DEPENDENCY_SPEC_DIR


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
    """Unified container holding all GNSS product spec registries."""

    def __init__(
        self,
        *,
        name: str,
        base_dir: Union[str, Path],
        meta: MetadataCatalog,
        products: ProductCatalog,
        remote: RemoteResourceFactory,
        local: LocalResourceFactory,
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

        self.local._base_dir = self.base_dir

    # ------------------------------------------------------------------
    # Manifest loader
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "Environment":
        """Load an Environment from a manifest YAML file."""
        path = Path(path)
        with open(path) as fh:
            raw = yaml.safe_load(fh)

        specs = raw.get("specs", {})

        # ---- meta ----
        meta_path = _resolve_spec_path(
            specs.get("meta", "meta_spec.yaml"), _META_DIR
        )
        meta = MetadataCatalog.from_yaml(meta_path)
        register_computed_fields(meta)

        # ---- products ----
        prod_path = _resolve_spec_path(
            specs.get("products", "product_spec.yaml"), _PRODUCT_DIR
        )
        products = ProductCatalog.from_yaml(prod_path)

        # ---- remote centers ----
        center_files = specs.get("centers", [])
        remote = RemoteResourceFactory()
        if center_files:
            for cf in center_files:
                p = _resolve_spec_path(cf, _REMOTE_DIR)
                remote.load_from_yaml(p)
        else:
            remote = RemoteResourceFactory.load_from_directory(_REMOTE_DIR)

        # ---- local ----
        local_path = _resolve_spec_path(
            specs.get("local", "local_v2.yml"), _LOCAL_DIR
        )
        local = LocalResourceFactory()
        local.load_from_yaml(local_path)

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

        base_dir = Path(raw.get("base_dir", "~/gnss_products")).expanduser()
        defaults = raw.get("defaults", {})

        return cls(
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
        """Build an Environment using the standard built-in spec files."""
        meta = MetadataCatalog.from_yaml(_cfg.META_SPEC_YAML)
        register_computed_fields(meta)

        products = ProductCatalog.from_yaml(_cfg.PRODUCT_SPEC_YAML)

        local = LocalResourceFactory()
        local.load_from_yaml(_cfg.LOCAL_SPEC_YAML)

        query = QuerySpec.from_yaml(_cfg.QUERY_SPEC_YAML)

        if center_files:
            remote = RemoteResourceFactory()
            for cf in center_files:
                p = _resolve_spec_path(cf, _REMOTE_DIR)
                remote.load_from_yaml(p)
        else:
            remote = RemoteResourceFactory.load_from_directory(_REMOTE_DIR)

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

        Returns a list of error strings.  Empty = consistent.
        """
        errors: List[str] = []
        product_names = set(self.products.products.keys())
        center_ids = set(self.remote.centers.keys())
        local_collections = set(self.local.collections.keys())
        query_specs = set(self.query_spec.products.keys())
        local_specs = set(self.local.all_specs)

        for cid, center in self.remote.centers.items():
            for rp in center.products:
                if rp.spec_name not in product_names:
                    errors.append(
                        f"remote center '{cid}' product '{rp.id}' references "
                        f"unknown spec '{rp.spec_name}'"
                    )

        for s in local_specs:
            if s not in product_names:
                errors.append(
                    f"local spec '{s}' not found in product_spec "
                    f"(known: {sorted(product_names)})"
                )

        for s in query_specs:
            if s not in product_names:
                errors.append(
                    f"query profile '{s}' not found in product_spec"
                )

        for s, profile in self.query_spec.products.items():
            coll = profile.local_collection
            if coll and coll not in local_collections:
                errors.append(
                    f"query profile '{s}' references local_collection "
                    f"'{coll}' not found in local spec "
                    f"(known: {sorted(local_collections)})"
                )

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
        errors = self.validate()
        if errors:
            raise EnvironmentValidationError(errors)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def query(self, date) -> "ProductQuery":
        """Build a :class:`ProductQuery` scoped to this environment."""
        if isinstance(date, str):
            date = datetime.date.fromisoformat(date)
        return ProductQuery(
            date,
            query_spec=self.query_spec,
            remote_factory=self.remote,
            local_factory=self.local,
            meta_catalog=self.meta,
            product_catalog=self.products,
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
        """Resolve dependencies using this environment's registries."""
        if self.dependencies is None:
            raise RuntimeError(
                "No dependency spec configured in this environment."
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
    p = Path(filename).expanduser()
    if p.is_absolute():
        return p
    candidate = default_dir / p
    if candidate.exists():
        return candidate
    return p
