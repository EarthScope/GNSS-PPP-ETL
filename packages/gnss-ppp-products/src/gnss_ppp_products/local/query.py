"""
Local File Query
================

Given a FileQuery variant (with a populated ``filename`` regex pattern),
resolve the local directory and search for matching files on disk.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from ..assets.base import AssetBase, ProductType, ProductFileFormat
from ..assets.products.query import ProductFileQuery
from ..assets.antennae.query import AntennaeFileQuery
from ..assets.rinex.query import RinexFileQuery
from ..assets.troposphere.query import TroposphereFileQuery
from ..assets.orography.query import OrographyFileQuery
from ..assets.leo.query import LEOFileQuery
from ..assets.reference_tables.query import ReferenceTableFileQuery
from .utils import check_file
from .config import LocalStorageConfig

# Type alias for any FileQuery variant
FileQuery = Union[
    ProductFileQuery,
    AntennaeFileQuery,
    RinexFileQuery,
    TroposphereFileQuery,
    OrographyFileQuery,
    LEOFileQuery,
    ReferenceTableFileQuery,
]

# ---------------------------------------------------------------------------
# FileQuery → ProductType mapping
# ---------------------------------------------------------------------------

# ProductFileQuery uses its ``format`` field to identify the product type.
_FORMAT_TO_PRODUCT_TYPE: dict[ProductFileFormat, ProductType] = {
    ProductFileFormat.SP3: ProductType.SP3,
    ProductFileFormat.CLK: ProductType.CLK,
    ProductFileFormat.ERP: ProductType.ERP,
    ProductFileFormat.BIA: ProductType.BIAS,
    ProductFileFormat.OBX: ProductType.OBX,
    ProductFileFormat.SUM: ProductType.SUM,
    ProductFileFormat.INX: ProductType.GIM,
}


def _product_type_from_query(query: FileQuery) -> ProductType:
    """Infer the :class:`ProductType` from a FileQuery variant."""

    if isinstance(query, ProductFileQuery):
        if query.format is not None and query.format in _FORMAT_TO_PRODUCT_TYPE:
            return _FORMAT_TO_PRODUCT_TYPE[query.format]
        raise ValueError(
            f"Cannot infer ProductType from ProductFileQuery with format={query.format!r}"
        )

    if isinstance(query, RinexFileQuery):
        from ..assets.base.igs_conventions import RinexVersion
        if query.version == RinexVersion.V3 or query.version == RinexVersion.V4:
            return ProductType.RINEX3_NAV
        return ProductType.RINEX2_NAV

    if isinstance(query, TroposphereFileQuery):
        from ..assets.troposphere.base import VMFProduct
        if query.product == VMFProduct.VMF3:
            return ProductType.VMF3
        return ProductType.VMF1

    if isinstance(query, LEOFileQuery):
        from ..assets.leo.base import GRACEInstrument
        _INSTRUMENT_MAP = {
            GRACEInstrument.GNV: ProductType.GRACE_GNV,
            GRACEInstrument.ACC: ProductType.GRACE_ACC,
            GRACEInstrument.SCA: ProductType.GRACE_SCA,
            GRACEInstrument.KBR: ProductType.GRACE_KBR,
            GRACEInstrument.LRI: ProductType.GRACE_LRI,
        }
        if query.instrument in _INSTRUMENT_MAP:
            return _INSTRUMENT_MAP[query.instrument]
        raise ValueError(
            f"Cannot infer ProductType from LEOFileQuery with instrument={query.instrument!r}"
        )

    if isinstance(query, AntennaeFileQuery):
        return ProductType.ATX

    if isinstance(query, OrographyFileQuery):
        return ProductType.OROGRAPHY

    if isinstance(query, ReferenceTableFileQuery):
        from ..assets.reference_tables.base import ReferenceTableType
        if query.table_type == ReferenceTableType.SAT_PARAMETERS:
            return ProductType.SAT_PARAMETERS
        return ProductType.LEAP_SECONDS

    raise TypeError(f"Unsupported query type: {type(query).__name__}")


# ---------------------------------------------------------------------------
# Local query class
# ---------------------------------------------------------------------------


class LocalFileQuery:
    """
    Search a local directory structure for files matching a FileQuery.

    Parameters
    ----------
    config : LocalStorageConfig
        Provides the ProductType → directory mapping.

    Examples
    --------
    >>> from gnss_ppp_products.local import LocalStorageConfig
    >>> from gnss_ppp_products.local.query import LocalFileQuery
    >>> cfg = LocalStorageConfig("/data/gnss")
    >>> lfq = LocalFileQuery(cfg)
    >>> results = lfq.search(product_query)  # product_query.filename is a regex
    """

    def __init__(self, config: LocalStorageConfig) -> None:
        self.config = config

    def resolve_directory(self, query: FileQuery) -> Path:
        """
        Return the local directory where *query* should be stored/found.

        Parameters
        ----------
        query : FileQuery
            Any FileQuery variant with optional ``date``.

        Returns
        -------
        Path
            Absolute directory path.
        """
        product_type = _product_type_from_query(query)
        return self.config.resolve(product_type, query.date)

    def search(self, query: FileQuery) -> list[Path]:
        """
        Find files in the local store matching *query*.

        Uses the query's ``filename`` attribute as a regex pattern
        against filenames in the resolved directory.

        Parameters
        ----------
        query : FileQuery
            Must have ``filename`` populated (typically via ``build_filename``
            with a template that produces a regex when fields are missing).

        Returns
        -------
        list[Path]
            Sorted list of matching file paths (empty if directory
            doesn't exist or nothing matches).

        Raises
        ------
        ValueError
            If ``query.filename`` is ``None``.
        """
        if query.filename is None:
            raise ValueError(
                "query.filename is None — call build_filename() on the query first"
            )

        directory = self.resolve_directory(query)

        if not directory.exists():
            return []

        pattern = re.compile(query.filename, re.IGNORECASE)
        matches = [
            p for p in directory.iterdir()
            if p.is_file() and pattern.search(p.name)
        ]
        # Check matches for corrupted files (e.g. zero-byte downloads) and delete and exclude them
        valid_matches = []
        for p in matches:
            if not check_file(p):
                p.unlink()  # Delete the corrupted file
            else:
                valid_matches.append(p)
        return sorted(valid_matches, key=lambda p: p.name)

    def exists(self, query: FileQuery) -> bool:
        """Return ``True`` if at least one local file matches *query*."""
        return len(self.search(query)) > 0

    def best_match(self, query: FileQuery) -> Optional[Path]:
        """
        Return the newest matching file, or ``None``.

        "Newest" is determined by filesystem modification time.
        """
        matches = self.search(query)
        if not matches:
            return None
        return max(matches, key=lambda p: p.stat().st_mtime)
