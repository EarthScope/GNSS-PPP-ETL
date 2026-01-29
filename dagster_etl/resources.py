"""Dagster resources for GNSS processing."""

from pathlib import Path
from dagster import ConfigurableResource
from pydantic import Field


class GNSSConfigResource(ConfigurableResource):
    """Configuration resource for GNSS processing pipeline."""

    pride_base_dir: str = Field(
        description="Base directory for PRIDE-PPP products and outputs"
    )
    default_source: str = Field(
        default="all",
        description="Default source for GNSS products: 'all', 'wuhan', or 'cligs'",
    )

    def get_pride_dir(self) -> Path:
        """Get the PRIDE directory as a Path object."""
        return Path(self.pride_base_dir)


# Create a default instance
gnss_config_resource = GNSSConfigResource(
    pride_base_dir="./pride_data",
    default_source="all",
)
