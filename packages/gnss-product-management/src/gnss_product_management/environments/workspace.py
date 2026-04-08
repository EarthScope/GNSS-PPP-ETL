"""Author: Franklyn Dunbar

Workspace management for local GNSS product storage.

Maps :class:`LocalResourceSpec` definitions (loaded from YAML) to concrete
base directories on disk so that local resources can be queried through the
same :class:`ResourceQuery` interface used for remote servers.

Base directories may be local filesystem paths (``/data/gnss``) or cloud
URIs (``s3://bucket/prefix``).  Path operations are dispatched through
:func:`~gnss_product_management.utilities.paths.as_path` so that all
filesystem interactions work uniformly regardless of backend.
"""

from pathlib import Path

from typing import Dict, Optional, List

from gnss_product_management.specifications.remote.resource import Server
from gnss_product_management.utilities.paths import AnyPath, as_path
from pydantic import BaseModel

from gnss_product_management.specifications.local.local import LocalResourceSpec


def paths_overlap(p1: AnyPath | str, p2: AnyPath | str) -> bool:
    """Check whether two paths share a common ancestor-descendant relationship.

    For local paths, checks the resolved filesystem hierarchy.  For cloud
    URIs, falls back to string prefix comparison (cloud paths have no
    symlinks to resolve).

    Args:
        p1: First path or URI.
        p2: Second path or URI.

    Returns:
        ``True`` if either path is a parent of (or equal to) the other.
    """
    s1 = str(p1).rstrip("/")
    s2 = str(p2).rstrip("/")

    # Cloud paths — use string prefix comparison
    if "://" in s1 or "://" in s2:
        return s1.startswith(s2) or s2.startswith(s1)

    # Local paths — resolve symlinks before comparing
    r1 = Path(s1).resolve()
    r2 = Path(s2).resolve()
    return r1.is_relative_to(r2) or r2.is_relative_to(r1)


class RegisteredLocalResource(BaseModel):
    """A local resource spec that has been bound to a base directory.

    ``base_dir`` is stored as a URI string so that it can represent both
    local paths (``/data/gnss``) and cloud locations
    (``s3://bucket/prefix``).  Use the :attr:`base_path` property to
    obtain the appropriate :class:`~pathlib.Path` or
    :class:`~cloudpathlib.CloudPath` object for filesystem operations.

    Attributes:
        name: Human-readable identifier for this resource.
        base_dir: Base directory URI (local path or cloud URI).
        spec: The underlying local resource specification.
        item_to_dir: Mapping of item names to their subdirectory.
        server: A ``file``-protocol :class:`Server` wrapping *base_dir*.
    """

    name: str
    base_dir: str
    spec: LocalResourceSpec
    item_to_dir: Dict[str, str]
    server: Server

    @property
    def base_path(self) -> AnyPath:
        """The base directory as a :class:`~pathlib.Path` or cloud path."""
        return as_path(self.base_dir)


