# """
# ProductEnvironment — unified container for the specification/factory layer.

# Builds the full catalog chain (ParameterCatalog → FormatCatalog → ProductCatalog)
# and wires up remote/local resource factories.

# **Preferred construction** — supply only a workspace directory::

#     env = ProductEnvironment(workspace="/data/gnss_products")
#     result = env.classify("WUM0MGXFIN_20250010000_01D_05M_ORB.SP3")

# The ``workspace`` path becomes the ``base_dir`` for local storage.
# All bundled specification YAMLs are loaded automatically.

# **Legacy construction** — explicit catalogue dicts / YAML paths are still
# supported via the keyword-only ``base_dir`` + individual spec arguments,
# and via ``from_yaml()``.
# """

# from __future__ import annotations

# import re
# from pathlib import Path
# from threading import local
# from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple, Union

# from gnss_ppp_products.specifications.parameters.parameter import Parameter, ParameterCatalog
# from gnss_ppp_products.specifications.format.format_spec import FormatCatalog, FormatSpecCatalog
# from gnss_ppp_products.specifications.products.catalog import ProductCatalog, ProductSpecCatalog
# from gnss_ppp_products.specifications.remote.resource import ResourceSpec
# from gnss_ppp_products.specifications.local.local import LocalResourceSpec
# from gnss_ppp_products.factories.local_factory import LocalResourceFactory
# from gnss_ppp_products.specifications.dependencies.dependencies import DependencySpec
# from gnss_ppp_products.factories.remote_factory import RemoteResourceFactory
# from gnss_ppp_products.factories.resource_fetcher import ResourceFetcher
# from gnss_ppp_products.specifications.products.product import Product
# from gnss_ppp_products.utilities.metadata_funcs import register_computed_fields
# from gnss_ppp_products.configs import (
#     META_SPEC_YAML,
#     FORMAT_SPEC_YAML,
#     PRODUCT_SPEC_YAML,
#     LOCAL_SPEC_DIR,
#     CENTERS_RESOURCE_DIR,
#     DEPENDENCY_SPEC_DIR,
# )

# # Type alias for a single path-like value
# _PathLike = Union[str, Path]


# def _coerce_path_list(
#     value: Optional[Union[_PathLike, Sequence[_PathLike]]],
# ) -> List[Path]:
#     """Normalise ``None``, a single path, or a list to ``List[Path]``."""
#     if value is None:
#         return []
#     if isinstance(value, (str, Path)):
#         return [Path(value)]
#     return [Path(v) for v in value]


# # ── Precompiled match table for classify() ────────────────────────


# class _MatchEntry(NamedTuple):
#     template_len: int
#     compiled_regex: re.Pattern
#     product_name: str
#     format_name: str
#     version: str
#     variant: str
#     fixed_params: dict


# def _build_match_table(
#     product_spec_catalog: ProductSpecCatalog,
#     product_catalog: ProductCatalog,
#     parameter_catalog: ParameterCatalog,
# ) -> list[_MatchEntry]:
#     """Precompile a regex match table sorted by template specificity (longest first)."""
#     entries: list[_MatchEntry] = []
#     for prod_name, ver_cat in product_catalog.products.items():
#         for ver_name, var_cat in ver_cat.versions.items():
#             for var_name, product in var_cat.variants.items():
#                 if product.filename is None:
#                     continue
#                 spec = product_spec_catalog.products[prod_name].versions[ver_name].variants[var_name]
#                 merged = _merged_parameter_catalog(parameter_catalog, product.parameters)
#                 regex_str = product.filename.to_regex(merged)
#                 entries.append(_MatchEntry(
#                     template_len=len(product.filename.pattern),
#                     compiled_regex=re.compile(regex_str),
#                     product_name=prod_name,
#                     format_name=spec.format,
#                     version=ver_name,
#                     variant=var_name,
#                     fixed_params={p.name: p.value for p in product.parameters if p.value is not None},
#                 ))
#     entries.sort(key=lambda e: -e.template_len)
#     return entries


