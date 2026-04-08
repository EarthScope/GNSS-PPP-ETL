"""Author: Franklyn Dunbar

DownloadPipeline — found resource → local path.

Fetches remote :class:`FoundResource` objects to the local workspace
using :class:`WormHole` and :class:`LocalSearchPlanner` for
sink path resolution.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import List, Optional, Union

from gnss_product_management.environments import ProductRegistry
from gnss_product_management.environments import WorkSpace
from gnss_product_management.factories.local_search_planner import LocalSearchPlanner
from gnss_product_management.factories.models import FoundResource
from gnss_product_management.factories.remote_transport import WormHole
from gnss_product_management.factories.search_planner import SearchPlanner

logger = logging.getLogger(__name__)


class DownloadPipeline:
    """Download :class:`FoundResource` objects to the local workspace.

    Already-local resources return immediately with their existing path.
    Remote resources are downloaded via :class:`WormHole`.

    Args:
        env: The product registry with built catalogs.
        workspace: Workspace with registered local resources.
        max_connections: Maximum concurrent connections per host.
    """

    def __init__(
        self,
        env: ProductRegistry,
        workspace: WorkSpace,
        *,
        transport: Optional[WormHole] = None,
        max_connections: int = 4,
    ) -> None:
        self._env = env
        self._planner = SearchPlanner(product_registry=env, workspace=workspace)
        self._transport = transport or WormHole(
            max_connections=max_connections, env=env
        )

    def run(
        self,
        resources: Union[FoundResource, List[FoundResource]],
        date: datetime.datetime,
        *,
        sink_id: str = "local_config",
    ) -> Union[Optional[Path], List[Optional[Path]]]:
        """Download found resources to the workspace.

        Args:
            resources: A single :class:`FoundResource` or a list of them.
            date: Target date for computing sink directory.
            sink_id: Local resource alias to download into.

        Returns:
            A :class:`Path` (or ``None`` on failure) for a single resource,
            or a list of paths for multiple resources.
        """
        single = isinstance(resources, FoundResource)
        if single:
            resources = [resources]

        paths: List[Optional[Path]] = []
        for r in resources:
            path = self._download_one(r, date, sink_id)
            paths.append(path)

        if single:
            return paths[0]
        return paths

    def _download_one(
        self,
        resource: FoundResource,
        date: datetime.datetime,
        sink_id: str,
    ) -> Optional[Path]:
        """Download a single resource.

        Args:
            resource: The resource to download.
            date: Target date.
            sink_id: Local resource alias.

        Returns:
            Path to the downloaded file, or ``None`` on failure.
        """
        if resource.is_local:
            local_path = resource.path
            if local_path and local_path.exists():
                logger.debug("Already local: %s", local_path)
                return local_path

        query = resource._query
        if query is None:
            logger.warning("FoundResource has no internal query; cannot download.")
            return None

        return self._transport.download_one(
            query=query,
            local_resource_id=sink_id,
            local_factory=self._planner.local_planner,
            date=date,
        )
