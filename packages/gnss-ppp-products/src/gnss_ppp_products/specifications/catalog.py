"""Base class for Layer 2 catalog objects.

All catalog classes must implement ``build()`` as a classmethod that
constructs a fully-built instance from lower-layer specifications.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from pydantic import BaseModel


class Catalog(BaseModel):
    """Abstract base for built catalogs.

    Subclasses **must** implement::

        @classmethod
        def build(cls, ...) -> Self:
            ...

    The ``build`` classmethod is the only way to construct a catalog
    in production code.  Direct ``__init__`` is still available for
    testing or deserialization.
    """

    @classmethod
    @abstractmethod
    def build(cls, *args: Any, **kwargs: Any) -> "Catalog":
        """Build a concrete catalog instance from lower-layer specs."""
        ...
