"""
ProductEnvironment — unified container for the new specification/factory layer.

Builds the full catalog chain (ParameterCatalog → FormatCatalog → ProductCatalog)
and wires up remote/local resource factories from raw spec dicts or file paths.

The environment owns the built objects but does NOT perform queries or downloads
itself — callers pull out the pieces they need::

    env = ProductEnvironment.from_yaml(
        base_dir="~/gnss_products",
        meta_spec_yaml="configs/meta/meta_spec.yaml",
        product_spec_yaml="configs/products/product_spec.yaml",
        local_configs=["configs/local/local_config.yaml"],
        remote_specs=list(Path("configs/centers").glob("*.yaml")),
        dependency_specs=["configs/dependencies/pride_pppar.yaml"],
    )

    qf = QueryFactory(
        remote_factory=env.remote_factory,
        local_factory=env.local_factory,
        product_catalog=env.product_catalog,
        parameter_catalog=env.parameter_catalog,
    )
    results = qf.get(date=..., product={...}, parameters={...})
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from gnss_ppp_products.specifications.parameters.parameter import Parameter, ParameterCatalog
from gnss_ppp_products.specifications.format.format_spec import FormatCatalog, FormatSpecCatalog
from gnss_ppp_products.specifications.products.catalog import ProductCatalog, ProductSpecCatalog
from gnss_ppp_products.specifications.remote.remote import RemoteResourceSpec
from gnss_ppp_products.specifications.remote.resource import ResourceSpec
from gnss_ppp_products.specifications.local.local import LocalResourceSpec
from gnss_ppp_products.specifications.local.factory import LocalResourceFactory
from gnss_ppp_products.specifications.dependencies.dependencies import DependencySpec
from gnss_ppp_products.factories.remote_factory import RemoteResourceFactory
from gnss_ppp_products.utilities.metadata_funcs import register_computed_fields

# Type alias for a single path-like value
_PathLike = Union[str, Path]


def _coerce_path_list(
    value: Optional[Union[_PathLike, Sequence[_PathLike]]],
) -> List[Path]:
    """Normalise ``None``, a single path, or a list to ``List[Path]``."""
    if value is None:
        return []
    if isinstance(value, (str, Path)):
        return [Path(value)]
    return [Path(v) for v in value]


class ProductEnvironment:
    """Unified container holding all built catalogs and factories.

    Constructs every layer in dependency order from raw spec dicts,
    then exposes them as read-only properties.

    Parameters
    ----------
    base_dir : str | Path
        Root directory for local product storage.
    parameter_specs : list[dict]
        Raw parameter specification dicts (→ :class:`ParameterCatalog`).
    format_specs : list[dict]
        Raw format specification dicts (→ :class:`FormatCatalog`).
    product_specs : list[dict]
        Raw product specification dicts (→ :class:`ProductCatalog`).
    local_configs : str | Path | list | None
        One or more paths to ``LocalResourceSpec`` YAML files.  When
        multiple files are given their collections are merged (later
        files add to / override earlier ones).  A single path is also
        accepted for convenience.  ``None`` means no local factory.
    remote_specs : list[dict] | None
        Raw remote resource specification dicts.  Each is registered with
        the :class:`RemoteResourceFactory`.
    dependency_specs : str | Path | list | None
        One or more paths (or raw dicts) for :class:`DependencySpec`
        YAML files.  Loaded into a name-keyed registry accessible via
        :attr:`dependency_specs`.
    local_config
        **Deprecated** — use *local_configs* instead.  Accepted for
        backward compatibility; ignored when *local_configs* is given.
    """

    def __init__(
        self,
        *,
        base_dir: Union[str, Path],
        parameter_specs: List[dict],
        format_specs: List[dict],
        product_specs: List[dict],
        local_configs: Optional[Union[_PathLike, List[_PathLike]]] = None,
        remote_specs: Optional[List[dict]] = None,
        dependency_specs: Optional[Union[_PathLike, List[Union[_PathLike, dict]]]] = None,
        # Backward compat: accept the old singular name
        local_config: Optional[_PathLike] = None,
    ) -> None:
        self._base_dir = Path(base_dir)

        # ── Layer 1: catalogs (built in dependency order) ─────────
        self._parameter_catalog = ParameterCatalog(
            parameters=[Parameter(**p) for p in parameter_specs]
        )
        register_computed_fields(self._parameter_catalog)

        self._format_catalog = FormatCatalog(
            format_spec_catalog=FormatSpecCatalog(formats=format_specs),
            parameter_catalog=self._parameter_catalog,
        )

        self._product_catalog = ProductCatalog(
            product_spec_catalog=ProductSpecCatalog(products=product_specs),
            format_catalog=self._format_catalog,
        )

        # ── Layer 2: resource factories ───────────────────────────
        self._remote_factory = RemoteResourceFactory(self._product_catalog)
        for spec_dict in (remote_specs or []):
            self._remote_factory.register(ResourceSpec(**spec_dict))

        # Local factory — merge one or more local config YAMLs
        local_paths = _coerce_path_list(local_configs) or _coerce_path_list(local_config)
        self._local_factory: Optional[LocalResourceFactory] = None
        if local_paths:
            self._local_factory = self._build_local_factory(local_paths)

        # ── Dependency specifications ─────────────────────────────
        self._dependency_specs: Dict[str, DependencySpec] = {}
        self._load_dependency_specs(dependency_specs)

    # ── Private builders ──────────────────────────────────────────

    def _build_local_factory(self, paths: List[Path]) -> LocalResourceFactory:
        """Load and merge local config YAMLs, then build a factory."""
        specs = [LocalResourceSpec.from_yaml(str(p)) for p in paths]
        merged = LocalResourceSpec.merge(specs) if len(specs) > 1 else specs[0]
        return LocalResourceFactory(
            merged,
            self._product_catalog,
            self._parameter_catalog,
            base_dir=self._base_dir,
        )

    def _load_dependency_specs(
        self,
        sources: Optional[Union[_PathLike, List[Union[_PathLike, dict]]]],
    ) -> None:
        """Load dependency specs from paths or dicts into the registry."""
        if sources is None:
            return
        if isinstance(sources, (str, Path)):
            sources = [sources]
        for src in sources:
            if isinstance(src, dict):
                ds = DependencySpec.model_validate(src)
            else:
                ds = DependencySpec.from_yaml(src)
            self._dependency_specs[ds.name] = ds

    # ── YAML class-method constructor ─────────────────────────────

    @classmethod
    def from_yaml(
        cls,
        *,
        base_dir: Union[str, Path],
        meta_spec_yaml: Union[str, Path],
        product_spec_yaml: Union[str, Path],
        local_configs: Optional[Union[_PathLike, List[_PathLike]]] = None,
        remote_specs: Optional[List[Union[str, Path, dict]]] = None,
        dependency_specs: Optional[Union[_PathLike, List[Union[_PathLike, dict]]]] = None,
        # Backward compat
        local_config: Optional[_PathLike] = None,
    ) -> "ProductEnvironment":
        """Build a ProductEnvironment directly from YAML config files.

        Uses the specification layer's ``from_yaml`` class methods
        to load catalogs, then wires them together.
        """
        base_dir = Path(base_dir)
        pc = ParameterCatalog.from_yaml(meta_spec_yaml)
        register_computed_fields(pc)
        fsc = FormatSpecCatalog.from_yaml(product_spec_yaml)
        fc = FormatCatalog(format_spec_catalog=fsc, parameter_catalog=pc)
        psc = ProductSpecCatalog.from_yaml(product_spec_yaml)
        prod_cat = ProductCatalog(product_spec_catalog=psc, format_catalog=fc)

        env = object.__new__(cls)
        env._base_dir = base_dir
        env._parameter_catalog = pc
        env._format_catalog = fc
        env._product_catalog = prod_cat

        # Remote centres
        env._remote_factory = RemoteResourceFactory(prod_cat)
        for spec in (remote_specs or []):
            if isinstance(spec, dict):
                env._remote_factory.register(ResourceSpec(**spec))
            else:
                env._remote_factory.register(ResourceSpec.from_yaml(str(spec)))

        # Local storage — merge multiple configs
        local_paths = _coerce_path_list(local_configs) or _coerce_path_list(local_config)
        env._local_factory = None
        if local_paths:
            env._local_factory = env._build_local_factory(local_paths)

        # Dependency specs
        env._dependency_specs = {}
        env._load_dependency_specs(dependency_specs)

        return env

    # ── Registration helpers ──────────────────────────────────────

    def register_remote(self, spec_dict: dict) -> None:
        """Register an additional remote center from a raw spec dict."""
        self._remote_factory.register(ResourceSpec(**spec_dict))

    def register_dependency_spec(
        self, source: Union[_PathLike, dict, DependencySpec],
    ) -> DependencySpec:
        """Register an additional dependency spec at runtime."""
        if isinstance(source, DependencySpec):
            ds = source
        elif isinstance(source, dict):
            ds = DependencySpec.model_validate(source)
        else:
            ds = DependencySpec.from_yaml(source)
        self._dependency_specs[ds.name] = ds
        return ds

    # ── Read-only accessors ───────────────────────────────────────

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    @property
    def parameter_catalog(self) -> ParameterCatalog:
        return self._parameter_catalog

    @property
    def format_catalog(self) -> FormatCatalog:
        return self._format_catalog

    @property
    def product_catalog(self) -> ProductCatalog:
        return self._product_catalog

    @property
    def remote_factory(self) -> RemoteResourceFactory:
        return self._remote_factory

    @property
    def local_factory(self) -> Optional[LocalResourceFactory]:
        return self._local_factory

    @local_factory.setter
    def local_factory(self, value: Union[_PathLike, List[_PathLike]]) -> None:
        """Rebuild the local factory from one or more config YAML paths."""
        paths = _coerce_path_list(value)
        self._local_factory = self._build_local_factory(paths)

    @property
    def dependency_specs(self) -> Dict[str, DependencySpec]:
        """All registered dependency specs, keyed by name."""
        return self._dependency_specs

    def get_dependency_spec(self, name: str) -> DependencySpec:
        """Retrieve a dependency spec by name, raising ``KeyError`` if missing."""
        try:
            return self._dependency_specs[name]
        except KeyError:
            raise KeyError(
                f"Dependency spec {name!r} not found. "
                f"Available: {sorted(self._dependency_specs)}"
            )

    def __repr__(self) -> str:
        n_centers = len(self._remote_factory.centers)
        n_products = len(self._product_catalog.products)
        n_deps = len(self._dependency_specs)
        local_str = "yes" if self._local_factory else "no"
        return (
            f"ProductEnvironment(base_dir={self._base_dir!r}, "
            f"products={n_products}, centers={n_centers}, "
            f"local={local_str}, dep_specs={n_deps})"
        )
