"""Pure Pydantic models for local storage specifications."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from pydantic import BaseModel, Field, PrivateAttr, model_validator
import yaml

logger = logging.getLogger(__name__)


class LocalCollection(BaseModel):
    """A group of product specs sharing a directory template."""

    directory: str
    description: Optional[str] = None
    items: List = Field(default_factory=list)


class LocalResourceSpec(BaseModel):
    """Root model for a local storage layout.

    A single spec maps collection names to :class:`LocalCollection`
    objects.  Multiple specs can be merged via :meth:`merge` so that
    different YAML files (e.g. per-project or per-workflow) combine
    into one unified layout.
    """

    name: str = "default"
    description: Optional[str] = None
    collections: Dict[str, LocalCollection] = Field(default_factory=dict)
    source_file: Optional[Path] = None

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "LocalResourceSpec":
        """Load from a YAML file.

        Accepts either a top-level ``local:`` wrapper or a flat file
        whose top-level key is ``collections:``.
        """
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        
        class_instance = cls.model_validate(raw.get("local", raw))
        class_instance.source_file = Path(path)
        return class_instance

    @classmethod
    def merge(cls, specs: Sequence["LocalResourceSpec"]) -> "LocalResourceSpec":
        """Merge multiple local storage specs into one.

        Later specs override collections with the same name.  Items
        within identically-named collections are combined (union).
        """
        merged_collections: Dict[str, LocalCollection] = {}
        name = "_".join(spec.name for spec in specs)
        for spec in specs:
            for coll_name, coll in spec.collections.items():
                if coll_name in merged_collections:
                    existing = merged_collections[coll_name]
                    # Combine items (avoid duplicates, preserve order)
                    combined_items = list(existing.items)
                    for item in coll.items:
                        if item not in combined_items:
                            combined_items.append(item)
                    merged_collections[coll_name] = LocalCollection(
                        directory=coll.directory,
                        description=coll.description or existing.description,
                        items=combined_items,
                    )
                else:
                    merged_collections[coll_name] = coll.model_copy(deep=True)
        return cls(name=name, collections=merged_collections)
