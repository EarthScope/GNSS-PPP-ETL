"""Pydantic models for lockfile entries and dependency lockfiles."""

import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class LockProductAlternative(BaseModel):
    """An alternative (mirror / fallback) source for a locked product."""

    url: str = Field(..., description="Absolute URL to the alternative resource.")


class LockProduct(BaseModel):
    """A single resolved product entry in the lockfile."""

    name: str
    description: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 timestamp of when the product was locked.",
    )
    # Primary source
    url: str = Field(..., description="Absolute URL to the primary resource.")
    hash: str = Field("", description="Hash of the resource for integrity verification.")
    size: Optional[int] = Field(None, description="Size of the resource in bytes.")

    # Relative directory template for local layout, e.g. "products/{year}/orbit/"
    sink: str = Field("", description="Sink Path")

    alternatives: List[LockProductAlternative] = Field(
        default_factory=list,
        description="List of alternative sources for the product.",
    )


class DependencyLockFile(BaseModel):
    """Top-level lockfile: a fully-resolved, reproducible product manifest.

    The lockfile is date-scoped — one lockfile per processing day.
    """

    station: str = Field(
        ..., description="Name of the station this lockfile corresponds to, e.g. 'ALIC'."
    )
    date: str = Field(
        ..., description="Processing date this lockfile corresponds to, in YYYY-MM-DD format."
    )
    package: str = Field(
        ..., description="Name of the package this lockfile corresponds to, e.g. 'PRIDE'."
    )
    task: str = Field(
        ..., description="Name of the processing task this lockfile corresponds to, e.g. 'PPP'."
    )
    version: str = Field(
        "0", description="Version of the lockfile format, for future compatibility."
    )
    requires_date: bool = Field(
        True, description="Whether the lockfile is date-scoped (one lockfile per processing day)."
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 timestamp of when the lockfile was created.",
    )
    products: List[LockProduct] = Field(default_factory=list)
    metadata: Optional[dict] = Field(
        None, description="Optional additional metadata about the lockfile or resolution process."
    )
