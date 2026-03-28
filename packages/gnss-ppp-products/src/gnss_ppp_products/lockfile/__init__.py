"""
Author: Franklyn Dunbar

Lockfile — models and I/O for reproducible product manifests.

This package provides Pydantic models and file-system operations for
creating, reading, writing, and validating *lockfiles*.  A lockfile
records the exact resolved products (with hashes, sizes, and source
URLs) for a single processing date, enabling reproducible GNSS PPP
runs.

Public API
----------
Models:
    :class:`LockProduct`, :class:`LockProductAlternative`,
    :class:`DependencyLockFile`

Operations:
    :func:`validate_lock_product`, :func:`build_lock_product`,
    :func:`get_lock_product_path`, :func:`get_lock_product`,
    :func:`write_lock_product`, :func:`get_dependency_lockfile_name`,
    :func:`get_dependency_lockfile`, :func:`write_dependency_lockfile`
"""

from gnss_ppp_products.lockfile.models import (
    LockProduct,
    LockProductAlternative,
    DependencyLockFile,
)
from gnss_ppp_products.lockfile.operations import (
    validate_lock_product,
    build_lock_product,
    get_lock_product_path,
    get_lock_product,
    write_lock_product,
    get_dependency_lockfile_name,
    get_dependency_lockfile,
    write_dependency_lockfile,
)

__all__ = [
    # models
    "LockProduct",
    "LockProductAlternative",
    "DependencyLockFile",
    # operations
    "validate_lock_product",
    "build_lock_product",
    "get_lock_product_path",
    "get_lock_product",
    "write_lock_product",
    "get_dependency_lockfile_name",
    "get_dependency_lockfile",
    "write_dependency_lockfile",
]
