"""
ProductEnvironment — unified container for the new specification/factory layer.

Builds the full catalog chain (ParameterCatalog → FormatCatalog → ProductCatalog)
and wires up remote/local resource factories from raw spec dicts or file paths.

The environment owns the built objects but does NOT perform queries or downloads
itself — callers pull out the pieces they need::

    env = ProductEnvironment(
        base_dir="~/gnss_products",
        parameter_specs=param_dicts,
        format_specs=fmt_dicts,
        product_specs=prod_dicts,
        local_config="path/to/local_config.yaml",
        remote_specs=[wuhan_dict, igs_dict, code_dict],
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
from typing import Dict, List, Optional, Union

from gnss_ppp_products.specifications.parameters.parameter import Parameter, ParameterCatalog
from gnss_ppp_products.specifications.format.format_spec import FormatCatalog, FormatSpecCatalog
from gnss_ppp_products.specifications.products.catalog import ProductCatalog, ProductSpecCatalog
from gnss_ppp_products.specifications.remote.resource import ResourceSpec
from gnss_ppp_products.specifications.local.local import LocalResourceSpec
from gnss_ppp_products.specifications.local.factory import LocalResourceFactory
from gnss_ppp_products.factories.remote_factory import RemoteResourceFactory
from gnss_ppp_products.utilities.metadata_funcs import register_computed_fields


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
    local_config : str | Path | None
        Path to a ``LocalResourceSpec`` YAML file.  Optional — if omitted
        the environment will have no local factory.
    remote_specs : list[dict] | None
        Raw remote resource specification dicts.  Each is registered with
        the :class:`RemoteResourceFactory`.
    """

    def __init__(
        self,
        *,
        base_dir: Union[str, Path],
        parameter_specs: List[dict],
        format_specs: List[dict],
        product_specs: List[dict],
        local_config: Optional[Union[str, Path]] = None,
        remote_specs: Optional[List[dict]] = None,
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

        self._local_factory: Optional[LocalResourceFactory] = None
        if local_config is not None:
            local_spec = LocalResourceSpec.from_yaml(str(local_config))
            self._local_factory = LocalResourceFactory(
                local_spec,
                self._product_catalog,
                self._parameter_catalog,
                base_dir=self._base_dir,
            )

    # ── Registration ──────────────────────────────────────────────

    @classmethod
    def from_yaml(
        cls,
        *,
        base_dir: Union[str, Path],
        meta_spec_yaml: Union[str, Path],
        product_spec_yaml: Union[str, Path],
        local_config: Optional[Union[str, Path]] = None,
        remote_specs: Optional[List[dict]] = None,
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
        env._remote_factory = RemoteResourceFactory(prod_cat)
        for spec_dict in (remote_specs or []):
            env._remote_factory.register(ResourceSpec(**spec_dict))
        env._local_factory = None
        if local_config is not None:
            local_spec = LocalResourceSpec.from_yaml(str(local_config))
            env._local_factory = LocalResourceFactory(
                local_spec, prod_cat, pc, base_dir=base_dir,
            )
        return env

    def register_remote(self, spec_dict: dict) -> None:
        """Register an additional remote center from a raw spec dict."""
        self._remote_factory.register(ResourceSpec(**spec_dict))

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
    def local_factory(self, local_config: Union[str, Path]) -> None:
        """Rebuild the local factory from a new config YAML path."""
        local_spec = LocalResourceSpec.from_yaml(str(local_config))
        self._local_factory = LocalResourceFactory(
            local_spec,
            self._product_catalog,
            self._parameter_catalog,
            base_dir=self._base_dir,
        )

    def __repr__(self) -> str:
        n_centers = len(self._remote_factory.centers)
        n_products = len(self._product_catalog.products)
        local_str = "yes" if self._local_factory else "no"
        return (
            f"ProductEnvironment(base_dir={self._base_dir!r}, "
            f"products={n_products}, centers={n_centers}, local={local_str})"
        )
