"""gnss CLI entry point — assembles all subcommands and exposes ``main()``."""

from gnss_ppp_etl_cli import app
from gnss_ppp_etl_cli.cmd_config import config_app
from gnss_ppp_etl_cli.cmd_download import download
from gnss_ppp_etl_cli.cmd_ppp import ppp
from gnss_ppp_etl_cli.cmd_resolve import resolve
from gnss_ppp_etl_cli.cmd_search import search

app.add_typer(config_app, name="config")
app.command("search")(search)
app.command("download")(download)
app.command("resolve")(resolve)
app.command("ppp")(ppp)


def main() -> None:
    app()
