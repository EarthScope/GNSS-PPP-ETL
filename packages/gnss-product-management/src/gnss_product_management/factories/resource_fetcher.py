"""Author: Franklyn Dunbar

ResourceFetcher — backward-compatible wrapper around RemoteTransport.

.. deprecated::
    Import :class:`RemoteTransport` from
    ``gnss_product_management.factories.remote_transport`` instead.

This module also provides a :class:`FetchResult` shim so that existing
code that iterates ``fetcher.search()`` results via ``r.found``,
``r.matched_filenames``, ``r.query``, and ``r.error`` continues to work.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from gnss_product_management.factories.remote_transport import RemoteTransport
from gnss_product_management.specifications.remote.resource import SearchTarget
from gnss_product_management.factories.local_search_planner import LocalSearchPlanner

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Shim that wraps a :class:`SearchTarget` with the old FetchResult API.

    Provides ``found``, ``matched_filenames``, ``query``, and ``error``
    attributes for backward compatibility with code written against the
    old ``ResourceFetcher.search()`` return type.
    """

    query: SearchTarget
    matched_filenames: List[str] = field(default_factory=list)
    error: Optional[str] = None
    download_dest: Optional[Path] = None

    @property
    def found(self) -> bool:
        """``True`` if at least one filename matched the query pattern."""
        return len(self.matched_filenames) > 0

    @property
    def downloaded(self) -> bool:
        """``True`` if the file was successfully downloaded to *download_dest*."""
        return self.download_dest is not None and self.download_dest.exists()


class ResourceFetcher(RemoteTransport):
    """Backward-compatible subclass of :class:`RemoteTransport`.

    ``search()`` is overridden to return ``List[FetchResult]`` so that
    existing call sites continue to work without modification.
    """

    def search(self, queries: List[SearchTarget]) -> List[FetchResult]:  # type: ignore[override]
        """Search every query's server/directory for matching files.

        Returns a list of :class:`FetchResult` objects for backward
        compatibility.  Each result groups all matched filenames for a
        single query directory into one ``FetchResult``.

        Args:
            queries: SearchTarget objects to search.

        Returns:
            A list of :class:`FetchResult` per unique (query, directory).
        """
        from collections import defaultdict

        # Use the parent implementation which returns List[SearchTarget]
        expanded: List[SearchTarget] = super().search(queries)

        # Group expanded targets back into FetchResult objects keyed by the
        # original (server, directory, filename_pattern) so existing code that
        # accesses r.matched_filenames still works as expected.
        _key_map: dict = defaultdict(lambda: None)
        result_map: dict = {}

        for st in expanded:
            if st.product.filename is None or st.product.filename.value is None:
                continue
            dir_val = st.directory.value or st.directory.pattern
            pat = st.product.filename.pattern if st.product.filename else ""
            key = (st.server.hostname, dir_val, pat)
            if key not in result_map:
                result_map[key] = FetchResult(
                    query=st,
                    matched_filenames=[],
                )
            result_map[key].matched_filenames.append(st.product.filename.value)

        # Also include queries that had no matches (so callers see r.error)
        # by rebuilding from the original queries list.
        found_keys = set(result_map.keys())
        for q in queries:
            dir_val = q.directory.value or q.directory.pattern
            pat = q.product.filename.pattern if q.product.filename else ""
            key = (q.server.hostname, dir_val, pat)
            if key not in found_keys:
                result_map[key] = FetchResult(
                    query=q,
                    matched_filenames=[],
                    error="No matches found",
                )

        return list(result_map.values())

    def download_one(
        self,
        query: SearchTarget,
        local_resource_id: str,
        local_factory: LocalSearchPlanner,
        date: datetime.datetime,
    ) -> Optional[Path]:
        """Synchronously download matched files for one query.

        Delegates to :meth:`RemoteTransport.download_one`.

        Args:
            query: The resolved query with filename value.
            local_resource_id: Target local resource identifier.
            local_factory: Factory for resolving local sink paths.
            date: Target date for computing sink directory.

        Returns:
            Path to the downloaded file, or ``None`` on failure.
        """
        return super().download_one(
            query=query,
            local_resource_id=local_resource_id,
            local_factory=local_factory,
            date=date,
        )


__all__ = ["ResourceFetcher", "FetchResult", "RemoteTransport"]
