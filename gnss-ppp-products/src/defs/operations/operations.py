import dagster as dg
import datetime
from typing import Dict, Optional
from ftplib import FTP
import re
from ..utils import load_product_sources_FTP,ProductSourcePathFTP,ProductSourcesFTP,ProductSourceCollectionFTP


@dg.op()
def get_ftp_product_sources(
    context: dg.OpExecutionContext, date: datetime.date
) -> Dict[str, ProductSourcesFTP]:
    """
    Load GNSS product sources from FTP based on the given date.

    Parameters
    ----------
        date (datetime.date)
            The date for which to load product sources.
    Returns
    -------
        Dict[str, ProductSourcesFTP]
            A dictionary of product sources.
    """
    context.log.info(f"Loading product sources for date: {date}")
    sources: Dict[str, ProductSourcesFTP] = load_product_sources_FTP(date)
    context.log.info(f"Loaded product sources: {sources.keys()}")
    return sources

source_type = dg.DagsterType(
    name="ProductSourcePathFTP|ProductSourceCollectionFTP",
    typing_type=ProductSourceCollectionFTP | ProductSourcePathFTP,
    type_check_fn=lambda _, value: isinstance(value, (ProductSourceCollectionFTP, ProductSourcePathFTP)),
)
@dg.op(
    ins={"source": dg.In(source_type)},
    out=dg.Out(source_type),
    retry_policy=dg.RetryPolicy(max_retries=3, delay=10),
)
def search_ftp_source(context:dg.OpExecutionContext,
                      source:ProductSourcePathFTP|ProductSourceCollectionFTP) -> Optional[ProductSourcePathFTP|ProductSourceCollectionFTP]:

    try:
        with FTP(source.ftpserver.replace("ftp://", ""), timeout=60) as ftp:
            ftp.set_pasv(True)
            ftp.login()
            ftp.cwd("/" + source.directory)
            dir_list = ftp.nlst()
    except Exception as e:
        context.log.error(
            f"Failed to list directory {source.directory} on {source.ftpserver} | {e}"
        )
        return None
    
    def match_source(regex_str:str) -> list[str]:
        regex = re.compile(regex_str)
        dir_match = [d for d in dir_list if regex.search(d)]
        if len(dir_match) == 0:
            context.log.info(f"No match found for {regex_str} in {source.directory}")
            return []
        return dir_match
    
    if isinstance(source,ProductSourcePathFTP):
        dir_match = match_source(source.filename_regex)
        if dir_match:
            source.discovered_remote_path = dir_match[0]
            return source
     
    elif isinstance(source,ProductSourceCollectionFTP):
        final_regex = source.final.filename_regex
        rapid_regex = source.rapid.filename_regex
        rts_regex = source.rts.filename_regex
        dir_match_final = match_source(final_regex)
        if dir_match_final:
            source.final.discovered_remote_path = dir_match_final[0]
        else:
            context.log.info("No final product found, checking rapid product")
        dir_match_rapid = match_source(rapid_regex)
        if dir_match_rapid:
            source.rapid.discovered_remote_path = dir_match_rapid[0]
        else:
            context.log.info("No rapid product found, checking rts product")
        dir_match_rts = match_source(rts_regex)
        if dir_match_rts:
            source.rts.discovered_remote_path = dir_match_rts[0]
        else:
            context.log.info("No rts product found")
        if not (dir_match_final or dir_match_rapid or dir_match_rts):
            context.log.info("No products found matching any quality level")
        return source

# Given a Dict[str, ProductSourcesFTP], search each source on the FTP server.

@dg.op(
    ins={"sources": dg.In(dg.Dict(dg.String, source_type))},
    out=dg.Out(dg.Dict(dg.String, source_type)),
    retry_policy=dg.RetryPolicy(max_retries=3, delay=10),
)
def search_ftp_product_sources(
    context: dg.OpExecutionContext,
    sources: Dict[str, ProductSourcePathFTP|ProductSourceCollectionFTP],
) -> Dict[str, ProductSourcePathFTP|ProductSourceCollectionFTP]:
    """
    Search GNSS product sources on FTP based on the given sources.

    Parameters
    ----------
        sources (Dict[str, ProductSourcesFTP])
            The dictionary of product sources to search.
    Returns
    -------
        Dict[str, ProductSourcesFTP]
            A dictionary of found product sources.
    """
    found_sources: Dict[str, ProductSourcePathFTP|ProductSourceCollectionFTP] = {}
    for key, source in sources.items():
        context.log.info(f"Searching for source: {key}")
        found_source = search_ftp_source(context, source)
        if found_source is not None:
            found_sources[key] = found_source
            context.log.info(f"Found source for {key}: {found_source}")
        else:
            context.log.info(f"No source found for {key}")
    return found_sources