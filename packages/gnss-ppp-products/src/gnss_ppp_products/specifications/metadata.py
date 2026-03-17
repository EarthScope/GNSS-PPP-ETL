"""Pure Pydantic model for metadata field declarations."""

import datetime
from typing import Callable, Optional

from pydantic import BaseModel


class MetadataField(BaseModel):
    """A single registered metadata key."""

    name: str
    pattern: Optional[str] = None
    compute: Optional[Callable[[datetime.datetime], str]] = None
    description: Optional[str] = None
