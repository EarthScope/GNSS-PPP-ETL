"""Author: Franklyn Dunbar

Path utilities — unified local/cloud path construction.

``as_path`` is the single entry point for converting URI strings into the
appropriate path object.  Callers never need to import :mod:`cloudpathlib`
directly; this module dispatches to :class:`~cloudpathlib.CloudPath` for
``s3://``, ``gs://``, and ``az://`` URIs and falls back to
:class:`~pathlib.Path` for everything else.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from cloudpathlib import CloudPath

# Convenience alias used throughout the package for type annotations.
AnyPath = Union[Path, CloudPath]

_CLOUD_SCHEMES = ("s3://", "gs://", "az://", "gcs://", "abfs://")


def as_path(uri: str | Path | CloudPath) -> AnyPath:
    """Return a :class:`~pathlib.Path` or :class:`~cloudpathlib.CloudPath`.

    Detects the scheme from *uri* and dispatches accordingly:

    * ``s3://``, ``gs://``, ``az://`` → :class:`~cloudpathlib.CloudPath`
    * anything else (including bare POSIX paths) → :class:`~pathlib.Path`

    Args:
        uri: A URI string, local path string, :class:`~pathlib.Path`, or
            :class:`~cloudpathlib.CloudPath`.

    Returns:
        The appropriate path object for the given URI.

    Examples::

        >>> as_path("/data/gnss")
        PosixPath('/data/gnss')
        >>> as_path("s3://my-bucket/gnss-data")
        S3Path('s3://my-bucket/gnss-data')
        >>> as_path(Path("/data/gnss"))
        PosixPath('/data/gnss')
    """
    if isinstance(uri, CloudPath):
        return uri
    s = str(uri)
    if any(s.startswith(scheme) for scheme in _CLOUD_SCHEMES):
        return CloudPath(s)
    return Path(s)
