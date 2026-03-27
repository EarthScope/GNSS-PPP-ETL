"""Connection pool — thread-safe fsspec filesystem instances per host."""

import logging
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import fsspec
import fsspec.utils

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Thread-safe pool of fsspec filesystem instances for a single host."""

    def __init__(self, hostname: str, max_connections: int = 4):
        self.hostname = hostname
        self.protocol = fsspec.utils.get_protocol(hostname) or "file"
        self.max_connections = max_connections
        self._pool: List[fsspec.AbstractFileSystem] = []
        self._semaphore: Optional[threading.Semaphore] = None
        self._pool_lock = threading.Lock()
        self._initialized = False
        self._failed = False

    def _connect(self) -> Optional[fsspec.AbstractFileSystem]:
        if self.protocol == "file":
            try:
                return fsspec.filesystem("file")
            except Exception as e:
                logger.error(f"Error creating local filesystem: {e}")
                return None

        if self.protocol == "ftp":
            parsed = urlparse(self.hostname)
            host = parsed.hostname or self.hostname
            # Try plain FTP first, then FTPS (TLS) fallback
            for tls in (False, True):
                try:
                    return fsspec.filesystem(
                        "ftp", host=host, tls=tls, skip_instance_cache=True,
                    )
                except Exception:
                    continue
            logger.error(f"FTP/FTPS connection failed for {self.hostname}")
            return None

        # HTTP, HTTPS, and other protocols
        try:
            fs, _ = fsspec.core.url_to_fs(self.hostname, skip_instance_cache=True)
            return fs
        except Exception as e:
            logger.error(f"Error creating filesystem for {self.hostname}: {e}")
            return None

    def _initialize_pool(self):
        if self._initialized or self._failed:
            return
        with self._pool_lock:
            if self._initialized or self._failed:
                return
            first = self._connect()
            if first is None:
                self._failed = True
                return
            self._pool.append(first)
            for _ in range(self.max_connections - 1):
                conn = self._connect()
                if conn is None:
                    break
                self._pool.append(conn)
            self._semaphore = threading.Semaphore(len(self._pool))
            self._initialized = True
            logger.debug(f"Pool for {self.hostname}: {len(self._pool)} connections")

    @contextmanager
    def get_connection(self):
        self._initialize_pool()
        if not self._initialized:
            raise ConnectionError(f"No connections available for {self.hostname}")
        self._semaphore.acquire()
        with self._pool_lock:
            connection = self._pool.pop(0)
        try:
            yield connection
        finally:
            with self._pool_lock:
                self._pool.append(connection)
            self._semaphore.release()

    def replace_connection(self, dead: "fsspec.AbstractFileSystem") -> Optional["fsspec.AbstractFileSystem"]:
        """Swap a dead connection for a fresh one in the pool.

        Returns the new connection, or *None* if reconnection fails.
        The caller must already hold a semaphore slot (i.e. be inside
        ``get_connection``).
        """
        with self._pool_lock:
            try:
                self._pool.remove(dead)
            except ValueError:
                pass
        fresh = self._connect()
        if fresh is not None:
            with self._pool_lock:
                self._pool.append(fresh)
        else:
            # Give back the semaphore slot since we can't replace it
            logger.warning(f"Reconnect failed for {self.hostname}; pool shrunk by 1")
        return fresh

    def full_path(self, directory: str) -> str:
        """Combine hostname base with a relative directory."""
        if self.protocol == "file":
            return os.path.join(self.hostname, directory)
        if self.protocol in ("http", "https"):
            return f"{self.hostname.rstrip('/')}/{directory.lstrip('/')}"
        # FTP: directory is already an absolute server path
        return directory


class ConnectionPoolFactory:
    """Manage per-host connection pools with a shared directory listing cache."""

    def __init__(self, max_connections: int = 4):
        self.max_connections = max_connections
        self._pools: Dict[str, ConnectionPool] = {}
        self._factory_lock = threading.Lock()
        self._listing_cache: Dict[str, List[str]] = {}
        self._listing_cache_lock = threading.Lock()

    def add_connection(self, hostname: str):
        with self._factory_lock:
            if hostname not in self._pools:
                self._pools[hostname] = ConnectionPool(hostname, self.max_connections)

    @contextmanager
    def get_connection(self, hostname: str):
        if hostname not in self._pools:
            raise ValueError(f"No connection pool for: {hostname}")
        with self._pools[hostname].get_connection() as connection:
            yield connection

    def list_directory(self, hostname: str, directory: str) -> List[str]:
        pool = self._pools.get(hostname)
        if pool is None:
            raise ValueError(f"No connection pool for: {hostname}")

        full_path = pool.full_path(directory)

        def _ls(conn: "fsspec.AbstractFileSystem") -> List[str]:
            raw = conn.ls(full_path, detail=False)
            # fsspec returns full paths; extract just filenames
            return [os.path.basename(p) for p in raw]

        # Don't cache local filesystem listings
        if pool.protocol == "file":
            with pool.get_connection() as conn:
                return _ls(conn)

        cache_key = f"{hostname}:{directory}"
        with self._listing_cache_lock:
            if cache_key in self._listing_cache:
                return self._listing_cache[cache_key]

        with pool.get_connection() as conn:
            try:
                listing = _ls(conn)
            except (BrokenPipeError, ConnectionError, EOFError, OSError) as e:
                logger.debug(f"Stale connection for {hostname}, reconnecting: {e}")
                fresh = pool.replace_connection(conn)
                if fresh is None:
                    return []
                try:
                    listing = _ls(fresh)
                except Exception as e2:
                    logger.error(f"Retry failed listing {directory} on {hostname}: {e2}")
                    return []
            except Exception as e:
                logger.error(f"Error listing {directory} on {hostname}: {e}")
                return []

        with self._listing_cache_lock:
            self._listing_cache[cache_key] = listing
        return listing

    def download_file(self, hostname: str, remote_path: str, target_dir: str) -> Optional[Path]:
        pool = self._pools.get(hostname)
        if pool is None:
            raise ValueError(f"No connection pool for: {hostname}")

        full_path = pool.full_path(remote_path)
        filename = Path(remote_path).name
        local_path = Path(target_dir) / filename

        def _get(conn: "fsspec.AbstractFileSystem") -> Optional[Path]:
            conn.get(full_path, str(local_path))
            if local_path.exists() and local_path.stat().st_size > 0:
                return local_path
            logger.error(f"Downloaded file is missing or empty: {local_path}")
            local_path.unlink(missing_ok=True)
            return None

        with pool.get_connection() as conn:
            try:
                return _get(conn)
            except (BrokenPipeError, ConnectionError, EOFError, OSError) as e:
                logger.debug(f"Stale connection for {hostname}, reconnecting: {e}")
                fresh = pool.replace_connection(conn)
                if fresh is None:
                    return None
                try:
                    return _get(fresh)
                except Exception as e2:
                    logger.error(f"Retry failed downloading {remote_path} from {hostname}: {e2}")
                    return None
            except Exception as e:
                logger.error(f"Download failed {remote_path} from {hostname}: {e}")
                return None