# def _merged_parameter_catalog(
#     base: ParameterCatalog,
#     product_params: List[Parameter],
# ) -> ParameterCatalog:
#     """Merge product-specific parameter patterns into the global catalog."""
#     merged = {name: param.model_copy(deep=True) for name, param in base.parameters.items()}
#     for p in product_params:
#         if p.name in merged:
#             updates = {}
#             if p.pattern is not None:
#                 updates["pattern"] = p.pattern
#             if updates:
#                 merged[p.name] = merged[p.name].model_copy(update=updates, deep=True)
#         else:
#             merged[p.name] = p.model_copy(deep=True)
#     return ParameterCatalog(list(merged.values()))


# class ProductEnvironment:
#     """Unified container holding all built catalogs and factories.

#     **Primary constructor** — auto-loads bundled specifications::

#         env = ProductEnvironment(workspace="/data/gnss")

#     ``workspace`` may also be a ``(base_dir, alias)`` tuple::

#         env = ProductEnvironment(workspace=("/data/gnss", "campaign1"))

#     **Legacy constructor** — explicit dicts / paths (used by tests)::

#         env = ProductEnvironment(
#             base_dir="/tmp/test",
#             parameter_specs=[...],
#             format_specs=[...],
#             product_specs=[...],
#         )

#     The environment is **immutable** after construction.
#     """

#     def __init__(
#         self,
#         *,
#         workspace: Union[str, Path, Tuple[Union[str, Path], str], None] = None,
#         # ── Legacy params (used when workspace is None) ───────────
#         base_dir: Optional[Union[str, Path]] = None,
#         parameter_spec: Path | str = META_SPEC_YAML,
#         format_spec: Path | str = FORMAT_SPEC_YAML,
#         product_spec: Path | str = PRODUCT_SPEC_YAML,
#         local_resource_configs: Union[_PathLike, List[_PathLike]] = LOCAL_SPEC_DIR,
#         remote_specs: List[_PathLike] = list(CENTERS_RESOURCE_DIR.glob("*.yaml")),
#         dependency_specs: Optional[Union[_PathLike, List[Union[_PathLike, dict]]]] = None,

#     ) -> None:
#         if workspace is not None:
#             self._init_from_workspace(workspace)
#             return

#         if base_dir is None:
#             raise TypeError("ProductEnvironment requires either workspace= or base_dir=")

#         parameter_spec = Path(parameter_spec)
#         format_spec = Path(format_spec)
#         product_spec = Path(product_spec)
#         local_resource_configs: List[Path] = _coerce_path_list(local_resource_configs)
#         remote_specs: List[Path] = _coerce_path_list(remote_specs)

#         self._base_dir = Path(base_dir) if base_dir else Path.cwd()
#         self._alias = self._base_dir.stem

#         # ── Layer 1: catalogs (built in dependency order) ─────────
#         self._parameter_catalog = ParameterCatalog.from_yaml(
#             yaml_path=parameter_spec
#         )

#         register_computed_fields(self._parameter_catalog)

#         self._format_catalog = FormatCatalog.build(
#             format_spec_catalog=FormatSpecCatalog.from_yaml(format_spec),
#             parameter_catalog=self._parameter_catalog,
#         )

#         _psc = ProductSpecCatalog.from_yaml(product_spec)
#         self._product_catalog = ProductCatalog.build(
#             product_spec_catalog=_psc,
#             format_catalog=self._format_catalog,
#         )
#         self._match_table = _build_match_table(_psc, self._product_catalog, self._parameter_catalog)

#         # ── Layer 2: resource factories ───────────────────────────
#         self._remote_factory = RemoteResourceFactory(self._product_catalog, self._parameter_catalog)
#         for spec_resource_yaml in remote_specs:
#             self._remote_factory.register(ResourceSpec.from_yaml(str(spec_resource_yaml)))

#         # Local factory — merge one or more local config YAMLs
#         self._local_factory = LocalResourceFactory(
#             product_catalog=self._product_catalog,
#             parameter_catalog=self._parameter_catalog,
#         )


#         for local_file_spec_yaml in local_resource_configs:
#             local_resource_spec = LocalResourceSpec.from_yaml(str(local_file_spec_yaml))
#             self._local_factory.register(local_resource_spec, base_dir=self._base_dir/local_resource_spec.name.upper())

