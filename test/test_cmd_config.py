"""CLI tests for `gnss config` subcommands.

Uses Typer's CliRunner to invoke commands and asserts on exit codes,
stdout content, and filesystem side effects.  Live network calls are
avoided; connectivity checks in `validate` are not exercised here.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from gnss_ppp_etl.cli.app import app  # triggers subcommand assembly
from gnss_ppp_etl.config import UserConfig

runner = CliRunner()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _patch_config_path(tmp_path: Path):
    """Context manager that redirects the user config file to *tmp_path*."""
    cfg_file = tmp_path / "config.toml"
    return patch("gnss_ppp_etl.config._USER_CONFIG_PATH", cfg_file)


# ── gnss config show ──────────────────────────────────────────────────────────


def test_show_exits_zero(tmp_path):
    with _patch_config_path(tmp_path):
        result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0


def test_show_contains_all_keys(tmp_path):
    with _patch_config_path(tmp_path):
        result = runner.invoke(app, ["config", "show"])
    for key in (
        "base-dir",
        "pride-dir",
        "output-dir",
        "centers",
        "max-connections",
        "log-level",
        "default-mode",
    ):
        assert key in result.output, f"Expected key {key!r} in show output"


def test_show_reflects_file_values(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('max_connections = 12\nlog_level = "DEBUG"\n')

    with patch("gnss_ppp_etl.config._USER_CONFIG_PATH", cfg_file):
        result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "12" in result.output
    assert "DEBUG" in result.output


# ── gnss config set ───────────────────────────────────────────────────────────


def test_set_max_connections(tmp_path):
    with _patch_config_path(tmp_path) as _:
        result = runner.invoke(app, ["config", "set", "max-connections", "8"])

    assert result.exit_code == 0
    assert "8" in result.output
    assert (tmp_path / "config.toml").exists()


def test_set_and_reload(tmp_path):
    cfg_file = tmp_path / "config.toml"
    with patch("gnss_ppp_etl.config._USER_CONFIG_PATH", cfg_file):
        result = runner.invoke(app, ["config", "set", "max-connections", "16"])
        assert result.exit_code == 0

    with patch("gnss_ppp_etl.config._USER_CONFIG_PATH", cfg_file):
        cfg = UserConfig.load()
    assert cfg.max_connections == 16


def test_set_centers_multi_value(tmp_path):
    cfg_file = tmp_path / "config.toml"
    with patch("gnss_ppp_etl.config._USER_CONFIG_PATH", cfg_file):
        result = runner.invoke(app, ["config", "set", "centers", "COD", "ESA", "GFZ"])

    assert result.exit_code == 0

    from gnss_ppp_etl.config import UserConfig

    with patch("gnss_ppp_etl.config._USER_CONFIG_PATH", cfg_file):
        cfg = UserConfig.load()
    assert cfg.centers == ["COD", "ESA", "GFZ"]


def test_set_invalid_key_exits_nonzero(tmp_path):
    with _patch_config_path(tmp_path):
        result = runner.invoke(app, ["config", "set", "nonexistent-key", "value"])
    assert result.exit_code != 0


def test_set_log_level(tmp_path):
    cfg_file = tmp_path / "config.toml"
    with patch("gnss_ppp_etl.config._USER_CONFIG_PATH", cfg_file):
        result = runner.invoke(app, ["config", "set", "log-level", "DEBUG"])
    assert result.exit_code == 0

    from gnss_ppp_etl.config import UserConfig

    with patch("gnss_ppp_etl.config._USER_CONFIG_PATH", cfg_file):
        cfg = UserConfig.load()
    assert cfg.log_level == "DEBUG"


# ── gnss config reset ─────────────────────────────────────────────────────────


def test_reset_removes_file(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("max_connections = 8\n")

    with patch("gnss_ppp_etl.config._USER_CONFIG_PATH", cfg_file):
        result = runner.invoke(app, ["config", "reset", "--yes"])

    assert result.exit_code == 0
    assert not cfg_file.exists()


def test_reset_no_file_succeeds(tmp_path):
    """reset --yes when no config file exists should not error."""
    with _patch_config_path(tmp_path):
        result = runner.invoke(app, ["config", "reset", "--yes"])
    assert result.exit_code == 0


def test_reset_without_yes_prompts(tmp_path):
    """Without --yes, reset should prompt for confirmation."""
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("max_connections = 8\n")

    with patch("gnss_ppp_etl.config._USER_CONFIG_PATH", cfg_file):
        # Provide 'n' to decline
        result = runner.invoke(app, ["config", "reset"], input="n\n")

    assert result.exit_code == 0
    assert cfg_file.exists()  # file should still exist


# ── gnss config validate ──────────────────────────────────────────────────────


def test_validate_existing_base_dir_passes(tmp_path):
    base_dir = tmp_path / "gnss"
    base_dir.mkdir()
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(f'base_dir = "{base_dir}"\n')

    # Patch connectivity to skip live network calls
    with (
        patch("gnss_ppp_etl.config._USER_CONFIG_PATH", cfg_file),
        patch("gnss_ppp_etl.cli.cmd_config.ConnectionPoolFactory") as mock_cpf,
    ):
        mock_pool = mock_cpf.return_value
        mock_pool.list_directory.return_value = ["entry"]
        mock_pool._pools = {}

        # Use --no-connectivity to skip server checks in unit tests
        result = runner.invoke(app, ["config", "validate", "--no-connectivity"])

    assert result.exit_code == 0


def test_validate_missing_base_dir_fails(tmp_path):
    missing = tmp_path / "nonexistent"
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(f'base_dir = "{missing}"\n')

    with patch("gnss_ppp_etl.config._USER_CONFIG_PATH", cfg_file):
        result = runner.invoke(app, ["config", "validate", "--no-connectivity"])

    assert result.exit_code != 0


def test_validate_unknown_center_fails(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('centers = ["ZZZNOT_A_CENTER"]\n')

    with patch("gnss_ppp_etl.config._USER_CONFIG_PATH", cfg_file):
        result = runner.invoke(app, ["config", "validate", "--no-connectivity"])

    assert result.exit_code != 0
    assert "unknown" in result.output.lower() or "ZZZNOT_A_CENTER" in result.output


def test_validate_known_center_passes(tmp_path):
    cfg_file = tmp_path / "config.toml"
    # COD is a known center in DefaultProductEnvironment
    cfg_file.write_text('centers = ["COD"]\n')

    with patch("gnss_ppp_etl.config._USER_CONFIG_PATH", cfg_file):
        result = runner.invoke(app, ["config", "validate", "--no-connectivity"])

    assert result.exit_code == 0
    assert "COD" in result.output
