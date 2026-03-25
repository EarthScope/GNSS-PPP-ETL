"""DownloadPipeline — fetch remote resources to the local workspace."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Union
from urllib.parse import urlparse

import datetime

from gnss_ppp_products.factories.models import FoundResource

if TYPE_CHECKING:
    from gnss_ppp_products.factories.environment import ProductEnvironment

logger = logging.getLogger(__name__)


def _hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


class DownloadPipeline:
    """Fetch remote resources to the local workspace.

    Already-local resources are returned as-is (no-op).  Remote resources
    are downloaded to the workspace path determined by the environment's
    ``LocalResourceFactory.sink_product()``.

    Downloads are routed through the environment's shared
    ``ResourceFetcher``, which provides protocol adapters and
    connection/listing caches.

    Parameters
    ----------
    env
        A constructed ``ProductEnvironment`` with a local factory
        and resource fetcher.

    Example
    -------
    ::

        dl = DownloadPipeline(env)
        path = dl.run(found_resource, date=dt)
    """

    def __init__(self, env: ProductEnvironment) -> None:
        self._env = env

    def run(
        self,
        resources: Union[FoundResource, List[FoundResource]],
        date: datetime.datetime,
    ) -> Union[Path, List[Path]]:
        """Download resources to the local workspace.

        Parameters
        ----------
        resources
            A single ``FoundResource`` or a list of them.
        date
            Target date used to resolve sink directory templates.

        Returns
        -------
        Path or list[Path]
            The local path(s) where files were written.  For already-local
            resources the existing path is returned without downloading.
        """
        single = isinstance(resources, FoundResource)
        items = [resources] if single else resources

        paths: List[Path] = []
        for resource in items:
            path = self._download_one(resource, date)
            paths.append(path)

        if single:
            return paths[0]
        return paths

    # ── Internal helpers ──────────────────────────────────────────

    def _download_one(
        self, resource: FoundResource, date: datetime.datetime,
    ) -> Path:
        """Download a single resource, returning the local path."""
        if resource.is_local:
            return Path(resource.uri)

        # Determine local destination
        dest_dir = self._resolve_dest_dir(resource, date)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Parse URI for protocol / hostname / directory / filename
        parsed = urlparse(resource.uri)
        protocol = (parsed.scheme or "").upper()
        hostname = parsed.hostname or ""
        path_str = parsed.path or "/"
        parts = path_str.rsplit("/", 1)
        directory = parts[0] if len(parts) > 1 else "/"
        filename = parts[1] if len(parts) > 1 else parts[0]

        # Delegate to the environment's ResourceFetcher adapter registry
        fetcher = self._env.resource_fetcher
        adapter = fetcher._adapters.get(protocol)
        if adapter is None:
            raise ValueError(f"Unsupported download protocol: {protocol!r}")

        dest = dest_dir / filename
        ok = adapter.download_file(
            hostname=hostname,
            directory=directory,
            filename=filename,
            dest_path=dest,
        )
        if ok:
            logger.info("Downloaded %s → %s", filename, dest)
            return dest
        raise RuntimeError(f"Download failed for {protocol.lower()}://{hostname}{directory}/{filename}")

    def _resolve_dest_dir(
        self, resource: FoundResource, date: datetime.datetime,
    ) -> Path:
        """Determine the local destination directory for a resource."""
        local_factory = self._env.local_factory
        if local_factory is None:
            raise RuntimeError(
                "No local factory configured — cannot determine download destination"
            )
        local_ids = local_factory.resource_ids
        if not local_ids:
            raise RuntimeError(
                "No local resource IDs registered — cannot determine download destination"
            )

        # If the FindPipeline stored the original ResourceQuery, use its
        # Product to get the correct sink path.
        rq = resource._query
        if rq is not None:
            sink_rq = local_factory.sink_product(rq.product, local_ids[0], date)
            return Path(sink_rq.server.hostname) / sink_rq.directory.value

        # Fallback: look up any matching product template from the catalog.
        version_cat = self._env.product_catalog.products.get(resource.product)
        if version_cat is None:
            raise ValueError(f"Product {resource.product!r} not in catalog")

        for ver in version_cat.versions.values():
            for product in ver.variants.values():
                try:
                    sink_rq = local_factory.sink_product(product, local_ids[0], date)
                    return Path(sink_rq.server.hostname) / sink_rq.directory.value
                except KeyError:
                    continue

        raise ValueError(
            f"No local sink path found for product {resource.product!r}"
        )
