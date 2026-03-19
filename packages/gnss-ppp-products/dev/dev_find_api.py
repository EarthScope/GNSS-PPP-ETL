'''
Lazy narrowing query factory for GNSS product discovery.

Uses class definitions from dev_parameter_spec_claude.py:
  - ParameterCatalog / Parameter  (static parameter definitions + fallback regex)
  - ProductCatalog / Product      (nested version→variant→Product hierarchy)
  - RemoteResourceFactory         (registration interface; raw ResourceSpec stored via ._specs)
  - LocalResourceFactory          (collections-based local storage)
  - MetadataCatalog               (computed date-field resolution only)

Design:
  - NO pre-materialization of parameter combinations
  - Parameter ranges are narrowed (intersected), not cartesian-expanded
  - Templates resolved only at get() time via three-pass substitution:
        1. Date-computed fields  (YYYY, DDD, GPSWEEK …)  — via MetadataCatalog
        2. Narrowed metadata     (single → literal, multi → regex alternation)
        3. Default regex patterns (from ParameterCatalog)
  - Multi-valued metadata in directory templates expanded only when
    necessary (directories must be exact paths for listing)
'''

import datetime
import enum
import itertools
from math import prod
from pathlib import Path
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from gnss_ppp_products.specifications.metadata.metadata_catalog import MetadataCatalog
from pytest import param
from tomlkit import date
import sys
sys.path.append(str(Path(__file__).parent.parent))
from dev_parameter_spec_claude import (
    FormatCatalog,
    FormatSpecCatalog,
    ParameterCatalog,
    Parameter,
    Product,
    ProductCatalog,
    ProductPath,
    ProductSpecCatalog,
    ResourceProductSpec,
    ResourceSpec,
    ResourceSpec,
    Server,
    RemoteResourceFactory,
    LocalResourceFactory,
    QueryProfile,
    ResourceQuery,
    VariantCatalog,
    VersionCatalog,
    _build_metadata_catalog,
)

from dev_specs import (
    parameter_spec_dict,
    format_spec_dict,
    product_spec_dict,
    wuhan_resource_spec_dict,
    igs_resource_spec_dict,
    code_resource_spec_dict,
    local_resource_spec_dict,
)

from itertools import product

def expand_dict_combinations(d: dict[str, list[str]]) -> list[dict[str, str]]:
    keys = list(d.keys())
    values_product = product(*(d[k] for k in keys))
    return [dict(zip(keys, combo)) for combo in values_product]
# ─── Axis aliases ────────────────────────────────────────────────

_AXIS_TO_PARAM = {
    "center": "AAA",
    "solution": "TTT",
    "campaign": "PPP",
    "sampling": "SMP",
}


# ─── Result type ─────────────────────────────────────────────────

@dataclass(frozen=True)
class SearchableResource:
    """One searchable location with a file-matching regex.

    NOT a cartesian expansion of parameters — multi-valued metadata
    fields become ``(?:A|B|C)`` alternations in ``file_pattern``.
    """

    product_name: str        # e.g. "ORBIT", "CLOCK"
    source: str              # center_id or "local"
    host: str
    protocol: str
    directory: str           # fully resolved path
    file_pattern: str        # regex for filename matching
    metadata: Dict[str, List[str]] = field(default_factory=dict)
    is_local: bool = False

    def match(self, filenames: list[str]) -> list[str]:
        """Filter a directory listing against ``file_pattern``."""
        try:
            rx = re.compile(self.file_pattern, re.IGNORECASE)
            return [f for f in filenames if rx.search(f)]
        except re.error:
            return [f for f in filenames if self.file_pattern in f]

    @property
    def uri(self) -> str:
        if self.is_local:
            return f"file://{self.directory}"
        sep = "" if self.directory.startswith("/") else "/"
        return f"{self.protocol}://{self.host}{sep}{self.directory}"


# ─── QueryFactory ────────────────────────────────────────────────

