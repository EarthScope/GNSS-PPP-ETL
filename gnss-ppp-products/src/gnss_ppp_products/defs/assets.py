import dagster as dg
import datetime
from ..utils import load_product_sources_FTP


@dg.asset()
def get_date(context: dg.AssetExecutionContext) -> datetime.date:
    """
    Get the processing date from the execution context.

    Returns
    -------
        datetime.date
            The processing date.
    """
    date = context.get_op_execution_context().resources.date
    context.log.info(f"Using processing date: {date}")
    return date

@dg.asset(deps=[get_date])
def ftp_product_sources(context: dg.AssetExecutionContext) -> dict:
    """
    Load GNSS product sources from FTP based on the given date.

    Parameters
    ----------
        date (datetime.date)
            The date for which to load product sources.
    Returns
    -------
        dict
            A dictionary of product sources.
    """
    date = context.get_asset_value(get_date)
    context.log.info(f"Loading product sources for date: {date}")
    sources = load_product_sources_FTP(date)
    context.log.info(f"Loaded product sources: {sources.keys()}")
    return sources