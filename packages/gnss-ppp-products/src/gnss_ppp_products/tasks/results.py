"""
Task resolution result types.

:class:`ResolvedProduct` tracks whether a single file query was
satisfied from local storage or still needs a remote download.
:class:`TaskResult` aggregates all resolutions for a task.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

from pydantic import BaseModel, ConfigDict

from ..assets.products.query import ProductFileQuery
from ..assets.antennae.query import AntennaeFileQuery
from ..assets.rinex.query import RinexFileQuery
from ..assets.troposphere.query import TroposphereFileQuery
from ..assets.orography.query import OrographyFileQuery
from ..assets.leo.query import LEOFileQuery
from ..assets.reference_tables.query import ReferenceTableFileQuery

from .dependencies import DependencyType

logger = logging.getLogger(__name__)

FileQuery = Union[
    ProductFileQuery,
    AntennaeFileQuery,
    RinexFileQuery,
    TroposphereFileQuery,
    OrographyFileQuery,
    LEOFileQuery,
    ReferenceTableFileQuery,
]


class ResolvedProduct(BaseModel):
    """Resolution result for a single file query.

    Attributes
    ----------
    dependency_type : DependencyType
        Which dependency category this result belongs to.
    query : FileQuery
        The file query that was resolved (carries server + filename info).
    local_paths : list[Path]
        Files found in local storage.  Empty when nothing was found.
    downloaded_path : Path or None
        Path to the downloaded file, populated after a successful
        remote download.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    dependency_type: DependencyType
    query: FileQuery
    local_paths: list[Path] = []
    downloaded_path: Path | None = None

    @property
    def found_locally(self) -> bool:
        """``True`` if at least one local file matched the query."""
        return len(self.local_paths) > 0

    @property
    def fulfilled(self) -> bool:
        """``True`` if the product is available (locally or downloaded)."""
        return self.found_locally or self.downloaded_path is not None


class TaskResult(BaseModel):
    """Aggregated results of task resolution.

    Provides convenience accessors for found / missing products and
    a summary for logging.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    resolved: list[ResolvedProduct] = []

    @property
    def found(self) -> list[ResolvedProduct]:
        """Products that were found in local storage."""
        return [r for r in self.resolved if r.found_locally]

    @property
    def missing(self) -> list[ResolvedProduct]:
        """Products not found locally (candidates for download)."""
        return [r for r in self.resolved if not r.found_locally]

    @property
    def fulfilled(self) -> list[ResolvedProduct]:
        """Products that are available (locally or after download)."""
        return [r for r in self.resolved if r.fulfilled]

    @property
    def unfulfilled(self) -> list[ResolvedProduct]:
        """Products still unavailable after resolution + download."""
        return [r for r in self.resolved if not r.fulfilled]

    def summary(self) -> str:
        """Return a human-readable summary string."""
        total = len(self.resolved)
        local = len(self.found)
        downloaded = sum(1 for r in self.resolved if r.downloaded_path is not None)
        missing = len(self.unfulfilled)
        return (
            f"TaskResult: {total} queries — "
            f"{local} found locally, "
            f"{downloaded} downloaded, "
            f"{missing} unfulfilled"
        )