#         # ── Resource fetcher (shared, caches connections) ─────────
#         self._resource_fetcher = ResourceFetcher()

#         # ── Dependency specifications ─────────────────────────────
#         self._dependency_specs: Dict[str, DependencySpec] = {}
#         self._load_dependency_specs(dependency_specs)

#     # ── Workspace constructor ─────────────────────────────────────

#     def _init_from_workspace(
#         self,
#         workspace: Union[str, Path, Tuple[Union[str, Path], str]],
#     ) -> None:
#         """Auto-load all bundled specifications from a workspace path."""
#         if isinstance(workspace, tuple):
#             raw_dir, alias = workspace
#         else:
#             raw_dir = workspace
#             alias = Path(raw_dir).stem

#         bd = Path(raw_dir)
#         if not bd.exists():
#             raise FileNotFoundError(f"Workspace directory does not exist: {bd}")

#         self._base_dir = bd
#         self._alias = alias

#         # Layer 1: catalogs
#         self._parameter_catalog = ParameterCatalog.from_yaml(META_SPEC_YAML)
#         register_computed_fields(self._parameter_catalog)

#         fsc = FormatSpecCatalog.from_yaml(PRODUCT_SPEC_YAML)
#         self._format_catalog = FormatCatalog.build(
#             format_spec_catalog=fsc, parameter_catalog=self._parameter_catalog,
#         )

#         psc = ProductSpecCatalog.from_yaml(PRODUCT_SPEC_YAML)
#         self._product_catalog = ProductCatalog.build(
#             product_spec_catalog=psc, format_catalog=self._format_catalog,
#         )
#         self._match_table = _build_match_table(psc, self._product_catalog, self._parameter_catalog)

#         # Layer 2: remote centres (all YAML files in CENTERS_DIR)
#         self._remote_factory = RemoteResourceFactory(self._product_catalog, self._parameter_catalog)
#         for yaml_path in sorted(CENTERS_RESOURCE_DIR.glob("*.yaml")):
#             self._remote_factory.register(ResourceSpec.from_yaml(str(yaml_path)))

#         # Local storage
#         local_paths = sorted(LOCAL_SPEC_DIR.glob("*.yaml"))
#         self._local_factory: Optional[LocalResourceFactory] = None
#         if local_paths:
#             self._local_factory = self._build_local_factory(local_paths)

#         # Resource fetcher (shared, caches connections)
#         self._resource_fetcher = ResourceFetcher()

#         # Dependency specs
#         self._dependency_specs: Dict[str, DependencySpec] = {}
#         dep_paths: List[Union[str, Path]] = sorted(DEPENDENCY_SPEC_DIR.glob("*.yaml"))
#         self._load_dependency_specs(dep_paths)

#     # ── Private builders ──────────────────────────────────────────

#     def _build_local_factory(self, local_paths: List[Path]) -> LocalResourceFactory:
#         """Create and populate a LocalResourceFactory from YAML config files."""
#         factory = LocalResourceFactory(
#             product_catalog=self._product_catalog,
#             parameter_catalog=self._parameter_catalog,
#         )
#         for yaml_path in local_paths:
#             spec = LocalResourceSpec.from_yaml(str(yaml_path))
#             factory.register(spec, base_dir=self._base_dir / spec.name.upper())
#         return factory

#     def _load_dependency_specs(
#         self,
#         sources: Optional[Union[_PathLike, List[Union[_PathLike, dict]]]],
#     ) -> None:
#         """Load dependency specs from paths or dicts into the registry."""
#         if sources is None:
#             return
#         if isinstance(sources, (str, Path)):
#             sources = [sources]
#         for src in sources:
#             if isinstance(src, dict):
#                 ds = DependencySpec.model_validate(src)
#             else:
#                 ds = DependencySpec.from_yaml(src)
#             self._dependency_specs[ds.name] = ds

#     # ── YAML class-method constructor ─────────────────────────────