class WorkSpace:
    """Registry of local storage directories and their layout specifications.

    Manages the mapping between ``LocalResourceSpec`` definitions (loaded from
    YAML) and concrete base directories on disk or in cloud storage.  Each
    registered spec gets a ``Server(protocol='file')`` so that local resources
    can be queried with the same ``ResourceQuery`` interface used for remote
    servers.

    Attributes:
        _registered_specs: Mapping of spec names to registered resources.
        _alias_map: Mapping of aliases to canonical spec names.
        _resource_specs: Loaded but not-yet-registered spec objects.

    Usage::

        ws = WorkSpace()
        ws.add_resource_spec('local_config.yaml')
        ws.register_spec(base_dir='/data/gnss', spec_ids=['local_config'], alias='local')
        # or with S3:
        ws.register_spec(base_dir='s3://bucket/gnss', spec_ids=['local_config'], alias='s3')
    """

    def __init__(self):
        """Initialise an empty workspace with no specs loaded."""

        self._registered_specs: Dict[str, RegisteredLocalResource] = {}
        self._alias_map: Dict[str, str] = {}  # alias → spec name
        self._resource_specs: Dict[str, LocalResourceSpec] = {}

    def add_resource_spec(self, path: Path | str, id: Optional[str] = None) -> None:
        """Load a :class:`LocalResourceSpec` from a YAML file.

        Args:
            path: Path to the YAML specification file.
            id: Optional override for the spec name.  Defaults to the
                name declared inside the YAML file.

        Raises:
            AssertionError: If *path* does not exist or a spec with
                the same name is already registered.
        """
        path = Path(path)
        assert path.exists(), f"Resource spec file not found: {path}"
        assert path.is_file(), f"Resource spec path must be a file: {path}"
        spec = LocalResourceSpec.from_yaml(path)
        name = spec.name
        if id is not None:
            name = id
        assert name not in self._resource_specs, (
            f"Resource spec with name '{name}' already exists. Please choose a unique name."
        )
        self._resource_specs[name] = spec

    def register_spec(
        self, base_dir: AnyPath | str, spec_ids: List[str], alias: Optional[str] = None
    ) -> None:
        """Bind loaded spec(s) to a base directory and register the result.

        *base_dir* may be a local filesystem path or a cloud URI such as
        ``s3://bucket/prefix``.  When multiple *spec_ids* are given they are
        merged into a single :class:`LocalResourceSpec`.

        Args:
            base_dir: Root directory for the resource (local path or cloud URI).
            spec_ids: One or more previously loaded spec identifiers.
            alias: Optional alias that also maps to this resource.

        Raises:
            AssertionError: If *base_dir* does not exist or any
                *spec_id* has not been loaded.
            ValueError: If *alias* is already in use or *base_dir* overlaps
                with an existing registration.
        """
        base_path = as_path(str(base_dir))
        assert base_path.exists(), f"Base directory not found: {base_dir}"
        assert base_path.is_dir(), f"Base directory must be a directory: {base_dir}"

        specs_to_register: List[LocalResourceSpec] = []
        for spec_id in spec_ids:
            assert spec_id in self._resource_specs, (
                f"Spec id '{spec_id}' not found. Available specs: {list(self._resource_specs.keys())}"
            )
            built_spec = self._resource_specs[spec_id]
            specs_to_register.append(built_spec)

        spec_to_register = LocalResourceSpec.merge(specs_to_register)
        server = Server(
            id=spec_to_register.name,
            hostname=str(base_path),
            protocol="file",
            auth_required=False,
            description=specs_to_register[-1].description,
        )
        if alias:
            if alias in self._alias_map:
                alias_mapped_spec = self._alias_map[alias]
                if alias_mapped_spec != spec_to_register.name:
                    raise ValueError(
                        f"Alias {alias!r} is already in use for spec {self._alias_map[alias]!r}."
                    )
            self._alias_map[alias] = spec_to_register.name

        item_to_dir: Dict[str, str] = {}
        for coll_name, coll in spec_to_register.collections.items():
            for item in coll.items:
                if item in item_to_dir:
                    raise ValueError(
                        f"Spec {item!r} is in multiple collections: "
                        f"{item_to_dir[item]!r} and {coll_name!r}"
                    )
                item_to_dir[item] = coll.directory

        local_resource = RegisteredLocalResource(
            name=spec_to_register.name,
            base_dir=str(base_path),
            spec=spec_to_register,
            item_to_dir=item_to_dir,
            server=server,
        )

        # Check for overlapping base directories with existing registered resources
        for registered_spec in self._registered_specs.values():
            if paths_overlap(registered_spec.base_dir, str(base_path)):
                raise ValueError(
                    f"Base directory {base_dir!r} overlaps with existing base directory "
                    f"{registered_spec.base_dir!r} for spec {registered_spec.name!r}. "
                    f"Please choose non-overlapping base directories for local resources."
                )
        self._registered_specs[spec_to_register.name] = local_resource
