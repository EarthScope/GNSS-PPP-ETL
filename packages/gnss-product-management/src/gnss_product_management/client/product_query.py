"""Author: Franklyn Dunbar

ProductQuery — fluent builder for GNSS product search and download.
"""

from __future__ import annotations
import copy
import datetime
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from gnss_product_management.client.search_result import SearchResult
from gnss_product_management.factories.search_planner import SearchPlanner
from gnss_product_management.factories.remote_transport import WormHole
from gnss_product_management.factories.ranking import (
    sort_by_preferences,
    sort_by_protocol,
)
from gnss_product_management.specifications.dependencies.dependencies import (
    SearchPreference,
)

logger = logging.getLogger(__name__)


class ProductQuery:
    """Fluent builder for constructing and executing a GNSS product search.

    Constructed via :meth:`GNSSClient.query` — do not instantiate directly.

    Chain method calls to build the query, then call :meth:`search` or
    :meth:`download` to execute::

        results = (
            client.query("ORBIT")
            .on(date)
            .where(TTT="FIN")
            .sources("COD", "ESA")
            .prefer(TTT=["FIN", "RAP", "ULT"])
            .search()
        )

        paths = (
            client.query("CLOCK")
            .on(date)
            .where(TTT="FIN")
            .sources("local", "COD")
            .download(sink_id="local")
        )

    Args:
        fetcher: :class:`WormHole` used for directory listing and
            file download.
        query_factory: :class:`SearchPlanner` used to build
            :class:`SearchTarget` objects from product specs.
        product: Product name (e.g. ``"ORBIT"``) or dict with ``name``,
            and optionally ``version`` / ``variant``.
    """

    def __init__(
        self,
        wormhole: WormHole,
        search_planner: SearchPlanner,
    ) -> None:
        self._wormhole = wormhole
        self._search_planner = search_planner
        self._product: Optional[dict] = None
        self._date: Optional[datetime.datetime] = None
        self._parameters: dict = {}
        self._source_ids: Optional[tuple] = None  # None = all sources
        self._preferences: List[SearchPreference] = []

    def for_product(self, product: Union[str, dict]) -> "ProductQuery":
        """Set the target product for the query.

        Args:
            product: Product name (e.g. ``"ORBIT"``) or dict with ``name``,
                and optionally ``version`` / ``variant``.

        Returns:
            ``self`` for chaining.
        """
        clone = copy.copy(self)
        clone._product = {"name": product} if isinstance(product, str) else product
        return clone

    def on(self, date: datetime.datetime) -> "ProductQuery":
        """Set the target date for the query.

        Args:
            date: Timezone-aware datetime.

        Returns:
            ``self`` for chaining.
        """
        clone = copy.copy(self)
        clone._date = date
        return clone

    def where(self, **parameters) -> "ProductQuery":
        """Constrain product parameters.

        Keyword arguments map parameter names to required values, e.g.
        ``where(TTT="FIN")`` or ``where(TTT=["FIN", "RAP"])``.

        Args:
            **parameters: Parameter name → value (or list of values).

        Returns:
            ``self`` for chaining.
        """
        clone = copy.copy(self)
        clone._parameters.update(parameters)
        return clone

    def sources(self, *ids: str) -> "ProductQuery":
        """Restrict the search to specific local or remote sources.

        Pass any mix of registered local aliases and remote center IDs.
        Each ID is resolved at :meth:`search` time — local aliases are
        routed to local disk, everything else is treated as a remote
        center ID.

        Calling :meth:`sources` with no arguments is an error; omit the
        call entirely to search all available sources.

        Args:
            *ids: One or more source identifiers.

        Returns:
            ``self`` for chaining.

        Raises:
            ValueError: If no IDs are provided.
        """
        if not ids:
            raise ValueError(
                "sources() requires at least one resource ID. "
                "Omit the call entirely to search all sources."
            )
        clone = copy.copy(self)
        clone._source_ids = ids
        return clone

    def prefer(self, **kwargs) -> "ProductQuery":
        """Define a preference cascade for ranking results.

        Keyword arguments map parameter names to an ordered list of
        preferred values.  The first entry is most preferred::

            .prefer(TTT=["FIN", "RAP", "ULT"])

        Multiple calls accumulate preferences in call order.

        Args:
            **kwargs: Parameter name → ordered list of preferred values.

        Returns:
            ``self`` for chaining.
        """
        clone = copy.copy(self)
        for param, sorting in kwargs.items():
            if isinstance(sorting, str):
                sorting = [sorting]
            clone._preferences.append(
                SearchPreference(parameter=param, sorting=list(sorting))
            )
        return clone

    def search(self) -> List[SearchResult]:
        """Execute the query and return ranked results.

        Returns:
            Ranked list of :class:`SearchResult` objects, best first.
            Local/file results precede remote ones; within each protocol
            tier results are ordered by *preferences*.

        Raises:
            ValueError: If :meth:`on` has not been called.
        """
        if self._product is None:
            raise ValueError("Call .for_product(product) before .search()")

        if self._date is None:
            raise ValueError("Call .on(date) before .search()")

        logger.debug(
            "Executing search for product=%s on date=%s with parameters=%s, sources=%s, preferences=%s",
            self._product,
            self._date,
            self._parameters,
            self._source_ids,
            self._preferences,
        )
        logger.debug("Using search planner: %s", self._search_planner)
        logger.debug("Using wormhole: %s", self._wormhole)
        local_ids, remote_ids = self._resolve_sources()

        queries = self._search_planner.get(
            date=self._date,
            product=self._product,
            parameters=self._parameters or None,
            local_resources=local_ids,
            remote_resources=remote_ids,
        )

        expanded = self._wormhole.search(queries)
        if self._preferences:
            expanded = sort_by_preferences(expanded, self._preferences)
        ranked = sort_by_protocol(expanded)

        results: List[SearchResult] = []
        seen: Dict[Tuple[str, str], bool] = {}
        for rq in ranked:
            hostname = rq.server.hostname
            filename: str = (
                (rq.product.filename.value or "") if rq.product.filename else ""
            )  # type: ignore[union-attr]
            key: Tuple[str, str] = (hostname, filename)
            if key in seen:
                continue
            seen[key] = True
            params = {
                p.name: p.value for p in rq.product.parameters if p.value is not None
            }
            r = SearchResult(
                hostname=hostname,
                protocol=rq.server.protocol or "",
                directory=rq.directory.value or rq.directory.pattern,  # type: ignore[union-attr]
                filename=filename,
                parameters=params,
            )
            r._query = rq
            results.append(r)

        return results

    def download(
        self,
        sink_id: str,
        *,
        limit: Optional[int] = None,
    ) -> List[Path]:
        """Search and download results in one call.

        Args:
            sink_id: Local resource alias to download into (e.g. ``"local"``).
            limit: Maximum number of files to download.  ``None`` downloads
                all results (use with care).

        Returns:
            Paths to successfully downloaded files.

        Raises:
            ValueError: If :meth:`on` has not been called.
        """
        if self._date is None:
            raise ValueError("Call .on(date) before .download()")

        results = self.search()
        if limit is not None:
            results = results[:limit]

        paths: List[Path] = []
        for r in results:
            if r._query is None:
                logger.warning("SearchResult has no internal query; skipping.")
                continue
            path = self._wormhole.download_one(
                query=r._query,
                local_resource_id=sink_id,
                local_factory=self._search_planner._workspace,
                date=self._date,
            )
            if path is not None:
                r.local_path = path
                paths.append(path)
        return paths

    # -- Internal --------------------------------------------------

    def _resolve_sources(self) -> Tuple[Optional[List[str]], Optional[List[str]]]:
        """Split source IDs into (local_ids, remote_ids) for SearchPlanner.

        Returns:
            A ``(local_ids, remote_ids)`` tuple, each ``None`` when empty
            (meaning "all of that type").
        """
        if self._source_ids is None:
            return None, None

        local_ids: List[str] = []
        remote_ids: List[str] = []

        for sid in self._source_ids:
            try:
                self._search_planner._workspace._get_registered_spec(sid)
                local_ids.append(sid)
            except KeyError:
                remote_ids.append(sid)

        return local_ids or None, remote_ids or None
