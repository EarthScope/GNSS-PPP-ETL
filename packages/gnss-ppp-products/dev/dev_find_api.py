'''
Lazy narrowing query factory for GNSS product discovery.

Uses class definitions from dev_parameter_spec_claude.py:
  - ParameterCatalog / Parameter  (static parameter definitions + fallback regex)
  - ProductCatalog / Product      (nested version→variant→Product hierarchy)
  - RemoteResourceFactory         (registration interface; raw ResourceSpec stored via ._specs)
  - LocalResourceFactory          (collections-based local storage)
  - MetadataCatalog               (computed date-field resolution only)

Design:
  - NO pre-materialization of parameter combinations
  - Parameter ranges are narrowed (intersected), not cartesian-expanded
  - Templates resolved only at get() time via three-pass substitution:
        1. Date-computed fields  (YYYY, DDD, GPSWEEK …)  — via MetadataCatalog
        2. Narrowed metadata     (single → literal, multi → regex alternation)
        3. Default regex patterns (from ParameterCatalog)
  - Multi-valued metadata in directory templates expanded only when
    necessary (directories must be exact paths for listing)
'''

import datetime
import enum
import itertools
from math import prod
from pathlib import Path
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from gnss_ppp_products.server.ftp import ftp_list_directory
from gnss_ppp_products.specifications.local.local import LocalResourceSpec
from gnss_ppp_products.specifications.metadata.metadata_catalog import MetadataCatalog
from gnss_ppp_products.server.http import http_list_directory, extract_filenames_from_html

import sys
sys.path.append(str(Path(__file__).parent.parent))
from dev_parameter_spec_claude import (
    LOCAL_CONFIG_PATH,
    FormatCatalog,
    FormatSpecCatalog,
    ParameterCatalog,
    Parameter,
    Product,
    ProductCatalog,
    ProductPath,
    ProductSpecCatalog,
    ResourceProductSpec,
    ResourceSpec,
    ResourceSpec,
    Server,
    RemoteResourceFactory,
    LocalResourceFactory,
    QueryProfile,
    ResourceQuery,
    VariantCatalog,
    VersionCatalog,
    _build_metadata_catalog,
)

from dev_specs import (
    parameter_spec_dict,
    format_spec_dict,
    product_spec_dict,
    wuhan_resource_spec_dict,
    igs_resource_spec_dict,
    code_resource_spec_dict,
    local_resource_spec_dict,
)

from itertools import product


# ─── QueryFactory ────────────────────────────────────────────────
def _listify(v) -> list[str]:
    if v is None:
        return []
    return [v] if isinstance(v, str) else list(v)


def expand_dict_combinations(d: dict[str, list[str]]) -> list[dict[str, str]]:
    """Cartesian product of dict values.

    >>> expand_dict_combinations({"A": ["1","2"], "B": ["x","y"]})
    [{"A":"1","B":"x"}, {"A":"1","B":"y"}, {"A":"2","B":"x"}, {"A":"2","B":"y"}]
    """
    keys = list(d.keys())
    vals = [d[k] for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*vals)]


