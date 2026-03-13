import datetime
from typing import Tuple

GNSS_START_TIME = datetime.datetime(
    1980, 1, 6, tzinfo=datetime.timezone.utc
)  # GNSS start time


def parse_date(date: datetime.date | datetime.datetime) -> Tuple[str, str]:
    """
    Parse a date or datetime object and return the year and day of year (DOY) as strings.
    Args:
        date (datetime.date | datetime.datetime): The date or datetime object to parse.
    Returns:
        Tuple[str, str]: A tuple containing the year and the day of year (DOY) as strings.
    """

    if isinstance(date, datetime.datetime):
        date = date.date()
    year = str(date.year)
    doy = date.timetuple().tm_yday
    if doy < 10:
        doy = f"00{doy}"
    elif doy < 100:
        doy = f"0{doy}"
    doy = str(doy)
    return year, doy


def date_to_gps_week(date: datetime.date | datetime.datetime) -> int:
    """
    Convert a given date to the corresponding GPS week number.

    The GPS week number is calculated as the number of weeks since the start of the GPS epoch (January 6, 1980).

    Args:
        date (datetime.date | datetime.datetime): The date to be converted. Can be either a datetime.date or datetime.datetime object.

    Returns:
        int: The GPS week number corresponding to the given date.
    """
    # get the number of weeks since the start of the GPS epoch

    if isinstance(date, datetime.datetime):
        date = date.date()
    time_since_epoch = date - GNSS_START_TIME.date()
    gps_week = time_since_epoch.days // 7
    return gps_week

def gps_week_to_date(gps_week: int) -> datetime.datetime:
    """
    Convert a GPS week number to the corresponding date.

    The GPS week number is calculated as the number of weeks since the start of the GPS epoch (January 6, 1980).

    Args:
        gps_week (int): The GPS week number to be converted.
    Returns:
        datetime.datetime: The date corresponding to the given GPS week number.
    """
    date = GNSS_START_TIME + datetime.timedelta(weeks=gps_week)
    return date.astimezone(datetime.timezone.utc)