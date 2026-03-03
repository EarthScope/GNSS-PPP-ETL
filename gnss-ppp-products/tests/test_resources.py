"""
Tests for gnss_ppp_products.resources.GNSSOutputResource
"""
from __future__ import annotations

import datetime

import pytest

from gnss_ppp_products.resources import GNSSOutputResource


class TestGNSSOutputResource:
    DATE = datetime.date(2025, 11, 1)   # DOY 305, year 2025

    def _resource(self, tmp_path) -> GNSSOutputResource:
        return GNSSOutputResource(output_base_dir=str(tmp_path / "gnss"))

    # ── product_dir ──────────────────────────────────────────────────────────

    def test_product_dir_path_structure(self, tmp_path):
        r = self._resource(tmp_path)
        p = r.product_dir(self.DATE)
        assert p.parts[-3] == "2025"
        assert p.parts[-2] == "product"
        assert p.parts[-1] == "common"

    def test_product_dir_is_created(self, tmp_path):
        r = self._resource(tmp_path)
        p = r.product_dir(self.DATE)
        assert p.is_dir()

    def test_product_dir_is_year_independent_per_date(self, tmp_path):
        r = self._resource(tmp_path)
        p2025 = r.product_dir(datetime.date(2025, 6, 15))
        p2024 = r.product_dir(datetime.date(2024, 6, 15))
        assert "2025" in str(p2025)
        assert "2024" in str(p2024)
        assert p2025 != p2024

    # ── nav_dir ──────────────────────────────────────────────────────────────

    def test_nav_dir_path_structure(self, tmp_path):
        r = self._resource(tmp_path)
        p = r.nav_dir(self.DATE)
        assert p.parts[-2] == "2025"
        assert p.parts[-1] == "305"

    def test_nav_dir_is_created(self, tmp_path):
        r = self._resource(tmp_path)
        p = r.nav_dir(self.DATE)
        assert p.is_dir()

    def test_nav_dir_jan_1_gives_001(self, tmp_path):
        r = self._resource(tmp_path)
        p = r.nav_dir(datetime.date(2025, 1, 1))
        assert p.parts[-1] == "001"

    def test_nav_dir_dec_31_non_leap_gives_365(self, tmp_path):
        r = self._resource(tmp_path)
        p = r.nav_dir(datetime.date(2025, 12, 31))
        assert p.parts[-1] == "365"

    def test_nav_dir_dec_31_leap_gives_366(self, tmp_path):
        r = self._resource(tmp_path)
        p = r.nav_dir(datetime.date(2024, 12, 31))
        assert p.parts[-1] == "366"

    # ── config_file_path ─────────────────────────────────────────────────────

    def test_config_file_path_name(self, tmp_path):
        r = self._resource(tmp_path)
        p = r.config_file_path(self.DATE)
        assert p.name == "pride_ppp_ar_config"

    def test_config_file_path_under_nav_dir(self, tmp_path):
        r = self._resource(tmp_path)
        nav = r.nav_dir(self.DATE)
        cfg = r.config_file_path(self.DATE)
        assert cfg.parent == nav

    def test_config_file_path_contains_year_and_doy(self, tmp_path):
        r = self._resource(tmp_path)
        p = r.config_file_path(self.DATE)
        assert "2025" in str(p)
        assert "305" in str(p)

    # ── custom base dir ──────────────────────────────────────────────────────

    def test_default_base_dir_is_data_gnss(self):
        r = GNSSOutputResource()
        assert r.output_base_dir == "/data/gnss_products"

    def test_custom_base_dir_honoured(self, tmp_path):
        r = GNSSOutputResource(output_base_dir=str(tmp_path / "custom"))
        p = r.product_dir(self.DATE)
        assert str(tmp_path / "custom") in str(p)
