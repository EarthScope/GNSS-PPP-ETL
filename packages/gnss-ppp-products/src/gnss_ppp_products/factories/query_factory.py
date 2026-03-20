"""QueryFactory and QueryProfile — lazy narrowing query builder."""

import datetime
import logging
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel

from gnss_ppp_products.specifications.parameters.parameter import ParameterCatalog
from gnss_ppp_products.specifications.products.product import Product, ProductPath, VariantCatalog, VersionCatalog
from gnss_ppp_products.specifications.remote.resource import ResourceQuery, Server
from gnss_ppp_products.specifications.local.factory import LocalResourceFactory
from gnss_ppp_products.factories.remote_factory import RemoteResourceFactory
from gnss_ppp_products.utilities.helpers import _listify, expand_dict_combinations

logger = logging.getLogger(__name__)


class AxisAlias(BaseModel):
    """Maps a human-friendly axis name to one or more parameter names."""
    alias: str
    parameters: List[str]
    description: Optional[str] = None


class SortPreference(BaseModel):
    """Defines the preferred order for an axis during resolution."""
    axis: str
    order: List[str]


class QueryProfile(BaseModel):
    """Thin query configuration — just axis aliases and sort preferences."""
    axes: List[AxisAlias] = []
    sort_preferences: List[SortPreference] = []

    def resolve_axis(self, alias: str) -> List[str]:
        """Map an alias to parameter names."""
        for ax in self.axes:
            if ax.alias == alias:
                return ax.parameters
        return [alias]

    def get_preference(self, axis: str) -> Optional[List[str]]:
        """Get sort order for a given axis."""
        for sp in self.sort_preferences:
            if sp.axis == axis:
                return sp.order
        return None


