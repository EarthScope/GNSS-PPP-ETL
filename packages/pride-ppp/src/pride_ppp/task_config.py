"""
Task configuration loader for PRIDE-PPP.

Reads ``dependency.yaml`` and ``local_config.yaml`` from the bundled
config directory and constructs :class:`~gnss_ppp_products.tasks.Task`
instances ready for resolution and download.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import List, Optional, Union

import yaml

from gnss_ppp_products.assets.center.config import GNSSCenterConfig
from gnss_ppp_products.assets import (
    WuhanCenterConfig,
    IGSCenterConfig,
    CDDISCenterConfig,
)
from gnss_ppp_products.tasks import DependencyType, ProductDependency, Task

# ---------------------------------------------------------------------------
# Path to bundled config files
# ---------------------------------------------------------------------------

_CONFIG_DIR = Path(__file__).parent / "config_files"


def _load_dependency_yaml(path: Optional[Path] = None) -> dict:
    """Load and return the raw dependency YAML."""
    path = path or _CONFIG_DIR / "dependency.yaml"
    with open(path) as fh:
        return yaml.safe_load(fh)


CENTERS = {
    "wuhan": WuhanCenterConfig,
    "igs": IGSCenterConfig,
    "cddis": CDDISCenterConfig,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_centers(
    names: Optional[List[str]] = None,
    dependency_yaml: Optional[Path] = None,
) -> List[GNSSCenterConfig]:
    """Load ``GNSSCenterConfig`` objects for the requested center names.

    Parameters
    ----------
    names : list[str], optional
        Center names matching YAML filenames (e.g. ``["wuhan", "igs"]``).
        If ``None``, reads names from the dependency YAML.
    dependency_yaml : Path, optional
        Override path to the dependency YAML.

    Returns
    -------
    list[GNSSCenterConfig]
    """
    if names is None:
        dep = _load_dependency_yaml(dependency_yaml)
        names = dep.get("centers", [])

    centers: List[GNSSCenterConfig] = []
    for name in names or []:
        if name not in CENTERS:
            raise ValueError(f"Unknown center name: {name}")
        centers.append(CENTERS[name])

    return centers


def load_dependencies(
    dependency_yaml: Optional[Path] = None,
) -> List[ProductDependency]:
    """Parse the dependency YAML into ``ProductDependency`` objects.

    Parameters
    ----------
    dependency_yaml : Path, optional
        Override path to the dependency YAML.

    Returns
    -------
    list[ProductDependency]
    """
    dep = _load_dependency_yaml(dependency_yaml)
    dependencies: List[ProductDependency] = []
    for entry in dep.get("dependencies", []):
        dependencies.append(
            ProductDependency(
                type=DependencyType(entry["type"]),
                required=entry.get("required", True),
                description=entry.get("description"),
            )
        )
    return dependencies


def build_task(
    local_storage_root: Union[str, Path],
    *,
    dependency_yaml: Optional[Path] = None,
    center_names: Optional[List[str]] = None,
) -> Task:
    """Construct a fully configured :class:`Task` for PRIDE-PPP.

    Parameters
    ----------
    local_storage_root : str or Path
        Root directory for local product storage (the "pride_dir").
    dependency_yaml : Path, optional
        Override path to a custom dependency YAML.
    center_names : list[str], optional
        Override center names (instead of reading from the YAML).

    Returns
    -------
    Task
    """
    dependencies = load_dependencies(dependency_yaml)
    centers = load_centers(center_names, dependency_yaml)

    return Task(
        dependencies=dependencies,
        centers=centers,
        local_storage=local_storage_root,
    )
