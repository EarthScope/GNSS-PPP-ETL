"""Pure Pydantic models and result types for dependency specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field


class SearchPreference(BaseModel):
    """One slot in the preference cascade."""

    center: str
    solution: str = ""
    campaign: str = ""


class Dependency(BaseModel):
    """A single product dependency."""

    spec: str
    required: bool = True
    description: str = ""
    constraints: Dict[str, str] = Field(default_factory=dict)


class DependencySpec(BaseModel):
    """Full dependency specification for a processing task."""

    name: str
    description: str = ""
    preferences: List[SearchPreference] = Field(default_factory=list)
    dependencies: List[Dependency] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "DependencySpec":
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate(raw)


@dataclass
class ResolvedDependency:
    """Resolution result for one dependency."""

    spec: str
    required: bool
    status: str  # "local" | "downloaded" | "missing"
    query_result: object = None
    local_path: Optional[Path] = None
    preference_rank: int = -1
    preference_label: str = ""


@dataclass
class DependencyResolution:
    """Aggregated resolution result for all dependencies."""

    spec_name: str
    resolved: List[ResolvedDependency] = field(default_factory=list)

    @property
    def fulfilled(self) -> List[ResolvedDependency]:
        return [r for r in self.resolved if r.status != "missing"]

    @property
    def missing(self) -> List[ResolvedDependency]:
        return [r for r in self.resolved if r.status == "missing"]

    @property
    def all_required_fulfilled(self) -> bool:
        return all(
            r.status != "missing"
            for r in self.resolved
            if r.required
        )

    def product_paths(self) -> Dict[str, Path]:
        return {
            r.spec: r.local_path
            for r in self.resolved
            if r.local_path is not None
        }

    def summary(self) -> str:
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
