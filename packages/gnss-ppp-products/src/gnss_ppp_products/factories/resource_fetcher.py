"""ResourceFetcher — protocol-agnostic file search and download."""

import asyncio
import datetime
from functools import cache
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import connect
from threading import Lock
from typing import Dict, List, Optional, Union

from gnss_ppp_products.server import protocol
from gnss_ppp_products.server.protocol import DirectoryAdapter
from gnss_ppp_products.server.ftp import FTPAdapter
from gnss_ppp_products.server.http import HTTPAdapter
from gnss_ppp_products.server.local import LocalAdapter
from gnss_ppp_products.specifications.products.product import ProductPath
from gnss_ppp_products.specifications.remote.resource import ResourceQuery
from gnss_ppp_products.factories.local_factory import LocalResourceFactory

logger = logging.getLogger(__name__)


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
        ftp_timeout: int = 60,
        download_timeout: int = 180,
    ) -> None:
        self._ftp_timeout = ftp_timeout
        self._download_timeout = download_timeout
        self._listing_cache: Dict[str, List[str]] = {}
        self._connectivity_cache: Dict[str, bool] = {}
        self._adapters: Dict[str, DirectoryAdapter] = {
            "FTP": FTPAdapter(timeout=ftp_timeout),
            "FTPS": FTPAdapter(timeout=ftp_timeout, use_tls=True),
            "HTTP": HTTPAdapter(timeout=download_timeout),
            "HTTPS": HTTPAdapter(timeout=download_timeout),
            "FILE": LocalAdapter(),
            "LOCAL": LocalAdapter(),
            "": LocalAdapter(),
        }
        self.thread_lock = Lock()  # protects both caches for thread safety
        self._key_locks: Dict[str, Lock] = {}  # per-cache-key locks to prevent thundering herd

    def get_connection_cache_key(self,protocol:str,hostname:str) -> str:
        return f"{protocol.upper()}://{hostname}"

    def warm_connectivity_cache(self, queries: List[ResourceQuery]) -> None:
        """Pre-check reachability for all unique remote servers in *queries*.

        Populates the internal connectivity cache so that subsequent
        ``search()`` calls skip redundant connection probes.  Local
        protocols are ignored.  Checks run concurrently.

        FTP and FTPS share the same underlying host, so a single probe
        result is propagated to both protocol keys.
        """
        # Deduplicate by hostname — one probe covers both FTP and FTPS
        seen_hosts: Dict[str, str] = {}  # hostname → protocol to use for probe
        for q in queries:
            protocol = (q.server.protocol or "").upper()
            if protocol in ("FILE", "LOCAL", ""):
                continue
            hostname = q.server.hostname
            cache_key = self.get_connection_cache_key(protocol,hostname)
            if cache_key in self._connectivity_cache:
                continue

            seen_hosts[cache_key] = protocol

        if not seen_hosts:
            return

        def _check(item: tuple[str, str]) -> None:
            cache_key, protocol = item
            adapter = self._adapters.get(protocol)
            if cache_key in self._connectivity_cache or adapter is None:
                return  # already cached, no lock needed for dict read

            hostname = cache_key.split("://", 1)[1]
            reachable = adapter.can_connect(hostname)
            self._connectivity_cache[cache_key] = reachable

            label = "reachable" if reachable else "unreachable"
            logger.info(f"Connectivity check: {cache_key} --> {label}")

        with ThreadPoolExecutor(max_workers=15) as pool:
            _ = list(pool.map(_check, seen_hosts.items()))

    def search(self, queries: List[ResourceQuery]) -> List[FetchResult]:
        """Search every query's server/directory for matching files.

        Groups queries by directory so each remote listing is fetched at
        most once, then matches all file patterns in-memory.
        """
        # ---- 1. Group queries by their listing cache key ----
        groups: Dict[str, List[ResourceQuery]] = {}
        query_meta: Dict[int, tuple[str, str, str]] = {}  # id(q) → (cache_key, directory, file_pattern)
        for q in queries:
            directory = self._get_directory(q)
            file_pattern = self._get_file_pattern(q)
            if not directory or not file_pattern:
                continue
            protocol = (q.server.protocol or "").upper()
            hostname = q.server.hostname
            cache_key = f"{protocol}://{hostname}/{directory}"
            groups.setdefault(cache_key, []).append(q)
            query_meta[id(q)] = (cache_key, directory, file_pattern)

        # ---- 2. Fetch each unique directory once (concurrently) ----
        keys_to_fetch = [k for k in groups if k not in self._listing_cache]
        if keys_to_fetch:
            with ThreadPoolExecutor(max_workers=15) as pool:
                list(pool.map(self._fetch_listing, keys_to_fetch, [groups[k][0] for k in keys_to_fetch]))

        # ---- 3. Match patterns against cached listings ----
        results: List[FetchResult] = []
        for q in queries:
            meta = query_meta.get(id(q))
            if meta is None:
                results.append(FetchResult(
                    query=q,
                    error=f"Missing directory or file pattern",
                ))
                continue
            cache_key, directory, file_pattern = meta
            listing = self._listing_cache.get(cache_key)
            if listing is None:
                results.append(FetchResult(query=q, error=f"Listing unavailable for {cache_key}"))
                continue

            q.directory.value = directory  # type: ignore[union-attr]
            matches = self._match_files(listing, file_pattern)
            if matches:
                results.append(FetchResult(query=q, matched_filenames=matches))
            else:
                results.append(FetchResult(query=q, error="No matches found"))
        return results

    def _fetch_listing(self, cache_key: str, representative_query: ResourceQuery) -> None:
        """Fetch and cache the directory listing for *cache_key*.

        Uses per-key locking so concurrent calls for the same directory
        block rather than stampede the server.
        """
        if cache_key in self._listing_cache:
            return

        protocol = (representative_query.server.protocol or "").upper()
        hostname = representative_query.server.hostname
        directory = self._get_directory(representative_query) or ""

        # Connectivity gate
        conn_key = self.get_connection_cache_key(protocol, hostname)
        if conn_key in self._connectivity_cache and not self._connectivity_cache[conn_key]:
            return  # host known unreachable

        # Per-key lock
        if cache_key not in self._key_locks:
            self._key_locks[cache_key] = Lock()
        key_lock = self._key_locks[cache_key]

        adapter = self._adapters.get(protocol)
        if adapter is None:
            return

        try:
            with key_lock:
                if cache_key in self._listing_cache:
                    return  # another thread filled it while we waited
                logger.info(f"Listing {protocol} directory: {hostname}/{directory}")
                listing = adapter.list_directory(hostname, directory)
                if "FILE" not in cache_key:
                    self._listing_cache[cache_key] = listing
        except Exception as e:
            logger.warning(f"Listing failed for {cache_key}: {e}")

    # -- Pattern matching ------------------------------------------

    @staticmethod
    def _match_files(listing: List[str], file_pattern: str) -> List[str]:
        """Match filenames in a directory listing against a regex pattern."""
        # remove .lock files from listing before matching, since they are not actual resources
        listing = [f for f in listing if not f.endswith(".lock")]
        try:
            rx = re.compile(file_pattern, re.IGNORECASE)
            return [f for f in listing if rx.search(f)]
        except re.error:
            return [f for f in listing if file_pattern in f]

    # -- Value resolution ------------------------------------------

    @staticmethod
    def _resolve_values(query: ResourceQuery, directory: str, matched_filename: str) -> None:
        """Populate .value on the query's directory and filename ProductPaths."""
        if isinstance(query.directory, ProductPath):
            query.directory.value = directory
        if query.product.filename is not None and isinstance(query.product.filename, ProductPath):
            query.product.filename.value = matched_filename

    # -- Helpers ---------------------------------------------------

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

    # -- Async download --------------------------------------------

    async def download(
        self,
        results: List[ResourceQuery],
        local_resource_id:str,
        local_factory: LocalResourceFactory,
        date: datetime.datetime,
        *,
        max_workers: int = 4,
    ) -> List[FetchResult]:
        """Download found remote files to the complementary local directory.

        For each ``FetchResult`` with ``found=True`` and a non-local protocol,
        resolves the local directory via *local_factory*, creates it, and
        downloads every matched file into it.

        Downloads run concurrently in a thread pool (FTP/HTTP are blocking IO).
        """
        loop = asyncio.get_running_loop()
        remote_found = [
            fr for fr in results
            if fr.found and (fr.query.server.protocol or "").upper() not in ("FILE", "LOCAL", "")
        ]
        if not remote_found:
            return results

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            tasks = [
                loop.run_in_executor(pool, self.download_one, fr, local_factory, date)
                for fr in remote_found
            ]
            await asyncio.gather(*tasks)

        return results

    def download_one(
        self,
        query: ResourceQuery,
        local_resource_id: str,
        local_factory: LocalResourceFactory,
        date: datetime.datetime,
    ) -> Optional[Path]:
        """Synchronously download all matched files for one FetchResult."""

        hostname = query.server.hostname

        destination_resource = local_factory.sink_product(query.product, local_resource_id, date)
        destination_dir = Path(destination_resource.server.hostname) / destination_resource.directory.value  # type: ignore[union-attr]
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination_path = destination_dir / query.product.filename.value  # type: ignore[union-attr]
        protocol = (query.server.protocol or "").upper()
        adapter: Optional[Union[FTPAdapter,HTTPAdapter,LocalAdapter,DirectoryAdapter]] = self._adapters.get(protocol)
        if adapter is None:
            logger.error(f"Unsupported protocol for download: {protocol!r}")
            return None

        try:
            return adapter.download_file(
                hostname=hostname,
                directory=query.directory.value,  # type: ignore[union-attr]
                filename=query.product.filename.value,
                dest_path=destination_path,
            )
        except Exception as e:
            logger.error(f"Download failed for {hostname}/{query.directory.value}/{query.product.filename.value}: {e}")
            return None
