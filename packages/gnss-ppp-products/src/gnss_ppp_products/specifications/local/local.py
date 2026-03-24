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
        return cls(name="merged", collections=merged_collections)
   

    # @model_validator(mode="after")
    # def _validate_spec_uniqueness(self) -> "LocalResourceSpec":
    #     spec_to_collection: Dict[str, str] = {}
    #     for coll_name, coll in self.collections.items():
    #         for s in coll.specs:
    #             if s in spec_to_collection:
    #                 raise ValueError(
    #                     f"Spec {s!r} is in multiple collections: "
    #                     f"{spec_to_collection[s]!r} and {coll_name!r}"
    #                 )
    #             spec_to_collection[s] = coll_name
    #     self._spec_to_collection_map = spec_to_collection
    #     return self

    # def get_collection(self, name: str) -> LocalCollection:
    #     try:
    #         return self.collections[name]
    #     except KeyError:
    #         raise KeyError(
    #             f"Collection {name!r} not found. "
    #             f"Available: {list(self.collections)}"
    #         )

    # def collection_for_spec(self, spec_name: str) -> LocalCollection:
    #     coll_name = self._spec_to_collection_map.get(spec_name)
    #     if coll_name is None:
    #         raise KeyError(
    #             f"Spec {spec_name!r} not found in any collection. "
    #             f"Known specs: {self.all_specs}"
    #         )
    #     return self.collections[coll_name]

    # def collection_name_for_spec(self, spec_name: str) -> str:
    #     """Return the collection name that owns *spec_name*."""
    #     coll_name = self._spec_to_collection_map.get(spec_name)
    #     if coll_name is None:
    #         raise KeyError(
    #             f"Spec {spec_name!r} not found in any collection. "
    #             f"Known specs: {self.all_specs}"
    #         )
    #     return coll_name

    # @property
    # def all_specs(self) -> List[str]:
    #     return [s for coll in self.collections.values() for s in coll.specs]

    # @property
    # def base_dir(self) -> Optional[Path]:
    #     return self._base_dir

    # @base_dir.setter
    # def base_dir(self, value: str | Path) -> None:
    #     self._base_dir = Path(value)