#     @classmethod
#     def from_yaml(
#         cls,
#         *,
#         base_dir: Union[str, Path],
#         meta_spec_yaml: Union[str, Path],
#         product_spec_yaml: Union[str, Path],
#         local_configs: Optional[Union[_PathLike, List[_PathLike]]] = None,
#         remote_specs: Optional[List[Union[str, Path, dict]]] = None,
#         dependency_specs: Optional[Union[_PathLike, List[Union[_PathLike, dict]]]] = None,
#         # Backward compat
#         local_config: Optional[_PathLike] = None,
#     ) -> "ProductEnvironment":
#         """Build a ProductEnvironment directly from YAML config files.

#         Uses the specification layer's ``from_yaml`` class methods
#         to load catalogs, then wires them together.
#         """
#         base_dir = Path(base_dir)
#         pc = ParameterCatalog.from_yaml(meta_spec_yaml)
#         register_computed_fields(pc)
#         fsc = FormatSpecCatalog.from_yaml(product_spec_yaml)
#         fc = FormatCatalog.build(format_spec_catalog=fsc, parameter_catalog=pc)
#         psc = ProductSpecCatalog.from_yaml(product_spec_yaml)
#         prod_cat = ProductCatalog.build(product_spec_catalog=psc, format_catalog=fc)

#         env = object.__new__(cls)
#         env._base_dir = base_dir
#         env._alias = base_dir.stem
#         env._parameter_catalog = pc
#         env._format_catalog = fc
#         env._product_catalog = prod_cat
#         env._match_table = _build_match_table(psc, prod_cat, pc)

#         # Remote centres
#         env._remote_factory = RemoteResourceFactory(prod_cat, pc)
#         for spec in (remote_specs or []):
#             if isinstance(spec, dict):
#                 env._remote_factory.register(ResourceSpec(**spec))
#             else:
#                 env._remote_factory.register(ResourceSpec.from_yaml(str(spec)))

#         # Local storage — merge multiple configs
#         local_paths = _coerce_path_list(local_configs) or _coerce_path_list(local_config)
#         env._local_factory = None
#         if local_paths:
#             env._local_factory = env._build_local_factory(local_paths)

#         # Resource fetcher (shared, caches connections)
#         env._resource_fetcher = ResourceFetcher()

#         # Dependency specs
#         env._dependency_specs = {}
#         env._load_dependency_specs(dependency_specs)

#         return env

#     # ── Read-only accessors ───────────────────────────────────────

#     @property
#     def base_dir(self) -> Path:
#         return self._base_dir

#     @property
#     def alias(self) -> str:
#         return self._alias

#     @property
#     def parameter_catalog(self) -> ParameterCatalog:
#         return self._parameter_catalog

#     @property
#     def format_catalog(self) -> FormatCatalog:
#         return self._format_catalog

#     @property
#     def product_catalog(self) -> ProductCatalog:
#         return self._product_catalog

#     @property
#     def remote_factory(self) -> RemoteResourceFactory:
#         return self._remote_factory

#     @property
#     def local_factory(self) -> Optional[LocalResourceFactory]:
#         return self._local_factory

#     @property
#     def resource_fetcher(self) -> ResourceFetcher:
#         return self._resource_fetcher

#     @property
#     def dependency_specs(self) -> Dict[str, DependencySpec]:
#         """All registered dependency specs, keyed by name."""
#         return self._dependency_specs

#     def get_dependency_spec(self, name: str) -> DependencySpec:
#         """Retrieve a dependency spec by name, raising ``KeyError`` if missing."""
#         try:
#             return self._dependency_specs[name]
#         except KeyError:
#             raise KeyError(
#                 f"Dependency spec {name!r} not found. "
#                 f"Available: {sorted(self._dependency_specs)}"
#             )

#     # ── Public operations ─────────────────────────────────────────

#     def classify(
#         self,
#         filename: str,
#         parameters: Optional[List[Parameter]] = None,
#     ) -> Optional[Dict[str, str]]:
#         """Parse a product filename and return its metadata.

#         Parameters
#         ----------
#         filename
#             A product filename, optionally including a directory path
#             and/or compression extension.
#         parameters
#             Optional hard constraints.  Products whose fixed parameters
#             conflict with a supplied value are skipped, and extracted
#             values that conflict also cause the candidate to be skipped.

