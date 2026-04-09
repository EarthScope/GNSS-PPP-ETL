"""Author: Franklyn Dunbar

GNSSClient — high-level entry point for searching and downloading GNSS products.
"""

from __future__ import annotations

import datetime
from itertools import groupby
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union, cast

from gnss_product_management.factories.models import FoundResource
from gnss_product_management.factories.pipelines.download import DownloadPipeline
from gnss_product_management.factories.pipelines.find import FindPipeline
from gnss_product_management.factories.pipelines.resolve import ResolvePipeline
from gnss_management_specs.configs import LOCAL_SPEC_DIR
from gnss_product_management.defaults import DefaultProductEnvironment
from gnss_product_management.environments import WorkSpace
from gnss_product_management.client.product_query import ProductQuery
from gnss_product_management.utilities.paths import AnyPath

from gnss_product_management.specifications.dependencies.dependencies import (
    DependencyResolution,
    DependencySpec,
    SearchPreference,
)

if TYPE_CHECKING:
    from gnss_product_management.environments import ProductRegistry

logger = logging.getLogger(__name__)


class GNSSClient:
    """High-level client for searching and downloading GNSS products.

    ``GNSSClient`` is the single entry point for all product retrieval.
    It wraps :class:`FindPipeline`, :class:`DownloadPipeline`, and
    :class:`ResolvePipeline` as internal implementation details.

    Use :meth:`from_defaults` to get started with the bundled specs::

        # Search only — no local sink needed
        client = GNSSClient.from_defaults()
        results = client.search(date, product="ORBIT")

        # Search and download
        client = GNSSClient.from_defaults(base_dir="/data/gnss")
        results = client.search(date, product="CLOCK", parameters={"TTT": "FIN"})
        paths = client.download(results, sink_id="local")

        # Full dependency resolution
        client = GNSSClient.from_defaults(base_dir="/data/gnss")
        resolution, lockfile = client.resolve_dependencies("spec.yaml", date, sink_id="local")

    Args:
        product_registry: Configured :class:`ProductRegistry` with loaded product and
            center specs.
        workspace: :class:`WorkSpace` with registered local directories.
        max_connections: Maximum concurrent connections per host.
    """

    def __init__(
        self,
        product_registry: "ProductRegistry",
        workspace: WorkSpace,
        *,
        max_connections: int = 4,
    ) -> None:

        self._product_registry = product_registry
        self._finder = FindPipeline(
            product_registry, workspace, max_connections=max_connections
        )
        self._downloader = DownloadPipeline(
            product_registry,
            workspace,
            transport=self._finder.transport,
            max_connections=max_connections,
        )

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
            product_registry=DefaultProductEnvironment,
            workspace=workspace,
            max_connections=max_connections,
        )

    def query(self, product: Union[str, dict] = None) -> "ProductQuery":
        """Return a fluent :class:`ProductQuery` builder for *product*.

        This is the preferred entry point for building searches.  Chain
        calls to narrow the query, then call :meth:`ProductQuery.search`
        or :meth:`ProductQuery.download` to execute::

            results = (
                client.query("ORBIT")
                .on(date)
                .where(TTT="FIN")
                .sources("COD", "ESA")
                .search()
            )

        Args:
            product: Product name (e.g. ``"ORBIT"``) or dict with ``name``,
                and optionally ``version`` / ``variant``.

        Returns:
            A :class:`ProductQuery` bound to this client.
        """
        return ProductQuery(
            wormhole=self._finder.transport,
            search_planner=self._finder.planner,
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
    ) -> List[FoundResource]:
        """Search for products matching the given criteria.

        Delegates to :class:`FindPipeline` internally: builds queries,
        lists remote directories, expands matches, infers parameters,
        and ranks by preference and protocol.

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
            Ranked list of :class:`FoundResource` objects, best first.
            Local/file results precede remote ones; within each protocol
            tier results are ordered by *preferences*.
        """
        product_name: str = (
            product.get("name", "") if isinstance(product, dict) else product
        )

        found = cast(
            List[FoundResource],
            self._finder.run(
                date,
                product_name,
                filters=parameters,
                preferences=preferences,
                local_resources=local_resources,
                centers=remote_resources,
                all=True,
            ),
        )
        for fr in found:
            fr.date = date
        return found

    def download(
        self,
        results: List[FoundResource],
        *,
        sink_id: str,
    ) -> List[Path]:
        """Download product candidates to the local sink.

        Pass a pre-sliced list to limit how many files are fetched, e.g.
        ``client.download(results[:1], sink_id="local")``.

        Args:
            results: Ranked :class:`FoundResource` list from :meth:`search`
                or :meth:`ProductQuery.search`.  Each result must carry a
                ``date`` (set automatically by the query builders).
            sink_id: Local resource identifier (alias registered in the
                workspace, e.g. ``"local"``).

        Returns:
            Paths to successfully downloaded (and decompressed) files.
        """
        # by_date: Dict[datetime.datetime, List[FoundResource]] = {}
        # for r in results:
        #     if r.date is None:
        #         logger.warning("FoundResource has no date; skipping.")
        #         continue
        #     by_date.setdefault(r.date, []).append(r)
        by_date = {
            k: list(v)
            for k, v in groupby(
                results,
                key=lambda r: r.date if r.date is not None else datetime.datetime.min,
            )
        }

        paths: List[Path] = []
        for date, date_results in by_date.items():
            downloaded = cast(
                List[Optional[Path]],
                self._downloader.run(date_results, date, sink_id=sink_id),
            )
            for r, path in zip(date_results, downloaded):
                if path is not None:
                    r.local_path = path
                    if isinstance(path, Path):
                        paths.append(path)
        return paths

    def resolve_dependencies(
        self,
        dep_spec: Union[DependencySpec, Path, str],
        date: datetime.datetime,
        *,
        sink_id: str,
    ) -> Tuple[DependencyResolution, Optional[AnyPath]]:
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

        pipeline = ResolvePipeline(
            env=self._product_registry,
            workspace=self._finder.planner._workspace,
            transport=self._finder.transport,
        )
        return pipeline.run(dep_spec, date, sink_id=sink_id)
