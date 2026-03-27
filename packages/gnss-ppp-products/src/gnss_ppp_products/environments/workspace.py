from pathlib import Path

from typing import Any, Dict, Optional, List


from gnss_ppp_products.specifications.remote.resource import ResourceSpec, Server
from pydantic import BaseModel

from gnss_ppp_products.specifications.local.local import LocalResourceSpec


def paths_overlap(p1: Path, p2: Path) -> bool:
    p1 = p1.resolve()
    p2 = p2.resolve()
    return p1.is_relative_to(p2) or p2.is_relative_to(p1)


class RegisteredLocalResource(BaseModel):
    name: str
    base_dir: Path
    spec: LocalResourceSpec
    item_to_dir: Dict[str, str]
    server: Server


class WorkSpace:
    """Registry of local storage directories and their layout specifications.

    Manages the mapping between ``LocalResourceSpec`` definitions (loaded from
    YAML) and concrete base directories on disk.  Each registered spec gets a
    ``Server(protocol='file')`` so that local resources can be queried with the
    same ``ResourceQuery`` interface used for remote servers.

    Usage::

        ws = WorkSpace()
        ws.add_resource_spec('local_config.yaml')
        ws.register_spec(base_dir='/data/gnss', spec_ids=['local_config'], alias='local')
    """

    def __init__(self):

        self._registered_specs: Dict[str, RegisteredLocalResource] = {}
        self._alias_map: Dict[str, str] = {}  # alias → spec name
        self._resource_specs: Dict[str, LocalResourceSpec] = {}

    def add_resource_spec(self, path: Path | str, id: Optional[str] = None) -> None:
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
        self, base_dir: Path | str, spec_ids: List[str], alias: Optional[str] = None
    ) -> None:
        if isinstance(base_dir, str):
            base_dir = Path(base_dir)
        assert base_dir.exists(), f"Base directory not found: {base_dir}"
        assert base_dir.is_dir(), f"Base directory must be a directory: {base_dir}"
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
            hostname=str(base_dir),
            protocol="file",
            auth_required=False,
            description=specs_to_register[-1].description,
        )
        if alias:
            if alias in self._alias_map:
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
            base_dir=base_dir,
            spec=spec_to_register,
            item_to_dir=item_to_dir,
            server=server,
        )

        # Check for overlapping base directories with existing registered resources
        for registered_spec in self._registered_specs.values():
            if paths_overlap(registered_spec.base_dir, base_dir):
                raise ValueError(
                    f"Base directory {base_dir!r} overlaps with existing base directory {registered_spec.base_dir!r} for spec {registered_spec.name!r}. "
                    f"Please choose non-overlapping base directories for local resources."
                )
        self._registered_specs[spec_to_register.name] = local_resource
