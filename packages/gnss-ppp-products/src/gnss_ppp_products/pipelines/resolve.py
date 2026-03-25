"""ResolvePipeline — walk a dependency spec, find + download + lockfile."""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from gnss_ppp_products.factories.models import FoundResource, MissingProductError
from gnss_ppp_products.pipelines.download import DownloadPipeline, _hash_file
from gnss_ppp_products.pipelines.find import FindPipeline
from gnss_ppp_products.pipelines.lockfile_writer import LockfileWriter
from gnss_ppp_products.specifications.dependencies.dependencies import (
    Dependency,
    DependencyResolution,
    ResolvedDependency,
    SearchPreference,
)
from gnss_ppp_products.specifications.dependencies.lockfile import LockProduct

if TYPE_CHECKING:
    from gnss_ppp_products.factories.environment import ProductEnvironment

logger = logging.getLogger(__name__)


class ResolvePipeline:
    """Resolve all dependencies for a task by composing
    :class:`FindPipeline`, :class:`DownloadPipeline`, and
    :class:`LockfileWriter`.

    Replaces the legacy ``DependencyResolver``.

    Parameters
    ----------
    env
        A constructed ``ProductEnvironment``.

    Example
    -------
    ::

        resolve = ResolvePipeline(env)
        resolution = resolve.run(task="pride-pppar", date=dt)
        print(resolution.summary())
    """

    def __init__(self, env: ProductEnvironment) -> None:
        self._env = env
        self._find = FindPipeline(env)
        self._download = DownloadPipeline(env)
        self._lockfile_writer = LockfileWriter(env.base_dir)

    def run(
        self,
        task: str,
        date: datetime.datetime,
        *,
        centers: Optional[List[str]] = None,
        filters: Optional[dict[str, str]] = None,
        download: bool = True,
    ) -> DependencyResolution:
        """Resolve all dependencies for a task.

        Parameters
        ----------
        task
            Dependency spec name (e.g. ``"pride-pppar"``).
        date
            Target date (timezone-aware datetime).
        centers
            Optional subset of centers.
        filters
            Parameter constraints (merged with per-dependency constraints).
        download
            If ``True``, download missing remote products.
            If ``False``, discover without downloading.

        Returns
        -------
        DependencyResolution

        Raises
        ------
        KeyError
            If *task* is not a registered dependency spec.
        MissingProductError
            If any required dependency cannot be found.
        """
        dep_spec = self._env.get_dependency_spec(task)
        results: List[ResolvedDependency] = []

        for dep in dep_spec.dependencies:
            resolved = self._resolve_one(
                dep,
                date,
                centers=centers,
                filters=filters,
                preferences=dep_spec.preferences,
                download=download,
            )
            results.append(resolved)

        resolution = DependencyResolution(
            spec_name=dep_spec.name,
            resolved=results,
        )

        # Write lockfile (implicit, always happens when there are fulfilled deps)
        if resolution.fulfilled:
            self._lockfile_writer.write(resolution, date)

        # Raise on missing required deps
        missing_required = [
            r.spec for r in resolution.resolved
            if r.status == "missing" and r.required
        ]
        if missing_required:
            raise MissingProductError(missing=missing_required, task=task)

        logger.info(resolution.summary())
        return resolution

    # ── Internal helpers ──────────────────────────────────────────

    def _resolve_one(
        self,
        dep: Dependency,
        date: datetime.datetime,
        *,
        centers: Optional[List[str]],
        filters: Optional[dict[str, str]],
        preferences: Optional[List[SearchPreference]],
        download: bool,
    ) -> ResolvedDependency:
        """Resolve a single dependency."""
        # Merge dep-level constraints with caller-level filters
        merged_filters: Optional[dict[str, str]] = None
        if dep.constraints or filters:
            merged_filters = {}
            if dep.constraints:
                merged_filters.update(dep.constraints)
            if filters:
                merged_filters.update(filters)

        try:
            found = self._find.run(
                date=date,
                product=dep.spec,
                centers=centers,
                filters=merged_filters,
                preferences=preferences,
                all=False,
            )
        except (ValueError, KeyError) as exc:
            logger.debug("Cannot find %s: %s", dep.spec, exc)
            return ResolvedDependency(
                spec=dep.spec, required=dep.required, status="missing",
            )

        assert isinstance(found, FoundResource)

        # ── Local hit ─────────────────────────────────────────────
        if found.is_local:
            local_path = Path(found.uri)
            file_hash = ""
            file_size: Optional[int] = None
            if local_path.exists():
                file_hash = _hash_file(local_path)
                file_size = local_path.stat().st_size
            return self._make_resolved(
                dep, found,
                status="local",
                local_path=local_path,
                file_hash=file_hash,
                file_size=file_size,
            )

        # ── Remote hit, download requested ────────────────────────
        if download:
            local_path = self._download.run(found, date)
            if isinstance(local_path, list):
                local_path = local_path[0]
            file_hash = ""
            file_size = None
            if local_path.exists():
                file_hash = _hash_file(local_path)
                file_size = local_path.stat().st_size
            return self._make_resolved(
                dep, found,
                status="downloaded",
                local_path=local_path,
                file_hash=file_hash,
                file_size=file_size,
            )

        # ── Remote hit, no download ───────────────────────────────
        return self._make_resolved(
            dep, found,
            status="remote",
            local_path=None,
            file_hash="",
            file_size=None,
        )

    @staticmethod
    def _make_resolved(
        dep: Dependency,
        found: FoundResource,
        *,
        status: str,
        local_path: Optional[Path],
        file_hash: str = "",
        file_size: Optional[int] = None,
    ) -> ResolvedDependency:
        """Build a ``ResolvedDependency`` from a find result."""
        remote_url = found.uri if not found.is_local else ""

        # Check for an existing sidecar lockfile
        lock_product: Optional[LockProduct] = None
        if local_path is not None and local_path.exists():
            lock_sidecar = local_path.parent / f"{local_path.name}.lock"
            if lock_sidecar.exists():
                with open(lock_sidecar) as f:
                    lock_product = LockProduct.model_validate(json.load(f))

        if lock_product is None:
            lock_product = LockProduct(
                name=dep.spec,
                description=dep.description or "",
                required=dep.required,
                url=remote_url,
                regex="",
                hash=file_hash,
                size=file_size,
                local_directory=str(local_path.parent) if local_path else "",
            )

        return ResolvedDependency(
            spec=dep.spec,
            required=dep.required,
            status=status,
            local_path=local_path,
            remote_url=remote_url,
            hash=file_hash,
            size=file_size,
            description=dep.description,
            lockfile=lock_product,
        )
