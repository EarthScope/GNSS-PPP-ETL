"""
Author: Franklyn Dunbar

Lockfile manager — single facade for all lockfile operations.

Provides a unified interface for checking, loading, saving, and
sharing dependency lockfiles.  All callers (:class:`ResolvePipeline`,
:class:`PrideProcessor`, CLI) should go through :class:`LockfileManager`
rather than calling operations functions directly.

``lockfile_dir`` may be a local filesystem path or a cloud URI
(``s3://bucket/prefix``).  All reads and writes are dispatched through
:class:`~cloudpathlib.CloudPath` / :class:`~pathlib.Path` so the
manager is storage-agnostic.
"""

from __future__ import annotations

import datetime
import logging

from gnss_product_management.lockfile.models import DependencyLockFile, LockProduct
from gnss_product_management.lockfile.operations import (
    HashMismatchMode,
    get_dependency_lockfile_name,
    get_package_version,
    validate_lock_product,
)
from gnss_product_management.utilities.paths import AnyPath, as_path

logger = logging.getLogger(__name__)


class LockfileManager:
    """Facade for dependency lockfile lifecycle.

    Attributes:
        _dir: Directory where aggregate lockfiles are stored.

    Args:
        lockfile_dir: Directory for aggregate lockfile storage.  May be a
            local :class:`~pathlib.Path`, a URI string, or a
            :class:`~cloudpathlib.CloudPath` (e.g. ``s3://bucket/locks``).
    """

    def __init__(self, lockfile_dir: AnyPath | str) -> None:
        """Initialise the manager.

        Args:
            lockfile_dir: Directory for aggregate lockfile storage.
        """
        self._dir: AnyPath = as_path(str(lockfile_dir))

    @property
    def lockfile_dir(self) -> AnyPath:
        """The directory where aggregate lockfiles are stored."""
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
        """Check if a lockfile exists for the given identity.

        Args:
            package: Package name.
            task: Task name.
            date: Processing date.
            version: Optional package version.
        """
        name = get_dependency_lockfile_name(package=package, task=task, date=date, version=version)
        return (self._dir / name).exists()

    def load(
        self,
        package: str,
        task: str,
        date: datetime.datetime,
        version: str | None = None,
    ) -> tuple[DependencyLockFile | None, AnyPath]:
        """Load an existing lockfile, or ``None``.

        Args:
            package: Package name.
            task: Task name.
            date: Processing date.
            version: Optional package version.
        """
        name = get_dependency_lockfile_name(package=package, task=task, date=date, version=version)
        path = self._dir / name
        if not path.exists():
            return None, path
        return DependencyLockFile.model_validate_json(path.read_text(encoding="utf-8")), path

    def lockfile_path(
        self,
        package: str,
        task: str,
        date: datetime.datetime,
        version: str | None = None,
    ) -> AnyPath:
        """Return the expected path for a lockfile (may not exist yet).

        Args:
            package: Package name.
            task: Task name.
            date: Processing date.
            version: Optional package version.
        """
        name = get_dependency_lockfile_name(package=package, task=task, date=date, version=version)
        return self._dir / name

    # ------------------------------------------------------------------ #
    # Write
    # ------------------------------------------------------------------ #

    def save(self, lockfile: DependencyLockFile) -> AnyPath:
        """Write (or overwrite) an aggregate lockfile.

        Returns:
            Path (local or cloud) to the written file.
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
        products: list[LockProduct],
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

        date_str = date.strftime("%Y-%m-%d") if isinstance(date, datetime.datetime) else date

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
    ) -> AnyPath:
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
        path: AnyPath | str,
        strict: bool = False,
    ) -> DependencyLockFile:
        """Import a lockfile from another machine or cloud location.

        Validates each product's hash.  In warn mode (default),
        mismatches are logged but products are kept.  In strict
        mode, invalid products are removed so the caller can
        re-resolve them.

        Args:
            path: Path or URI to the lockfile JSON to import.
            strict: If ``True``, remove products with hash mismatches.

        Returns:
            The imported (and possibly pruned) lockfile.
        """
        path = as_path(str(path))
        data = path.read_text(encoding="utf-8")
        lockfile = DependencyLockFile.model_validate_json(data)

        mode = HashMismatchMode.STRICT if strict else HashMismatchMode.WARN
        valid_products: list[LockProduct] = []
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
        """Return the canonical lockfile filename for the given identity.

        Args:
            package: Package name.
            task: Task name.
            date: Processing date.
            version: Optional package version.
        """
        return get_dependency_lockfile_name(package=package, task=task, date=date, version=version)
