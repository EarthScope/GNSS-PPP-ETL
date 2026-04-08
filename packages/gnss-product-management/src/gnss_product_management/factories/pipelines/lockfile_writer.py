"""Author: Franklyn Dunbar

LockfileWriter — write a :class:`DependencyResolution` to a lockfile.

Thin wrapper around :class:`LockfileManager` that converts a resolution
into a persisted, reproducible manifest.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import List, Optional

from gnss_product_management.lockfile.manager import LockfileManager
from gnss_product_management.lockfile.models import DependencyLockFile, LockProduct
from gnss_product_management.lockfile.operations import get_package_version
from gnss_product_management.specifications.dependencies.dependencies import (
    DependencyResolution,
)

logger = logging.getLogger(__name__)


class LockfileWriter:
    """Write a :class:`DependencyResolution` to a JSON lockfile.

    Args:
        lockfile_dir: Directory where lockfiles are stored.
        package: Package name (e.g. ``'PRIDE'``).
    """

    def __init__(self, lockfile_dir: Path, *, package: str = "PRIDE") -> None:
        self._manager = LockfileManager(lockfile_dir)
        self._package = package

    def write(
        self,
        resolution: DependencyResolution,
        date: datetime.datetime,
        *,
        version: Optional[str] = None,
    ) -> Path:
        """Persist *resolution* as a lockfile.

        Args:
            resolution: The completed dependency resolution.
            date: Processing date.
            version: Package version; defaults to the installed version.

        Returns:
            Path to the written lockfile.
        """
        products: List[LockProduct] = []
        for dep in resolution.fulfilled:
            url = str(dep.local_path) if dep.local_path else ""
            products.append(
                LockProduct(
                    name=dep.spec,
                    url=url,
                    description=f"Resolved via {dep.status}",
                )
            )

        lockfile = self._manager.build_aggregate(
            products=products,
            package=self._package,
            task=resolution.spec_name,
            date=date,
            version=version or get_package_version(),
        )
        return self._manager.save(lockfile)
