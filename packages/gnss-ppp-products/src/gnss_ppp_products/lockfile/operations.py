"""
Author: Franklyn Dunbar

Read, write, build, and validate lockfile entries.

Provides pure-function helpers for the lockfile lifecycle:

* **Validate** — verify that a lock-product's sink file still exists
  and that its hash matches.
* **Build** — construct a :class:`LockProduct` from a local file,
  computing its SHA-256 hash and byte size.
* **Read / Write** — serialize and deserialize individual
  :class:`LockProduct` sidecar JSON files and date-scoped
  :class:`DependencyLockFile` manifests.
"""

import datetime
from pathlib import Path
from typing import List, Optional, Tuple
import logging
from venv import logger
from gnss_ppp_products.lockfile.models import (
    DependencyLockFile,
    LockProduct,
    LockProductAlternative,
)
from gnss_ppp_products.utilities.helpers import hash_file as _hash_file

logger  = logging.getLogger(__name__)

def validate_lock_product(product: LockProduct) -> bool:
    """Check that a lock-product's sink file exists and its hash matches.

    Args:
        product: The lock-product entry to validate.

    Returns:
        ``True`` if the sink file exists and (when a hash is recorded)
        the file's current SHA-256 matches the stored hash.
    """
    sink_path = Path(product.sink)
    if not sink_path.exists():
        logger.warning(f"Lock product validation failed: sink file does not exist: {sink_path}")
        return False
    if product.hash:
        actual_hash = _hash_file(sink_path)
        if actual_hash != product.hash:
            return False
    return True


def build_lock_product(
    sink: Path | str,
    url: str,
    name: str = "",
    description: str = "",
    alternative_urls: Optional[List[str]] = None,
) -> LockProduct:
    """Build a :class:`LockProduct` from a local file.

    Computes the SHA-256 hash and byte size of *sink* and packages
    them into a new ``LockProduct`` model.

    Args:
        sink: Path to the local file.
        url: Primary remote URL the file was downloaded from.
        name: Human-readable product name (e.g. ``'ORBIT'``).
        description: Free-text description of the product.
        alternative_urls: Optional mirror / fallback URLs.

    Returns:
        A fully-populated :class:`LockProduct`.

    Raises:
        FileNotFoundError: If *sink* does not exist on disk.
    """
    sink_path = Path(sink)
    if not sink_path.exists():
        raise FileNotFoundError(f"Sink path does not exist: {sink_path}")
    hash_value = _hash_file(sink_path)
    size = sink_path.stat().st_size
    return LockProduct(
        name=name,
        description=description,
        url=url,
        sink=str(sink_path),
        hash=hash_value,
        size=size,
        alternatives=[
            LockProductAlternative(url=alt_url) for alt_url in (alternative_urls or [])
        ],
    )


def get_lock_product_path(sink: Path | str) -> Path:
    """Return the ``_lock.json`` sidecar path for a sink file.

    Args:
        sink: Path to the downloaded product file.

    Returns:
        A :class:`Path` pointing to the companion lock JSON
        (``<sink>_lock.json``).

    Raises:
        FileNotFoundError: If *sink* does not exist.
    """
    sink = Path(sink)
    if not sink.exists():
        raise FileNotFoundError(f"Sink path does not exist: {sink}")
    return Path(str(sink) + "_lock.json")


def get_lock_product(sink: Path | str) -> Optional[LockProduct]:
    """Read the :class:`LockProduct` sidecar JSON for *sink*.

    Args:
        sink: Path to the downloaded product file.

    Returns:
        The deserialized :class:`LockProduct`, or ``None`` if the
        sidecar file does not exist.
    """
    lock_product_path = get_lock_product_path(sink)
    if not lock_product_path.exists():
        return None
    with open(lock_product_path, "r") as f:
        lock_product_data = f.read()
    return LockProduct.model_validate_json(lock_product_data)


