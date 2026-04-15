"""Computed metadata field registrations for a :class:`ParameterCatalog`.

Defines date-to-metadata transformations (``DDD``, ``GPSWEEK``, ``YYYY``,
``REFFRAME``, etc.) and :func:`register_computed_fields` which wires
them onto a catalog so that parameter values can be derived from a
processing date at query time.

Usage::

    from gnss_product_management.specifications.parameters.parameter import ParameterCatalog
    from gnss_product_management.utilities.metadata_funcs import register_computed_fields

    cat = ParameterCatalog.from_yaml("meta_spec.yaml")
    register_computed_fields(cat)
"""

from __future__ import annotations

import datetime
from enum import Enum

# GPS epoch used for GPS-week calculations.
GNSS_START_TIME = datetime.datetime(1980, 1, 6, tzinfo=datetime.timezone.utc)


class IGSAntexReferenceFrameType(Enum):
    """IGS ANTEX reference frame identifiers.

    Maps each IGS reference frame to its canonical lowercase string
    used in ANTEX filenames (e.g. ``igs20.atx``).
    """

    IGS05 = "igs05"
    IGS08 = "igs08"
    IGS14 = "igs14"
    IGS20 = "igs20"
    IGSR3 = "igsR3"


# ------------------------------------------------------------------
# Helper functions (pure — no registry dependency)
# ------------------------------------------------------------------


def _date_to_doy(date: datetime.datetime) -> str:
    """Convert a datetime to a zero-padded day-of-year string (001–366)."""
    doy = date.timetuple().tm_yday
    if doy < 10:
        return f"00{doy}"
    elif doy < 100:
        return f"0{doy}"
    return str(doy)


# ------------------------------------------------------------------
# Computed field functions
# ------------------------------------------------------------------


def _ddd(date: datetime.datetime) -> str:
    """Compute day-of-year (``DDD``) from *date*."""
    return _date_to_doy(date)


def _gpsweek(date: datetime.datetime) -> str:
    """Compute the GPS week number from *date*."""
    time_since_epoch = date - GNSS_START_TIME
    gps_week = time_since_epoch.days // 7
    return str(gps_week)


def _yyyy(date: datetime.datetime) -> str:
    """Return four-digit year (``YYYY``)."""
    return date.strftime("%Y")


def _day(date: datetime.datetime) -> str:
    """Return zero-padded day of month (``DD``)."""
    return date.strftime("%d").zfill(2)


def _month(date: datetime.datetime) -> str:
    """Return zero-padded month (``MM``)."""
    return date.strftime("%m").zfill(2)


def _yy(date: datetime.datetime) -> str:
    """Return two-digit year (``YY``)."""
    return date.strftime("%y")


def _hh(date: datetime.datetime) -> str:
    """Return zero-padded hour (``HH``)."""
    return date.strftime("%H")


def _mm(date: datetime.datetime) -> str:
    """Return zero-padded minute (``MM``)."""
    return date.strftime("%M")


def _refframe(date: datetime.datetime) -> str:
    """Return the IGS ANTEX reference frame string for *date*."""
    d = date.date() if isinstance(date, datetime.datetime) else date
    if d >= datetime.date(2022, 11, 27):
        return IGSAntexReferenceFrameType.IGS20.value
    elif d >= datetime.date(2017, 1, 29):
        return IGSAntexReferenceFrameType.IGS14.value
    elif d >= datetime.date(2011, 4, 17):
        return IGSAntexReferenceFrameType.IGS08.value
    elif d >= datetime.date(2006, 11, 5):
        return IGSAntexReferenceFrameType.IGS05.value
    else:
        return ""


# ------------------------------------------------------------------
# Registration entry-point
# ------------------------------------------------------------------


# (name, compute_function, pattern) triples registered onto every ParameterCatalog.
_COMPUTED_FIELDS = [
    ("DDD", _ddd, None),
    ("GPSWEEK", _gpsweek, None),
    ("YYYY", _yyyy, None),
    ("DAY", _day, None),
    ("MONTH", _month, None),
    ("YY", _yy, None),
    ("HH", _hh, None),
    ("MM", _mm, None),
    ("REFFRAME", _refframe, None),
]


def register_computed_fields(registry) -> None:
    """Register all date-derived computed fields onto *registry*.

    Iterates over the built-in ``_COMPUTED_FIELDS`` list and calls
    ``registry.computed()`` for each one, wiring the pure date
    transformation functions into the catalog.

    Args:
        registry: A :class:`ParameterCatalog` instance to extend.
    """
    for name, func, pattern in _COMPUTED_FIELDS:
        registry.computed(name=name, pattern=pattern)(func)
