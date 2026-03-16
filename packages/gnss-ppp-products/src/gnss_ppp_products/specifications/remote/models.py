"""
Pydantic models for remote resource specifications (``*_v2.yml``).

A :class:`RemoteResourceSpec` represents a single GNSS data center
and the products it hosts.  Each :class:`RemoteProduct` references a
product definition and adds center-specific metadata values and
directory layout.

This module is agnostic — it does not import any global singletons.
Callers pass registry instances explicitly when calling methods that
need them (``resolve_directory``, ``to_regexes``).
"""

from __future__ import annotations

import datetime
import itertools
import re
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field


# ===================================================================
# Server
# ===================================================================


class Server(BaseModel):
    """A remote server definition."""

    id: str
    name: str = ""
    hostname: str
    protocol: str = "ftp"
    auth_required: bool = False
    notes: str = ""


# ===================================================================
# Remote product
# ===================================================================


class RemoteProduct(BaseModel):
    """A product hosted by a data center."""

    id: str
    spec: Union[str, Dict]
    server_id: str
    available: bool = True
    description: str = ""
    metadata: Dict[str, List[str]] = Field(default_factory=dict)
    directory: str = ""

    # ------------------------------------------------------------------
    # Spec helpers
    # ------------------------------------------------------------------

    @property
    def spec_name(self) -> str:
        if isinstance(self.spec, str):
            return self.spec
        return next(iter(self.spec))

    @property
    def format_indices(self) -> list[int]:
        if isinstance(self.spec, str):
            return [0]
        entries = next(iter(self.spec.values()))
        return [e["format"] for e in entries if isinstance(e, dict) and "format" in e]

    # ------------------------------------------------------------------
    # Directory resolution
    # ------------------------------------------------------------------

    def resolve_directory(
        self,
        date: datetime.date | datetime.datetime,
        *,
        meta_registry=None,
    ) -> str:
        """Substitute date-derived placeholders in the directory template.

        Parameters
        ----------
        meta_registry
            Metadata registry instance.  **Required** — this module
            does not fall back to a global singleton.
        """
        if isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
            date = datetime.datetime(
                date.year, date.month, date.day,
                tzinfo=datetime.timezone.utc,
            )
        if meta_registry is None:
            raise TypeError(
                "meta_registry is required — specifications.remote.models "
                "does not use global singletons"
            )
        return meta_registry.resolve(
            self.directory, date, computed_only=True
        )

    # ------------------------------------------------------------------
    # Regex generation
    # ------------------------------------------------------------------

    def _metadata_combinations(self) -> list[dict[str, str]]:
        """Expand the center metadata lists into every combination."""
        if not self.metadata:
            return [{}]
        keys = list(self.metadata.keys())
        value_lists = [self.metadata[k] for k in keys]
        return [dict(zip(keys, combo)) for combo in itertools.product(*value_lists)]

    def to_regexes(
        self,
        date: datetime.date | datetime.datetime | None = None,
        *,
        meta_registry=None,
        product_registry=None,
    ) -> list[str]:
        """Build filename regexes incorporating center-specific metadata.

        Parameters
        ----------
        meta_registry
            Metadata registry instance.  **Required**.
        product_registry
            Product spec registry instance.  **Required**.
        """
        if meta_registry is None:
            raise TypeError("meta_registry is required")
        if product_registry is None:
            raise TypeError("product_registry is required")

        if date is not None and isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
            date = datetime.datetime(
                date.year, date.month, date.day,
                tzinfo=datetime.timezone.utc,
            )

        spec_name = self.spec_name
        regexes: list[str] = []

        for ref_index in self.format_indices:
            templates = product_registry.resolve_filename_templates(
                spec_name, ref_index
            )
            spec_constraints = product_registry.resolve_metadata_constraints(
                spec_name, ref_index
            )

            product = product_registry.products[spec_name]
            ref = product.formats[ref_index]
            fmt = product_registry.formats[ref.format]
            ver = fmt.versions[ref.version]
            format_overrides = ver.get_metadata_overrides()

        _PLACEHOLDER = re.compile(r"\{([^}]+)\}")
        _WB = re.compile(r"\\b")

        def _ci_get(mapping: dict[str, str], key: str) -> str | None:
            if key in mapping:
                return mapping[key]
            key_lower = key.lower()
            for k, v in mapping.items():
                if k.lower() == key_lower:
                    return v
            return None

        def _strip_wb(pattern: str) -> str:
            return _WB.sub("", pattern)

        regexes: list[str] = []

        for combo in self._metadata_combinations():
            merged = {**spec_constraints, **combo}

            for tmpl in templates:
                parts: list[str] = []
                last_end = 0
                for m in _PLACEHOLDER.finditer(tmpl):
                    literal = re.escape(tmpl[last_end : m.start()])
                    parts.append(
                        literal.replace(r"\.\*", ".*").replace(r"\*", ".*")
                    )
                    field = m.group(1)
                    hit = _ci_get(merged, field)
                    if hit is None:
                        hit = _ci_get(format_overrides, field)
                    if hit is None and date is not None:
                        meta_field = meta_registry.get(field)
                        if meta_field and meta_field.compute:
                            hit = re.escape(meta_field.compute(date))
                    if hit is None:
                        hit = _ci_get(meta_registry.defaults(), field)
                    parts.append(_strip_wb(hit) if hit is not None else ".+")
                    last_end = m.end()

                trailing = re.escape(tmpl[last_end:])
                parts.append(
                    trailing.replace(r"\.\*", ".*").replace(r"\*", ".*")
                )
                regexes.append("".join(parts))

        return regexes

    def get_server(self, spec: "RemoteResourceSpec") -> Server:
        """Look up the :class:`Server` for this product."""
        for s in spec.servers:
            if s.id == self.server_id:
                return s
        raise KeyError(f"Server {self.server_id!r} not found in {spec.id}")


# ===================================================================
# Root model
# ===================================================================


class RemoteResourceSpec(BaseModel):
    """Root model for a center's ``*_v2.yml`` remote resource spec."""

    id: str
    name: str = ""
    description: str = ""
    website: str = ""
    servers: List[Server] = Field(default_factory=list)
    products: List[RemoteProduct] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "RemoteResourceSpec":
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate(raw)

    def get_server(self, server_id: str) -> Server:
        for s in self.servers:
            if s.id == server_id:
                return s
        raise KeyError(f"Server {server_id!r} not found in {self.id}")

    def get_product(self, product_id: str) -> RemoteProduct:
        for p in self.products:
            if p.id == product_id:
                return p
        raise KeyError(f"Product {product_id!r} not found in {self.id}")

    def products_for_spec(self, spec_name: str) -> list[RemoteProduct]:
        return [p for p in self.products if p.spec_name == spec_name]
