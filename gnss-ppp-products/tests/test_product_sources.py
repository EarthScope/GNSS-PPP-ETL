"""
Tests for gnss_ppp_products.utils.product_sources

These tests only parse dates and load the local sources.yml — no FTP needed.
"""
from __future__ import annotations

import datetime

import pytest

from gnss_ppp_products.utils.product_sources import (
    ProductQuality,
    ProductSourceCollectionFTP,
    ProductSourcesFTP,
    _date_to_gps_week,
    _parse_date,
    load_product_sources_FTP,
)


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_jan_1_gives_doy_001(self):
        year, doy = _parse_date(datetime.date(2025, 1, 1))
        assert year == "2025"
        assert doy == "001"

    def test_single_digit_day_zero_padded(self):
        year, doy = _parse_date(datetime.date(2025, 1, 9))
        assert doy == "009"

    def test_double_digit_day_zero_padded(self):
        year, doy = _parse_date(datetime.date(2025, 4, 10))
        # DOY 100 is Apr 10 in 2025 (31+28+31+10)
        assert doy == "100"

    def test_nov_1_2025_is_doy_305(self):
        # Jan31+Feb28+Mar31+Apr30+May31+Jun30+Jul31+Aug31+Sep30+Oct31+Nov1 = 305
        year, doy = _parse_date(datetime.date(2025, 11, 1))
        assert year == "2025"
        assert doy == "305"

    def test_dec_31_non_leap_year_is_doy_365(self):
        year, doy = _parse_date(datetime.date(2025, 12, 31))
        assert doy == "365"

    def test_dec_31_leap_year_is_doy_366(self):
        year, doy = _parse_date(datetime.date(2024, 12, 31))
        assert doy == "366"

    def test_datetime_object_accepted(self):
        year, doy = _parse_date(datetime.datetime(2025, 11, 1, 12, 30, 0))
        assert year == "2025"
        assert doy == "305"


# ---------------------------------------------------------------------------
# _date_to_gps_week
# ---------------------------------------------------------------------------

class TestDateToGpsWeek:
    def test_gps_epoch_is_week_zero(self):
        # The GPS epoch begins on 1980-01-06
        assert _date_to_gps_week(datetime.date(1980, 1, 6)) == 0

    def test_one_week_after_epoch(self):
        assert _date_to_gps_week(datetime.date(1980, 1, 13)) == 1

    def test_known_week_2025_nov_1(self):
        # Verified by CLIGS directory pub/igs/data/2390/
        assert _date_to_gps_week(datetime.date(2025, 11, 1)) == 2390

    def test_datetime_accepted(self):
        assert _date_to_gps_week(datetime.datetime(2025, 11, 1)) == 2390


# ---------------------------------------------------------------------------
# ProductQuality enum
# ---------------------------------------------------------------------------

class TestProductQuality:
    def test_members_present(self):
        names = {q.name for q in ProductQuality}
        assert "FINAL" in names
        assert "RAPID" in names
        assert "REAL_TIME_STREAMING" in names

    def test_fin_value(self):
        assert ProductQuality.FINAL.value == "FIN"

    def test_rap_value(self):
        assert ProductQuality.RAPID.value == "RAP"

    def test_rts_value(self):
        assert ProductQuality.REAL_TIME_STREAMING.value == "RTS"


# ---------------------------------------------------------------------------
# load_product_sources_FTP (reads sources.yml — no FTP)
# ---------------------------------------------------------------------------

class TestLoadProductSourcesFTP:
    def test_returns_both_servers(self):
        sources = load_product_sources_FTP(datetime.date(2025, 11, 1))
        assert "wuhan" in sources
        assert "cligs" in sources

    def test_wuhan_sp3_has_final_source(self):
        sources = load_product_sources_FTP(datetime.date(2025, 11, 1))
        sp3 = sources["wuhan"].sp3
        assert isinstance(sp3, ProductSourceCollectionFTP)
        assert sp3.final.file_regex  # non-empty

    def test_sp3_regex_contains_doy_305(self):
        sources = load_product_sources_FTP(datetime.date(2025, 11, 1))
        assert "2025305" in sources["wuhan"].sp3.final.file_regex

    def test_all_product_attrs_present(self):
        sources = load_product_sources_FTP(datetime.date(2025, 11, 1))
        wuhan: ProductSourcesFTP = sources["wuhan"]
        for attr in ("sp3", "clk", "obx", "erp", "bias"):
            assert hasattr(wuhan, attr), f"Missing attribute: {attr}"
            coll = getattr(wuhan, attr)
            assert isinstance(coll, ProductSourceCollectionFTP)

    def test_broadcast_rnx3_present(self):
        sources = load_product_sources_FTP(datetime.date(2025, 11, 1))
        assert sources["wuhan"].broadcast_rnx3 is not None

    def test_different_dates_give_different_regex(self):
        s1 = load_product_sources_FTP(datetime.date(2025, 11, 1))
        s2 = load_product_sources_FTP(datetime.date(2025, 1, 1))
        assert s1["wuhan"].sp3.final.file_regex != s2["wuhan"].sp3.final.file_regex
