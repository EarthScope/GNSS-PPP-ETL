"""
Tests for gnss_ppp_products.utils.ftp_download

Pure-logic tests (find_best_match_in_listing, _QUALITY_ATTR) are offline.
Integration tests that open real FTP connections are marked ``integration``
and skipped by default::

    pytest -m "not integration"   # fast, offline suite
    pytest -m integration          # live FTP suite
"""
from __future__ import annotations

import pytest

from gnss_ppp_products.utils.ftp_download import (
    _QUALITY_ATTR,
    find_best_match_in_listing,
)
from gnss_ppp_products.utils.product_sources import ProductQuality


# ---------------------------------------------------------------------------
# find_best_match_in_listing
# ---------------------------------------------------------------------------

SAMPLE_LISTING = [
    "WMC0DEMFIN_20253050000_01D_05M_ORB.SP3.gz",
    "WMC0DEMRAP_20253050000_01D_05M_ORB.SP3.gz",
    "WMC0DEMRTS_20253050000_01D_05M_ORB.SP3.gz",
    "WMC0DEMFIN_20253050000_01D_30S_CLK.CLK.gz",
    "WUM0MGXRAP_20253050000_01D_01D_ERP.ERP.gz",
    "WMC0DEMFIN_20253050000_01D_30S_ATT.OBX.gz",
    "README.txt",
    "MD5SUMS",
]


class TestFindBestMatchInListing:
    def test_final_sp3_match(self):
        result = find_best_match_in_listing(SAMPLE_LISTING, r"FIN.*2025305.*SP3.*")
        assert result == "WMC0DEMFIN_20253050000_01D_05M_ORB.SP3.gz"

    def test_rapid_sp3_match(self):
        result = find_best_match_in_listing(SAMPLE_LISTING, r"RAP.*2025305.*SP3.*")
        assert result == "WMC0DEMRAP_20253050000_01D_05M_ORB.SP3.gz"

    def test_rts_sp3_match(self):
        result = find_best_match_in_listing(SAMPLE_LISTING, r"RTS.*2025305.*SP3.*")
        assert result == "WMC0DEMRTS_20253050000_01D_05M_ORB.SP3.gz"

    def test_clk_match(self):
        result = find_best_match_in_listing(SAMPLE_LISTING, r"FIN.*2025305.*CLK.*")
        assert result == "WMC0DEMFIN_20253050000_01D_30S_CLK.CLK.gz"

    def test_no_match_returns_none(self):
        result = find_best_match_in_listing(SAMPLE_LISTING, r"FIN.*202501.*SP3.*")
        assert result is None

    def test_empty_listing_returns_none(self):
        result = find_best_match_in_listing([], r"FIN.*SP3.*")
        assert result is None

    def test_regex_anchored_to_full_line(self):
        # README.txt should not match a broad SP3 pattern scoped correctly
        result = find_best_match_in_listing(SAMPLE_LISTING, r".*\.SP3\.gz$")
        # Should match the first SP3 file
        assert result is not None
        assert result.endswith(".SP3.gz")

    def test_case_sensitive_match(self):
        # Pattern in lowercase should not match upper-case filenames
        result = find_best_match_in_listing(SAMPLE_LISTING, r"fin.*2025305.*sp3.*")
        assert result is None

    @pytest.mark.parametrize("pattern,expected", [
        (r"FIN.*ERP.*", None),          # ERP has no FIN in this listing
        (r"RAP.*ERP.*", "WUM0MGXRAP_20253050000_01D_01D_ERP.ERP.gz"),
        (r"FIN.*OBX.*", "WMC0DEMFIN_20253050000_01D_30S_ATT.OBX.gz"),
    ])
    def test_parametrized_patterns(self, pattern, expected):
        result = find_best_match_in_listing(SAMPLE_LISTING, pattern)
        assert result == expected


# ---------------------------------------------------------------------------
# _QUALITY_ATTR mapping
# ---------------------------------------------------------------------------

class TestQualityAttrMapping:
    def test_all_quality_levels_present(self):
        for q in ProductQuality:
            assert q in _QUALITY_ATTR, f"ProductQuality.{q.name} missing from _QUALITY_ATTR"

    def test_final_maps_to_final(self):
        assert _QUALITY_ATTR[ProductQuality.FINAL] == "final"

    def test_rapid_maps_to_rapid(self):
        assert _QUALITY_ATTR[ProductQuality.RAPID] == "rapid"

    def test_rts_maps_to_rts(self):
        assert _QUALITY_ATTR[ProductQuality.REAL_TIME_STREAMING] == "rts"

    def test_values_are_valid_python_identifiers(self):
        for q, attr in _QUALITY_ATTR.items():
            assert attr.isidentifier(), f"{q}: '{attr}' is not a valid identifier"


# ---------------------------------------------------------------------------
# FTP integration tests (require live network — skipped by default)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_ftp_list_directory_wuhan():
    from gnss_ppp_products.utils.ftp_download import ftp_list_directory
    listing = ftp_list_directory(
        "ftp://igs.gnsswhu.cn",
        "pub/whu/phasebias/2025/orbit/",
    )
    assert listing, "Expected non-empty directory listing from Wuhan FTP"


@pytest.mark.integration
def test_download_sp3_wuhan(tmp_path):
    import datetime
    from gnss_ppp_products.utils.ftp_download import download_product_with_fallback
    from gnss_ppp_products.utils.product_sources import load_product_sources_FTP

    source_map = load_product_sources_FTP(datetime.date(2025, 11, 1))
    result = download_product_with_fallback(source_map, "sp3", tmp_path)
    assert result is not None, "SP3 download failed"
    local_path, server, quality = result
    assert local_path.exists()
    assert local_path.stat().st_size > 0