def write_lock_product(lock_product: LockProduct) -> Path:
    """Write a :class:`LockProduct` to its sidecar ``_lock.json`` file.

    Args:
        lock_product: The lock entry to persist.

    Returns:
        Path to the written sidecar file.
    """
    lock_product_path = get_lock_product_path(lock_product.sink)
    lock_product_path.write_text(
        lock_product.model_dump_json(indent=2), encoding="utf-8"
    )
    return lock_product_path


# ---------------------------------------------------------------------------
# Dependency lockfile (collection of LockProducts for one processing day)
# ---------------------------------------------------------------------------


def get_dependency_lockfile_name(
    station: Optional[str],
    package: str,
    task: str,
    date: str | datetime.datetime,
    version: str = "0",
) -> str:
    """Derive the canonical filename for a dependency lockfile.

    The filename encodes station, package, task, year, day-of-year,
    and version so that each processing day gets its own file.

    Args:
        station: Station identifier (e.g. ``'ALIC'``), or ``None``.
        package: Processing package name (e.g. ``'PRIDE'``).
        task: Processing task name (e.g. ``'PPP'``).
        date: Processing date as a ``datetime`` or ``'YYYY-MM-DD'`` string.
        version: Lockfile format version (default ``'0'``).

    Returns:
        A filename string like ``ALIC_PRIDE_PPP_2024_015_0_lock.json``.

    Raises:
        ValueError: If *date* cannot be parsed.
    """
    if isinstance(date, str):
        try:
            date = datetime.datetime.strptime(date, "%Y-%m-%d")
        except Exception:
            try:
                date = datetime.datetime.fromisoformat(date)
            except Exception as e:
                raise ValueError(
                    f"Invalid date format: {date}. Expected YYYY-MM-DD or ISO format."
                ) from e

    try:
        YYYY, DOY = date.strftime("%Y"), date.timetuple().tm_yday
    except Exception as e:
        raise ValueError(
            f"Invalid date value: {date}. Expected datetime or string in YYYY-MM-DD format."
        ) from e

    return (
        "_".join([station or "", package, task, str(YYYY), str(DOY).zfill(3), version])
        + "_lock.json"
    )


def get_dependency_lockfile(
    directory: Path,
    station: Optional[str],
    package: str,
    task: str,
    version: str = "0",
    date: Optional[datetime.datetime | str] = None,
) -> Tuple[Optional[DependencyLockFile], Optional[Path]]:
    """Read a :class:`DependencyLockFile` from *directory*.

    Args:
        directory: Folder containing lockfile JSON files.
        station: Station identifier (e.g. ``'ALIC'``).
        package: Processing package name.
        task: Processing task name.
        version: Lockfile format version.
        date: Processing date used to derive the filename.

    Returns:
        A ``(lockfile, path)`` tuple.  If the file does not exist,
        ``lockfile`` is ``None`` but ``path`` is still returned so
        the caller knows where to write a new one.
    """
    lockfile_name = get_dependency_lockfile_name(
        station=station, package=package, task=task, version=version, date=date
    )
    lockfile_path = directory / lockfile_name
    if not lockfile_path.exists():
        return None, lockfile_path

    dep_lockfile_data = lockfile_path.read_text(encoding="utf-8")
    return DependencyLockFile.model_validate_json(dep_lockfile_data), lockfile_path


def write_dependency_lockfile(
    lockfile: DependencyLockFile,
    directory: Path,
    update: bool = False,
) -> Path:
    """Write a :class:`DependencyLockFile` to *directory*.

    Args:
        lockfile: The lockfile model to persist.
        directory: Target directory on disk.
        update: If ``True``, overwrite an existing file.  Otherwise
            raise :class:`FileExistsError`.

    Returns:
        Path to the written lockfile.

    Raises:
        FileExistsError: If the lockfile already exists and *update*
            is ``False``.
    """
    lockfile_name = get_dependency_lockfile_name(
        lockfile.station, lockfile.package, lockfile.task, date=lockfile.date
    )
    lockfile_path = directory / lockfile_name
    if lockfile_path.exists() and not update:
        raise FileExistsError(
            f"Lockfile already exists: {lockfile_path}, consider incrementing the version."
        )
    lockfile_path.write_text(lockfile.model_dump_json(indent=2), encoding="utf-8")
    return lockfile_path
