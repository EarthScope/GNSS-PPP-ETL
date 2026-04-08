"""Author: Franklyn Dunbar

ResolvePipeline — Find + Download + LockfileWriter in one call.

High-level composition that resolves a :class:`DependencySpec` for a
given date: finds remote resources, optionally downloads them, and
persists the result as a lockfile.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from gnss_product_management.environments import ProductRegistry, WorkSpace
from gnss_product_management.factories.models import FoundResource
from gnss_product_management.factories.pipelines.find import FindPipeline
from gnss_product_management.factories.pipelines.download import DownloadPipeline
from gnss_product_management.factories.pipelines.lockfile_writer import LockfileWriter
from gnss_product_management.specifications.dependencies.dependencies import (
    DependencyResolution,
    DependencySpec,
    ResolvedDependency,
    SearchPreference,
)

logger = logging.getLogger(__name__)


class ResolvePipeline:
    """Find → Download → Lockfile for every dependency in a spec.

    Args:
        env: The product registry with built catalogs.
        workspace: Workspace with registered local resources.
        lockfile_dir: Directory for lockfile storage.
        max_connections: Maximum concurrent connections per host.
        package: Package name written into lockfiles.
    """

    def __init__(
        self,
        env: ProductRegistry,
        workspace: WorkSpace,
        lockfile_dir: Path,
        *,
        max_connections: int = 4,
        package: str = "PRIDE",
    ) -> None:
        self._finder = FindPipeline(env, workspace, max_connections=max_connections)
        self._downloader = DownloadPipeline(
            env,
            workspace,
            transport=self._finder.transport,
            max_connections=max_connections,
        )
        self._writer = LockfileWriter(lockfile_dir, package=package)

    def run(
        self,
        spec: DependencySpec,
        date: datetime.datetime,
        *,
        centers: Optional[List[str]] = None,
        download: bool = True,
        sink_id: str = "local_config",
    ) -> Tuple[DependencyResolution, Optional[Path]]:
        """Resolve all dependencies in *spec* for *date*.

        Args:
            spec: The dependency specification.
            date: Target date.
            centers: Restrict remote search to these center IDs.
            download: If ``True``, download remote resources.
            sink_id: Local resource alias for download destination.

        Returns:
            A tuple of (:class:`DependencyResolution`, lockfile path or ``None``).
        """
        resolved: List[ResolvedDependency] = []

        for dep in spec.dependencies:
            preferences = dep.preferences if hasattr(dep, "preferences") else None
            found = self._finder.run(
                date,
                dep.spec,
                centers=centers,
                filters=dep.constraints or None,
                preferences=preferences,
                all=False,
            )

            if found is None:
                resolved.append(
                    ResolvedDependency(
                        spec=dep.spec,
                        required=dep.required,
                        status="missing",
                    )
                )
                continue

            local_path: Optional[Path] = None
            status = "local" if found.is_local else "remote"

            if download and not found.is_local:
                local_path = self._downloader.run(found, date, sink_id=sink_id)
                if local_path is not None:
                    status = "downloaded"
                else:
                    status = "missing"
            elif found.is_local:
                local_path = found.path

            resolved.append(
                ResolvedDependency(
                    spec=dep.spec,
                    required=dep.required,
                    status=status,
                    remote_url=found.uri if not found.is_local else "",
                    local_path=local_path,
                )
            )

        resolution = DependencyResolution(
            spec_name=spec.name,
            resolved=resolved,
        )

        lockfile_path: Optional[Path] = None
        if resolution.fulfilled:
            lockfile_path = self._writer.write(resolution, date)

        logger.info(resolution.summary())
        return resolution, lockfile_path
