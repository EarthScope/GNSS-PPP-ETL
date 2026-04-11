"""Config data models for gnss-ppp-etl.

Hierarchy
---------
AppConfig
├── client:    ClientConfig       → GNSSClient.from_defaults() kwargs
└── processor: ProcessorConfig    → PrideProcessor.__init__() kwargs
                   └── cli: PrideCLIConfig  (from pride_ppp package)

The models are Pydantic BaseModels so they can be validated, serialised to
YAML, and composed with the upstream package models (PrideCLIConfig).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pride_ppp.specifications.cli import PrideCLIConfig
from pydantic import BaseModel, Field, PrivateAttr, field_validator

# ── helpers ───────────────────────────────────────────────────────────────────


def _expand(v: Any) -> Any:
    """Expand a path-like value and return a Path, or None."""
    if v is None or v == "":
        return None
    return Path(str(v)).expanduser()


def _paths_to_str(d: dict) -> None:
    """Recursively convert Path values in a dict to plain strings (in-place)."""
    for k, v in d.items():
        if isinstance(v, Path):
            d[k] = str(v)
        elif isinstance(v, dict):
            _paths_to_str(v)


# ── sub-models ────────────────────────────────────────────────────────────────


class ClientConfig(BaseModel):
    """Configuration for :func:`gnss_product_management.GNSSClient.from_defaults`.

    Attributes
    ----------
    base_dir:
        Root directory (local path or cloud URI) where products are stored.
    max_connections:
        Maximum per-host connection-pool size.
    centers:
        Ordered list of preferred analysis-center IDs.  An empty list means
        *all* known centers are used.
    """

    base_dir: Path | None = None
    max_connections: int = 4
    centers: list[str] = Field(default_factory=list)

    @field_validator("base_dir", mode="before")
    @classmethod
    def _expand_base_dir(cls, v: Any) -> Any:
        return _expand(v)

    def to_kwargs(self) -> dict[str, Any]:
        """Return keyword arguments for ``GNSSClient.from_defaults()``."""
        kwargs: dict[str, Any] = {"max_connections": self.max_connections}
        if self.base_dir:
            kwargs["base_dir"] = self.base_dir
        return kwargs


class ProcessorConfig(BaseModel):
    """Configuration for :class:`pride_ppp.PrideProcessor`.

    Attributes
    ----------
    pride_dir:
        Working directory where PRIDE writes intermediate files.
    output_dir:
        Final destination for ``.kin`` / ``.res`` output files.
    default_mode:
        Product-timeliness mode: ``"default"`` (FIN→RAP→ULT cascade)
        or ``"final"`` (FINAL products only).
    cli:
        Fine-grained ``pdp3`` binary flags.  Inherits the full
        :class:`pride_ppp.specifications.cli.PrideCLIConfig` model so any
        pdp3 option can be set directly in the YAML config file.
    """

    pride_dir: Path | None = None
    output_dir: Path | None = None
    default_mode: str = "default"
    cli: PrideCLIConfig = Field(default_factory=PrideCLIConfig)

    @field_validator("pride_dir", "output_dir", mode="before")
    @classmethod
    def _expand_paths(cls, v: Any) -> Any:
        return _expand(v)

    def to_kwargs(self) -> dict[str, Any]:
        """Return keyword arguments for ``PrideProcessor.__init__()``."""
        kwargs: dict[str, Any] = {
            "mode": self.default_mode.upper(),
            "cli_config": self.cli,
        }
        if self.pride_dir:
            kwargs["pride_dir"] = self.pride_dir
        if self.output_dir:
            kwargs["output_dir"] = self.output_dir
        return kwargs


# ── root model ────────────────────────────────────────────────────────────────


class AppConfig(BaseModel):
    """Root configuration model for gnss-ppp-etl.

    Loaded via :class:`~gnss_ppp_etl.config.loader.ConfigLoader` which
    applies the full resolution chain::

        compiled defaults
            → ~/.config/gnss-ppp-etl/config.yaml
            → ./gnss-ppp-etl.yaml  (walks up from cwd)
            → $GNSS_CONFIG         (explicit override file)

    All three YAML sources share the same schema.  Later sources win on a
    per-key basis (deep-merged, not replaced wholesale).

    Example YAML
    ------------
    .. code-block:: yaml

        log_level: WARNING

        client:
          base_dir: ~/gnss_data
          max_connections: 4
          centers: [COD, ESA, GFZ]

        processor:
          pride_dir: ~/gnss_data/pride
          output_dir: ~/gnss_data/output
          default_mode: default
          cli:
            system: GREC23J
            cutoff_elevation: 7
            loose_edit: true
            tides: SOP
    """

    log_level: str = "WARNING"
    client: ClientConfig = Field(default_factory=ClientConfig)
    processor: ProcessorConfig = Field(default_factory=ProcessorConfig)

    # Private attribute: populated by ConfigLoader to label where each
    # top-level section came from ("default" | "user" | "project" | "env").
    _sources: dict[str, str] = PrivateAttr(default_factory=dict)

    # ── SDK bridge ────────────────────────────────────────────────────────────

    def to_client_kwargs(self) -> dict[str, Any]:
        """Return kwargs for :func:`GNSSClient.from_defaults`."""
        return self.client.to_kwargs()

    def to_processor_kwargs(self) -> dict[str, Any]:
        """Return kwargs for :class:`PrideProcessor.__init__`."""
        return self.processor.to_kwargs()

    # ── I/O ───────────────────────────────────────────────────────────────────

    def to_yaml(self) -> str:
        """Serialise the config to a YAML string.

        Only fields that differ from their defaults (or have been explicitly
        set) are included — ``exclude_none=True`` keeps the file tidy.
        """
        data = self.model_dump(exclude_none=True)
        _paths_to_str(data)
        return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def save(self, path: Path) -> None:
        """Serialise and write the config to *path*."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# gnss-ppp-etl configuration — managed by `gnss config`\n" + self.to_yaml()
        )

    @classmethod
    def from_yaml(cls, path: Path) -> AppConfig:
        """Load an :class:`AppConfig` from a YAML file.

        Returns a fully validated instance with Pydantic coercions applied
        (path expansion, list normalisation, etc.).
        """
        with path.open() as fh:
            data = yaml.safe_load(fh) or {}
        return cls.model_validate(data)
