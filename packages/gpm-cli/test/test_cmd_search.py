"""CLI tests for `gnss search`.

Network calls are mocked — tests verify exit codes, table rendering,
and JSON output.  Integration tests that hit live servers are marked
`pytest.mark.integration` and excluded from the default CI run.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from gpm_cli.app import app  # triggers subcommand assembly
from typer.testing import CliRunner

runner = CliRunner()

# ── Shared mock helpers ───────────────────────────────────────────────────────


def _make_resource(
    product="ORBIT",
    center="COD",
    quality="FIN",
    filename="COD0OPSULT_20250150000_01D_15M_ORB.SP3.gz",
    is_local=False,
    uri="ftp://gnss.bkg.bund.de/path/to/file.sp3.gz",
):
    r = MagicMock()
    r.product = product
    r.center = center
    r.quality = quality
    r.filename = filename
    r.is_local = is_local
    r.hostname = "gnss.bkg.bund.de" if not is_local else ""
    r.uri = uri if not is_local else f"/data/{filename}"
    r.parameters = {"AAA": center, "TTT": quality}
    return r


def _patch_client(results):
    """Patch GNSSClient.from_defaults to return a mock that yields *results* from .search()."""
    mock_client = MagicMock()
    query = MagicMock()
    query.for_product.return_value = query
    query.on.return_value = query
    query.on_range.return_value = query
    query.where.return_value = query
    query.sources.return_value = query
    query.search.return_value = results
    mock_client.query.return_value = query
    return patch("gpm_cli.cmd_search.GNSSClient.from_defaults", return_value=mock_client)


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_search_unknown_product_exits_nonzero(tmp_path):
    """A product that returns no results should exit with code 1."""
    cfg_file = tmp_path / "config.toml"
    with (
        patch("gpm_cli.config._USER_CONFIG_PATH", cfg_file),
        _patch_client([]),
    ):
        result = runner.invoke(app, ["search", "NOTAPRODUCT", "--date", "2025-01-15"])

    assert result.exit_code != 0


def test_search_renders_table_columns(tmp_path):
    """Successful search should render Center, Quality, Filename, Local columns."""
    cfg_file = tmp_path / "config.toml"
    resources = [
        _make_resource(center="COD", quality="FIN"),
        _make_resource(center="ESA", quality="RAP", filename="ESA_file.sp3.gz"),
    ]

    with (
        patch("gpm_cli.config._USER_CONFIG_PATH", cfg_file),
        _patch_client(resources),
    ):
        result = runner.invoke(app, ["search", "ORBIT", "--date", "2025-01-15"])

    assert result.exit_code == 0
    assert "COD" in result.output
    assert "ESA" in result.output
    assert "FIN" in result.output
    assert "RAP" in result.output


def test_search_local_marker(tmp_path):
    """Resources already on disk should show a check mark in the Local column."""
    cfg_file = tmp_path / "config.toml"
    resources = [_make_resource(is_local=True)]

    with (
        patch("gpm_cli.config._USER_CONFIG_PATH", cfg_file),
        _patch_client(resources),
    ):
        result = runner.invoke(app, ["search", "ORBIT", "--date", "2025-01-15"])

    assert result.exit_code == 0
    assert "✓" in result.output


def test_search_json_output(tmp_path):
    """--json PATH should write a parseable JSON array to the given path."""
    cfg_file = tmp_path / "config.toml"
    json_out = tmp_path / "results.json"
    resources = [_make_resource()]

    with (
        patch("gpm_cli.config._USER_CONFIG_PATH", cfg_file),
        _patch_client(resources),
    ):
        result = runner.invoke(
            app, ["search", "ORBIT", "--date", "2025-01-15", "--json", str(json_out)]
        )

    assert result.exit_code == 0
    assert json_out.exists()
    data = json.loads(json_out.read_text())
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["center"] == "COD"
    assert data[0]["filename"] == "COD0OPSULT_20250150000_01D_15M_ORB.SP3.gz"
    assert data[0]["is_local"] is False


def test_search_json_contains_all_fields(tmp_path):
    """Each JSON record should include product, center, quality, filename, uri, is_local."""
    cfg_file = tmp_path / "config.toml"
    json_out = tmp_path / "out.json"
    resources = [_make_resource()]

    with (
        patch("gpm_cli.config._USER_CONFIG_PATH", cfg_file),
        _patch_client(resources),
    ):
        runner.invoke(app, ["search", "ORBIT", "--date", "2025-01-15", "--json", str(json_out)])

    data = json.loads(json_out.read_text())
    required_keys = {"product", "center", "quality", "filename", "uri", "is_local", "parameters"}
    assert required_keys.issubset(data[0].keys())


def test_search_where_filter_passed_to_query(tmp_path):
    """--where KEY=VALUE should call .where(**{KEY: VALUE}) on the query builder."""
    cfg_file = tmp_path / "config.toml"
    mock_client = MagicMock()
    query = MagicMock()
    query.for_product.return_value = query
    query.on.return_value = query
    query.where.return_value = query
    query.sources.return_value = query
    query.search.return_value = [_make_resource()]
    mock_client.query.return_value = query

    with (
        patch("gpm_cli.config._USER_CONFIG_PATH", cfg_file),
        patch("gpm_cli.cmd_search.GNSSClient.from_defaults", return_value=mock_client),
    ):
        result = runner.invoke(
            app, ["search", "ORBIT", "--date", "2025-01-15", "--where", "TTT=FIN"]
        )

    assert result.exit_code == 0
    query.where.assert_called_once_with(TTT="FIN")


def test_search_sources_filter_passed_to_query(tmp_path):
    """--sources COD ESA should call .sources('COD', 'ESA') on the query builder."""
    cfg_file = tmp_path / "config.toml"
    mock_client = MagicMock()
    query = MagicMock()
    query.for_product.return_value = query
    query.on.return_value = query
    query.where.return_value = query
    query.sources.return_value = query
    query.search.return_value = [_make_resource()]
    mock_client.query.return_value = query

    with (
        patch("gpm_cli.config._USER_CONFIG_PATH", cfg_file),
        patch("gpm_cli.cmd_search.GNSSClient.from_defaults", return_value=mock_client),
    ):
        result = runner.invoke(
            app, ["search", "ORBIT", "--date", "2025-01-15", "--sources", "COD", "--sources", "ESA"]
        )

    assert result.exit_code == 0
    query.sources.assert_called_once_with("COD", "ESA")


def test_search_invalid_date_exits_nonzero(tmp_path):
    """A malformed --date should exit with code 1."""
    cfg_file = tmp_path / "config.toml"
    with patch("gpm_cli.config._USER_CONFIG_PATH", cfg_file):
        result = runner.invoke(app, ["search", "ORBIT", "--date", "not-a-date"])
    assert result.exit_code != 0


def test_search_invalid_where_exits_nonzero(tmp_path):
    """A --where value without '=' should exit with code 1."""
    cfg_file = tmp_path / "config.toml"
    with (
        patch("gpm_cli.config._USER_CONFIG_PATH", cfg_file),
        _patch_client([]),
    ):
        result = runner.invoke(
            app, ["search", "ORBIT", "--date", "2025-01-15", "--where", "NOEQUALS"]
        )
    assert result.exit_code != 0


def test_search_date_range_uses_on_range(tmp_path):
    """Specifying --to should call .on_range() instead of .on() on the query."""
    cfg_file = tmp_path / "config.toml"
    mock_client = MagicMock()
    query = MagicMock()
    query.for_product.return_value = query
    query.on_range.return_value = query
    query.where.return_value = query
    query.sources.return_value = query
    query.search.return_value = [_make_resource()]
    mock_client.query.return_value = query

    with (
        patch("gpm_cli.config._USER_CONFIG_PATH", cfg_file),
        patch("gpm_cli.cmd_search.GNSSClient.from_defaults", return_value=mock_client),
    ):
        result = runner.invoke(
            app, ["search", "ORBIT", "--date", "2025-01-15", "--to", "2025-01-17"]
        )

    assert result.exit_code == 0
    query.on_range.assert_called_once()
    query.on.assert_not_called()
