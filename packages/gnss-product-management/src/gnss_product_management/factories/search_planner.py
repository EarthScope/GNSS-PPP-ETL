"""Author: Franklyn Dunbar

SearchPlanner — lazy narrowing query builder.
"""

import datetime
import logging
from typing import Dict, List, Optional, Union

from gnss_product_management.environments import ProductRegistry
from gnss_product_management.environments import WorkSpace
from gnss_product_management.specifications.parameters.parameter import ParameterCatalog
from gnss_product_management.specifications.products.catalog import ProductCatalog
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

    Uses ``ProductRegistry`` for remote resource catalogs,
    ``WorkSpace`` for local resource resolution,
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
                catalogs and remote resource catalogs ready.
            workspace: :class:`WorkSpace` with registered local resources.
        """
        self._product_registry: ProductRegistry = product_registry
        self._workspace: WorkSpace = workspace
        self._workspace.bind(product_registry)

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

        product_version_catalog: Optional[VersionCatalog] = (
            self._product_registry._product_catalog.products.get(product_name_query)
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
                product_templates.append(
                    variant_cat.variants[variant].model_copy(deep=True)
                )

        # 2. Resolve date fields via ParameterCatalog
        for template in product_templates:
            update_date_params = (
                self._product_registry._parameter_catalog.resolve_params(
                    template.parameters, date
                )
            )
            template.parameters = update_date_params

        # 3. Narrow parameter ranges by query constraints
        product_templates_1: List[Product] = []
        for name, values in parameters.items():
            parameters[name] = _listify(values)

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
        local_out = self.build_queries_from_planner(
            templates=product_templates_1,
            date=date,
            query_planner=self._workspace,
            resource_selection=local_resources,
        )
        out.extend(local_out)

        # 5.2 Remote resources
        remote_out = self.build_queries_from_planner(
            templates=product_templates_1,
            date=date,
            query_planner=self._product_registry,
            resource_selection=remote_resources,
        )
        if not remote_out:
            logger.debug(
                "No remote search targets found for product query %s on date %s.",
                product,
                date.date(),
            )
        out.extend(remote_out)

        # 6. Replace unresolved placeholders with regex patterns
        for rq in out:
            for param in rq.product.parameters:
                if param.value is None:
                    param.value = param.pattern
            if rq.product.filename is not None:
                rq.product.filename.derive(rq.product.parameters)

        return out

    @staticmethod
    def build_queries_from_planner(
        templates: List[Product],
        date: datetime.datetime,
        query_planner: Union[WorkSpace, ProductRegistry],
        resource_selection: Optional[List[str]] = None,
    ) -> List[SearchTarget]:
        """Build search queries from a given planner and resource selection.

        Args:
            templates: List of product templates to build queries from.
            date: Target date for resolving computed directory fields.
            query_planner: A :class:`WorkSpace` (local) or
                :class:`ProductRegistry` (remote) with ``resource_ids``
                and ``source_product`` interface.
            resource_selection: Optional list of resource IDs to restrict to.

        Returns:
            A list of :class:`SearchTarget` objects built from the planner.
        """
        out = []
        for template in templates:
            for resource_id in query_planner.resource_ids:
                if resource_selection and resource_id not in resource_selection:
                    continue
                try:
                    resolved_queries: List[SearchTarget] = query_planner.source_product(
                        template, resource_id
                    )
                except KeyError as e:
                    logger.debug(
                        "KeyError resolving product %s on resource %s: %s",
                        template.name,
                        resource_id,
                        e,
                    )
                    continue
                for rq in resolved_queries:
                    resolved_dir: str = query_planner._parameter_catalog.interpolate(
                        rq.directory.pattern, date, computed_only=True
                    )
                    rq.directory = PathTemplate(pattern=resolved_dir)
                    out.append(rq)
        return out
