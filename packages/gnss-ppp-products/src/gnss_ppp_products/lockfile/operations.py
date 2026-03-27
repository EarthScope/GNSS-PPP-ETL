"""Read, write, build, and validate lockfile entries."""

import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from gnss_ppp_products.lockfile.models import (
    DependencyLockFile,
    LockProduct,
    LockProductAlternative,
)
from gnss_ppp_products.utilities.helpers import hash_file as _hash_file


def validate_lock_product(product: LockProduct) -> bool:
    """Check that the sink path exists and its hash matches the lock entry."""
    sink_path = Path(product.sink)
    if not sink_path.exists():
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
    """Build a ``LockProduct`` from a local file, computing its hash and size."""
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
    """Return the ``_lock.json`` sidecar path for a sink file."""
    sink = Path(sink)
    if not sink.exists():
        raise FileNotFoundError(f"Sink path does not exist: {sink}")
    return Path(str(sink) + "_lock.json")


def get_lock_product(sink: Path | str) -> Optional[LockProduct]:
    """Read the ``LockProduct`` sidecar JSON for *sink*, or ``None`` if absent."""
    lock_product_path = get_lock_product_path(sink)
    if not lock_product_path.exists():
        return None
    with open(lock_product_path, "r") as f:
        lock_product_data = f.read()
    return LockProduct.model_validate_json(lock_product_data)


def write_lock_product(lock_product: LockProduct) -> Path:
    """Write a ``LockProduct`` to its sidecar ``_lock.json`` file."""
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
    """Derive the canonical filename for a dependency lockfile."""
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
    """Read a ``DependencyLockFile`` from *directory*, or ``(None, path)`` if absent."""
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
    """Write a ``DependencyLockFile`` to *directory*."""
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