class QueryFactory:
    """Lazy query factory — narrows parameter ranges, resolves on demand.

    Accepts the type system from ``dev_parameter_spec_claude.py``:
    ``RemoteResourceFactory`` for registration ergonomics,
    ``ProductCatalog`` (nested version→variant→Product hierarchy),
    ``ParameterCatalog`` for fallback regex patterns,
    and ``MetadataCatalog`` for computed date-field resolution.

    Usage::

        qf = QueryFactory(
            remote_factory=remote,
            local_factory=local,
            meta_catalog=METADATA_CATALOG,
            product_catalog=PRODUCT_CATALOG,
            parameter_catalog=PARAMETER_CATALOG,
        )

        results = qf.get(
            datetime.date(2024, 1, 1),
            spec="ORBIT",
            center="WUM",
            solution=["FIN", "RAP"],
        )

        for r in results:
            print(r.uri, r.file_pattern)
    """

    def __init__(
        self,
        remote_factory: RemoteResourceFactory,
        local_factory: LocalResourceFactory,
        product_catalog: ProductCatalog,
        metadata_catalog: MetadataCatalog,
        parameter_catalog: ParameterCatalog,
    ):
        self._remote = remote_factory
        self._local = local_factory
        self._products = product_catalog
        self._metadata = metadata_catalog
        self._params = parameter_catalog

    def get(
        self,
        date: datetime.datetime,
        product: Dict[str, str | list[str]],
        parameters: Dict[str, str | list[str]],
        local_resources: Optional[List[str]] = None,
        remote_resources: Optional[List[str]] = None,
    ) -> list[ResourceQuery]:
        """Narrow parameter ranges and return searchable resources.

        Parameters
        ----------
        date : datetime.datetime
            Target date for computed metadata fields (e.g. YYYY, DDD).
        product: dict
        parameters: dict[str, str | list[str]]
            User constraints on metadata fields. Keys must match parameter
        local_resources: list[str]
            If specified, only include local resources with these collection IDs.
        remote_resources: list[str]
            If specified, only include remote resources with these center IDs.

        Returns
        -------
        list[ResourceQuery]
            Each entry is one (server, directory, file_pattern) target —
            NOT a cartesian expansion.

        Examples
        --------
        >>> qf = QueryFactory(remote, local, meta, products, params)
        >>> product = {name:"ORBIT",version: ["1"]}
        >>> parameters = {"AAA":["WUM","COD"], "TTT":["FIN","RAP"]}
        >>> local_resource = ["my_local_id"]
        >>> remote_resources = ["WUM", "COD"]
        >>> results = qf.get(
        ...     datetime.date(2024, 1, 1),
        ...     product=product,
        ...     parameters=parameters,
        ...     remote_resources=remote_resources,
        ...     local_resources=local_resource,
        ... )
        """

        local_resources = _listify(local_resources)
        remote_resources = _listify(remote_resources)
        out: List[ResourceQuery] = []
        #################
        # 1. Get product templates matching the query product spec (name + optional version/variant)
        #################
        product_templates: List[Product] = []

        product_name_query = product.get("name")
        product_version_query = _listify(product.get("version"))
        product_variant_query = _listify(product.get("variant"))

        product_version_catalog:Optional[VersionCatalog] = self._products.products.get(product_name_query)
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
        #################
        # 2. Resolve the parameter file template date fields (e.g. YYYY, DDD) via the metadata catalog.
        # TODO: migrate the datefield resolution to the ProductCatalog.
        #################

        for template in product_templates:
            update_date_params = self._metadata.resolve_params(template.parameters, date)
            template.parameters = update_date_params

        #################
        # 3. Get the cartesian product of all parameter values from the query constraints and all product templates. This is the set of all possible metadata combinations that could satisfy the query.
        #################
        product_templates_1: List[Product] = []
        for name, values in parameters.items():
            parameters[name] = _listify(values)
        # Get the cartesian product of all paramter values.
        # ex: {"AAA": ["WUM","COD"], "TTT": ["FIN","RAP"]} → [{"AAA":"WUM","TTT":"FIN"},{"AAA":"WUM","TTT":"RAP"},{"AAA":"COD","TTT":"FIN"},{"AAA":"COD","TTT":"RAP"}]
        parameter_combinations = expand_dict_combinations(parameters)
        # For each product template, we will narrow the parameter ranges by intersecting with the query constraints. This will give us a narrowed set of metadata combinations that are actually relevant to the query.
        for template in product_templates:
            print(f"Template: {template.filename.pattern}")
            for combo in parameter_combinations:
                # Narrow the template's parameter ranges by intersecting with the query constraints. This will give us a narrowed set of metadata combinations that are actually relevant to the query.
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
        # #################
        # # 4. For each product template, if the value of a parameter is still None (meaning it wasn't constrained by the query), 
        # # replace it with its regex pattern. This will give us a file pattern that can be used to match files on the server.
        # #################
        # product_templates_2: List[Product] = []
        # for template in product_templates_1:
        #     updated = template.model_copy()
        #     for param in updated.parameters:
        #         if param.value is None:
        #             param.value = param.pattern
        #     product_templates_2.append(updated)

        '''
        5. For each product template, build a ResourceQuery for each local and remote resource that matches the query constraints. 
        
        This will give us a list of searchable resources with file patterns that can be used to find matching files on the server or local storage.

        5.1 For local resources:
            5.1.1
                If local_resources is specified, only include local resources with collection IDs in local_resources, otherwise include all local resources in 
                the LocalResourceFactory.
            5.1.2 
                For each included local resource, resolve the directory path using the LocalResourceFactory's resolve_directory method. 
                ex. self._local.resolve_directory(Product,resource_name=None) = (Server, directory)
            5.1.3
                Build a ResourceQuery for each local resource with the resolved directory and the ProductPath object.
        
        5.2 For remote resources:
            5.2.1
                If remote_resources is specified, only include remote resources with center IDs in remote_resources, otherwise include all remote resources in the RemoteResourceFactory.
            5.2.2
                For each included remote resource, resolve the directory path using the RemoteResourceFactory's resolve_directory method. 
                ex. self._remote.resolve_directory(Product,resource_name=None) = (Server, directory)
            5.2.3
                Build a ResourceQuery for each remote resource with the resolved directory and the ProductPath object.
        '''
        for template in product_templates_1:
            to_update = template.model_copy(deep=True)
            resolution: Tuple[Server,ProductPath] = self._local.resolve_product(to_update, date)
            server, directory = resolution
            directory.pattern = self._metadata.resolve(directory.pattern, date, computed_only=True)
            rq = ResourceQuery(
                product=to_update,
                server=server,
                directory=directory
            )
            out.append(rq)
        print("\nTEST 3: final ResourceQuery objects with resolved directories and file patterns:")
        for rq in out:
            print(f"Server: {rq.server.hostname}, Directory: {rq.directory}, File Pattern: {rq.product.filename.pattern}")
        
        # 5.2
        for template in product_templates_1:
            to_update = template.model_copy(deep=True)
            for center_id in self._remote.centers:
                if remote_resources and center_id.upper() in remote_resources:
                    continue

                to_update = template.model_copy(deep=True)
                resolution: Optional[ResourceQuery] = self._remote.resolve_product(to_update, center_id)
                if resolution is None:
                    print(f"Warning: Product {to_update.name!r} did not match any pinned queries for resource {center_id!r}. Skipping.")
                    continue
        
                # TODO: resolve in the .resolve_product() method (missing GPSWEEK)
                resolution.directory = self._metadata.resolve(resolution.directory.pattern, date, computed_only=True)
              
                out.append(resolution)

        print("\nTEST 4: final ResourceQuery objects including remote resources:")
        for rq in out:
            print(f"Server: {rq.server.hostname}, Directory: {rq.directory}, File Pattern: {rq.product.filename.pattern}")

        '''
        6. Replace any unresolved placeholders in the file patterns with their parameter default regex patterns.
        
        6.1 For each ResourceQuery, iterate over their parameters and replace missing values with the regex pattern.
        6.2 Resolve any remaining file pattern placeholders with .derive()
        
        '''

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


