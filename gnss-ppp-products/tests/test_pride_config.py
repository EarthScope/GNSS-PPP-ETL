"""
Tests for gnss_ppp_products.utils.pride_config

All tests are offline — no FTP or PRIDE binary needed.
"""
from __future__ import annotations

import pytest

from gnss_ppp_products.utils.pride_config import (
    AmbiguityFixingOptions,
    DataProcessingStrategies,
    ObservationConfig,
    PRIDEPPPFileConfig,
    SatelliteList,
    SatelliteProducts,
    StationUsed,
    pride_default_satellites,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(tmp_path=None, **sp_kwargs) -> PRIDEPPPFileConfig:
    """Return a minimal PRIDEPPPFileConfig with controllable satellite products."""
    sp_defaults = dict(
        product_directory=str(tmp_path or "/tmp/products"),
        satellite_orbit="orbit.SP3",
        satellite_clock="clock.CLK",
        erp="erp.ERP",
        quaternions="quat.OBX",
    )
    sp_defaults.update(sp_kwargs)
    return PRIDEPPPFileConfig(
        observation=ObservationConfig(table_directory="/tmp/table"),
        satellite_products=SatelliteProducts(**sp_defaults),
    )


# ---------------------------------------------------------------------------
# SatelliteProducts
# ---------------------------------------------------------------------------

class TestSatelliteProducts:
    def test_defaults_use_placeholder_extensions(self):
        sp = SatelliteProducts(product_directory="/data")
        # validator converts "Default" → "Default.SP3" etc.
        assert sp.satellite_orbit == "Default.SP3"
        assert sp.satellite_clock == "Default.CLK"
        assert sp.erp == "Default.ERP"
        assert sp.quaternions == "Default.OBX"
        assert sp.code_phase_bias == "Default.BIA"

    def test_gz_filenames_accepted(self):
        sp = SatelliteProducts(
            satellite_orbit="WMC0DEMFIN_20253050000_01D_05M_ORB.SP3.gz",
            satellite_clock="WMC0DEMFIN_20253050000_01D_30S_CLK.CLK.gz",
            erp="WUM0MGXRAP_20253050000_01D_01D_ERP.ERP.gz",
            quaternions="WMC0DEMFIN_20253050000_01D_30S_ATT.OBX.gz",
        )
        assert "SP3" in sp.satellite_orbit
        assert "CLK" in sp.satellite_clock

    def test_none_accepted_for_optional_fields(self):
        sp = SatelliteProducts(code_phase_bias=None)
        assert sp.code_phase_bias is None

    def test_product_directory_stored(self):
        sp = SatelliteProducts(product_directory="/my/output/dir")
        assert sp.product_directory == "/my/output/dir"


# ---------------------------------------------------------------------------
# PRIDEPPPFileConfig.write_config_file
# ---------------------------------------------------------------------------

class TestWriteConfigFile:
    def test_file_is_created(self, tmp_path):
        cfg = _make_config(tmp_path)
        out = tmp_path / "pride_ppp_ar_config"
        cfg.write_config_file(out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_directory(self, tmp_path):
        cfg = _make_config(tmp_path)
        out = tmp_path / "deep" / "nested" / "pride_ppp_ar_config"
        cfg.write_config_file(out)
        assert out.exists()

    def test_required_section_headers_present(self, tmp_path):
        cfg = _make_config(tmp_path)
        out = tmp_path / "config"
        cfg.write_config_file(out)
        text = out.read_text()
        for header in (
            "## Observation configuration",
            "## Satellite product",
            "## Data processing strategies",
            "## Ambiguity fixing options",
            "## Satellite list",
            "+GNSS satellites",
            "-GNSS satellites",
            "+Station used",
            "-Station used",
        ):
            assert header in text, f"Missing section: {header!r}"

    def test_satellite_product_filenames_in_output(self, tmp_path):
        cfg = _make_config(tmp_path)
        out = tmp_path / "config"
        cfg.write_config_file(out)
        text = out.read_text()
        assert "orbit.SP3" in text
        assert "clock.CLK" in text
        assert "quat.OBX" in text
        assert "erp.ERP" in text

    def test_table_directory_in_output(self, tmp_path):
        cfg = _make_config(tmp_path)
        out = tmp_path / "config"
        cfg.write_config_file(out)
        assert "/tmp/table" in out.read_text()

    def test_none_bias_written_as_none(self, tmp_path):
        cfg = _make_config(tmp_path, code_phase_bias=None)
        out = tmp_path / "config"
        cfg.write_config_file(out)
        assert "Code/phase bias        = None" in out.read_text()

    def test_default_satellite_list_contains_gps_glonass_galileo(self, tmp_path):
        cfg = _make_config(tmp_path)
        out = tmp_path / "config"
        cfg.write_config_file(out)
        text = out.read_text()
        assert " G01   1" in text  # GPS
        assert " R01   1" in text  # GLONASS
        assert " E01   1" in text  # Galileo
        assert " C06   1" in text  # BeiDou


# ---------------------------------------------------------------------------
# PRIDEPPPFileConfig.read_config_file (roundtrip)
# ---------------------------------------------------------------------------

class TestReadConfigFileRoundtrip:
    def _write_and_read(self, tmp_path, **sp_kwargs) -> PRIDEPPPFileConfig:
        cfg = _make_config(tmp_path, **sp_kwargs)
        out = tmp_path / "config"
        cfg.write_config_file(out)
        return PRIDEPPPFileConfig.read_config_file(out)

    def test_satellite_orbit_roundtrip(self, tmp_path):
        loaded = self._write_and_read(tmp_path, satellite_orbit="TEST_ORBIT.SP3")
        assert loaded.satellite_products.satellite_orbit == "TEST_ORBIT.SP3"

    def test_satellite_clock_roundtrip(self, tmp_path):
        loaded = self._write_and_read(tmp_path, satellite_clock="TEST_CLOCK.CLK")
        assert loaded.satellite_products.satellite_clock == "TEST_CLOCK.CLK"

    def test_product_directory_roundtrip(self, tmp_path):
        loaded = self._write_and_read(tmp_path, product_directory="/roundtrip/dir")
        assert loaded.satellite_products.product_directory == "/roundtrip/dir"

    def test_table_directory_roundtrip(self, tmp_path):
        cfg = _make_config(tmp_path)
        out = tmp_path / "config"
        cfg.write_config_file(out)
        loaded = PRIDEPPPFileConfig.read_config_file(out)
        assert loaded.observation.table_directory == "/tmp/table"

    def test_ambiguity_duration_roundtrip(self, tmp_path):
        cfg = _make_config(tmp_path)
        cfg.ambiguity.ambiguity_duration = 900
        out = tmp_path / "config"
        cfg.write_config_file(out)
        loaded = PRIDEPPPFileConfig.read_config_file(out)
        assert loaded.ambiguity.ambiguity_duration == 900

    def test_satellite_list_roundtrip(self, tmp_path):
        loaded = self._write_and_read(tmp_path)
        assert "G01" in loaded.satellites.satellites
        assert loaded.satellites.satellites["G01"] == 1


# ---------------------------------------------------------------------------
# Default satellite table
# ---------------------------------------------------------------------------

class TestPrideDefaultSatellites:
    def test_contains_gps(self):
        gps = [k for k in pride_default_satellites if k.startswith("G")]
        assert len(gps) == 32

    def test_contains_glonass(self):
        glo = [k for k in pride_default_satellites if k.startswith("R")]
        assert len(glo) == 24

    def test_c18_has_variance_3(self):
        # C18 is a known problematic satellite, variance = 3
        assert pride_default_satellites["C18"] == 3

    def test_all_others_have_variance_1(self):
        for prn, var in pride_default_satellites.items():
            if prn != "C18":
                assert var == 1, f"{prn} expected variance 1, got {var}"
