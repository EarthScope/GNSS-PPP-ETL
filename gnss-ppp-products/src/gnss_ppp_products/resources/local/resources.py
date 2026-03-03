from pathlib import Path
from typing import Literal, Optional
import datetime
import re
import dagster as dg


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
