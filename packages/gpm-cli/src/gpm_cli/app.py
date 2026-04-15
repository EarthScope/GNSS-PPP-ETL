"""gnss CLI entry point — assembles all subcommands and exposes ``main()``."""

from gpm_cli import app
from gpm_cli.cmd_config import config_app
from gpm_cli.cmd_download import download
from gpm_cli.cmd_probe import probe
from gpm_cli.cmd_search import search

app.add_typer(config_app, name="config")
app.command("search")(search)
app.command("download")(download)
app.command("probe")(probe)


def main() -> None:
    app()
