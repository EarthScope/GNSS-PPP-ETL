"""LockfileWriter — serialize a DependencyResolution to a lockfile on disk."""

from __future__ import annotations

import datetime
import logging
from pathlib import Path

from gnss_ppp_products.specifications.dependencies.dependencies import DependencyResolution

logger = logging.getLogger(__name__)


class LockfileWriter:
    """Write a ``DependencyResolution`` to a JSON lockfile.

    Lockfiles are written to ``{base_dir}/.locks/{spec_name}_{date}.lock.json``
    and can be read back via ``ProductLockfile.from_json_file()``.

    Parameters
    ----------
    base_dir
        Root directory for local product storage.  The ``.locks/``
        subdirectory will be created automatically.

    Example
    -------
    ::

        writer = LockfileWriter(env.base_dir)
        path = writer.write(resolution, date=dt)
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def write(
        self,
        resolution: DependencyResolution,
        date: datetime.datetime,
    ) -> Path:
        """Serialize a resolution to a lockfile.

        Parameters
        ----------
        resolution
            The completed dependency resolution.
        date
            The processing date (used in the lockfile filename and metadata).

        Returns
        -------
        Path
            Path to the written lockfile.
        """
        lock_dir = self._base_dir / "locks"
        lock_dir.mkdir(parents=True, exist_ok=True)

        date_str = date.strftime("%Y%j")
        lock_path = lock_dir / f"{resolution.spec_name}_{date_str}.lock.json"

        lockfile = resolution.to_lockfile(date=date_str)
        lockfile.task_id = resolution.spec_name
        lockfile.to_json_file(lock_path)

        logger.info("Wrote lockfile %s", lock_path)
        return lock_path
