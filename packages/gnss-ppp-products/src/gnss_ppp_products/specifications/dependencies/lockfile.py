"""
Pydantic models for the GNSS product lockfile.

A lockfile is a fully-resolved, reproducible snapshot of every product
needed for a processing run.  It captures absolute URLs so that any
researcher can reconstruct the exact same file set without re-resolving
against remote servers.

Serialisation formats
~~~~~~~~~~~~~~~~~~~~~
JSON is the primary format — zero extra dependencies, universally readable,
round-trips perfectly through Pydantic.  YAML is offered as an alternative
since PyYAML is already a project dependency and some users prefer it for
readability.

Portability
~~~~~~~~~~~
Each ``LockProduct`` carries a ``local_directory`` template string
(e.g. ``"products/{year}/orbit/"``) so that the receiver can reconstruct
the local folder tree under their own base directory.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field


# ── Alternative source ────────────────────────────────────────────


class LockProductAlternative(BaseModel):
    """An alternative (mirror / fallback) source for a locked product."""

    url: str = Field(..., description="Absolute URL to the alternative resource.")


# ── Single locked product ─────────────────────────────────────────


class LockProduct(BaseModel):
    """A single resolved product entry in the lockfile."""

    name: str
    format: str = ""
    version: str = ""
    variant: str = ""
    description: str = ""
    required: bool = True

    # Primary source
    url: str = Field(..., description="Absolute URL to the primary resource.")
    regex: str = Field("", description="Regex pattern for validating the resource URL.")
    hash: str = Field("", description="Hash of the resource for integrity verification.")
    size: Optional[int] = Field(None, description="Size of the resource in bytes.")

    # Relative directory template for local layout, e.g. "products/{year}/orbit/"
    local_directory: str = Field("", description="Relative directory template for local layout.")

    alternatives: List[LockProductAlternative] = Field(default_factory=list, description="List of alternative sources for the product.")

# ── Top-level lockfile ────────────────────────────────────────────


class ProductLockfile(BaseModel):
    """Top-level lockfile: a fully-resolved, reproducible product manifest.

    The lockfile is date-scoped — one lockfile per processing day.
    """

    version: int = 1
    task_id: Optional[str] = Field(None, description="Optional identifier for the processing task this lockfile corresponds to.")
    requires_date: str
    timestamp: str = ""
    products: List[LockProduct] = Field(default_factory=list)

    # ── JSON (primary format — zero-dependency) ───────────────────

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a JSON string."""
        return self.model_dump_json(indent=indent, by_alias=True)

    def to_json_file(self, path: Union[str, Path]) -> None:
        """Write the lockfile as JSON."""
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_json(cls, text: str) -> "ProductLockfile":
        """Parse a lockfile from a JSON string."""
        return cls.model_validate_json(text)

    @classmethod
    def from_json_file(cls, path: Union[str, Path]) -> "ProductLockfile":
        """Load a lockfile from a JSON file on disk."""
        return cls.model_validate_json(Path(path).read_bytes())

    # ── YAML (human-friendly alternative — PyYAML already a dep) ──

    def to_yaml(self) -> str:
        """Serialize to a YAML string."""
        return yaml.dump(
            self._to_portable_dict(),
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    def to_yaml_file(self, path: Union[str, Path]) -> None:
        """Write the lockfile as YAML."""
        Path(path).write_text(self.to_yaml(), encoding="utf-8")

    @classmethod
    def from_yaml(cls, text: str) -> "ProductLockfile":
        """Parse a lockfile from a YAML string."""
        raw = yaml.safe_load(text)
        return cls.model_validate(cls._normalize_keys(raw))

    @classmethod
    def from_yaml_file(cls, path: Union[str, Path]) -> "ProductLockfile":
        """Load a lockfile from a YAML file on disk."""
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate(cls._normalize_keys(raw))

    # ── Auto-detect format from file extension ────────────────────

    @classmethod
    def load(cls, path: Union[str, Path]) -> "ProductLockfile":
        """Load a lockfile, auto-detecting format from the file extension.

        Supported extensions: ``.json``, ``.yaml``, ``.yml``.
        """
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix == ".json":
            return cls.from_json_file(p)
        if suffix in (".yaml", ".yml"):
            return cls.from_yaml_file(p)
        raise ValueError(f"Unsupported lockfile extension: {suffix!r}")

    def save(self, path: Union[str, Path]) -> None:
        """Save the lockfile, auto-detecting format from the file extension."""
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix == ".json":
            self.to_json_file(p)
        elif suffix in (".yaml", ".yml"):
            self.to_yaml_file(p)
        else:
            raise ValueError(f"Unsupported lockfile extension: {suffix!r}")

    # ── Helpers ───────────────────────────────────────────────────

    def _to_portable_dict(self) -> Dict[str, Any]:
        """Dict representation with clean key names for YAML output."""
        data = self.model_dump(exclude_defaults=True)
        # Rename underscore keys to hyphenated for file-friendliness
        if "requires_date" in data:
            data["requires-date"] = data.pop("requires_date")
        if "local_directory" in data:
            data["local-directory"] = data.pop("local_directory")
        for prod in data.get("products", []):
            if "local_directory" in prod:
                prod["local-directory"] = prod.pop("local_directory")
        return data

    @staticmethod
    def _normalize_keys(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Convert hyphenated keys back to underscored for Pydantic."""
        if "requires-date" in raw:
            raw["requires_date"] = raw.pop("requires-date")
        for prod in raw.get("products", []):
            if "local-directory" in prod:
                prod["local_directory"] = prod.pop("local-directory")
        return raw

    @classmethod
    def from_probe_results(
        cls,
        probe: Dict[str, Any],
        *,
        only_available: bool = True,
    ) -> "ProductLockfile":
        """Build a lockfile from a resource_probe.json dict.

        This bootstraps a lockfile from probe results without going
        through the full DependencyResolver pipeline.
        """
        products: List[LockProduct] = []

        results_by_spec = probe.get("results_by_spec", {})
        for spec_name, entries in results_by_spec.items():
            available = [
                e for e in entries if e.get("available")
            ] if only_available else entries
            if not available:
                continue

            primary = available[0]
            url_base = primary["remote_url"].rstrip("/")
            matched = primary.get("matched_files", [])
            primary_url = (
                f"{url_base}/{matched[0]}" if matched else url_base
            )

            alts: List[LockProductAlternative] = []
            for alt_entry in available[1:]:
                alt_base = alt_entry["remote_url"].rstrip("/")
                alt_matched = alt_entry.get("matched_files", [])
                alt_url = (
                    f"{alt_base}/{alt_matched[0]}" if alt_matched
                    else alt_base
                )
                alts.append(LockProductAlternative(
                    url=alt_url,
                    regex=alt_entry.get("regex", ""),
                ))

            products.append(LockProduct(
                name=spec_name,
                url=primary_url,
                regex=primary.get("regex", ""),
                alternatives=alts,
            ))

        return cls(
            requires_date=probe.get("summary", {}).get("probe_date", ""),
            timestamp=probe.get("summary", {}).get(
                "timestamp",
                datetime.now(timezone.utc).isoformat(),
            ),
            products=products,
        )