class QueryFactory:
    """Lazy query factory — narrows parameter ranges, resolves on demand.

    Uses ``RemoteResourceFactory`` for remote registration,
    ``ProductCatalog`` (nested version→variant→Product hierarchy),
    and ``ParameterCatalog`` for fallback regex patterns and computed
    date-field resolution.

    Usage::

        qf = QueryFactory(
            remote_factory=remote,
            local_factory=local,
            product_catalog=PRODUCT_CATALOG,
            parameter_catalog=PARAMETER_CATALOG,
        )

        results = qf.get(
            datetime.date(2024, 1, 1),
            product={"name": "ORBIT"},
            parameters={"AAA": ["WUM", "COD"]},
        )
    """

    def __init__(
        self,
        remote_factory: RemoteResourceFactory,
        local_factory: LocalResourceFactory,
        product_catalog,
        parameter_catalog: ParameterCatalog,
    ):
        self._remote = remote_factory
        self._local = local_factory
        self._products = product_catalog
        self._params = parameter_catalog

    def get(
        self,
        date: datetime.datetime,
        product: Dict[str, str | list[str]],
        parameters: Optional[Dict[str, str | list[str]]] = None,
        local_resources: Optional[List[str]] = None,
        remote_resources: Optional[List[str]] = None,
    ) -> list[ResourceQuery]:
        """Narrow parameter ranges and return searchable resources.

        Parameters
        ----------
        date : datetime.datetime
            Target date for computed metadata fields (e.g. YYYY, DDD).
        product : dict
            Product query with ``name``, optionally ``version``, ``variant``.
        parameters : dict[str, str | list[str]] | None
            User constraints on metadata fields.  If *None* or empty,
            no narrowing is applied — all parameter values remain as
            wildcards (resolved to regex patterns in the final step).
        local_resources : list[str]
            If specified, only include local resources with these collection IDs.
        remote_resources : list[str]
            If specified, only include remote resources with these center IDs.

        Returns
        -------
        list[ResourceQuery]
        """
        parameters = parameters or {}
        local_resources = _listify(local_resources)
        remote_resources = _listify(remote_resources)
        out: List[ResourceQuery] = []

        # 1. Get product templates matching the query product spec
        product_templates: List[Product] = []

        product_name_query = product.get("name")
        product_version_query = _listify(product.get("version"))
        product_variant_query = _listify(product.get("variant"))

        product_version_catalog: Optional[VersionCatalog] = self._products.products.get(product_name_query)
        if product_version_catalog is None:
            raise ValueError(f"Product {product_name_query!r} not found in ProductCatalog")
        versions = product_version_query or list(product_version_catalog.versions.keys())
        for version in versions:
            variant_cat: Optional[VariantCatalog] = product_version_catalog.versions.get(version)
            if variant_cat is None:
                raise ValueError(f"Version {version!r} not found for product {product_name_query!r}")
            variants = product_variant_query or list(variant_cat.variants.keys())
            for variant in variants:
                if variant not in variant_cat.variants:
                    raise ValueError(f"Variant {variant!r} not found for product {product_name_query!r} version {version!r}")
                product_templates.append(variant_cat.variants[variant])

        print("TEST 1: product templates matching query spec:")
        for template in product_templates:
            print(template.filename.pattern)

        # 2. Resolve date fields via ParameterCatalog
        for template in product_templates:
            update_date_params = self._params.resolve_params(template.parameters, date)
            template.parameters = update_date_params

        # 3. Narrow parameter ranges by query constraints
        product_templates_1: List[Product] = []
        for name, values in parameters.items():
            parameters[name] = _listify(values)
        parameter_combinations = expand_dict_combinations(parameters)

        for template in product_templates:
            print(f"Template: {template.filename.pattern}")
            for combo in parameter_combinations:
                print(f"Combo: {combo}")
                updated = template.model_copy(deep=True)
                for k, v in combo.items():
                    param_index = next((i for i, p in enumerate(updated.parameters) if p.name == k), None)
                    if param_index is not None:
                        updated.parameters[param_index].value = v
                if updated.filename is not None:
                    updated.filename.derive(updated.parameters)
                    print(updated.filename.pattern)
                product_templates_1.append(updated)

        print("\nTEST 2: product templates after narrowing parameter ranges by query constraints:")
        for template in product_templates_1:
            print(template.filename.pattern)

        # 5.1 Local resources
        for template in product_templates_1:
            to_update = template.model_copy(deep=True)
            resolution: Tuple[Server, ProductPath] = self._local.resolve_product(to_update, date)
            server, directory = resolution
            directory.pattern = self._params.resolve(directory.pattern, date, computed_only=True)
            rq = ResourceQuery(
                product=to_update,
                server=server,
                directory=directory,
            )
            out.append(rq)

        print("\nTEST 3: final ResourceQuery objects with resolved directories and file patterns:")
        for rq in out:
            print(f"Server: {rq.server.hostname}, Directory: {rq.directory}, File Pattern: {rq.product.filename.pattern}")

        # 5.2 Remote resources
        for template in product_templates_1:
            to_update = template.model_copy(deep=True)
            for center_id in self._remote.centers:
                if remote_resources and center_id.upper() in remote_resources:
                    continue

                to_update = template.model_copy(deep=True)
                resolution_rq: Optional[ResourceQuery] = self._remote.resolve_product(to_update, center_id)
                if resolution_rq is None:
                    print(f"Warning: Product {to_update.name!r} did not match any pinned queries for resource {center_id!r}. Skipping.")
                    continue

                resolution_rq.directory = self._params.resolve(resolution_rq.directory.pattern, date, computed_only=True)
                out.append(resolution_rq)

        print("\nTEST 4: final ResourceQuery objects including remote resources:")
        for rq in out:
            print(f"Server: {rq.server.hostname}, Directory: {rq.directory}, File Pattern: {rq.product.filename.pattern}")

        # 6. Replace unresolved placeholders with regex patterns
        for rq in out:
            for param in rq.product.parameters:
                if param.value is None:
                    param.value = param.pattern
            if rq.product.filename is not None:
                rq.product.filename.derive(rq.product.parameters)

        print("\nTEST 5: final ResourceQuery objects with all placeholders resolved to regex patterns:")
        for rq in out:
            print(f"Server: {rq.server.hostname}, Directory: {rq.directory}, File Pattern: {rq.product.filename.pattern}")
        return out
