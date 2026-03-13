import datetime

from .base import IGSAntexReferenceFrameType
from ..utils import date_to_gps_week,gps_week_to_date


def determine_frame(
    date: datetime.date | datetime.datetime,
) -> IGSAntexReferenceFrameType:
    """Determine the appropriate IGS frame based on date."""
    if isinstance(date, datetime.datetime):
        date = date.date()

    if date >= datetime.date(2022, 11, 27):
        return IGSAntexReferenceFrameType.IGS20
    elif date >= datetime.date(2017, 1, 29):
        return IGSAntexReferenceFrameType.IGS14
    elif date >= datetime.date(2011,4,17):
        return IGSAntexReferenceFrameType.IGS08
    elif date >= datetime.date(2006, 11, 5):
        return IGSAntexReferenceFrameType.IGS05  # Assuming a placeholder for the earliest frame
    else:
        raise ValueError(f"No suitable IGS frame found for date {date}")
    