class QueryFactory:
    """Lazy query factory — narrows parameter ranges, resolves on demand.

    Accepts the type system from ``dev_parameter_spec_claude.py``:
    ``RemoteResourceFactory`` for registration ergonomics,
    ``ProductCatalog`` (nested version→variant→Product hierarchy),
    ``ParameterCatalog`` for fallback regex patterns,
    and ``MetadataCatalog`` for computed date-field resolution.

    Usage::

        qf = QueryFactory(
            remote_factory=remote,
            local_factory=local,
            meta_catalog=METADATA_CATALOG,
            product_catalog=PRODUCT_CATALOG,
            parameter_catalog=PARAMETER_CATALOG,
        )

        results = qf.get(
            datetime.date(2024, 1, 1),
            spec="ORBIT",
            center="WUM",
            solution=["FIN", "RAP"],
        )

        for r in results:
            print(r.uri, r.file_pattern)
    """

    def __init__(
        self,
        remote_factory: RemoteResourceFactory,
        local_factory: LocalResourceFactory,
        product_catalog: ProductCatalog,
        metadata_catalog: MetadataCatalog,
        parameter_catalog: ParameterCatalog,
    ):
        self._remote = remote_factory
        self._local = local_factory
        self._products = product_catalog
        self._metadata = metadata_catalog
        self._params = parameter_catalog

    def get(
        self,
        date: datetime.datetime,
        product: Dict[str, str | list[str]],
        parameters: Dict[str, str | list[str]],
        local_resources: Optional[List[str]] = None,
        remote_resources: Optional[List[str]] = None,
    ) -> list[ResourceQuery]:
        """Narrow parameter ranges and return searchable resources.

        Parameters
        ----------
        date : datetime.datetime
            Target date for computed metadata fields (e.g. YYYY, DDD).
        product: dict
        parameters: dict[str, str | list[str]]
            User constraints on metadata fields. Keys must match parameter
        local_resources: list[str]
            If specified, only include local resources with these collection IDs.
        remote_resources: list[str]
            If specified, only include remote resources with these center IDs.

        Returns
        -------
        list[ResourceQuery]
            Each entry is one (server, directory, file_pattern) target —
            NOT a cartesian expansion.

        Examples
        --------
        >>> qf = QueryFactory(remote, local, meta, products, params)
        >>> product = {name:"ORBIT",version: ["1"]}
        >>> parameters = {"AAA":["WUM","COD"], "TTT":["FIN","RAP"]}
        >>> local_resource = ["my_local_id"]
        >>> remote_resources = ["WUM", "COD"]
        >>> results = qf.get(
        ...     datetime.date(2024, 1, 1),
        ...     product=product,
        ...     parameters=parameters,
        ...     remote_resources=remote_resources,
        ...     local_resources=local_resource,
        ... )
        """
        out: List[ResourceQuery] = []
        #################
        # 1. Get product templates matching the query product spec (name + optional version/variant)
        #################
        product_templates: List[Product] = []

        product_name_query = product.get("name")
        product_version_query = _listify(product.get("version"))
        product_variant_query = _listify(product.get("variant"))

        product_version_catalog:Optional[VersionCatalog] = self._products.products.get(product_name_query)
        if product_version_catalog is None:
            raise ValueError(f"Product {product_name_query!r} not found in ProductCatalog")
        versions = product_version_query or list(product_version_catalog.versions.keys())
        for version in versions:
            variant_cat: Optional[VariantCatalog] = product_version_catalog.versions.get(version)
            if variant_cat is None:
                raise ValueError(f"Version {version!r} not found for product {product_name_query!r}")
            variants = product_variant_query or list(variant_cat.variants.keys())
            for variant in variants:
                if variant not in variant_cat.variants:
                    raise ValueError(f"Variant {variant!r} not found for product {product_name_query!r} version {version!r}")
                product_templates.append(variant_cat.variants[variant])

        print("TEST 1: product templates matching query spec:")
        for template in product_templates:
            print(template.filename.pattern)
        #################
        # 2. Resolve the parameter file template date fields (e.g. YYYY, DDD) via the metadata catalog.
        # TODO: migrate the datefield resolution to the ProductCatalog.
        #################

        for template in product_templates:
            update_date_params = self._metadata.resolve_params(template.parameters, date)
            template.parameters = update_date_params

        #################
        # 3. Get the cartesian product of all parameter values from the query constraints and all product templates. This is the set of all possible metadata combinations that could satisfy the query.
        #################
        product_templates_1: List[Product] = []
        for name, values in parameters.items():
            parameters[name] = _listify(values)
        # Get the cartesian product of all paramter values.
        # ex: {"AAA": ["WUM","COD"], "TTT": ["FIN","RAP"]} → [{"AAA":"WUM","TTT":"FIN"},{"AAA":"WUM","TTT":"RAP"},{"AAA":"COD","TTT":"FIN"},{"AAA":"COD","TTT":"RAP"}]
        parameter_combinations = expand_dict_combinations(parameters)
        # For each product template, we will narrow the parameter ranges by intersecting with the query constraints. This will give us a narrowed set of metadata combinations that are actually relevant to the query.
        for template in product_templates:
            print(f"Template: {template.filename.pattern}")
            for combo in parameter_combinations:
                # Narrow the template's parameter ranges by intersecting with the query constraints. This will give us a narrowed set of metadata combinations that are actually relevant to the query.
                print(f"Combo: {combo}")
                updated = template.model_copy(deep=True)
                for k, v in combo.items():
                    param_index = next((i for i, p in enumerate(updated.parameters) if p.name == k), None)
                    if param_index is not None:
                        updated.parameters[param_index].value = v
                if updated.filename is not None:
                    updated.filename.derive(updated.parameters)
                    print(updated.filename.pattern)
                product_templates_1.append(updated)

        print("\nTEST 2: product templates after narrowing parameter ranges by query constraints:")
        for template in product_templates_1:
            print(template.filename.pattern)
        #################
        # 4. For each product template, if the value of a parameter is still None (meaning it wasn't constrained by the query), 
        # replace it with its regex pattern. This will give us a file pattern that can be used to match files on the server.
        #################
        product_templates_2: List[Product] = []
        for template in product_templates_1:
            updated = template.model_copy()
            for param in updated.parameters:
                if param.value is None:
                    param.value = param.pattern
            product_templates_2.append(updated)

        '''
        5. For each product template, build a ResourceQuery for each local and remote resource that matches the query constraints. 
        
        This will give us a list of searchable resources with file patterns that can be used to find matching files on the server or local storage.

        5.1 For local resources:
            5.1.1
                If local_resources is specified, only include local resources with collection IDs in local_resources, otherwise include all local resources in 
                the LocalResourceFactory.
            5.1.2 
                For each included local resource, resolve the directory path using the LocalResourceFactory's resolve_directory method. 
                ex. self._local.resolve_directory(template.parameters,resource_name=None) = (Server, directory)
        '''
        return product_templates_2

    # ── Remote ───────────────────────────────────────────────────

    def _remote_entries(self, dt, spec, constraints, location):
        loc_set = {x.upper() for x in _listify(location)} if location else None
        entries = []

        for cid, resource_spec in self._remote._specs.items():
            if loc_set and cid.upper() not in loc_set:
                continue

            for rp in resource_spec.products:
                if not rp.available:
                    continue
                if spec and rp.product_name.upper() != spec.upper():
                    continue

                # Group multi-valued parameters into ranges: {"AAA": ["WUM","WMC"], ...}
                declared = _param_ranges(rp.parameters)

                # Narrow this entry's declared metadata by user constraints
                narrowed = _intersect(declared, constraints)
                if narrowed is None:
                    continue  # constraint conflict — skip entirely

                # Merge: narrowed resource metadata + extra user constraints
                # (keys the resource doesn't declare → applied to file pattern only)
                merged = dict(narrowed)
                for k, v in constraints.items():
                    if k not in merged:
                        merged[k] = v

                server = next(
                    s for s in resource_spec.servers if s.id == rp.server_id
                )
                base_dir = self._meta.resolve(
                    rp.directory.pattern, dt, computed_only=True
                )

                # Directory placeholders must be exact paths — expand multi-valued
                for resolved_dir, pinned in _expand_dir(base_dir, merged):
                    effective = {
                        k: ([pinned[k]] if k in pinned else v)
                        for k, v in merged.items()
                    }
                    for pat in self._file_patterns(rp, dt, effective):
                        entries.append(SearchableResource(
                            product_name=rp.product_name, source=cid,
                            host=server.hostname, protocol=server.protocol or "",
                            directory=resolved_dir, file_pattern=pat,
                            metadata=effective, is_local=False,
                        ))
        return entries

    # ── Local ────────────────────────────────────────────────────

    def _local_entries(self, dt, spec, constraints):
        entries = []
        item_to_dir: dict[str, str] = getattr(self._local, '_item_to_dir', {})

        for product_name in item_to_dir:
            if spec and product_name.upper() != spec.upper():
                continue

            version_cat = self._products.products.get(product_name)
            if not version_cat:
                continue

            try:
                local_dir = str(self._local.resolve_directory(product_name, dt))
            except (KeyError, ValueError, TypeError, AssertionError):
                continue

            for pat in self._product_file_patterns(product_name, dt, constraints):
                entries.append(SearchableResource(
                    product_name=product_name, source="local",
                    host="", protocol="file",
                    directory=local_dir, file_pattern=pat,
                    metadata=constraints, is_local=True,
                ))
        return entries

    # ── Template resolution ──────────────────────────────────────

    def _file_patterns(self, rp: ResourceProductSpec, dt, meta) -> list[str]:
        """Build file regex patterns for a single remote product entry.

        Navigates ProductCatalog version→variant→Product, filtering by
        ``rp.product_version`` when specified.
        """
        return self._product_file_patterns(
            rp.product_name, dt, meta, versions=rp.product_version,
        )

    def _product_file_patterns(
        self,
        product_name: str,
        dt,
        meta: dict[str, list[str]],
        versions: str | list[str] | None = None,
    ) -> list[str]:
        """Build file regex patterns from the ProductCatalog hierarchy."""
        version_cat = self._products.products.get(product_name)
        if not version_cat:
            return []

        ver_keys: list[str]
        if versions is None:
            ver_keys = list(version_cat.versions.keys())
        elif isinstance(versions, str):
            ver_keys = [versions]
        else:
            ver_keys = list(versions)

        patterns: list[str] = []
        for vk in ver_keys:
            variant_cat = version_cat.versions.get(vk)
            if not variant_cat:
                continue
            for product in variant_cat.variants.values():
                if product.filename and product.filename.pattern:
                    patterns.append(
                        self._resolve_tmpl(product.filename.pattern, dt, meta)
                    )
        return patterns

    def _resolve_tmpl(self, template: str, dt, meta: dict[str, list[str]]) -> str:
        """Three-pass template resolution → regex string.

        1. Computed date fields  (YYYY → "2024", DDD → "001") via MetadataCatalog
        2. Metadata ranges       (single → literal, multi → alternation)
        3. Remaining unresolved  (→ default regex from ParameterCatalog)
        """
        # Pass 1: computed date fields
        r = self._meta.resolve(template, dt, computed_only=True)

        # Pass 2: narrowed metadata
        for k, vals in meta.items():
            ph = f"{{{k}}}"
            if ph not in r:
                continue
            if len(vals) == 1:
                r = r.replace(ph, re.escape(vals[0]))
            else:
                r = r.replace(ph, "(?:" + "|".join(re.escape(v) for v in sorted(vals)) + ")")

        # Pass 3: remaining {FIELD} → fallback regex from ParameterCatalog
        for match in re.findall(r'\{(\w+)\}', r):
            param = self._params.get(match)
            if param and param.pattern:
                r = r.replace(f"{{{match}}}", param.pattern)

        return r


