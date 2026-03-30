"""
Author: Franklyn Dunbar

Lockfile manager — single facade for all lockfile operations.

Provides a unified interface for checking, loading, saving, and
sharing dependency lockfiles.  All callers (DependencyResolver,
PrideProcessor, CLI) should go through :class:`LockfileManager`
rather than calling operations functions directly.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import List, Optional

from gnss_ppp_products.lockfile.models import DependencyLockFile, LockProduct
from gnss_ppp_products.lockfile.operations import (
    HashMismatchMode,
    get_dependency_lockfile_name,
    get_package_version,
    validate_lock_product,
)

logger = logging.getLogger(__name__)


class LockfileManager:
    """Facade for dependency lockfile lifecycle.

    Args:
        lockfile_dir: Directory where aggregate lockfiles are stored.
    """

    def __init__(self, lockfile_dir: Path) -> None:
        self._dir = lockfile_dir

    @property
    def lockfile_dir(self) -> Path:
        return self._dir

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #

    def exists(
        self,
        package: str,
        task: str,
        date: datetime.datetime,
        version: str | None = None,
    ) -> bool:
        """Check if a lockfile exists for the given identity."""
        name = get_dependency_lockfile_name(
            package=package, task=task, date=date, version=version
        )
        return (self._dir / name).exists()

    def load(
        self,
        package: str,
        task: str,
        date: datetime.datetime,
        version: str | None = None,
    ) -> Optional[DependencyLockFile]:
        """Load an existing lockfile, or ``None``."""
        name = get_dependency_lockfile_name(
            package=package, task=task, date=date, version=version
        )
        path = self._dir / name
        if not path.exists():
            return None
        return DependencyLockFile.model_validate_json(path.read_text(encoding="utf-8"))

    def lockfile_path(
        self,
        package: str,
        task: str,
        date: datetime.datetime,
        version: str | None = None,
    ) -> Path:
        """Return the expected path for a lockfile (may not exist yet)."""
        name = get_dependency_lockfile_name(
            package=package, task=task, date=date, version=version
        )
        return self._dir / name

    # ------------------------------------------------------------------ #
    # Write
    # ------------------------------------------------------------------ #

    def save(self, lockfile: DependencyLockFile) -> Path:
        """Write (or overwrite) an aggregate lockfile.

        Returns:
            Path to the written file.
        """
        name = get_dependency_lockfile_name(
            package=lockfile.package,
            task=lockfile.task,
            date=lockfile.date,
            version=lockfile.version,
        )
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / name
        path.write_text(lockfile.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Wrote lockfile %s", path)
        return path

    def build_aggregate(
        self,
        products: List[LockProduct],
        package: str,
        task: str,
        date: datetime.datetime | str,
        version: str | None = None,
    ) -> DependencyLockFile:
        """Build a :class:`DependencyLockFile` from per-file sidecar products.

        Args:
            products: Lock products collected from sidecar files.
            package: Package name (e.g. ``'PRIDE'``).
            task: Task name (e.g. ``'PPP'``).
            date: Processing date.
            version: Package version; defaults to installed version.

        Returns:
            A new :class:`DependencyLockFile` ready to be saved.
        """
        if version is None:
            version = get_package_version()

        date_str = (
            date.strftime("%Y-%m-%d") if isinstance(date, datetime.datetime) else date
        )

        return DependencyLockFile(
            date=date_str,
            package=package,
            task=task,
            version=version,
            products=list(products),
        )

    # ------------------------------------------------------------------ #
    # Import / Export
    # ------------------------------------------------------------------ #

    def export_lockfile(
        self,
        package: str,
        task: str,
        date: datetime.datetime,
        version: str | None = None,
    ) -> Path:
        """Return the path to the aggregate lockfile for sharing.

        Raises:
            FileNotFoundError: If no lockfile exists for the identity.
        """
        path = self.lockfile_path(package, task, date, version)
        if not path.exists():
            raise FileNotFoundError(f"No lockfile at {path}")
        return path

    def import_lockfile(
        self,
        path: Path,
        strict: bool = False,
    ) -> DependencyLockFile:
        """Import a lockfile from another machine.

        Validates each product's hash.  In warn mode (default),
        mismatches are logged but products are kept.  In strict
        mode, invalid products are removed so the caller can
        re-resolve them.

        Args:
            path: Path to the lockfile JSON to import.
            strict: If ``True``, remove products with hash mismatches.

        Returns:
            The imported (and possibly pruned) lockfile.
        """
        data = path.read_text(encoding="utf-8")
        lockfile = DependencyLockFile.model_validate_json(data)

        mode = HashMismatchMode.STRICT if strict else HashMismatchMode.WARN
        valid_products: List[LockProduct] = []
        for product in lockfile.products:
            if validate_lock_product(product, mode=mode):
                valid_products.append(product)
            else:
                logger.warning(
                    "Dropping invalid product %s from imported lockfile",
                    product.name,
                )
        lockfile.products = valid_products
        return lockfile

    # ------------------------------------------------------------------ #
    # Naming (static)
    # ------------------------------------------------------------------ #

    @staticmethod
    def lockfile_name(
        package: str,
        task: str,
        date: datetime.datetime,
        version: str | None = None,
    ) -> str:
        """Canonical filename (no station)."""
        return get_dependency_lockfile_name(
            package=package, task=task, date=date, version=version
        )
