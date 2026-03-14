import datetime
from re import M
from tkinter import N
from .registry import MetaDataRegistry

GNSS_START_TIME = datetime.datetime(
    1980, 1, 6, tzinfo=datetime.timezone.utc
)  # GNSS start time


def _date_to_doy(date:datetime.datetime) -> str:
    """
    Convert a given date to the corresponding day of year (DOY) string.

    The DOY is calculated as the day number within the year, with leading zeros for single and double-digit days.

    Args:
        date (datetime.datetime): The date to be converted.

    Returns:
        str: The DOY string corresponding to the given date, formatted with leading zeros if necessary.
    """
    doy = date.timetuple().tm_yday
    if doy < 10:
        doy_str = f"00{doy}"
    elif doy < 100:
        doy_str = f"0{doy}"
    else:
        doy_str = str(doy)
    return doy_str

def _date_to_yyyymmdd(date: datetime.datetime) -> str:
    """
    Convert a given date to the corresponding YYYYMMDD string.

    The YYYYMMDD format is a common way to represent dates as a continuous string of digits, with the year followed by the month and day.

    Args:
        date (datetime.datetime): The date to be converted.
    Returns:
        str: The YYYYMMDD string corresponding to the given date.
    """
    return date.strftime("%Y%m%d")

@MetaDataRegistry.computed(
    name="DDD",
    pattern=None,
)
def _date_to_ddd(date:datetime.datetime) -> str:
    """
    Convert a given date to the corresponding DDD string.

    The DDD format represents the day of year (DOY) as a three-digit number, with leading zeros for single and double-digit days.

    Args:
        date (datetime.datetime): The date to be converted.
    Returns:
        str: The DDD string corresponding to the given date, formatted with leading zeros if necessary.
    """
    return _date_to_doy(date)


@MetaDataRegistry.computed(
    name="GPSWEEK",
    pattern=None,
    description="GPS week number since January 6, 1980"
)
def _date_to_gps_week(date:datetime.datetime) -> str:
    """
    Convert a given date to the corresponding GPS week number.

    The GPS week number is calculated as the number of weeks since the start of the GPS epoch (January 6, 1980).

    Args:
        date (datetime.datetime): The date to be converted.

    Returns:
        int: The GPS week number corresponding to the given date.
    """
    # get the number of weeks since the start of the GPS epoch


    time_since_epoch = date - GNSS_START_TIME
    gps_week = time_since_epoch.days // 7
    return str(gps_week)

@MetaDataRegistry.computed(
    name="YYYY",
    pattern=None,

)
def _date_to_yyyy(date:datetime.datetime) -> str:
    """
    Convert a given date to the corresponding YYYY string.

    The YYYY format represents the year as a four-digit number.

    Args:
        date (datetime.datetime): The date to be converted.
    Returns:
        str: The YYYY string corresponding to the given date.
    """
    return date.strftime("%Y")

@MetaDataRegistry.computed(
    name="DAY"
)
def _date_to_day(date:datetime.datetime) -> str:
    """
    Convert a given date to the corresponding DAY string.

    The DAY format represents the day of the month as a two-digit number, with leading zeros for single-digit days.

    Args:
        date (datetime.datetime): The date to be converted.
    Returns:
        str: The DAY string corresponding to the given date, formatted with leading zeros if necessary.
    """
    return date.strftime("%d").zfill(2)

@MetaDataRegistry.computed(
    name="MONTH"
)
def _date_to_month(date:datetime.datetime) -> str:
    """
    Convert a given date to the corresponding MONTH string.

    The MONTH format represents the month as a two-digit number, with leading zeros for single-digit months.

    Args:
        date (datetime.datetime): The date to be converted.
    Returns:
        str: The MONTH string corresponding to the given date, formatted with leading zeros if necessary.
    """
    return date.strftime("%m").zfill(2)

