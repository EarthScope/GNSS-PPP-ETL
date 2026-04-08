"""
Author: Franklyn Dunbar

Read, write, build, and validate lockfile entries.

Provides pure-function helpers for the lockfile lifecycle:

* **Validate** — verify that a lock-product's sink file still exists
  and that its hash matches.
* **Build** — construct a :class:`LockProduct` from a local or cloud file,
  computing its SHA-256 hash and byte size.
* **Read / Write** — serialize and deserialize individual
  :class:`LockProduct` sidecar JSON files and date-scoped
  :class:`DependencyLockFile` manifests.

All path arguments accept local :class:`~pathlib.Path` objects and cloud
URIs / :class:`~cloudpathlib.CloudPath` objects interchangeably via
:func:`~gnss_product_management.utilities.paths.as_path`.
"""

import datetime
import enum
from importlib.metadata import version as _get_package_version
from pathlib import Path
from typing import List, Optional, Tuple
import logging
from gnss_product_management.lockfile.models import (
    DependencyLockFile,
    LockProduct,
    LockProductAlternative,
)
from gnss_product_management.utilities.helpers import hash_file as _hash_file
from gnss_product_management.utilities.paths import AnyPath, as_path

logger = logging.getLogger(__name__)


def get_package_version() -> str:
    """Return the installed gnss-product-management version."""
    try:
        return _get_package_version("gnss-product-management")
    except Exception:
        return "0.0.0-dev"


class HashMismatchMode(enum.Enum):
    """How to handle hash mismatches during lockfile validation."""

    WARN = "warn"
    STRICT = "strict"


def validate_lock_product(
    product: LockProduct,
    mode: HashMismatchMode = HashMismatchMode.WARN,
) -> bool:
    """Check that a lock-product's sink file exists and its hash matches.

    Also accepts the decompressed version of a ``.gz`` sink
    (e.g. ``foo.SP3`` when the lock records ``foo.SP3.gz``).

    Args:
        product: The lock-product entry to validate.
        mode: How to handle hash mismatches.
            ``WARN`` logs a warning but returns ``True``.
            ``STRICT`` returns ``False`` so the caller can re-download.

    Returns:
        ``True`` if the sink file (or its decompressed counterpart)
        exists and (when a hash is recorded) the file's current
        SHA-256 matches the stored hash (or mode is WARN).
    """
    sink_path = as_path(product.sink)

    # Accept the decompressed version when the .gz is gone
    if not sink_path.exists() and sink_path.suffix == ".gz":
        decompressed = as_path(str(sink_path)[: -len(".gz")])
        if decompressed.exists():
            # Update the lock product to point to the decompressed file
            product.sink = str(decompressed)
            product.hash = _hash_file(decompressed)
            product.size = decompressed.stat().st_size
            return True

    if not sink_path.exists():
        logger.warning(
            f"Lock product validation failed: sink file does not exist: {sink_path}"
        )
        return False
    if product.hash:
        actual_hash = _hash_file(sink_path)
        if actual_hash != product.hash:
            if mode == HashMismatchMode.STRICT:
                logger.warning(
                    f"Hash mismatch for {sink_path} (strict mode): "
                    f"expected {product.hash}, got {actual_hash}"
                )
                return False
            else:
                logger.warning(
                    f"Hash mismatch for {sink_path} (warn mode): "
                    f"expected {product.hash}, got {actual_hash}. "
                    f"Continuing with existing file."
                )
    return True


def build_lock_product(
    sink: AnyPath | str,
    url: str,
    name: str = "",
    description: str = "",
    alternative_urls: Optional[List[str]] = None,
) -> LockProduct:
    """Build a :class:`LockProduct` from a local or cloud file.

    Computes the SHA-256 hash and byte size of *sink* and packages
    them into a new ``LockProduct`` model.

    Args:
        sink: Path or URI to the file (local or cloud).
        url: Primary remote URL the file was downloaded from.
        name: Human-readable product name (e.g. ``'ORBIT'``).
        description: Free-text description of the product.
        alternative_urls: Optional mirror / fallback URLs.

    Returns:
        A fully-populated :class:`LockProduct`.

    Raises:
        FileNotFoundError: If *sink* does not exist.
    """
    sink_path = as_path(str(sink))
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


