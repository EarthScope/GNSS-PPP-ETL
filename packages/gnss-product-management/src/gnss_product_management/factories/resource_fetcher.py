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
from gnss_product_management.environments import ProductEnvironment
from gnss_product_management.specifications.dependencies.dependencies import (
    SearchPreference,
)
from gnss_product_management.specifications.parameters.parameter import Parameter
from gnss_product_management.specifications.products.product import (
    ProductPath,
    infer_from_regex,
)
from gnss_product_management.specifications.remote.resource import ResourceQuery
from gnss_product_management.factories.local_factory import LocalResourceFactory
from gnss_product_management.factories.connection_pool import ConnectionPoolFactory
from gnss_product_management.utilities.helpers import decompress_gzip

logger = logging.getLogger(__name__)

# Type alias for (hostname, directory) grouping key
_DirKey = Tuple[str, str]


def _get_param_value(rq: ResourceQuery, param_name: str) -> str:
    """Extract a parameter value from a ResourceQuery's product.

    Args:
        rq: The query to inspect.
        param_name: Parameter name to extract.

    Returns:
        The parameter value, or ``""`` if not found.
    """
    for p in rq.product.parameters:
        if p.name == param_name and p.value is not None:
            return p.value
    return ""


@dataclass
class FetchResult:
    """Outcome of searching one ResourceQuery against its server."""

    query: ResourceQuery
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


class ResourceFetcher:
    """Search for files described by ResourceQuery objects.

    For each query, lists the remote (FTP/HTTP) or local directory, matches
    ``product.filename.pattern`` against the listing, and populates
    ``directory.value`` and ``filename.value`` on the query.

    Attributes:
        _connection_pool_factory: Factory managing per-host connection pools.

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
        """Initialise the fetcher.

        Args:
            max_connections: Maximum connections per host pool.
        """
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
            try:
                self._connection_pool_factory.add_connection(hostname)
            except Exception as e:
                logger.error(f"Failed to create connection pool for {hostname}: {e}")
                # Mark all queries for this host as rejected.
                for key in list(groups.keys()):
                    if key[0] == hostname:
                        for q, _ in groups[key]:
                            rejected.append(
                                FetchResult(
                                    query=q,
                                    error=f"Connection pool creation failed for {hostname}: {e}",
                                )
                            )
                        del groups[key]

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

    # -- Result expansion and sorting ------------------------------

    @staticmethod
    def expand_results(
        fetched: List[FetchResult],
        env: Optional[ProductEnvironment] = None,
    ) -> List[ResourceQuery]:
        """Expand FetchResults into ResourceQueries with filename values filled in.

        Each matched filename from a :class:`FetchResult` becomes its own
        :class:`ResourceQuery` with ``filename.value`` set and parameters
        back-filled from the filename via regex inference.

        Args:
            fetched: List of fetch results from :meth:`search`.
            env: Optional product environment for parameter classification.

        Returns:
            Expanded list of :class:`ResourceQuery` objects.
        """
        expanded: List[ResourceQuery] = []
        for fq in fetched:
            if fq.error:
                continue
            assert fq.query.directory.value is not None, (
                "Fetched query must have directory value filled in"
            )
            assert fq.query.product.filename is not None, (
                "Fetched query must have filename value filled in"
            )
            if not fq.matched_filenames:
                logger.info(
                    f"No matches found for query {fq.query.product.filename.pattern}"
                )
                continue
            for filename in fq.matched_filenames:
                rq = fq.query.model_copy(deep=True)
                rq.product.filename.value = filename  # type: ignore[union-attr]
                rq = ResourceFetcher._update_parameters(rq, env)
                expanded.append(rq)
        return expanded

    @staticmethod
    def sort_by_protocol(queries: List[ResourceQuery]) -> List[ResourceQuery]:
        """Sort queries by server protocol, preferring local/file over remote.

        Order: FILE > LOCAL > FTP > FTPS > HTTP > HTTPS > unknown.

        Args:
            queries: ResourceQuery objects to sort.

        Returns:
            Sorted list of queries.
        """
        protocol_sort_order = ["FILE", "LOCAL", "FTP", "FTPS", "HTTP", "HTTPS"]
        return sorted(
            queries,
            key=lambda rq: (
                protocol_sort_order.index((rq.server.protocol or "").upper())
                if (rq.server.protocol or "").upper() in protocol_sort_order
                else len(protocol_sort_order)
            ),
        )

    @staticmethod
    def sort_by_preferences(
        queries: List[ResourceQuery],
        preferences: List[SearchPreference],
    ) -> List[ResourceQuery]:
        """Sort queries according to a preference cascade.

        Each :class:`SearchPreference` specifies a parameter name and an
        ordered list of preferred values.  Preferences are applied in
        reverse order so that the first entry in *preferences* is the most
        significant sort key.

        Args:
            queries: ResourceQuery objects to sort.
            preferences: Ordered preference cascade to apply.

        Returns:
            Sorted list of queries.
        """
        for pref in reversed(preferences):
            param_name = pref.parameter
            sorting = [v.upper() for v in pref.sorting]

            def _key(rq: ResourceQuery, _pn=param_name, _s=sorting) -> int:
                try:
                    val = _get_param_value(rq, _pn).upper()
                    return _s.index(val)
                except (ValueError, TypeError):
                    return len(_s)

            queries = sorted(queries, key=_key)

        return queries

    @staticmethod
    def _update_parameters(
        resource_query: ResourceQuery,
        env: Optional[ProductEnvironment] = None,
    ) -> ResourceQuery:
        """Back-fill parameters on a ResourceQuery from its matched filename.

        Uses :func:`infer_from_regex` to extract parameter values from the
        filename pattern, then optionally calls
        :meth:`ProductEnvironment.classify` for further classification.

        Args:
            resource_query: Query with ``filename.value`` already set.
            env: Optional product environment for parameter classification.

        Returns:
            A deep copy of the query with updated parameters.
        """
        updated = resource_query.model_copy(deep=True)
        updated_params: List[Parameter] = infer_from_regex(
            regex=updated.product.filename.pattern,  # type: ignore
            filename=updated.product.filename.value,  # type: ignore
            parameters=updated.product.parameters,
        )
        updated.product.parameters = updated_params
        if env is not None:
            classification_results = env.classify(
                filename=updated.product.filename.value,  # type: ignore[arg-type]
                parameters=updated.product.parameters,
            )
            if classification_results:
                class_parameters: Dict[str, str] = classification_results.get(  # type: ignore[union-attr]
                    "parameters", {}
                )  # TODO: make classify() return a structured type
                if updated.product.parameters is not None:
                    for p in updated.product.parameters:
                        if p.name in class_parameters and p.value is None:
                            p.value = class_parameters[p.name]
        return updated

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

        # Prefer an already-decompressed version on disk
        if destination_path.suffix == ".gz":
            decompressed_path = destination_path.with_suffix("")
            if decompressed_path.exists() and decompressed_path.stat().st_size > 0:
                logger.info(
                    f"Skipping download, decompressed file already exists: {decompressed_path}"
                )
                return decompressed_path

        # Skip download if the file already exists and is non-empty
        if destination_path.exists() and destination_path.stat().st_size > 0:
            logger.info(f"Skipping download, file already exists: {destination_path}")
            return destination_path

        try:
            result = self._connection_pool_factory.download_file(
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

        # Decompress gzip files after download
        if result is not None and result.suffix == ".gz":
            decompressed = decompress_gzip(result)
            if decompressed is not None:
                return decompressed
            logger.warning(
                f"Decompression failed for {result}, returning compressed file"
            )

        return result
