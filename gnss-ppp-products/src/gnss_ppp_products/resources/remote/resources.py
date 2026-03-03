"""
Dagster resources for the GNSS PPP-AR ETL pipeline.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import dagster as dg

from ...utils.ftp_download import (
    _QUALITY_ATTR,
    QUALITY_PRIORITY,
    find_best_match_in_listing,
    ftp_download_file,
    ftp_list_directory,
    ftp_try_download_md5_sidecar,
    resolve_product_source,
)
from ...utils.product_sources import (
    ConstellationCode,
    ProductQuality,
    ProductSourceCollectionFTP,
    load_product_sources_FTP,
)


class GNSSOutputResource(dg.ConfigurableResource):
    """
    Configures where downloaded GNSS products and generated config files are
    stored on the local filesystem.

    Directory layout (mirrors the PRIDE PPP-AR convention):

    .. code-block:: text

        <output_base_dir>/
          <year>/
            product/
              common/          ← precise orbit / clock / bias products
            <doy>/             ← per-day files: nav + config file

    Parameters
    ----------
    output_base_dir:
        Root directory for all GNSS output.  Defaults to ``/data/gnss_products``.
        Override at runtime via the Dagster launch config or the
        ``GNSS_OUTPUT_DIR`` environment variable.

    Examples
    --------
    Dagster ``definitions.py``::

        from gnss_ppp_products.resources import GNSSOutputResource
        import dagster as dg

        defs = dg.Definitions(
            assets=[...],
            resources={
                "gnss_output": GNSSOutputResource(
                    output_base_dir=dg.EnvVar("GNSS_OUTPUT_DIR")
                )
            },
        )
    """

    output_base_dir: str = "/data/gnss_products"
    table_dir: str = ""

    # ------------------------------------------------------------------
    # Directory helpers (create on first access)
    # ------------------------------------------------------------------

    def _year_doy(self, date: datetime.date) -> tuple[str, str]:
        year = str(date.year)
        doy = f"{date.timetuple().tm_yday:03d}"
        return year, doy

    def product_dir(self, date: datetime.date) -> Path:
        """
        Return (and create) the common precise-product directory for *date*.

        Path: ``<output_base_dir>/<year>/product/common/``
        """
        year, _ = self._year_doy(date)
        path = Path(self.output_base_dir) / year / "product" / "common"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def nav_dir(self, date: datetime.date) -> Path:
        """
        Return (and create) the per-day navigation file directory for *date*.

        Path: ``<output_base_dir>/<year>/<doy>/``
        """
        year, doy = self._year_doy(date)
        path = Path(self.output_base_dir) / year / doy
        path.mkdir(parents=True, exist_ok=True)
        return path

    def config_file_path(self, date: datetime.date) -> Path:
        """
        Return the path for the generated PRIDE PPP-AR config file.

        Path: ``<output_base_dir>/<year>/<doy>/pride_ppp_ar_config``

        The parent directory is created automatically by :meth:`nav_dir`.
        """
        year, doy = self._year_doy(date)
        return Path(self.output_base_dir) / year / doy / "pride_ppp_ar_config"


# ---------------------------------------------------------------------------
# FTPFileResult — query result
# ---------------------------------------------------------------------------


@dataclass
class FTPFileResult:
    """
    The result of a successful FTP file query.

    Attributes
    ----------
    ftpserver:
        FTP host URL, e.g. ``ftp://igs.gnsswhu.cn``.
    directory:
        Remote directory path (without leading slash), e.g.
        ``pub/whu/phasebias/2025/orbit``.
    filename:
        Remote filename, e.g.
        ``WMC0DEMFIN_20253050000_01D_05M_ORB.SP3.gz``.
    quality:
        The quality level at which the file was found.
    server_name:
        Human-readable server key, e.g. ``"wuhan"``.
    """

    ftpserver: str
    directory: str
    filename: str
    quality: ProductQuality
    server_name: str = ""

    @property
    def url(self) -> str:
        """Full FTP URL to the remote file."""
        host = self.ftpserver.rstrip("/")
        path = self.directory.strip("/")
        return f"{host}/{path}/{self.filename}"

    @property
    def quality_label(self) -> str:
        """Short quality label used in filenames (``FIN``, ``RAP``, ``RTS``)."""
        return self.quality.value


# ---------------------------------------------------------------------------
# FTPRemoteResource
# ---------------------------------------------------------------------------


def _parse_date(date: datetime.date | datetime.datetime) -> tuple[str, str]:
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


GNSS_START_TIME = datetime.datetime(
    1980, 1, 6, tzinfo=datetime.timezone.utc
)  # GNSS start time


def _date_to_gps_week(date: datetime.date | datetime.datetime) -> int:
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


class ProductFileSourceRegex:
    def __init__(
        self,
        product_sp3: str,
        product_obx: str,
        product_clk: str,
        product_erp: str,
        product_sum: str,
        product_bias: str,
        product_broadcast_rnx3: str,
        product_broadcast_rnx2: str,
        **kwargs,
    ):
        self.product_sp3: str = product_sp3
        self.product_obx: str = product_obx
        self.product_clk: str = product_clk
        self.product_erp: str = product_erp
        self.product_sum: str = product_sum
        self.product_bias: str = product_bias
        self.product_broadcast_rnx3: str = product_broadcast_rnx3
        self.product_broadcast_rnx2: str = product_broadcast_rnx2

    def sp3(
        self, date: datetime.date | datetime.datetime, quality: ProductQuality
    ) -> str:
        year, doy = _parse_date(date)
        return self.product_sp3.format(quality=quality.value, year=year, doy=doy)

    def obx(
        self, date: datetime.date | datetime.datetime, quality: ProductQuality
    ) -> str:
        year, doy = _parse_date(date)
        return self.product_obx.format(quality=quality.value, year=year, doy=doy)

    def clk(
        self, date: datetime.date | datetime.datetime, quality: ProductQuality
    ) -> str:
        year, doy = _parse_date(date)
        return self.product_clk.format(quality=quality.value, year=year, doy=doy)

    def erp(
        self, date: datetime.date | datetime.datetime, quality: ProductQuality
    ) -> str:
        year, doy = _parse_date(date)
        return self.product_erp.format(quality=quality.value, year=year, doy=doy)

    def sum(
        self, date: datetime.date | datetime.datetime, quality: ProductQuality
    ) -> str:
        year, doy = _parse_date(date)
        return self.product_sum.format(quality=quality.value, year=year, doy=doy)

    def bias(
        self, date: datetime.date | datetime.datetime, quality: ProductQuality
    ) -> str:
        year, doy = _parse_date(date)
        return self.product_bias.format(quality=quality.value, year=year, doy=doy)

    def broadcast_rnx3(self, date: datetime.date | datetime.datetime) -> str:
        year, doy = _parse_date(date)
        yy = str(year)[2:4]
        return self.product_broadcast_rnx3.format(year=year, doy=doy)

    def broadcast_rnx2(
        self, date: datetime.date | datetime.datetime, constellation: ConstellationCode
    ) -> str:
        year, doy = _parse_date(date)
        yy = str(year)[2:4]
        return self.product_broadcast_rnx2.format(
            doy=doy, yy=yy, constellation=constellation.value
        )


class ProductDirectorySourceFTP:

    def __init__(
        self,
        ftpserver: str,
        rinex_nav: Optional[str] = None,
        product_sp3: Optional[str] = None,
        product_clk: Optional[str] = None,
        product_sum: Optional[str] = None,
        product_bias: Optional[str] = None,
        product_erp: Optional[str] = None,
        product_obx: Optional[str] = None,
    ):
        self.ftpserver = ftpserver
        self.rinex_nav = rinex_nav
        self.product_sp3 = product_sp3
        self.product_clk = product_clk
        self.product_sum = product_sum
        self.product_bias = product_bias
        self.product_erp = product_erp
        self.product_obx = product_obx

    @classmethod
    def from_config(
        cls, ftpserver: str, directories: dict[str, str]
    ) -> ProductDirectorySourceFTP:
        return cls(
            ftpserver=ftpserver,
            rinex_nav=directories.get("rinex_nav"),
            product_sp3=directories.get("product_sp3"),
            product_clk=directories.get("product_clk"),
            product_sum=directories.get("product_sum"),
            product_bias=directories.get("product_bias"),
            product_erp=directories.get("product_erp"),
            product_obx=directories.get("product_obx"),
        )

    def rinex_nav_directory(
        self, date: datetime.date | datetime.datetime
    ) -> Optional[str]:
        if self.rinex_nav is None:
            return None
        year, doy = _parse_date(date)
        yy = str(year)[2:4]
        return self.rinex_nav.format(year=year, doy=doy, yy=yy)

    def product_sp3_directory(
        self, date: datetime.date | datetime.datetime
    ) -> Optional[str]:
        if self.product_sp3 is None:
            return None
        year, doy = _parse_date(date)
        gps_week = _date_to_gps_week(date)
        return self.product_sp3.format(year=year, doy=doy, gps_week=gps_week)

    def product_clk_directory(
        self, date: datetime.date | datetime.datetime
    ) -> Optional[str]:
        if self.product_clk is None:
            return None
        year, doy = _parse_date(date)
        gps_week = _date_to_gps_week(date)
        return self.product_clk.format(year=year, doy=doy, gps_week=gps_week)

    def product_sum_directory(
        self, date: datetime.date | datetime.datetime
    ) -> Optional[str]:
        if self.product_sum is None:
            return None
        year, doy = _parse_date(date)
        gps_week = _date_to_gps_week(date)
        return self.product_sum.format(year=year, doy=doy, gps_week=gps_week)

    def product_bias_directory(
        self, date: datetime.date | datetime.datetime
    ) -> Optional[str]:
        if self.product_bias is None:
            return None
        year, doy = _parse_date(date)
        gps_week = _date_to_gps_week(date)
        return self.product_bias.format(year=year, doy=doy, gps_week=gps_week)

    def product_erp_directory(
        self, date: datetime.date | datetime.datetime
    ) -> Optional[str]:
        if self.product_erp is None:
            return None
        year, doy = _parse_date(date)
        gps_week = _date_to_gps_week(date)
        return self.product_erp.format(year=year, doy=doy, gps_week=gps_week)

    def product_obx_directory(
        self, date: datetime.date | datetime.datetime
    ) -> Optional[str]:
        if self.product_obx is None:
            return None
        year, doy = _parse_date(date)
        gps_week = _date_to_gps_week(date)
        return self.product_obx.format(year=year, doy=doy, gps_week=gps_week)


class FTPRemoteResource(dg.ConfigurableResource):
    """
    Dagster resource for querying and downloading GNSS precise products
    from a single configured FTP server.

    Use this resource when you need direct, on-demand access to the FTP
    server — for example, to check file availability for a specific quality
    level before triggering a full pipeline run.

    Parameters
    ----------
    server:
        Server key as defined in ``sources.yml`` (``"wuhan"`` or
        ``"cligs"``).  Defaults to ``"wuhan"``.
    timeout:
        FTP connection timeout in seconds.  Defaults to ``60``.

    Examples
    --------
    In ``definitions.py``::

        from gnss_ppp_products.resources import FTPRemoteResource
        import dagster as dg

        defs = dg.Definitions(
            assets=[...],
            resources={
                "ftp_remote": FTPRemoteResource(server="wuhan"),
            },
        )

    Inside an asset::

        @dg.asset
        def my_asset(ftp_remote: FTPRemoteResource):
            result = ftp_remote.query("sp3", datetime.date(2025, 11, 1))
            if result:
                print(result.url)       # ftp://igs.gnsswhu.cn/.../file.SP3.gz
                print(result.quality)   # ProductQuality.FINAL
    """

    server: str = "wuhan"
    timeout: int = 60

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_collection(
        self,
        product_attr: str,
        date: datetime.date,
    ) -> Optional[ProductSourceCollectionFTP]:
        """
        Load sources.yml for *date* and return the
        ``ProductSourceCollectionFTP`` for *product_attr* on the configured
        server, or *None* if the server or product is not present.
        """
        source_map = load_product_sources_FTP(date)
        sources = source_map.get(self.server)
        if sources is None:
            return None
        return getattr(sources, product_attr, None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(
        self,
        product_attr: str,
        date: datetime.date,
        quality: Optional[ProductQuality] = None,
    ) -> Optional[FTPFileResult]:
        """
        Query the configured FTP server for a GNSS product file.

        The FTP directory is listed **once** per call; all applicable quality
        regex patterns are tested against that cached listing.

        Parameters
        ----------
        product_attr:
            Product type: ``"sp3"``, ``"clk"``, ``"obx"``, ``"erp"``,
            ``"bias"``.
        date:
            The GNSS product date (Dagster partition date).
        quality:
            Specific quality level to search for.  Pass *None* (default)
            to auto-fallback through ``FINAL → RAPID → RTS`` and return the
            best quality found.  Pass a ``ProductQuality`` value to restrict
            the search to that level only.

        Returns
        -------
        FTPFileResult or None
            *None* if the server is unreachable, the directory is empty, or
            no file matching the requested quality/product is found.
        """
        collection = self._get_collection(product_attr, date)
        if collection is None:
            return None

        ftpserver = collection.final.ftpserver
        directory = collection.final.directory

        dir_listing = ftp_list_directory(ftpserver, directory, timeout=self.timeout)
        if not dir_listing:
            return None

        qualities_to_try = [quality] if quality is not None else QUALITY_PRIORITY

        for q in qualities_to_try:
            source_path = getattr(collection, _QUALITY_ATTR[q])
            filename = find_best_match_in_listing(dir_listing, source_path.file_regex)
            if filename:
                return FTPFileResult(
                    ftpserver=ftpserver,
                    directory=directory,
                    filename=filename,
                    quality=q,
                    server_name=self.server,
                )

        return None

    def list_directory(
        self,
        product_attr: str,
        date: datetime.date,
    ) -> list[str]:
        """
        Return the raw FTP directory listing for the given product and date.

        Useful for debugging or building custom regex searches against the
        live server state.  Returns an empty list if the server is
        unreachable or the directory does not exist.

        Parameters
        ----------
        product_attr:
            Product type: ``"sp3"``, ``"clk"``, ``"obx"``, ``"erp"``,
            ``"bias"``.
        date:
            The GNSS product date.
        """
        collection = self._get_collection(product_attr, date)
        if collection is None:
            return []
        src = collection.final
        return ftp_list_directory(src.ftpserver, src.directory, timeout=self.timeout)

    def download(
        self,
        product_attr: str,
        date: datetime.date,
        dest_dir: Path,
        quality: Optional[ProductQuality] = None,
    ) -> Optional[tuple[Path, FTPFileResult]]:
        """
        Query then download a GNSS product file.

        Parameters
        ----------
        product_attr:
            Product type: ``"sp3"``, ``"clk"``, ``"obx"``, ``"erp"``,
            ``"bias"``.
        date:
            The GNSS product date.
        dest_dir:
            Local directory in which to save the downloaded file.
        quality:
            Quality level to search for.  *None* auto-fallbacks through
            ``FINAL → RAPID → RTS``.

        Returns
        -------
        (local_path, FTPFileResult) on success, or *None* on failure.
        """
        result = self.query(product_attr, date, quality)
        if result is None:
            return None

        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / result.filename

        # Re-use cached file if already present and non-empty
        if dest_path.exists() and dest_path.stat().st_size > 0:
            ftp_try_download_md5_sidecar(
                result.ftpserver, result.directory, result.filename, dest_dir
            )
            return (dest_path, result)

        success = ftp_download_file(
            result.ftpserver,
            result.directory,
            result.filename,
            dest_path,
            timeout=self.timeout * 3,  # downloads need more time than listings
        )
        if not success:
            return None

        ftp_try_download_md5_sidecar(
            result.ftpserver, result.directory, result.filename, dest_dir
        )
        return (dest_path, result)


class FTPProductSource:
    def __init__(self, ftpserver: str, name: str):
        self.ftpserver = ftpserver
        self.name = name
        self.ftp_product_file_regex: Optional[ProductFileSourceRegex] = None
        self.ftp_product_dir: Optional[ProductDirectorySourceFTP] = None

    def _search(
        self, regex: str, directory: str, quality: ProductQuality
    ) -> Optional[FTPFileResult]:
        dir_listing = ftp_list_directory(self.ftpserver, directory, timeout=60)
        if not dir_listing:
            return None
        filename = find_best_match_in_listing(dir_listing, regex)
        if filename:
            return FTPFileResult(
                ftpserver=self.ftpserver,
                directory=directory,
                filename=filename,
                quality=quality,
            )
        return None

    def query(
        self,
        product: Literal[
            "rinex_3_nav",
            "rinex_2_nav",
            "sp3",
            "orbit",
            "clk",
            "sum",
            "bias",
            "erp",
            "obx",
        ],
        date: datetime.date,
        quality: Optional[ProductQuality] = None,
        constellation: Optional[ConstellationCode] = None,
    ) -> Optional[FTPFileResult]:

        assert self.ftp_product_file_regex is not None, "FTPProductFileRegex not set"
        assert self.ftp_product_dir is not None, "FTPProductDirectory not set"

        match product:
            case "sp3":
                regex = self.ftp_product_file_regex.sp3(date, quality)
                directory = self.ftp_product_dir.product_sp3_directory(date)
            case "clk":
                regex = self.ftp_product_file_regex.clk(date, quality)
                directory = self.ftp_product_dir.product_clk_directory(date)
            case "sum":
                regex = self.ftp_product_file_regex.sum(date, quality)
                directory = self.ftp_product_dir.product_sum_directory(date)
            case "bias":
                regex = self.ftp_product_file_regex.bias(date, quality)
                directory = self.ftp_product_dir.product_bias_directory(date)
            case "erp":
                regex = self.ftp_product_file_regex.erp(date, quality)
                directory = self.ftp_product_dir.product_erp_directory(date)
            case "obx":
                regex = self.ftp_product_file_regex.obx(date, quality)
                directory = self.ftp_product_dir.product_obx_directory(date)
            case "rinex_3_nav":
                regex = self.ftp_product_file_regex.broadcast_rnx3(date)
                directory = self.ftp_product_dir.rinex_nav_directory(date)
            case "rinex_2_nav":
                assert (
                    constellation is not None
                ), "Constellation code required for rinex_2_nav"
                regex = self.ftp_product_file_regex.broadcast_rnx2(date, constellation)
                directory = self.ftp_product_dir.rinex_nav_directory(date)
            case _:
                raise ValueError(f"Unknown product type: {product}")

        if regex is None or directory is None:
            raise ValueError(f"Regex or directory not defined for product {product}")

        try:
            ftp_file_result = self._search(regex, directory, quality)
            return ftp_file_result
        except Exception as e:
            print(f"Error querying FTP for product {product}: {e}")
            return None