def get_lock_product_path(sink: AnyPath | str) -> AnyPath:
    """Return the ``_lock.json`` sidecar path for a sink file.

    Works for both local paths and cloud URIs — the sidecar is placed
    alongside the data file in the same storage backend.

    Args:
        sink: Path or URI to the downloaded product file.

    Returns:
        A path (local or cloud) pointing to the companion lock JSON
        (``<sink>_lock.json``).

    Raises:
        FileNotFoundError: If *sink* does not exist.
    """
    sink_path = as_path(str(sink))
    if not sink_path.exists():
        raise FileNotFoundError(f"Sink path does not exist: {sink_path}")
    return as_path(str(sink_path) + "_lock.json")


def get_lock_product(sink: AnyPath | str) -> Optional[LockProduct]:
    """Read the :class:`LockProduct` sidecar JSON for *sink*.

    Args:
        sink: Path or URI to the downloaded product file.

    Returns:
        The deserialized :class:`LockProduct`, or ``None`` if the
        sidecar file does not exist.
    """
    lock_product_path = get_lock_product_path(sink)
    if not lock_product_path.exists():
        return None
    with lock_product_path.open("r") as f:
        lock_product_data = f.read()
    return LockProduct.model_validate_json(lock_product_data)


def write_lock_product(lock_product: LockProduct) -> AnyPath:
    """Write a :class:`LockProduct` to its sidecar ``_lock.json`` file.

    Args:
        lock_product: The lock entry to persist.

    Returns:
        Path (local or cloud) to the written sidecar file.
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
    package: str,
    task: str,
    date: str | datetime.datetime,
    version: str | None = None,
) -> str:
    """Derive the canonical filename for a dependency lockfile.

    The filename encodes package, task, year, day-of-year, and version
    so that each processing day gets its own file.  Station is **not**
    part of the identity.

    Args:
        package: Processing package name (e.g. ``'PRIDE'``).
        task: Processing task name (e.g. ``'PPP'``).
        date: Processing date as a ``datetime`` or ``'YYYY-MM-DD'`` string.
        version: gnss-product-management package version.  Defaults to the
            installed version.

    Returns:
        A filename string like ``PRIDE_PPP_2025_015_0.1.0_lock.json``.

    Raises:
        ValueError: If *date* cannot be parsed.
    """
    if version is None:
        version = get_package_version()

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
        "_".join([package, task, str(YYYY), str(DOY).zfill(3), version]) + "_lock.json"
    )


def get_dependency_lockfile(
    directory: AnyPath | str,
    package: str,
    task: str,
    date: datetime.datetime | str,
    version: str | None = None,
) -> Tuple[Optional[DependencyLockFile], Optional[AnyPath]]:
    """Read a :class:`DependencyLockFile` from *directory*.

    Args:
        directory: Folder (local or cloud) containing lockfile JSON files.
        package: Processing package name.
        task: Processing task name.
        date: Processing date used to derive the filename.
        version: gnss-product-management package version.  Defaults to
            the installed version.

    Returns:
        A ``(lockfile, path)`` tuple.  If the file does not exist,
        ``lockfile`` is ``None`` but ``path`` is still returned so
        the caller knows where to write a new one.
    """
    dir_path = as_path(str(directory))
    lockfile_name = get_dependency_lockfile_name(
        package=package, task=task, version=version, date=date
    )
    lockfile_path = dir_path / lockfile_name
    if not lockfile_path.exists():
        return None, lockfile_path

    dep_lockfile_data = lockfile_path.read_text(encoding="utf-8")
    return DependencyLockFile.model_validate_json(dep_lockfile_data), lockfile_path


def write_dependency_lockfile(
    lockfile: DependencyLockFile,
    directory: AnyPath | str,
    update: bool = False,
) -> AnyPath:
    """Write a :class:`DependencyLockFile` to *directory*.

    Args:
        lockfile: The lockfile model to persist.
        directory: Target directory (local path or cloud URI).
        update: If ``True``, overwrite an existing file.  Otherwise
            raise :class:`FileExistsError`.

    Returns:
        Path (local or cloud) to the written lockfile.

    Raises:
        FileExistsError: If the lockfile already exists and *update*
            is ``False``.
    """
    dir_path = as_path(str(directory))
    lockfile_name = get_dependency_lockfile_name(
        package=lockfile.package,
        task=lockfile.task,
        date=lockfile.date,
        version=lockfile.version,
    )
    lockfile_path = dir_path / lockfile_name
    if lockfile_path.exists() and not update:
        raise FileExistsError(
            f"Lockfile already exists: {lockfile_path}, consider incrementing the version."
        )
    dir_path.mkdir(parents=True, exist_ok=True)
    lockfile_path.write_text(lockfile.model_dump_json(indent=2), encoding="utf-8")
    return lockfile_path