#         Returns
#         -------
#         dict or None
#             ``{"product", "format", "version", "variant", "parameters": {...}}``
#             on match, or ``None`` if no product template matches.
#         """
#         name = Path(filename).name
#         constraints = {
#             p.name: p.value
#             for p in (parameters or [])
#             if p.value is not None
#         }

#         for entry in self._match_table:
#             if any(
#                 k in entry.fixed_params and entry.fixed_params[k] != v
#                 for k, v in constraints.items()
#             ):
#                 continue

#             m = entry.compiled_regex.fullmatch(name)
#             if m is None:
#                 continue

#             extracted = {k: v for k, v in m.groupdict().items() if v is not None}

#             if any(
#                 k in extracted and extracted[k] != v
#                 for k, v in constraints.items()
#             ):
#                 continue

#             return {
#                 "product": entry.product_name,
#                 "format": entry.format_name,
#                 "version": entry.version,
#                 "variant": entry.variant,
#                 "parameters": {**entry.fixed_params, **extracted},
#             }

#         return None

#     def __repr__(self) -> str:
#         n_centers = len(self._remote_factory.centers)
#         n_products = len(self._product_catalog.products)
#         n_deps = len(self._dependency_specs)
#         local_str = "yes" if self._local_factory else "no"
#         return (
#             f"ProductEnvironment(alias={self._alias!r}, base_dir={self._base_dir!r}, "
#             f"products={n_products}, centers={n_centers}, "
#             f"local={local_str}, dep_specs={n_deps})"
#         )

from pathlib import Path

from typing import Any, Dict, NamedTuple, Optional, List
import re

from gnss_ppp_products.factories.environment import _build_match_table
from gnss_ppp_products.specifications.remote.resource import ResourceSpec, Server
from pydantic import BaseModel


from gnss_ppp_products.specifications.format.format_spec import (
    FormatCatalog,
    FormatSpecCatalog,
)
from gnss_ppp_products.specifications.parameters.parameter import (
    Parameter,
    ParameterCatalog,
)
from gnss_ppp_products.specifications.products.catalog import (
    ProductCatalog,
    ProductSpecCatalog,
)
from gnss_ppp_products.factories.remote_factory import (
    RemoteResourceFactory,
    ResourceSpec,
)
from gnss_ppp_products.utilities.metadata_funcs import register_computed_fields

from gnss_ppp_products.specifications.local.local import LocalResourceSpec

class _MatchEntry(NamedTuple):
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
    """Merge product-specific parameter patterns into the global catalog."""
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
    """Precompile a regex match table sorted by template specificity (longest first)."""
    entries: list[_MatchEntry] = []
    for prod_name, ver_cat in product_catalog.products.items():
        for ver_name, var_cat in ver_cat.versions.items():
            for var_name, product in var_cat.variants.items():
                if product.filename is None:
                    continue
                spec = product_spec_catalog.products[prod_name].versions[ver_name].variants[var_name]
                merged = _merged_parameter_catalog(parameter_catalog, product.parameters)
                regex_str = product.filename.to_regex(merged)
                entries.append(_MatchEntry(
                    template_len=len(product.filename.pattern),
                    compiled_regex=re.compile(regex_str),
                    product_name=prod_name,
                    format_name=spec.format,
                    version=ver_name,
                    variant=var_name,
                    fixed_params={p.name: p.value for p in product.parameters if p.value is not None},
                ))
    entries.sort(key=lambda e: -e.template_len)
    return entries

class LoadedSpecs(BaseModel):
    filename: Path | str
    built: Any


