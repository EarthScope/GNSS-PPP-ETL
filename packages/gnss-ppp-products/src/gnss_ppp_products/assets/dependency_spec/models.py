"""
Pydantic models for dependency specifications.

A :class:`DependencySpec` declares all the GNSS products a processing
task requires (e.g. ORBIT, CLOCK, ERP …) plus a preference cascade
that controls which data center and solution quality to try first.

The preference cascade works as follows:  for **each** dependency, the
resolver walks the ``preferences`` list top‑to‑bottom.  At every slot
it narrows the catalog by center (and optionally solution / campaign),
checks local storage, and — if downloading is enabled — fetches the
file from the remote server.  The first hit wins and the resolver
moves on to the next dependency.

Axes that a product does not use (e.g. ``solution`` for LEAP_SEC) are
silently ignored so a single preference list works across all product
types.

Usage::

    spec = DependencySpec.from_yaml("pride_ppp_kin.yml")
    for dep in spec.dependencies:
        print(dep.spec, dep.required)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field


# ===================================================================
# Preference cascade
# ===================================================================


class SearchPreference(BaseModel):
    """One slot in the preference cascade.

    At resolution time the resolver narrows the product catalog by
    ``center`` and — if the product has those axes — ``solution`` and
    ``campaign``.  Fields left blank are simply skipped.
    """

    center: str
    solution: str = ""
    campaign: str = ""


# ===================================================================
# Dependency declaration
# ===================================================================


class Dependency(BaseModel):
    """A single product dependency.

    Attributes
    ----------
    spec : str
        Product spec name (``"ORBIT"``, ``"CLOCK"``, …).  Must match a
        key in ``ProductSpecRegistry.products``.
    required : bool
        If ``True`` the task cannot succeed without this product.
    description : str
        Human‑readable explanation of this dependency.
    constraints : dict[str, str]
        Extra axis values to pin when querying (e.g.
        ``{"sampling": "05M"}``).  These are applied *before* the
        preference cascade.
    """

    spec: str
    required: bool = True
    description: str = ""
    constraints: Dict[str, str] = Field(default_factory=dict)


# ===================================================================
# Root model
# ===================================================================


class DependencySpec(BaseModel):
    """Full dependency specification for a processing task.

    Attributes
    ----------
    name : str
        Short identifier (e.g. ``"pride_ppp_kinematic"``).
    description : str
        Human‑readable summary.
    preferences : list[SearchPreference]
        Ordered preference cascade — tried top→bottom for every
        dependency.
    dependencies : list[Dependency]
        Product specs the task needs.
    """

    name: str
    description: str = ""
    preferences: List[SearchPreference] = Field(default_factory=list)
    dependencies: List[Dependency] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "DependencySpec":
        """Load a dependency spec from a YAML file."""
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate(raw)


# ===================================================================
# Resolution result types
# ===================================================================


@dataclass
class ResolvedDependency:
    """Resolution result for one dependency.

    Attributes
    ----------
    spec : str
        Product spec name.
    required : bool
        Whether this dependency is required.
    status : str
        ``"local"`` — found on disk.
        ``"downloaded"`` — fetched from a remote server.
        ``"missing"`` — not found anywhere.
    query_result
        The :class:`QueryResult` that was matched (``None`` when
        missing).
    local_path : Path or None
        Full path to the file on disk (after local find or download).
    preference_rank : int
        Index into the preference list that succeeded (``-1`` when
        missing or when no preference list was defined).
    preference_label : str
        Human‑readable summary of the winning preference slot
        (e.g. ``"WUM/FIN/MGX"``).
    """

    spec: str
    required: bool
    status: str  # "local" | "downloaded" | "missing"
    query_result: object = None
    local_path: Optional[Path] = None
    preference_rank: int = -1
    preference_label: str = ""


@dataclass
class DependencyResolution:
    """Aggregated resolution result for all dependencies.

    Provides convenience accessors, a summary line, and a
    ``product_paths`` dict mapping spec names to local file paths.
    """

    spec_name: str
    resolved: List[ResolvedDependency] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def fulfilled(self) -> List[ResolvedDependency]:
        """Dependencies that were found (locally or downloaded)."""
        return [r for r in self.resolved if r.status != "missing"]

    @property
    def missing(self) -> List[ResolvedDependency]:
        """Dependencies that could not be resolved."""
        return [r for r in self.resolved if r.status == "missing"]

    @property
    def all_required_fulfilled(self) -> bool:
        """``True`` when every *required* dependency is satisfied."""
        return all(
            r.status != "missing"
            for r in self.resolved
            if r.required
        )

    def product_paths(self) -> Dict[str, Path]:
        """Map spec name → local file path for all fulfilled deps."""
        return {
            r.spec: r.local_path
            for r in self.resolved
            if r.local_path is not None
        }

    def summary(self) -> str:
        """One‑line human‑readable summary."""
        total = len(self.resolved)
        local = sum(1 for r in self.resolved if r.status == "local")
        downloaded = sum(1 for r in self.resolved if r.status == "downloaded")
        missing_count = sum(1 for r in self.resolved if r.status == "missing")
        return (
            f"DependencyResolution({self.spec_name}): "
            f"{total} deps — "
            f"{local} local, {downloaded} downloaded, "
            f"{missing_count} missing"
        )

    def table(self) -> str:
        """Formatted table of results."""
        lines = [
            f"{'spec':<14s} {'required':<10s} {'status':<12s} "
            f"{'preference':<20s} {'path'}"
        ]
        lines.append("-" * 90)
        for r in self.resolved:
            path_str = str(r.local_path) if r.local_path else "(none)"
            lines.append(
                f"{r.spec:<14s} {'yes' if r.required else 'no':<10s} "
                f"{r.status:<12s} {r.preference_label:<20s} {path_str}"
            )
        return "\n".join(lines)
