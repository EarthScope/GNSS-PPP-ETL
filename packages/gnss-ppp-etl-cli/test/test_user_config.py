"""Unit tests for UserConfig — resolution chain, persistence, and SDK bridge."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from gnss_ppp_etl_cli.config import UserConfig

# ── Helpers ───────────────────────────────────────────────────────────────────


def _write_toml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ── Defaults ──────────────────────────────────────────────────────────────────


def test_default_values():
    cfg = UserConfig.defaults()
    assert cfg.base_dir is None
    assert cfg.centers == []
    assert cfg.max_connections == 4
    assert cfg.log_level == "WARNING"


def test_default_sources_empty():
    cfg = UserConfig.defaults()
    assert cfg._sources == {}


# ── Resolution chain ──────────────────────────────────────────────────────────


def test_load_from_user_file(tmp_path):
    user_cfg = tmp_path / "config.toml"
    _write_toml(user_cfg, 'base_dir = "/data/gnss"\nmax_connections = 8\n')

    with patch("gnss_ppp_etl_cli.config._USER_CONFIG_PATH", user_cfg):
        cfg = UserConfig.load()

    assert cfg.base_dir == Path("/data/gnss")
    assert cfg.max_connections == 8
    assert cfg.log_level == "WARNING"  # default preserved
    assert cfg._sources.get("base_dir") == "user"
    assert cfg._sources.get("max_connections") == "user"


def test_project_config_overrides_user(tmp_path):
    user_cfg = tmp_path / "config.toml"
    _write_toml(user_cfg, 'max_connections = 4\nlog_level = "INFO"\n')

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_toml(project_dir / "gnss-ppp-etl.toml", "max_connections = 12\n")

    with patch("gnss_ppp_etl_cli.config._USER_CONFIG_PATH", user_cfg):
        cfg = UserConfig.load(project_dir=project_dir)

    assert cfg.max_connections == 12  # project overrides user
    assert cfg.log_level == "INFO"  # user value preserved
    assert cfg._sources.get("max_connections") == "project"
    assert cfg._sources.get("log_level") == "user"


def test_env_var_overrides_file(tmp_path, monkeypatch):
    user_cfg = tmp_path / "config.toml"
    _write_toml(user_cfg, "max_connections = 4\n")

    monkeypatch.setenv("GNSS_MAX_CONNECTIONS", "16")
    monkeypatch.setenv("GNSS_BASE_DIR", "/env/data")
    monkeypatch.setenv("GNSS_CENTERS", "COD,ESA,GFZ")
    monkeypatch.setenv("GNSS_LOG_LEVEL", "DEBUG")

    with patch("gnss_ppp_etl_cli.config._USER_CONFIG_PATH", user_cfg):
        cfg = UserConfig.load()

    assert cfg.max_connections == 16
    assert cfg.base_dir == Path("/env/data")
    assert cfg.centers == ["COD", "ESA", "GFZ"]
    assert cfg.log_level == "DEBUG"
    assert cfg._sources.get("max_connections") == "env"
    assert cfg._sources.get("base_dir") == "env"


def test_invalid_env_max_connections_ignored(tmp_path, monkeypatch):
    """A non-integer GNSS_MAX_CONNECTIONS env var should be silently ignored."""
    user_cfg = tmp_path / "config.toml"
    _write_toml(user_cfg, "max_connections = 6\n")

    monkeypatch.setenv("GNSS_MAX_CONNECTIONS", "not-a-number")

    with patch("gnss_ppp_etl_cli.config._USER_CONFIG_PATH", user_cfg):
        cfg = UserConfig.load()

    assert cfg.max_connections == 6  # file value preserved


# ── to_client_kwargs ──────────────────────────────────────────────────────────


def test_to_client_kwargs_with_base_dir():
    cfg = UserConfig(base_dir="/data/gnss", max_connections=8)
    kwargs = cfg.to_client_kwargs()
    assert kwargs["max_connections"] == 8
    assert kwargs["base_dir"] == Path("/data/gnss")


def test_to_client_kwargs_no_base_dir():
    cfg = UserConfig(max_connections=4)
    kwargs = cfg.to_client_kwargs()
    assert kwargs["max_connections"] == 4
    assert "base_dir" not in kwargs


def test_to_processor_kwargs():
    pass  # processor/pride functionality removed


def test_to_processor_kwargs_minimal():
    pass  # processor/pride functionality removed


# ── Persistence ───────────────────────────────────────────────────────────────


def test_save_and_reload(tmp_path):
    user_cfg = tmp_path / "config.toml"

    with patch("gnss_ppp_etl_cli.config._USER_CONFIG_PATH", user_cfg):
        cfg = UserConfig(max_connections=8, log_level="INFO")
        cfg.save()

    assert user_cfg.exists()

    with patch("gnss_ppp_etl_cli.config._USER_CONFIG_PATH", user_cfg):
        cfg2 = UserConfig.load()

    assert cfg2.max_connections == 8
    assert cfg2.log_level == "INFO"


def test_set_scalar_key(tmp_path):
    user_cfg = tmp_path / "config.toml"

    with patch("gnss_ppp_etl_cli.config._USER_CONFIG_PATH", user_cfg):
        cfg = UserConfig()
        cfg.set("max_connections", "12")

    assert cfg.max_connections == 12
    assert user_cfg.exists()

    with patch("gnss_ppp_etl_cli.config._USER_CONFIG_PATH", user_cfg):
        reloaded = UserConfig.load()
    assert reloaded.max_connections == 12


def test_set_centers_as_list(tmp_path):
    user_cfg = tmp_path / "config.toml"

    with patch("gnss_ppp_etl_cli.config._USER_CONFIG_PATH", user_cfg):
        cfg = UserConfig()
        cfg.set("centers", ["COD", "ESA", "GFZ"])

    assert cfg.centers == ["COD", "ESA", "GFZ"]

    with patch("gnss_ppp_etl_cli.config._USER_CONFIG_PATH", user_cfg):
        reloaded = UserConfig.load()
    assert reloaded.centers == ["COD", "ESA", "GFZ"]


def test_set_centers_as_comma_string(tmp_path):
    user_cfg = tmp_path / "config.toml"

    with patch("gnss_ppp_etl_cli.config._USER_CONFIG_PATH", user_cfg):
        cfg = UserConfig()
        cfg.set("centers", "COD, ESA, GFZ")

    assert cfg.centers == ["COD", "ESA", "GFZ"]


def test_set_unknown_key_raises():
    cfg = UserConfig()
    with pytest.raises(KeyError, match="Unknown config key"):
        cfg.set("nonexistent_field", "value")


def test_reset_removes_file(tmp_path):
    user_cfg = tmp_path / "config.toml"
    _write_toml(user_cfg, "max_connections = 8\n")

    with patch("gnss_ppp_etl_cli.config._USER_CONFIG_PATH", user_cfg):
        cfg = UserConfig.load()
        assert user_cfg.exists()
        cfg.reset()

    assert not user_cfg.exists()


def test_reset_no_file_is_safe(tmp_path):
    """reset() should not raise if the config file doesn't exist."""
    user_cfg = tmp_path / "config.toml"

    with patch("gnss_ppp_etl_cli.config._USER_CONFIG_PATH", user_cfg):
        cfg = UserConfig()
        cfg.reset()  # no file — should not raise


# ── TOML round-trip ───────────────────────────────────────────────────────────


def test_toml_roundtrip_all_fields(tmp_path):
    user_cfg = tmp_path / "config.toml"

    with patch("gnss_ppp_etl_cli.config._USER_CONFIG_PATH", user_cfg):
        cfg = UserConfig(
            base_dir=str(tmp_path / "data"),
            centers=["COD", "GFZ"],
            max_connections=10,
            log_level="DEBUG",
        )
        cfg.save()
        reloaded = UserConfig.load()

    assert reloaded.max_connections == 10
    assert reloaded.log_level == "DEBUG"
    assert reloaded.centers == ["COD", "GFZ"]
