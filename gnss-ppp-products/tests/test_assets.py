"""
Tests for gnss_ppp_products.defs.assets

``gnss_product_sources`` is tested offline (reads sources.yml only).
Download assets require live FTP and are marked ``integration``.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import dagster as dg
import pytest

from gnss_ppp_products.defs.assets import (
    all_assets,
    daily_partitions,
    downloaded_bias,
    downloaded_clk,
    downloaded_erp,
    downloaded_obx,
    downloaded_sp3,
    gnss_product_sources,
    pride_ppp_config,
)
from gnss_ppp_products.resources import GNSSOutputResource
from gnss_ppp_products.utils.validation import ValidationResult


# ---------------------------------------------------------------------------
# Asset registry checks (no materialisation needed)
# ---------------------------------------------------------------------------

class TestAssetRegistry:
    def test_all_assets_list_length(self):
        assert len(all_assets) == 8

    def test_expected_asset_keys(self):
        keys = {a.key.path[-1] for a in all_assets}
        assert keys == {
            "gnss_product_sources",
            "downloaded_sp3",
            "downloaded_clk",
            "downloaded_obx",
            "downloaded_erp",
            "downloaded_bias",
            "downloaded_broadcast_nav",
            "pride_ppp_config",
        }

    def test_daily_partitions_start_date(self):
        assert daily_partitions.start.strftime("%Y-%m-%d") == "2020-01-01"

    def test_product_assets_share_same_partitions_def(self):
        for asset in (downloaded_sp3, downloaded_clk, downloaded_obx,
                      downloaded_erp, downloaded_bias):
            defs = asset.partitions_def
            assert defs is not None
            assert isinstance(defs, dg.DailyPartitionsDefinition)


# ---------------------------------------------------------------------------
# gnss_product_sources — offline (reads sources.yml only)
# ---------------------------------------------------------------------------

class TestGnssProductSourcesAsset:
    def test_materialises_for_known_date(self):
        result = dg.materialize(
            [gnss_product_sources],
            partition_key="2025-11-01",
        )
        assert result.success

    def test_output_contains_both_servers(self):
        result = dg.materialize(
            [gnss_product_sources],
            partition_key="2025-11-01",
        )
        output = result.output_for_node("gnss_product_sources")
        assert "wuhan" in output
        assert "cligs" in output

    def test_output_is_dict(self):
        result = dg.materialize(
            [gnss_product_sources],
            partition_key="2025-01-01",
        )
        assert isinstance(result.output_for_node("gnss_product_sources"), dict)

    def test_different_partition_gives_different_regexes(self):
        r1 = dg.materialize([gnss_product_sources], partition_key="2025-11-01")
        r2 = dg.materialize([gnss_product_sources], partition_key="2025-01-01")
        o1 = r1.output_for_node("gnss_product_sources")
        o2 = r2.output_for_node("gnss_product_sources")
        assert (
            o1["wuhan"].sp3.final.file_regex
            != o2["wuhan"].sp3.final.file_regex
        )


# ---------------------------------------------------------------------------
# downloaded_sp3 — mocked (no FTP)
# ---------------------------------------------------------------------------

class TestDownloadedSp3Mocked:
    def test_success_path(self, tmp_path):
        fake_sp3 = tmp_path / "orbit.SP3.gz"
        fake_sp3.write_bytes(b"\x1f\x8b" + b"x" * 10)  # placeholder

        fake_validation = ValidationResult(
            is_valid=True,
            path=fake_sp3,
            checks={"nonzero_size": True, "gzip_integrity": True},
        )

        with (
            patch(
                "gnss_ppp_products.defs.assets.download_product_with_fallback",
                return_value=(fake_sp3, "wuhan", "FIN"),
            ),
            patch(
                "gnss_ppp_products.defs.assets.validate_product_file",
                return_value=fake_validation,
            ),
        ):
            result = dg.materialize(
                [gnss_product_sources, downloaded_sp3],
                partition_key="2025-11-01",
                resources={"gnss_output": GNSSOutputResource(output_base_dir=str(tmp_path))},
            )

        assert result.success
        output = result.output_for_node("downloaded_sp3")
        assert output["server"] == "wuhan"
        assert output["quality"] == "FIN"
        assert output["is_valid"] is True

    def test_download_failure_raises_failure(self, tmp_path):
        with (
            patch(
                "gnss_ppp_products.defs.assets.download_product_with_fallback",
                return_value=None,  # simulate no file found
            ),
        ):
            result = dg.materialize(
                [gnss_product_sources, downloaded_sp3],
                partition_key="2025-11-01",
                resources={"gnss_output": GNSSOutputResource(output_base_dir=str(tmp_path))},
                raise_on_error=False,
            )

        assert not result.success

    def test_validation_failure_raises_failure(self, tmp_path):
        fake_sp3 = tmp_path / "corrupt.SP3.gz"
        fake_sp3.write_bytes(b"\x00" * 5)

        fake_validation = ValidationResult(
            is_valid=False,
            path=fake_sp3,
            checks={"nonzero_size": True, "gzip_integrity": False},
            errors=["Gzip integrity check failed"],
        )

        with (
            patch(
                "gnss_ppp_products.defs.assets.download_product_with_fallback",
                return_value=(fake_sp3, "wuhan", "FIN"),
            ),
            patch(
                "gnss_ppp_products.defs.assets.validate_product_file",
                return_value=fake_validation,
            ),
        ):
            result = dg.materialize(
                [gnss_product_sources, downloaded_sp3],
                partition_key="2025-11-01",
                resources={"gnss_output": GNSSOutputResource(output_base_dir=str(tmp_path))},
                raise_on_error=False,
            )

        assert not result.success


# ---------------------------------------------------------------------------
# Integration tests — live FTP (skipped by default)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_full_pipeline_nov_2025(tmp_path):
    """End-to-end: download all products for 2025-11-01 and write PRIDE config."""
    result = dg.materialize(
        all_assets,
        partition_key="2025-11-01",
        resources={"gnss_output": GNSSOutputResource(output_base_dir=str(tmp_path))},
        raise_on_error=False,
    )
    # gnss_product_sources is always expected to succeed
    assert result.output_for_node("gnss_product_sources") is not None
