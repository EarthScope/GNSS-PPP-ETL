"""Author: Franklyn Dunbar

GNSSClient — high-level entry point for searching and downloading GNSS products.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import List, Optional, Union

from gnss_product_management.client.search_result import SearchResult
from gnss_product_management.environments import ProductEnvironment, WorkSpace
from gnss_product_management.factories.query_factory import QueryFactory
from gnss_product_management.factories.resource_fetcher import ResourceFetcher
from gnss_product_management.factories.dependency_resolver import DependencyResolver
from gnss_product_management.specifications.dependencies.dependencies import (
    DependencyResolution,
    DependencySpec,
    SearchPreference,
)

logger = logging.getLogger(__name__)


class GNSSClient:
    """High-level client for searching and downloading GNSS products.

    ``GNSSClient`` is the single entry point for all product retrieval.
    It wraps :class:`QueryFactory`, :class:`ResourceFetcher`, and
    :class:`DependencyResolver` as internal implementation details.

    Use :meth:`from_defaults` to get started with the bundled specs::

        # Search only — no local sink needed
        client = GNSSClient.from_defaults()
        results = client.search(date, product="ORBIT")

        # Search and download
        client = GNSSClient.from_defaults(base_dir="/data/gnss")
        results = client.search(date, product="CLOCK", parameters={"TTT": "FIN"})
        paths = client.download(results, sink_id="local", date=date)

        # Full dependency resolution
        client = GNSSClient.from_defaults(base_dir="/data/gnss")
        resolution, lockfile = client.resolve_dependencies("spec.yaml", date, sink_id="local")

    Args:
        env: Configured :class:`ProductEnvironment` with loaded product and
            center specs.
        workspace: :class:`WorkSpace` with registered local directories.
        max_connections: Maximum concurrent connections per host.
    """

    def __init__(
        self,
        env: ProductEnvironment,
        workspace: WorkSpace,
        *,
        max_connections: int = 4,
    ) -> None:
        self._env = env
        self._qf = QueryFactory(product_environment=env, workspace=workspace)
        self._fetcher = ResourceFetcher(max_connections=max_connections)

    @classmethod
    def from_defaults(
        cls,
        base_dir: Optional[Union[Path, str]] = None,
        *,
        local_alias: str = "local",
        max_connections: int = 4,
    ) -> "GNSSClient":
        """Construct a client from the bundled default specs.

        Loads the pre-built :data:`DefaultProductEnvironment` and creates a
        fresh :class:`WorkSpace` from the bundled local layout specs.  If
        *base_dir* is provided, all local specs are registered against that
        directory, enabling downloads and local-first resolution.

        Args:
            base_dir: Root directory for local product storage.  If ``None``,
                the client operates in search-only mode (no local sink).
            local_alias: Alias for the registered local resource (default
                ``"local"``).  Used as the ``sink_id`` in
                :meth:`download` and :meth:`resolve_dependencies`.
            max_connections: Maximum concurrent connections per host.

        Returns:
            A configured :class:`GNSSClient` instance.
        """
        from gnss_management_specs.configs import LOCAL_SPEC_DIR
        from gnss_product_management.defaults import DefaultProductEnvironment

        workspace = WorkSpace()
        for path in Path(LOCAL_SPEC_DIR).glob("*.yaml"):
            workspace.add_resource_spec(path)

        if base_dir is not None:
            spec_ids = list(workspace._resource_specs.keys())
            workspace.register_spec(
                base_dir=Path(base_dir),
                spec_ids=spec_ids,
                alias=local_alias,
            )

        return cls(
            env=DefaultProductEnvironment,
            workspace=workspace,
            max_connections=max_connections,
        )

    def search(
        self,
        date: datetime.datetime,
        product: Union[str, dict],
        *,
        parameters: Optional[dict] = None,
        preferences: Optional[List[SearchPreference]] = None,
        local_resources: Optional[List[str]] = None,
        remote_resources: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """Search for products matching the given criteria.

        Runs the full pipeline internally: build queries → list remote
        directories → expand matches → infer parameters → rank by preference
        and protocol.

        Args:
            date: Target date (timezone-aware datetime).
            product: Product name as a string (e.g. ``"ORBIT"``) or a dict
                with ``name``, and optionally ``version`` / ``variant``.
            parameters: Parameter constraints, e.g. ``{"TTT": "FIN"}``.
            preferences: Optional preference cascade for ranking results.
                Each :class:`SearchPreference` specifies a parameter and
                an ordered list of preferred values.
            local_resources: Restrict to these local resource IDs.
            remote_resources: Restrict to these remote center IDs.

        Returns:
            Ranked list of :class:`SearchResult` objects, best first.
            Local/file results precede remote ones; within each protocol
            tier results are ordered by *preferences*.
        """
        if isinstance(product, str):
            product = {"name": product}

        queries = self._qf.get(
            date=date,
            product=product,
            parameters=parameters,
            local_resources=local_resources,
            remote_resources=remote_resources,
        )

        fetch_results = self._fetcher.search(queries)
        expanded = ResourceFetcher.expand_results(fetch_results, env=self._env)
        if preferences:
            expanded = ResourceFetcher.sort_by_preferences(expanded, preferences)
        ranked = ResourceFetcher.sort_by_protocol(expanded)

        results: List[SearchResult] = []
        for rq in ranked:
            params = {
                p.name: p.value for p in rq.product.parameters if p.value is not None
            }
            r = SearchResult(
                hostname=rq.server.hostname,
                protocol=rq.server.protocol or "",
                directory=rq.directory.value or rq.directory.pattern,  # type: ignore[union-attr]
                filename=rq.product.filename.value if rq.product.filename else "",  # type: ignore[union-attr]
                parameters=params,
            )
            r._query = rq
            results.append(r)

        return results

    def download(
        self,
        results: List[SearchResult],
        *,
        sink_id: str,
        date: datetime.datetime,
        limit: int = 1,
    ) -> List[Path]:
        """Download product candidates to the local sink.

        Args:
            results: Ranked :class:`SearchResult` list from :meth:`search`.
            sink_id: Local resource identifier (alias registered in the
                workspace, e.g. ``"local"``).
            date: Target date — used to resolve the destination directory.
            limit: Maximum number of files to download (default ``1``).

        Returns:
            Paths to successfully downloaded (and decompressed) files.
        """
        paths: List[Path] = []
        for r in results[:limit]:
            if r._query is None:
                logger.warning("SearchResult has no internal query; skipping.")
                continue
            path = self._fetcher.download_one(
                query=r._query,
                local_resource_id=sink_id,
                local_factory=self._qf._local,
                date=date,
            )
            if path is not None:
                r.local_path = path
                paths.append(path)
        return paths

    def resolve_dependencies(
        self,
        dep_spec: Union[DependencySpec, Path, str],
        date: datetime.datetime,
        *,
        sink_id: str,
    ) -> tuple:
        """Resolve all dependencies in a spec for the given date.

        Accepts a :class:`DependencySpec` object or a path to a YAML file.
        Checks local disk first, then downloads missing files.  Returns
        immediately if a lockfile already exists for
        ``(package, task, date, version)``.

        Args:
            dep_spec: Dependency specification — a :class:`DependencySpec`
                instance, or a path (``str`` or :class:`Path`) to a YAML file.
            date: Target date (timezone-aware datetime).
            sink_id: Local resource identifier for storing resolved files.

        Returns:
            A ``(DependencyResolution, lockfile_path)`` tuple.
        """
        if isinstance(dep_spec, (str, Path)):
            dep_spec = DependencySpec.from_yaml(dep_spec)

        resolver = DependencyResolver(
            dep_spec=dep_spec,
            query_factory=self._qf,
            product_environment=self._env,
            fetcher=self._fetcher,
        )
        return resolver.resolve(date=date, local_sink_id=sink_id)
