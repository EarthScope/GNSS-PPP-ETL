"""FindPipeline — query, search, and rank product resources."""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Union

from gnss_ppp_products.factories.local_factory import LocalResourceFactory
from gnss_ppp_products.factories.models import FoundResource
from gnss_ppp_products.factories.query_factory import QueryFactory
from gnss_ppp_products.factories.resource_fetcher import FetchResult
from gnss_ppp_products.specifications.dependencies.dependencies import SearchPreference
from gnss_ppp_products.specifications.products.product import infer_from_regex
from gnss_ppp_products.specifications.remote.resource import ResourceQuery

if TYPE_CHECKING:
    from gnss_ppp_products.factories.environment import ProductEnvironment

logger = logging.getLogger(__name__)


def _get_param_value(rq: ResourceQuery, param_name: str) -> str:
    """Extract a parameter value from a ResourceQuery's product."""
    for p in rq.product.parameters:
        if p.name == param_name and p.value is not None:
            return p.value
    return ""


def _build_remote_url(rq: ResourceQuery) -> str:
    """Construct a full remote URL from a ResourceQuery."""
    protocol = (rq.server.protocol or "").lower()
    hostname = rq.server.hostname
    directory = rq.directory.value or rq.directory.pattern
    filename = ""
    if rq.product.filename:
        filename = rq.product.filename.value or rq.product.filename.pattern
    sep = "" if directory.startswith("/") else "/"
    trail = "" if directory.endswith("/") else "/"
    hostname = hostname.split("//")[-1]  # Remove any existing protocol prefix
    return f"{protocol}://{hostname}{sep}{directory}{trail}{filename}"


class FindPipeline:
    """Query, search, and rank product resources.

    Builds queries via ``QueryFactory``, searches via the environment's
    ``ResourceFetcher``, and ranks results by a preference cascade.

    Parameters
    ----------
    env
        A constructed ``ProductEnvironment`` providing catalogs, factories,
        and the shared resource fetcher.

    Example
    -------
    ::

        find = FindPipeline(env)
        best = find.run(date=dt, product="ORBIT")
        all_results = find.run(date=dt, product="ORBIT", all=True)
    """

    def __init__(self, env: ProductEnvironment) -> None:
        self._env = env
        # Build a QueryFactory from the environment's state.
        # If no local factory exists, create an empty one so QF
        # can still function (it will simply produce no local queries).
        local = env.local_factory
        if local is None:
            local = LocalResourceFactory(
                product_catalog=env.product_catalog,
                parameter_catalog=env.parameter_catalog,
            )
        self._qf = QueryFactory(
            remote_factory=env.remote_factory,
            local_factory=local,
            product_catalog=env.product_catalog,
            parameter_catalog=env.parameter_catalog,
        )

    def run(
        self,
        date: datetime.datetime,
        product: str,
        *,
        centers: Optional[List[str]] = None,
        filters: Optional[dict[str, str]] = None,
        preferences: Optional[List[SearchPreference]] = None,
        all: bool = False,
    ) -> Union[FoundResource, List[FoundResource]]:
        """Find product resources for a given date.

        Parameters
        ----------
        date
            Target date (timezone-aware datetime).
        product
            Product name (e.g. ``"ORBIT"``, ``"CLOCK"``).
        centers
            Optional subset of center identifiers to search.
            ``None`` means all registered centers.
        filters
            Parameter constraints applied at query level
            (e.g. ``{"TTT": "FIN", "SMP": "05M"}``).
        preferences
            Explicit preference cascade for ranking results.
            ``None`` uses default ordering from search results.
        all
            If ``True``, return all found resources ranked by preference.
            If ``False`` (default), return the single best match.

        Returns
        -------
        FoundResource or list[FoundResource]

        Raises
        ------
        ValueError
            If no resources are found and ``all`` is ``False``.
        """
        # 1. Build queries
        queries = self._qf.get(
            date,
            product={"name": product},
            parameters=filters,
            remote_resources=[c.upper() for c in centers] if centers else None,
        )

        if not queries:
            if all:
                return []
            raise ValueError(f"No queries generated for product {product!r}")

        # 2. Search via the environment's shared fetcher
        fetch_results: List[FetchResult] = self._env.resource_fetcher.search(queries)

        # 3. Expand matched filenames into individual ResourceQuery objects
        expanded: List[ResourceQuery] = []
        for fr in fetch_results:
            if fr.error or not fr.matched_filenames:
                continue
            for filename in fr.matched_filenames:
                rq = fr.query.model_copy(deep=True)
                if rq.product.filename is not None:
                    rq.product.filename.value = filename
                expanded.append(rq)

        # 4. Infer parameter values from filenames
        for rq in expanded:
            if (
                rq.product.filename is not None
                and rq.product.filename.pattern
                and rq.product.filename.value
            ):
                updated = infer_from_regex(
                    regex=rq.product.filename.pattern,
                    filename=rq.product.filename.value,
                    parameters=rq.product.parameters,
                )
                if updated:
                    rq.product.parameters = updated

        # 5. Apply preference sorting
        if preferences:
            expanded = self._apply_preferences(expanded, preferences)

        # 6. Convert to FoundResource models
        found: List[FoundResource] = []
        for rq in expanded:
            protocol = (rq.server.protocol or "").upper()
            is_local = protocol in ("FILE", "LOCAL", "")

            if is_local:
                directory = Path(rq.server.hostname) / (
                    rq.directory.value or rq.directory.pattern
                )
                fname = (
                    rq.product.filename.value
                    if rq.product.filename is not None
                    else ""
                )
                uri = str(directory / fname)
            else:
                uri = _build_remote_url(rq)

            params = {
                p.name: p.value
                for p in rq.product.parameters
                if p.value is not None
            }

            resource = FoundResource(
                product=product,
                source="local" if is_local else "remote",
                uri=uri,
                center=_get_param_value(rq, "AAA"),
                quality=_get_param_value(rq, "TTT"),
                parameters=params,
            )
            resource._query = rq  # Store for DownloadPipeline
            found.append(resource)

        if not found:
            if all:
                return []
            raise ValueError(f"No resources found for product {product!r}")

        if all:
            return found
        return found[0]

    @staticmethod
    def _apply_preferences(
        queries: List[ResourceQuery],
        preferences: List[SearchPreference],
    ) -> List[ResourceQuery]:
        """Sort queries according to a preference cascade.

        Preferences are applied in reverse order so that the first
        preference in the list is the primary sort key.
        """
        for pref in reversed(preferences):
            param_name = pref.parameter
            sorting = [v.upper() for v in pref.sorting]

            def _key(rq: ResourceQuery, _pn=param_name, _s=sorting) -> int:
                val = _get_param_value(rq, _pn).upper()
                try:
                    return _s.index(val)
                except ValueError:
                    return len(_s)

            queries = sorted(queries, key=_key)

        return queries
