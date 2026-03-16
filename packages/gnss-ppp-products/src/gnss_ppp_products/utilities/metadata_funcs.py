"""
Computed metadata field registrations for a ``_MetadataRegistry``.

This module defines the domain-specific date→metadata transformations
(DDD, GPSWEEK, YYYY, REFFRAME, …) and a single entry-point
:func:`register_computed_fields` that wires them all onto a given
registry instance.

Unlike the original ``assets/meta_spec/funcs.py`` this module does
**not** import a global singleton.  Instead the registry is passed
as an argument, keeping Specifications agnostic.

Usage::

    from gnss_ppp_products.specifications.metadata import _MetadataRegistry
    from gnss_ppp_products.utilities.metadata_funcs import register_computed_fields

    reg = _MetadataRegistry.load_from_yaml("meta_spec.yaml")
    register_computed_fields(reg)        # DDD, GPSWEEK, etc. now live
"""

from __future__ import annotations

import datetime
from enum import Enum


GNSS_START_TIME = datetime.datetime(
    1980, 1, 6, tzinfo=datetime.timezone.utc
)


class IGSAntexReferenceFrameType(Enum):
    """Reference frame types for ANTEX files."""

    IGS05 = "igs05"
    IGS08 = "igs08"
    IGS14 = "igs14"
    IGS20 = "igs20"
    IGSR3 = "igsR3"


# ------------------------------------------------------------------
# Helper functions (pure — no registry dependency)
# ------------------------------------------------------------------


def _date_to_doy(date: datetime.datetime) -> str:
    doy = date.timetuple().tm_yday
    if doy < 10:
        return f"00{doy}"
    elif doy < 100:
        return f"0{doy}"
    return str(doy)


def _date_to_yyyymmdd(date: datetime.datetime) -> str:
    return date.strftime("%Y%m%d")


# ------------------------------------------------------------------
# Computed field functions
# ------------------------------------------------------------------


def _ddd(date: datetime.datetime) -> str:
    return _date_to_doy(date)


def _gpsweek(date: datetime.datetime) -> str:
    time_since_epoch = date - GNSS_START_TIME
    gps_week = time_since_epoch.days // 7
    return str(gps_week)


def _yyyy(date: datetime.datetime) -> str:
    return date.strftime("%Y")


def _day(date: datetime.datetime) -> str:
    return date.strftime("%d").zfill(2)


def _month(date: datetime.datetime) -> str:
    return date.strftime("%m").zfill(2)


def _yy(date: datetime.datetime) -> str:
    return date.strftime("%y")


def _hh(date: datetime.datetime) -> str:
    return date.strftime("%H")


def _mm(date: datetime.datetime) -> str:
    return date.strftime("%M")


def _refframe(date: datetime.datetime) -> str:
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


_COMPUTED_FIELDS = [
    ("DDD",      _ddd,      None),
    ("GPSWEEK",  _gpsweek,  None),
    ("YYYY",     _yyyy,     None),
    ("DAY",      _day,      None),
    ("MONTH",    _month,    None),
    ("YY",       _yy,       None),
    ("HH",       _hh,       None),
    ("MM",       _mm,       None),
    ("REFFRAME", _refframe, None),
]


def register_computed_fields(registry) -> None:
    """Register all date-derived computed fields onto *registry*.

    Parameters
    ----------
    registry : _MetadataRegistry
        The metadata registry instance to extend.
    """
    for name, func, pattern in _COMPUTED_FIELDS:
        registry.computed(name=name, pattern=pattern)(func)
