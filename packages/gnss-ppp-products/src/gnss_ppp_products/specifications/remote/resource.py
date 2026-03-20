"""Server, ResourceSpec, ResourceQuery, ResourceCatalog — remote resource models."""

from itertools import product as iterproduct
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from gnss_ppp_products.specifications.parameters.parameter import Parameter
from gnss_ppp_products.specifications.products.product import Product, ProductPath
from gnss_ppp_products.utilities.helpers import _PassthroughDict


class Server(BaseModel):
    """A remote or local server endpoint."""
    id: str
    hostname: str
    protocol: Optional[str] = None
    auth_required: Optional[bool] = False
    description: Optional[str] = None


class ResourceProductSpec(BaseModel):
    """A product offering within a resource/center — maps a catalog product to a server with parameter overrides."""
    id: str
    server_id: str
    available: bool = True
    product_name: str
    product_version: Optional[List[str] | str] = None
    description: Optional[str] = None
    parameters: List[Parameter]
    directory: ProductPath


class ResourceSpec(BaseModel):
    """Root resource specification for a data center."""
    id: str
    name: str
    description: Optional[str] = None
    website: Optional[str] = None
    servers: List[Server] = []
    products: List[ResourceProductSpec] = []


class ResourceQuery(BaseModel):
    """A single concrete query target — one combination of parameter values."""

    product: Product
    server: Server
    directory: ProductPath
    needed_parameters: List[Parameter] = []

    def resolve(self) -> 'ResourceQuery':
        to_keep = [p for p in self.product.parameters if p.value is None]
        to_update = {p.name: p for p in self.product.parameters if p.value is not None}
        format_dict = _PassthroughDict({k: p.value for k, p in to_update.items()})

        if self.product.filename:
            self.product = self.product.model_copy(deep=True, update={
                "filename": ProductPath(pattern=self.product.filename.pattern.format_map(format_dict))
            })
        self.directory = ProductPath(pattern=self.directory.pattern.format_map(format_dict))
        self.needed_parameters = to_keep
        return self


def _cartesian_product(
    param_groups: dict[str, list[Parameter]],
) -> list[list[Parameter]]:
    """Expand {name: [vals...]} into list of combinations, one Parameter per name."""
    names = list(param_groups.keys())
    if not names:
        return [[]]
    value_lists = [param_groups[n] for n in names]
    return [list(combo) for combo in iterproduct(*value_lists)]


def _merge_parameters(
    base_params: List[Parameter],
    overrides: List[Parameter],
) -> List[Parameter]:
    """Return base params with overrides applied (by name)."""
    result = {p.name: p.model_copy(deep=True) for p in base_params}
    for override in overrides:
        if override.name in result:
            result[override.name] = result[override.name].model_copy(
                update=override.model_dump(exclude_none=True), deep=True
            )
        else:
            result[override.name] = override.model_copy(deep=True)
    return list(result.values())


class ResourceCatalog(BaseModel):
    """Resolves a ResourceSpec against a ProductCatalog into queryable products."""

    id: str
    name: str
    description: Optional[str] = None
    website: Optional[str] = None
    servers: List[Server]
    queries: List[ResourceQuery]

    def __init__(self, resource_spec: ResourceSpec, product_catalog):
        queries = []
        for rp_spec in resource_spec.products:
            if not rp_spec.available:
                continue

            version_catalog = product_catalog.products.get(rp_spec.product_name)
            if version_catalog is None:
                continue

            versions = rp_spec.product_version or list(version_catalog.versions.keys())
            if isinstance(versions, str):
                versions = [versions]

            param_groups: dict[str, list[Parameter]] = {}
            for p in rp_spec.parameters:
                param_groups.setdefault(p.name, []).append(p)

            combos = _cartesian_product(param_groups)

            server = next(s for s in resource_spec.servers if s.id == rp_spec.server_id)

            for ver_key in versions:
                variant_catalog = version_catalog.versions.get(ver_key)
                if variant_catalog is None:
                    continue
                for variant_name, base_product in variant_catalog.variants.items():
                    for combo in combos:
                        merged_params = _merge_parameters(
                            base_product.parameters, combo
                        )
                        pinned_product = base_product.model_copy(
                            update={"parameters": merged_params, "name": rp_spec.product_name},
                            deep=True,
                        )
                        queries.append(
                            ResourceQuery(
                                product=pinned_product,
                                server=server,
                                directory=rp_spec.directory,
                            ).resolve()
                        )

        super().__init__(
            id=resource_spec.id,
            name=resource_spec.name,
            description=resource_spec.description,
            website=resource_spec.website,
            servers=resource_spec.servers,
            queries=queries,
        )
