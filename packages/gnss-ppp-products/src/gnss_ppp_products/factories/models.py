"""Author: Franklyn Dunbar

Public return types and exceptions for the ProductEnvironment API.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, PrivateAttr


class FoundResource(BaseModel):
    """A discovered product resource — either a local file or a remote URI."""

    product: str = Field(..., description="Product name (e.g. 'ORBIT', 'CLOCK').")
    source: str = Field(..., description="'local' or 'remote'.")
    uri: str = Field(..., description="Local file path or remote URL.")
    center: str = Field("", description="Analysis center identifier (e.g. 'WUM').")
    quality: str = Field("", description="Solution type (e.g. 'FIN', 'RAP', 'ULT').")
    parameters: Dict[str, str] = Field(
        default_factory=dict, description="All resolved parameter values."
    )

    # Internal: original ResourceQuery, not serialized. Used by DownloadPipeline.
    _query: Optional[object] = PrivateAttr(default=None)

    @property
    def is_local(self) -> bool:
        """``True`` if this resource was found on the local filesystem."""
        return self.source == "local"

    @property
    def path(self) -> Optional[Path]:
        """Return the local :class:`Path` if this is a local resource, else ``None``."""
        if self.is_local:
            return Path(self.uri)
        return None


class Resolution(BaseModel):
    """Result of resolving all dependencies for a task."""

    task: str = Field(..., description="Dependency spec name (e.g. 'pride-pppar').")
    paths: List[Path] = Field(
        default_factory=list, description="Local paths of all resolved products."
    )
    lockfile: Optional["ProductLockfile"] = None

    model_config = {"arbitrary_types_allowed": True}


class DiscoveryEntry(BaseModel):
    """A single entry in a discovery report."""

    product: str
    center: str = ""
    quality: str = ""
    source: str = ""
    uri: str = ""


class DiscoveryReport(BaseModel):
    """Structured summary of available products for a date."""

    entries: List[DiscoveryEntry] = Field(default_factory=list)

    @property
    def products(self) -> List[str]:
        """Sorted list of unique product names in this report."""
        return sorted(set(e.product for e in self.entries))

    @property
    def centers(self) -> List[str]:
        """Sorted list of unique center identifiers in this report."""
        return sorted(set(e.center for e in self.entries if e.center))

    def filter(
        self, product: Optional[str] = None, center: Optional[str] = None
    ) -> List[DiscoveryEntry]:
        """Filter entries by product name and/or center.

        Args:
            product: Product name filter.
            center: Center identifier filter.

        Returns:
            Matching :class:`DiscoveryEntry` instances.
        """
        out = self.entries
        if product:
            out = [e for e in out if e.product == product]
        if center:
            out = [e for e in out if e.center == center]
        return out


class MissingProductError(Exception):
    """Raised when a required product cannot be found during resolve()."""

    def __init__(self, missing: List[str], task: str = ""):
        self.missing = missing
        self.task = task
        products = ", ".join(missing)
        msg = (
            f"Missing required products for task {task!r}: {products}"
            if task
            else f"Missing required products: {products}"
        )
        super().__init__(msg)