# ─── Helpers ─────────────────────────────────────────────────────

def _param_ranges(parameters: list[Parameter]) -> dict[str, list[str]]:
    """Group multi-valued Parameter lists into {name: [values]}.

    Only includes parameters that have a concrete ``value`` set.
    Parameters with ``value=None`` are template defaults, not metadata.
    """
    ranges: dict[str, list[str]] = {}
    for p in parameters:
        if p.value is not None:
            ranges.setdefault(p.name, []).append(p.value)
    return ranges


def _listify(v) -> list[str]:
    if v is None:
        return []
    return [v] if isinstance(v, str) else list(v)


def _ensure_dt(d) -> datetime.datetime:
    if isinstance(d, datetime.datetime):
        return d.replace(tzinfo=datetime.timezone.utc) if d.tzinfo is None else d
    if isinstance(d, str):
        d = datetime.date.fromisoformat(d)
    return datetime.datetime(d.year, d.month, d.day, tzinfo=datetime.timezone.utc)


def _intersect(
    available: dict[str, list[str]],
    constraints: dict[str, list[str]],
) -> dict[str, list[str]] | None:
    """Narrow resource metadata by user constraints.

    Returns narrowed dict, or ``None`` if any constrained key has an
    empty intersection (meaning this resource cannot satisfy the query).
    Keys in *constraints* but not in *available* are ignored here — they
    don't filter out the resource, they only apply to file-pattern matching.
    """
    result = {k: list(v) for k, v in available.items()}
    for key, allowed in constraints.items():
        if key not in result:
            continue
        upper = {v.upper() for v in allowed}
        narrowed = [v for v in result[key] if v.upper() in upper]
        if not narrowed:
            return None
        result[key] = narrowed
    return result


