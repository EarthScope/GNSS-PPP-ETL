"""Shared helper functions and sentinel types."""

import datetime
import itertools


def _ensure_datetime(date: datetime.date | datetime.datetime) -> datetime.datetime:
    """Coerce a date to a timezone-aware datetime (UTC)."""
    if isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
        return datetime.datetime(date.year, date.month, date.day, tzinfo=datetime.timezone.utc)
    if date.tzinfo is None:
        return date.replace(tzinfo=datetime.timezone.utc)
    return date


class _PassthroughDict(dict):
    """Returns '{key}' for any key not in the dict, so unresolved placeholders survive."""

    def __missing__(self, key):
        return f"{{{key}}}"


def _listify(v) -> list[str]:
    """Convert None or a single string to a list; pass through lists unchanged."""
    if v is None:
        return []
    return [v] if isinstance(v, str) else list(v)


def expand_dict_combinations(d: dict[str, list[str]]) -> list[dict[str, str]]:
    """Cartesian product of dict values.

    >>> expand_dict_combinations({"A": ["1","2"], "B": ["x","y"]})
    [{"A":"1","B":"x"}, {"A":"1","B":"y"}, {"A":"2","B":"x"}, {"A":"2","B":"y"}]
    """
    keys = list(d.keys())
    vals = [d[k] for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*vals)]