# ─── ResourceFetcher ─────────────────────────────────────────────

@dataclass
class FetchResult:
    """Outcome of searching one ResourceQuery against its server."""

    query: ResourceQuery
    matched_filenames: List[str] = field(default_factory=list)
    directory_listing: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def found(self) -> bool:
        return len(self.matched_filenames) > 0


class ResourceFetcher:
    """Search for files described by ResourceQuery objects.

    For each query, lists the remote (FTP/HTTP) or local directory, matches
    ``product.filename.pattern`` against the listing, and populates
    ``directory.value`` and ``filename.value`` on the query.

    Usage::

        queries = qf.get(date=..., product=..., parameters=...)
        fetcher = ResourceFetcher()
        results = fetcher.search(queries)

        for r in results:
            if r.found:
                print(r.query.server.hostname, r.matched_filenames)
    """

    def __init__(
        self,
        *,
        ftp_timeout: int = 60,
        download_timeout: int = 180,
    ) -> None:
        self._ftp_timeout = ftp_timeout
        self._download_timeout = download_timeout
        self._listing_cache: Dict[str, List[str]] = {}  # key: "protocol://host/directory"

    def search(self, queries: List[ResourceQuery]) -> List[FetchResult]:
        """Search every query's server/directory for matching files.

        For each query:
        1. Determine the directory path from ``query.directory``
        2. List the directory via the appropriate protocol
        3. Match ``query.product.filename.pattern`` against the listing
        4. Populate ``query.directory.value`` and ``query.product.filename.value``
           for the first match

        Returns a list of ``FetchResult`` — one per input query, in order.
        """
        return [self._search_one(q) for q in queries]

    def _search_one(self, query: ResourceQuery) -> FetchResult:
        """Search a single query's directory for matching files."""
        directory = self._get_directory(query)
        file_pattern = self._get_file_pattern(query)

        if not directory or not file_pattern:
            return FetchResult(
                query=query,
                error=f"Missing directory or file pattern: dir={directory!r}, pat={file_pattern!r}",
            )

        protocol = (query.server.protocol or "").upper()
        hostname = query.server.hostname

        cache_key = f"{protocol}://{hostname}/{directory}"

        if cache_key in self._listing_cache:
            listing = self._listing_cache[cache_key]
        else:
            try:
                if protocol in ("FTP", "FTPS"):
                    listing = self._list_ftp(hostname, directory, use_tls=(protocol == "FTPS"))
                elif protocol in ("HTTP", "HTTPS"):
                    listing = self._list_http(hostname, directory)
                elif protocol in ("FILE", "LOCAL", ""):
                    listing = self._list_local(directory)
                else:
                    return FetchResult(query=query, error=f"Unsupported protocol: {protocol!r}")
                if not listing:
                    raise Exception("Listing returned empty")
            except Exception as e:
                return FetchResult(query=query, error=f"Listing failed: {e}")
            # Cache non-local listings (local dirs may change between calls)
            if protocol not in ("FILE", "LOCAL", ""):
                self._listing_cache[cache_key] = listing

        matches = self._match_files(listing, file_pattern)

        # Resolve .value fields on the query for matched results
        if matches:
            self._resolve_values(query, directory, matches[0])

        return FetchResult(
            query=query,
            matched_filenames=matches,
            directory_listing=listing,
        )

    # ── Protocol handlers ────────────────────────────────────────

    def _list_ftp(self, hostname: str, directory: str, *, use_tls: bool = False) -> List[str]:
    
        return ftp_list_directory(hostname, directory, timeout=self._ftp_timeout, use_tls=use_tls)

    def _list_http(self, hostname: str, directory: str) -> List[str]:

        html = http_list_directory(hostname, directory)
        if html is None:
            return []
        return extract_filenames_from_html(html)

    def _list_local(self, directory: str) -> List[str]:
        d = Path(directory)
        if not d.exists():
            return []
        return [p.name for p in sorted(d.iterdir()) if p.is_file()]

    # ── Pattern matching ─────────────────────────────────────────

    @staticmethod
    def _match_files(listing: List[str], file_pattern: str) -> List[str]:
        """Match filenames in a directory listing against a regex pattern."""
        try:
            rx = re.compile(file_pattern, re.IGNORECASE)
            return [f for f in listing if rx.search(f)]
        except re.error:
            # Fallback to substring match if pattern is invalid regex
            return [f for f in listing if file_pattern in f]

    # ── Value resolution ─────────────────────────────────────────

    @staticmethod
    def _resolve_values(query: ResourceQuery, directory: str, matched_filename: str) -> None:
        """Populate .value on the query's directory and filename ProductPaths."""
        if isinstance(query.directory, ProductPath):
            query.directory.value = directory
        if query.product.filename is not None and isinstance(query.product.filename, ProductPath):
            query.product.filename.value = matched_filename

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _get_directory(query: ResourceQuery) -> Optional[str]:
        """Extract the resolved directory string from a query."""
        d = query.directory
        if isinstance(d, ProductPath):
            return d.value or d.pattern
        if isinstance(d, str):
            return d
        return None

    @staticmethod
    def _get_file_pattern(query: ResourceQuery) -> Optional[str]:
        """Extract the file regex pattern from a query."""
        if query.product.filename is None:
            return None
        fn = query.product.filename
        if isinstance(fn, ProductPath):
            return fn.pattern
        if isinstance(fn, str):
            return fn
        return None