def _expand_dir(
    template: str,
    meta: dict[str, list[str]],
) -> list[tuple[str, dict[str, str]]]:
    """Expand multi-valued metadata placeholders in a directory path.

    Directories must be exact paths (you can't regex-list a directory),
    so any multi-valued metadata that appears as a ``{KEY}`` placeholder
    in the template is expanded into separate (path, pinned_values) pairs.
    Single-valued keys are substituted in-place.
    """
    # First substitute all single-valued keys
    resolved = template
    for k, vals in meta.items():
        if f"{{{k}}}" in resolved and len(vals) == 1:
            resolved = resolved.replace(f"{{{k}}}", vals[0])

    # Find multi-valued keys still present as placeholders
    multi = [k for k, v in meta.items() if f"{{{k}}}" in resolved and len(v) > 1]
    if not multi:
        return [(resolved, {})]

    results = []
    for combo in itertools.product(*(meta[k] for k in multi)):
        d = resolved
        pinned = dict(zip(multi, combo))
        for k, v in pinned.items():
            d = d.replace(f"{{{k}}}", v)
        results.append((d, pinned))
    return results


if __name__ == "__main__":
    from pathlib import Path
    date = datetime.datetime(2024, 1, 1)
    base_dir = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP")
    PARAMETER_CATALOG = ParameterCatalog(parameters=[Parameter(**p) for p in parameter_spec_dict])
    FORMAT_CATALOG = FormatCatalog(
        format_spec_catalog=FormatSpecCatalog(formats=format_spec_dict),
        parameter_catalog=PARAMETER_CATALOG,
    )
    PRODUCT_CATALOG = ProductCatalog(
        product_spec_catalog=ProductSpecCatalog(products=product_spec_dict),
        format_catalog=FORMAT_CATALOG,
    )
    REMOTE_RESOURCE_FACTORY = RemoteResourceFactory(PRODUCT_CATALOG)
    REMOTE_RESOURCE_FACTORY.register(ResourceSpec(**wuhan_resource_spec_dict))
    REMOTE_RESOURCE_FACTORY.register(ResourceSpec(**igs_resource_spec_dict))
    REMOTE_RESOURCE_FACTORY.register(ResourceSpec(**code_resource_spec_dict))
    METADATA_CATALOG = _build_metadata_catalog()

    QF = QueryFactory(
        remote_factory=REMOTE_RESOURCE_FACTORY,
        local_factory=None,
        product_catalog=PRODUCT_CATALOG,
        metadata_catalog=METADATA_CATALOG,
        parameter_catalog=PARAMETER_CATALOG,
    )

    test = QF.get(
        date=date,
        product={"name": "ORBIT", "version": ["1"]},
        parameters={"AAA": ["WUM", "COD"], "TTT": ["FIN", "RAP"]},
        remote_resources=["WUM", "COD"],
    )

    print("\n[RESULTS]")
    for r in test:
        r.filename.derive(r.parameters)
        print(r.filename.pattern)