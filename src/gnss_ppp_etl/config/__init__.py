"""gnss_ppp_etl.config — configuration models and loader.

Public API
----------
AppConfig
    Root Pydantic model for all gnss-ppp-etl settings.
ClientConfig
    Sub-model forwarded to ``GNSSClient.from_defaults()``.
ProcessorConfig
    Sub-model forwarded to ``PrideProcessor.__init__()``.
ConfigLoader
    Class that resolves the full priority chain and returns an AppConfig.
USER_CONFIG_PATH
    Path to ``~/.config/gnss-ppp-etl/config.yaml``.
ENV_VAR
    Name of the single environment variable (``GNSS_CONFIG``).
"""

from gnss_ppp_etl.config.loader import (
    ENV_VAR,
    USER_CONFIG_PATH,
    ConfigLoader,
)
from gnss_ppp_etl.config.models import AppConfig, ClientConfig, ProcessorConfig

__all__ = [
    "AppConfig",
    "ClientConfig",
    "ProcessorConfig",
    "ConfigLoader",
    "USER_CONFIG_PATH",
    "ENV_VAR",
]
