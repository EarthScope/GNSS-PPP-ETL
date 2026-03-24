"""Base class for Layer 2 catalog objects.

All catalog classes must implement ``resolve()`` as a classmethod that
constructs a fully-resolved instance from lower-layer specifications.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from pydantic import BaseModel


class Catalog(BaseModel):
    """Abstract base for resolved catalogs.

    Subclasses **must** implement::

        @classmethod
        def resolve(cls, ...) -> Self:
            ...

    The ``resolve`` classmethod is the only way to construct a catalog
    in production code.  Direct ``__init__`` is still available for
    testing or deserialization.
    """

    @classmethod
    @abstractmethod
    def resolve(cls, *args: Any, **kwargs: Any) -> "Catalog":
        """Resolve lower-layer specs into a concrete catalog instance."""
        ...
