"""Author: Franklyn Dunbar

Shared helper functions and sentinel types.

Contains low-level utilities used across the package:

* :func:`hash_file` — SHA-256 file hashing.
* :func:`_ensure_datetime` — date/datetime normalisation to UTC.
* :class:`_PassthroughDict` — dict that preserves ``{key}`` for missing keys.
* :func:`_listify` — coerce scalars to single-element lists.
* :func:`expand_dict_combinations` — Cartesian product of dict values.
"""

import datetime
import gzip
import hashlib
import itertools
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file.

    Args:
        path: Filesystem path to the file to hash.

    Returns:
        A string in the form ``sha256:<hex_digest>``.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def decompress_gzip(file_path: Path, dest_dir: Path | None = None) -> Path | None:
    """Decompress a gzip file and remove the original.

    Args:
        file_path: Path to the ``.gz`` file.
        dest_dir: Destination directory for the decompressed file.
            Defaults to the same directory as *file_path*.

    Returns:
        Path to the decompressed file, or ``None`` on failure.
    """
    if not file_path.exists():
        return None

    out_path = file_path.with_suffix("")
    if dest_dir is not None:
        dest_dir.mkdir(parents=True, exist_ok=True)
        out_path = dest_dir / out_path.name

    try:
        with gzip.open(file_path, "rb") as f_in, open(out_path, "wb") as f_out:
            f_out.write(f_in.read())
    except (EOFError, OSError) as exc:
        logger.error("Failed to decompress %s: %s", file_path, exc)
        out_path.unlink(missing_ok=True)
        return None

    file_path.unlink(missing_ok=True)
    return out_path


def _ensure_datetime(date: datetime.date | datetime.datetime) -> datetime.datetime:
    """Coerce a date to a timezone-aware ``datetime`` (UTC).

    Args:
        date: A :class:`~datetime.date` or :class:`~datetime.datetime`.
            Naive datetimes are tagged as UTC.

    Returns:
        A timezone-aware :class:`~datetime.datetime` in UTC.
    """
    if isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
        return datetime.datetime(
            date.year, date.month, date.day, tzinfo=datetime.timezone.utc
        )
    if date.tzinfo is None:
        return date.replace(tzinfo=datetime.timezone.utc)
    return date


class _PassthroughDict(dict):
    """Dict subclass that returns ``'{key}'`` for missing keys.

    Used with :meth:`str.format_map` so that unresolved placeholders
    survive template expansion rather than raising :class:`KeyError`.
    """

    def __missing__(self, key):
        return f"{{{key}}}"


def _listify(v) -> list[str]:
    """Convert ``None`` or a single string to a list.

    Args:
        v: ``None``, a single string, or an existing list.

    Returns:
        A (possibly empty) ``list[str]``.
    """
    if v is None:
        return []
    return [v] if isinstance(v, str) else list(v)


def expand_dict_combinations(d: dict[str, list[str]]) -> list[dict[str, str]]:
    """Compute the Cartesian product of dict values.

    Args:
        d: Mapping from parameter names to lists of candidate values.

    Returns:
        A list of dicts, one per combination, with a single value per key.

    Example::

        >>> expand_dict_combinations({"A": ["1","2"], "B": ["x","y"]})
        [{"A":"1","B":"x"}, {"A":"1","B":"y"}, {"A":"2","B":"x"}, {"A":"2","B":"y"}]
    """
    keys = list(d.keys())
    vals = [d[k] for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*vals)]
