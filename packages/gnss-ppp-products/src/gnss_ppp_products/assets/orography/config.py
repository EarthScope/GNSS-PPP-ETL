from typing import List, Optional

from pydantic import BaseModel

from .base import OrographyBase, OrographyGridResolution
from .query import OrographyFileQuery


# ---------------------------------------------------------------------------
# YAML configuration schemas
# ---------------------------------------------------------------------------


class OrographyResolutionConfig(BaseModel):
    resolution: OrographyGridResolution
    description: Optional[str] = None


class OrographyConfig(OrographyBase):
    """Configuration for an orography grid file (static, no date dependency)."""
    id: str
    server_id: str
    available: bool = True
    description: Optional[str] = None
    notes: Optional[str] = None
    resolution_set: List[OrographyResolutionConfig]

    def build(self) -> List[OrographyFileQuery]:
        """Expand config into queries for each resolution."""
        assert self.filename is not None, "OrographyConfig must have a filename template"
        assert self.directory is not None, "OrographyConfig must have a directory template"

        resolutions = [r.resolution for r in self.resolution_set] or [None]

        queries: list[OrographyFileQuery] = []
        for resolution in resolutions:
            query = OrographyFileQuery(resolution=resolution)
            query.build_filename(self.filename)
            query.build_directory(self.directory)
            queries.append(query)
        return queries
