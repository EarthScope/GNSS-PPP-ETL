"""Author: Franklyn Dunbar

ResourceFetcher — protocol-agnostic file search and download.
"""

import datetime
import logging
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import fsspec

import fsspec.utils
from gnss_ppp_products.specifications.products.product import ProductPath
from gnss_ppp_products.specifications.remote.resource import ResourceQuery
from gnss_ppp_products.factories.local_factory import LocalResourceFactory
from gnss_ppp_products.factories.connection_pool import ConnectionPoolFactory

logger = logging.getLogger(__name__)

# Type alias for (hostname, directory) grouping key
_DirKey = Tuple[str, str]


@dataclass
class FetchResult:
    """Outcome of searching one ResourceQuery against its server."""

    query: ResourceQuery
    matched_filenames: List[str] = field(default_factory=list)
    error: Optional[str] = None
    download_dest: Optional[Path] = None

    @property
    def found(self) -> bool:
        return len(self.matched_filenames) > 0

    @property
    def downloaded(self) -> bool:
        return self.download_dest is not None and self.download_dest.exists()


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
        max_connections: int = 4,
    ) -> None:
        self._connection_pool_factory = ConnectionPoolFactory(
            max_connections=max_connections
        )

    # -- Public API ------------------------------------------------

    def search(self, queries: List[ResourceQuery]) -> List[FetchResult]:
        """Search every query's server/directory for matching files.

        Queries are grouped by ``(hostname, directory)`` so each unique
        remote directory is listed exactly once.  Pattern matching for
        every query in the group runs against the shared listing.

        Args:
            queries: ResourceQuery objects to search.

        Returns:
            A list of :class:`FetchResult` per query.
        """
        groups, rejected = self._group_queries(queries)

        # Ensure connection pools exist for every hostname we'll contact.
        for hostname, _ in groups:
            self._connection_pool_factory.add_connection(hostname)

        # List each unique directory in parallel.
        dir_keys = list(groups.keys())
        with ThreadPoolExecutor(max_workers=min(len(dir_keys), 25)) as pool:
            listings = dict(zip(dir_keys, pool.map(self._list_dir, dir_keys)))

        # Match every query's file pattern against the pre-fetched listing.
        results: List[FetchResult] = list(rejected)
        for key, group_queries in groups.items():
            listing = listings[key]
            for query, file_pattern in group_queries:
                query.directory.value = key[1]  # type: ignore[union-attr]
                matches = self._match_files(listing, file_pattern)
                if matches:
                    results.append(FetchResult(query=query, matched_filenames=matches))
                else:
                    results.append(FetchResult(query=query, error="No matches found"))

        return results

    # -- Grouping --------------------------------------------------

    def _group_queries(
        self, queries: List[ResourceQuery]
    ) -> Tuple[Dict[_DirKey, List[Tuple[ResourceQuery, str]]], List[FetchResult]]:
        """Group queries by ``(hostname, directory)``.

        Args:
            queries: ResourceQuery objects to group.

        Returns:
            A tuple of (grouped queries, rejected FetchResults).
            Grouped queries map each unique key to the queries and
            file patterns for that directory. Rejected results are
            for queries missing directory or pattern.
        """
        groups: Dict[_DirKey, List[Tuple[ResourceQuery, str]]] = defaultdict(list)
        rejected: List[FetchResult] = []

        for q in queries:
            directory = self._get_directory(q)
            file_pattern = self._get_file_pattern(q)
            if not directory or not file_pattern:
                rejected.append(
                    FetchResult(
                        query=q,
                        error=f"Missing directory or file pattern: dir={directory!r}, pat={file_pattern!r}",
                    )
                )
                continue
            if fsspec.utils.get_protocol(q.server.hostname) == "file":
                if not (Path(q.server.hostname) / directory).exists():
                    rejected.append(
                        FetchResult(
                            query=q,
                            error=f"Local directory does not exist: {q.server.hostname}",
                        )
                    )
                    continue
            key: _DirKey = (q.server.hostname, directory)
            groups[key].append((q, file_pattern))

        return groups, rejected

    # -- Directory listing -----------------------------------------

    def _list_dir(self, key: _DirKey) -> List[str]:
        """List a single ``(hostname, directory)`` pair.

        Args:
            key: A ``(hostname, directory)`` tuple.

        Returns:
            A list of filenames, or ``[]`` on failure.
        """
        hostname, directory = key
        try:
            return self._connection_pool_factory.list_directory(hostname, directory)
        except Exception as e:
            logger.error(f"Listing failed for {hostname}/{directory}: {e}")
            return []

    # -- Pattern matching ------------------------------------------

    @staticmethod
    def _match_files(listing: List[str], file_pattern: str) -> List[str]:
        """Match filenames in a directory listing against a regex pattern.

        Args:
            listing: Filenames from a directory listing.
            file_pattern: Regex pattern to match.

        Returns:
            Matching filenames (excluding ``.lock`` files).
        """
        # remove .lock files from listing before matching, since they are not actual resources
        listing = [f for f in listing if not f.endswith(".lock")]
        try:
            rx = re.compile(file_pattern, re.IGNORECASE)
            return [f for f in listing if rx.search(f)]
        except re.error:
            return [f for f in listing if file_pattern in f]

    # -- Value resolution ------------------------------------------

    @staticmethod
    def _resolve_values(
        query: ResourceQuery, directory: str, matched_filename: str
    ) -> None:
        """Populate ``.value`` on the query's directory and filename ProductPaths.

        Args:
            query: The query to update in place.
            directory: Resolved directory string.
            matched_filename: The discovered filename.
        """
        if isinstance(query.directory, ProductPath):
            query.directory.value = directory
        if query.product.filename is not None and isinstance(
            query.product.filename, ProductPath
        ):
            query.product.filename.value = matched_filename

    # -- Helpers ---------------------------------------------------

    @staticmethod
    def _get_directory(query: ResourceQuery) -> Optional[str]:
        """Extract the resolved directory string from a query.

        Args:
            query: The query to inspect.

        Returns:
            The directory string, or ``None``.
        """
        d = query.directory
        if isinstance(d, ProductPath):
            return d.value or d.pattern
        if isinstance(d, str):
            return d
        return None

    @staticmethod
    def _get_file_pattern(query: ResourceQuery) -> Optional[str]:
        """Extract the file regex pattern from a query.

        Args:
            query: The query to inspect.

        Returns:
            The file pattern string, or ``None``.
        """
        if query.product.filename is None:
            return None
        fn = query.product.filename
        if isinstance(fn, ProductPath):
            return fn.pattern
        if isinstance(fn, str):
            return fn
        return None

    def download_one(
        self,
        query: ResourceQuery,
        local_resource_id: str,
        local_factory: LocalResourceFactory,
        date: datetime.datetime,
    ) -> Optional[Path]:
        """Synchronously download matched files for one query.

        Skips the download if the destination file already exists and
        is non-empty.

        Args:
            query: The resolved query with filename value.
            local_resource_id: Target local resource identifier.
            local_factory: Factory for resolving local sink paths.
            date: Target date for computing sink directory.

        Returns:
            Path to the downloaded file, or ``None`` on failure.
        """

        # TODO use fsspec ls to get file size in bytes, and skip download if size is zero.
        hostname = query.server.hostname

        destination_resource = local_factory.sink_product(
            query.product, local_resource_id, date
        )
        destination_dir = (
            Path(destination_resource.server.hostname)
            / destination_resource.directory.value
        )  # type: ignore[union-attr]
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination_path = destination_dir / query.product.filename.value  # type: ignore[union-attr]

        # Skip download if the file already exists and is non-empty
        if destination_path.exists() and destination_path.stat().st_size > 0:
            logger.info(f"Skipping download, file already exists: {destination_path}")
            return destination_path

        try:
            return self._connection_pool_factory.download_file(
                hostname=hostname,
                remote_path=str(
                    Path(query.directory.value) / query.product.filename.value
                ),  # type: ignore[union-attr]
                target_dir=destination_dir,
            )
        except Exception as e:
            logger.error(
                f"Download failed for {hostname}/{query.directory.value}/{query.product.filename.value}: {e}"
            )
            return None
