"""
Pydantic models for remote resource specifications (``*_v2.yml``).

A :class:`RemoteResourceSpec` represents a single GNSS data centre
(e.g. Wuhan, IGS/IGN) and the products it hosts.  Each
:class:`RemoteProduct` references a product definition from the
:class:`~gnss_ppp_products.assets.product_spec.productspec.ProductSpec`
and adds centre-specific metadata values and directory layout.

Usage::

    from gnss_ppp_products.assets.product_spec import ProductSpecRegistry
    from gnss_ppp_products.assets.remote_resource_spec.remote_resource import (
        RemoteResourceSpec,
    )

    spec = ProductSpecRegistry
    wuhan = RemoteResourceSpec.from_yaml("wuhan_v2.yml")

    # iterate products hosted by this centre
    for rp in wuhan.products:
        regexes = rp.to_regexes()
        ...
"""

from __future__ import annotations

import datetime
import itertools
import re
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field

from gnss_ppp_products.assets.meta_spec import MetaDataRegistry
from gnss_ppp_products.assets.product_spec import ProductSpecRegistry


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
    """A product hosted by this centre, linking to a ProductSpec entry.

    Attributes
    ----------
    id : str
        Unique identifier within this resource spec.
    spec : str | dict
        Either a plain product name (``"ORBIT"``) or a dict mapping a
        product name to a list of format-index dicts, e.g.
        ``{ATTATX: [{format: 0}]}``.
    server_id : str
        Which server hosts this product.
    available : bool
        Whether this product is currently available.
    description : str
        Human-readable description.
    metadata : dict[str, list[str]]
        Centre-specific metadata values.  Keys are metadata field names;
        values are the set of concrete values this centre provides for
        that field (e.g. ``AAA: ["WUM", "WMC"]``).
    directory : str
        Directory template on the remote server, may contain
        placeholders like ``{YYYY}``, ``{DDD}``, ``{GPSWK}``.
    """

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
        """Return the ProductSpec product name regardless of spec format."""
        if isinstance(self.spec, str):
            return self.spec
        return next(iter(self.spec))

    @property
    def format_indices(self) -> list[int]:
        """Return format ref indices specified in the spec, or ``[0]``."""
        if isinstance(self.spec, str):
            return [0]
        entries = next(iter(self.spec.values()))
        return [e["format"] for e in entries if isinstance(e, dict) and "format" in e]

    # ------------------------------------------------------------------
    # Directory resolution
    # ------------------------------------------------------------------

    def resolve_directory(self, date: datetime.date | datetime.datetime) -> str:
        """Substitute date-derived placeholders in the directory template.

        Only fields with a registered ``compute`` function are resolved;
        non-computable placeholders are left untouched.
        """
        if isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
            date = datetime.datetime(
                date.year, date.month, date.day,
                tzinfo=datetime.timezone.utc,
            )
        return MetaDataRegistry.resolve(
            self.directory, date, computed_only=True
        )
    

    # ------------------------------------------------------------------
    # Regex generation (delegates to ProductSpec)
    # ------------------------------------------------------------------

    def _metadata_combinations(self) -> list[dict[str, str]]:
        """Expand the centre metadata lists into every combination.

        For example ``{AAA: [WUM, WMC], TTT: [FIN, RAP]}`` yields
        four dicts: ``{AAA: WUM, TTT: FIN}``, ``{AAA: WUM, TTT: RAP}``,
        ``{AAA: WMC, TTT: FIN}``, ``{AAA: WMC, TTT: RAP}``.
        """
        if not self.metadata:
            return [{}]

        keys = list(self.metadata.keys())
        value_lists = [self.metadata[k] for k in keys]
        return [dict(zip(keys, combo)) for combo in itertools.product(*value_lists)]

    def to_regexes(
        self,
        date: datetime.date | datetime.datetime | None = None,
    ) -> list[str]:
        """Build filename regexes incorporating centre-specific metadata.

        Merges the product-spec constraints with each metadata
        combination from this centre, then delegates to
        :data:`ProductSpecRegistry` (with the centre values taking
        precedence).

        When *date* is provided, any metadata field that has a
        ``compute`` function is substituted with the concrete
        date-derived value (escaped as a regex literal) instead of
        the generic regex pattern.  This narrows the match to a
        single day/epoch.

        When the spec is a dict with explicit format indices, regexes
        are generated for each listed format index.  Otherwise, only
        format index 0 is used.

        Returns one regex per (format-index × metadata-combination × filename-template).
        """
        if date is not None and isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
            date = datetime.datetime(
                date.year, date.month, date.day,
                tzinfo=datetime.timezone.utc,
            )
        spec_name = self.spec_name
        regexes: list[str] = []

        for ref_index in self.format_indices:
            templates = ProductSpecRegistry.resolve_filename_templates(
                spec_name, ref_index
            )
            spec_constraints = ProductSpecRegistry.resolve_metadata_constraints(
                spec_name, ref_index
            )

            product = ProductSpecRegistry.products[spec_name]
            ref = product.formats[ref_index]
            fmt = ProductSpecRegistry.formats[ref.format]
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
            # Merge: centre values > spec constraints > format overrides > root defaults
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
                        meta_field = MetaDataRegistry.get(field)
                        if meta_field and meta_field.compute:
                            hit = re.escape(meta_field.compute(date))
                    if hit is None:
                        hit = _ci_get(MetaDataRegistry.defaults(), field)
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
    """Root model for a centre's ``*_v2.yml`` remote resource spec.

    Attributes
    ----------
    id : str
        Short centre identifier (e.g. ``"WUM"``, ``"IGS"``).
    name : str
        Human-readable name.
    description : str
        Detailed description.
    website : str
        Centre website URL.
    servers : list[Server]
        Available remote servers.
    products : list[RemoteProduct]
        Products hosted by this centre.
    """

    id: str
    name: str = ""
    description: str = ""
    website: str = ""
    servers: List[Server] = Field(default_factory=list)
    products: List[RemoteProduct] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "RemoteResourceSpec":
        """Load a ``RemoteResourceSpec`` from a YAML file."""
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate(raw)

    # ------------------------------------------------------------------
    # Look-ups
    # ------------------------------------------------------------------

    def get_server(self, server_id: str) -> Server:
        """Return a :class:`Server` by id."""
        for s in self.servers:
            if s.id == server_id:
                return s
        raise KeyError(f"Server {server_id!r} not found in {self.id}")

    def get_product(self, product_id: str) -> RemoteProduct:
        """Return a :class:`RemoteProduct` by id."""
        for p in self.products:
            if p.id == product_id:
                return p
        raise KeyError(f"Product {product_id!r} not found in {self.id}")

    def products_for_spec(self, spec_name: str) -> list[RemoteProduct]:
        """Return all products referencing a given ProductSpec name."""
        return [p for p in self.products if p.spec_name == spec_name]