if __name__ == "__main__":
    from pathlib import Path
    date = datetime.datetime(2024, 1, 1).astimezone(datetime.timezone.utc)
    base_dir = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP")
    PARAMETER_CATALOG = ParameterCatalog(parameters=[Parameter(**p) for p in parameter_spec_dict])
    FORMAT_CATALOG = FormatCatalog(
        format_spec_catalog=FormatSpecCatalog(formats=format_spec_dict),
        parameter_catalog=PARAMETER_CATALOG,
    )
    PRODUCT_CATALOG = ProductCatalog(
        product_spec_catalog=ProductSpecCatalog(products=product_spec_dict),
        format_catalog=FORMAT_CATALOG,
    )
    REMOTE_RESOURCE_FACTORY = RemoteResourceFactory(PRODUCT_CATALOG)
    REMOTE_RESOURCE_FACTORY.register(ResourceSpec(**wuhan_resource_spec_dict))
    REMOTE_RESOURCE_FACTORY.register(ResourceSpec(**igs_resource_spec_dict))
    REMOTE_RESOURCE_FACTORY.register(ResourceSpec(**code_resource_spec_dict))
    METADATA_CATALOG = _build_metadata_catalog()
    LOCAL_SPEC = LocalResourceSpec.from_yaml(str(LOCAL_CONFIG_PATH))
    local = LocalResourceFactory(LOCAL_SPEC, PRODUCT_CATALOG, METADATA_CATALOG,base_dir=base_dir)

    QF = QueryFactory(
        remote_factory=REMOTE_RESOURCE_FACTORY,
        local_factory=local,
        product_catalog=PRODUCT_CATALOG,
        metadata_catalog=METADATA_CATALOG,
        parameter_catalog=PARAMETER_CATALOG,
    )

    test = QF.get(
        date=date,
        product={"name": "ORBIT", "version": ["1"]},
        parameters={"AAA": ["WUM", "COD","IGS"], "TTT": ["FIN", "RAP"]},
        remote_resources=["WUM", "COD"],
    )

    # ── ResourceFetcher demo ─────────────────────────────────────
    print("\n" + "=" * 60)
    print("ResourceFetcher — searching for files…")
    print("=" * 60)
    fetcher = ResourceFetcher()
    fetch_results = fetcher.search(test)
    for fr in fetch_results:
        status = "FOUND" if fr.found else ("ERROR" if fr.error else "NO MATCH")
        dir_str = ResourceFetcher._get_directory(fr.query) or "?"
        print(f"\n[{status}] {fr.query.server.hostname} | {dir_str}")
        print(f"  Pattern:  {ResourceFetcher._get_file_pattern(fr.query)}")
        if fr.found:
            print(f"  Matches:  {fr.matched_filenames[:5]}")
            print(f"  dir.value = {fr.query.directory.value if isinstance(fr.query.directory, ProductPath) else fr.query.directory}")
            print(f"  fn.value  = {fr.query.product.filename.value if fr.query.product.filename else None}")
        elif fr.error:
            print(f"  Error:    {fr.error}")
