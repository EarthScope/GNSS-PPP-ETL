"""Author: Franklyn Dunbar

SearchPlanner — lazy narrowing query builder.
"""

import datetime
import logging
from typing import Dict, List, Optional

from gnss_product_management.environments import ProductRegistry
from gnss_product_management.factories.local_search_planner import LocalSearchPlanner
from gnss_product_management.environments import WorkSpace
from gnss_product_management.specifications.products.product import (
    Product,
    PathTemplate,
    VariantCatalog,
    VersionCatalog,
)
from gnss_product_management.specifications.remote.resource import SearchTarget
from gnss_product_management.utilities.helpers import _listify, expand_dict_combinations

logger = logging.getLogger(__name__)


class SearchPlanner:
    """Lazy search planner — narrows parameter ranges, resolves on demand.

    Uses ``RemoteSearchPlanner`` for remote registration,
    ``ProductCatalog`` (nested version→variant→Product hierarchy),
    and ``ParameterCatalog`` for fallback regex patterns and computed
    date-field resolution.

    Attributes:
        _env: The product registry backing this planner.
        _workspace: Workspace with registered local resources.

    Usage::

        sp = SearchPlanner(
            product_registry=registry,
            workspace=workspace,
        )

        results = sp.get(
            datetime.date(2024, 1, 1),
            product={"name": "ORBIT"},
            parameters={"AAA": ["WUM", "COD"]},
        )
    """

    def __init__(
        self,
        product_registry: ProductRegistry,
        workspace: WorkSpace,
    ):
        """Initialise the search planner.

        Args:
            product_registry: Built :class:`ProductRegistry` with
                catalogs and remote planner ready.
            workspace: :class:`WorkSpace` with registered local resources.
        """
        self._env = product_registry
        self._workspace = workspace
        self._remote = self._env._remote_resource_factory
        self._products = self._env._product_catalog
        self._params = self._env._parameter_catalog
        self._local = LocalSearchPlanner(
            workspace=self._workspace,
            product_registry=self._env,
        )

    def get(
        self,
        date: datetime.datetime,
        product: Dict[str, str | list[str]],
        parameters: Optional[Dict[str, str | list[str]]] = None,
        local_resources: Optional[List[str]] = None,
        remote_resources: Optional[List[str]] = None,
    ) -> list[SearchTarget]:
        """Narrow parameter ranges and return searchable resources.

        Args:
            date: Target date for computed metadata fields.
            product: Product query dict with ``name``, optionally
                ``version`` and ``variant``.
            parameters: User constraints on metadata fields.  Unset
                fields remain as wildcard regex patterns.
            local_resources: If given, restrict to these local collection IDs.
            remote_resources: If given, restrict to these remote center IDs.

        Returns:
            A list of :class:`SearchTarget` objects.

        Raises:
            ValueError: If the product, version, or variant is not found.
        """
        parameters = parameters or {}
        local_resources = _listify(local_resources)
        remote_resources = _listify(remote_resources)
        out: List[SearchTarget] = []

        # 1. Get product templates matching the query product spec
        product_templates: List[Product] = []

        product_name_query = product.get("name")
        product_version_query = _listify(product.get("version"))
        product_variant_query = _listify(product.get("variant"))

        product_version_catalog: Optional[VersionCatalog] = self._products.products.get(
            product_name_query
        )
        if product_version_catalog is None:
            raise ValueError(
                f"Product {product_name_query!r} not found in ProductCatalog"
            )
        versions = product_version_query or list(
            product_version_catalog.versions.keys()
        )
        for version in versions:
            variant_cat: Optional[VariantCatalog] = (
                product_version_catalog.versions.get(version)
            )
            if variant_cat is None:
                raise ValueError(
                    f"Version {version!r} not found for product {product_name_query!r}"
                )
            variants = product_variant_query or list(variant_cat.variants.keys())
            for variant in variants:
                if variant not in variant_cat.variants:
                    raise ValueError(
                        f"Variant {variant!r} not found for product {product_name_query!r} version {version!r}"
                    )
                product_templates.append(variant_cat.variants[variant])

        # 2. Resolve date fields via ParameterCatalog
        for template in product_templates:
            update_date_params = self._params.resolve_params(template.parameters, date)
            template.parameters = update_date_params

        # 3. Narrow parameter ranges by query constraints
        product_templates_1: List[Product] = []
        for name, values in parameters.items():
            parameters[name] = _listify(values)
        parameter_combinations = expand_dict_combinations(parameters)

        if parameters:
            parameter_combinations = expand_dict_combinations(parameters)
            for template in product_templates:
                for combo in parameter_combinations:
                    updated = template.model_copy(deep=True)
                    for k, v in combo.items():
                        param_index = next(
                            (
                                i
                                for i, p in enumerate(updated.parameters)
                                if p.name == k
                            ),
                            None,
                        )
                        if param_index is not None:
                            updated.parameters[param_index].value = v
                    if updated.filename is not None:
                        updated.filename.derive(updated.parameters)
                    product_templates_1.append(updated)
        else:
            product_templates_1 = product_templates
        # 5.1 Local resources
        for template in product_templates_1:
            for resource_id in self._local.resource_ids:
                if local_resources and resource_id not in local_resources:
                    continue
                to_update = template.model_copy(deep=True)
                try:
                    resolved_queries: List[SearchTarget] = self._local.source_product(
                        to_update, resource_id
                    )
                except KeyError:
                    continue
                for rq in resolved_queries:
                    resolved_dir: str = self._params.interpolate(
                        rq.directory.pattern, date, computed_only=True
                    )
                    rq.directory = PathTemplate(pattern=resolved_dir)
                    out.append(rq)

        # 5.2 Remote resources
        for template in product_templates_1:
            for center_id in self._remote.resource_ids:
                if remote_resources and center_id.upper() in remote_resources:
                    continue

                to_update = template.model_copy(deep=True)
                try:
                    resolved_queries: List[SearchTarget] = self._remote.source_product(
                        to_update, center_id
                    )
                except KeyError:
                    continue
                for resolution_rq in resolved_queries:
                    resolved_dir = self._params.interpolate(
                        resolution_rq.directory.pattern, date, computed_only=True
                    )
                    resolution_rq.directory = PathTemplate(pattern=resolved_dir)
                    out.append(resolution_rq)

        # 6. Replace unresolved placeholders with regex patterns
        for rq in out:
            for param in rq.product.parameters:
                if param.value is None:
                    param.value = param.pattern
            if rq.product.filename is not None:
                rq.product.filename.derive(rq.product.parameters)

        return out