class ProductEnvironment:

    def __init__(self) -> None:
        pass

        self._parameter_specs: Dict[str, LoadedSpecs] = {}
        self._format_specs: Dict[str, LoadedSpecs] = {}
        self._product_specs: Dict[str, LoadedSpecs] = {}
        self._resource_specs: Dict[str, LoadedSpecs] = {}

        self._parameter_catalog: Optional[ParameterCatalog] = None
        self._format_catalog: Optional[FormatCatalog] = None
        self._product_spec_catalog: Optional[ProductSpecCatalog] = None
        self._product_catalog: Optional[ProductCatalog] = None
        self._remote_resource_factory: Optional[RemoteResourceFactory] = None

    def add_parameter_spec(self, path: Path | str, id: str = "default") -> None:
        path = Path(path)
        assert path.exists(), f"Parameter spec file not found: {path}"
        assert path.is_file(), f"Parameter spec path must be a file: {path}"
        assert (
            id not in self._parameter_specs
        ), f"Parameter spec with id '{id}' already exists. Please choose a unique id."
        parameter_spec_catalog = ParameterCatalog.from_yaml(path)
        self._parameter_specs[id] = LoadedSpecs(
            filename=path, built=parameter_spec_catalog
        )

    def add_format_spec(self, path: Path | str, id: str = "default") -> None:
        path = Path(path)
        assert path.exists(), f"Format spec file not found: {path}"
        assert path.is_file(), f"Format spec path must be a file: {path}"
        assert (
            id not in self._format_specs
        ), f"Format spec with id '{id}' already exists. Please choose a unique id."

        format_spec_catalog = FormatSpecCatalog.from_yaml(path)
        self._format_specs[id] = LoadedSpecs(filename=path, built=format_spec_catalog)

    def add_product_spec(self, path: Path | str, id: str = "default") -> None:
        path = Path(path)
        assert path.exists(), f"Product spec file not found: {path}"
        assert path.is_file(), f"Product spec path must be a file: {path}"
        assert (
            id not in self._product_specs
        ), f"Product spec with id '{id}' already exists. Please choose a unique id."
        product_spec: ProductSpecCatalog = ProductSpecCatalog.from_yaml(path)
        self._product_specs[id] = LoadedSpecs(filename=path, built=product_spec)
        if self._product_spec_catalog is None:
            self._product_spec_catalog = product_spec
        else:
            self._product_spec_catalog = self._product_spec_catalog.merge(product_spec)

    def add_resource_spec(self, path: Path | str) -> None:
        path = Path(path)
        assert path.exists(), f"Resource spec file not found: {path}"
        assert path.is_file(), f"Resource spec path must be a file: {path}"

        resource_spec = ResourceSpec.from_yaml(path)
        id = resource_spec.id
        assert (
            id not in self._resource_specs
        ), f"Resource spec with id '{id}' already exists. Please choose a unique id."
        self._resource_specs[id] = LoadedSpecs(filename=path, built=resource_spec)

    def _build_parameter_catalog(self) -> None:
        for id, spec in self._parameter_specs.items():
            if self._parameter_catalog is None:
                self._parameter_catalog = ParameterCatalog.from_yaml(spec.filename)
            else:
                new_cat = ParameterCatalog.from_yaml(spec.filename)
                self._parameter_catalog = self._parameter_catalog.merge(new_cat)
        register_computed_fields(self._parameter_catalog)

    def _build_format_catalog(self) -> None:
        assert (
            self._parameter_catalog is not None
        ), "Parameter catalog must be built before building format catalog"
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
        assert (
            self._format_catalog is not None
        ), "Format catalog must be built before building product catalog"
        assert (
            self._product_spec_catalog is not None
        ), "Product spec catalog must be built before building product catalog"
        assert (
            self._parameter_catalog is not None
        ), "Parameter catalog must be built before building product catalog"
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
        assert (
            self._product_catalog is not None
        ), "Product catalog must be built before building remote resource factory"
        assert (
            self._parameter_catalog is not None
        ), "Parameter catalog must be built before building remote resource factory"
        factory = RemoteResourceFactory(
            product_catalog=self._product_catalog,
            parameter_catalog=self._parameter_catalog,
        )
        for id, spec in self._resource_specs.items():
            factory.register(spec.built)
        self._remote_resource_factory = factory

    def build(self) -> None:
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

        Parameters
        ----------
        filename
            A product filename, optionally including a directory path
            and/or compression extension.
        parameters
            Optional hard constraints.  Products whose fixed parameters
            conflict with a supplied value are skipped, and extracted
            values that conflict also cause the candidate to be skipped.

        Returns
        -------
        dict or None
            ``{"product", "format", "version", "variant", "parameters": {...}}``
            on match, or ``None`` if no product template matches.
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
