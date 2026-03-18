"""
Query engine — unified product query with resolved file templates.

Uses ``meta_catalog.resolve()`` to substitute date fields into file
templates from the product catalog.
"""

from __future__ import annotations

import datetime
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from gnss_ppp_products.specifications.queries.query import (
    AxisDef,
    ExtraAxisDef,
    ProductQueryProfile,
)

_GPS_EPOCH = datetime.datetime(1980, 1, 6, tzinfo=datetime.timezone.utc)
_GPSWEEK_RE = re.compile(r"_(\d{4})\.atx")


# ===================================================================
# Resource location
# ===================================================================


@dataclass(frozen=True)
class ResourceLocation:
    """Protocol-agnostic pointer to a directory of product files."""

    scheme: str          # "file", "ftp", "ftps", "http", "https", "s3"
    host: str = ""       # "" for file://, hostname for remote, bucket for s3
    path: str = ""       # directory path (remote path or local absolute path)
    label: str = ""      # human-readable origin: "IGS", "CDDIS", "local"

    @property
    def uri(self) -> str:
        if self.scheme == "file":
            return f"file://{self.path}"
        if self.host:
            sep = "" if self.path.startswith("/") else "/"
            return f"{self.scheme}://{self.host}{sep}{self.path}"
        return self.path

    @property
    def is_local(self) -> bool:
        return self.scheme == "file"

    @property
    def is_remote(self) -> bool:
        return not self.is_local


# ===================================================================
# Query result
# ===================================================================


@dataclass(frozen=True)
class QueryResult:
    """A single resolved product variant from a query."""

    spec: str
    product_id: str
    location: ResourceLocation

    center: str = ""
    campaign: str = ""
    solution: str = ""
    sampling: str = ""

    file_template: str = ""
    extras: Dict[str, str] = field(default_factory=dict)


# ===================================================================
# ANTEX best-match selection
# ===================================================================


def _gpsweek_from_filename(filename: str) -> Optional[int]:
    m = _GPSWEEK_RE.search(filename)
    return int(m.group(1)) if m else None


def select_best_antex(
    filenames: List[str],
    target_date: datetime.date,
) -> Optional[str]:
    """Pick the most recent ANTEX file whose GPS week <= the target."""
    target_dt = datetime.datetime(
        target_date.year, target_date.month, target_date.day,
        tzinfo=datetime.timezone.utc,
    )
    target_week = (target_dt - _GPS_EPOCH).days // 7

    best_name: Optional[str] = None
    best_week: int = -1

    for fn in filenames:
        week = _gpsweek_from_filename(fn)
        if week is not None and week <= target_week and week > best_week:
            best_week = week
            best_name = fn

    return best_name


# ===================================================================
# Query spec loader
# ===================================================================


class QuerySpec:
    """Loaded query specification — axes + product profiles."""

    def __init__(
        self,
        axes: Dict[str, AxisDef],
        products: Dict[str, ProductQueryProfile],
    ) -> None:
        self.axes = axes
        self.products = products

    @classmethod
    def from_yaml(cls, path: str | Path) -> "QuerySpec":
        import yaml

        with open(path) as f:
            raw = yaml.safe_load(f)

        axes = {
            name: AxisDef(**defn)
            for name, defn in raw.get("axes", {}).items()
        }

        products = {}
        for name, defn in raw.get("products", {}).items():
            extra_raw = defn.pop("extra_axes", {})
            extra = {k: ExtraAxisDef(**v) for k, v in extra_raw.items()}
            products[name] = ProductQueryProfile(extra_axes=extra, **defn)

        return cls(axes=axes, products=products)

    def axis_def(self, name: str) -> AxisDef:
        return self.axes[name]

    def profile(self, spec_name: str) -> ProductQueryProfile:
        return self.products[spec_name]

    @property
    def spec_names(self) -> List[str]:
        return list(self.products.keys())

    @property
    def solution_preference(self) -> List[str]:
        sol = self.axes.get("solution")
        if sol and sol.sort_preference:
            return sol.sort_preference
        return []


# ===================================================================
# Catalog builder
# ===================================================================


def _build_catalog(
    date: datetime.date,
    *,
    query_spec: QuerySpec,
    remote_factory,
    local_factory,
    meta_catalog,
    product_catalog,
) -> List[QueryResult]:
    """Enumerate every concrete product variant from the registries."""
    results: List[QueryResult] = []
    dt = _ensure_datetime(date)

    # Keep track of (spec, center, campaign, solution, sampling, tmpl)
    # tuples we've already emitted so we can add local results without
    # duplicating ones that also appear as remote.
    seen_identities: set[Tuple[str, ...]] = set()

    for center_id, center in remote_factory._centers.items():
        for rp in center.products:
            if not rp.available:
                continue

            spec_name = rp.spec_name

            if spec_name not in query_spec.products:
                continue

            server = remote_factory.get_server_for_product(rp.id)
            directory = meta_catalog.resolve(
                rp.directory, dt, computed_only=True
            )

            # Resolve file templates via the product catalog
            templates: List[str] = []
            indices = rp.format_indices
            if indices is None:
                collection = product_catalog.products.get(spec_name)
                indices = list(range(len(collection.variants))) if collection else []
            for ref_index in indices:
                try:
                    variant = product_catalog.get_variant(spec_name, ref_index)
                    templates.append(
                        meta_catalog.resolve(variant.file_template, dt, computed_only=True)
                    )
                except (KeyError, IndexError):
                    pass

            combos = rp.metadata_combinations()

            # Cross-product: every template × every combo
            for tmpl_base in (templates or [""]):
                for combo in combos:
                    tmpl = tmpl_base

                    dir_resolved = directory
                    for key, value in combo.items():
                        dir_resolved = dir_resolved.replace(f"{{{key}}}", value)
                        tmpl = tmpl.replace(f"{{{key}}}", value)

                    # Resolve any remaining placeholders as regex patterns
                    tmpl = meta_catalog.resolve(tmpl, dt)

                    extras = {
                        k: v for k, v in combo.items()
                        if k not in ("AAA", "PPP", "TTT", "SMP")
                    }

                    identity = (
                        spec_name,
                        combo.get("AAA", ""),
                        combo.get("PPP", ""),
                        combo.get("TTT", ""),
                        combo.get("SMP", ""),
                        tmpl,
                    )
                    seen_identities.add(identity)

                    location = ResourceLocation(
                        scheme=server.protocol.lower(),
                        host=server.hostname,
                        path=dir_resolved,
                        label=center_id,
                    )

                    results.append(QueryResult(
                        spec=spec_name,
                        product_id=rp.id,
                        location=location,
                        center=combo.get("AAA", ""),
                        campaign=combo.get("PPP", ""),
                        solution=combo.get("TTT", ""),
                        sampling=combo.get("SMP", ""),
                        file_template=tmpl,
                        extras=extras,
                    ))

    # ---- Local results ------------------------------------------------
    # For every product identity that appeared in the remote catalog, emit
    # a corresponding local result so callers can discover on-disk files.
    for identity in seen_identities:
        spec_name, aaa, ppp, ttt, smp, tmpl = identity
        try:
            local_dir = local_factory.resolve_directory(spec_name, date)
        except (KeyError, ValueError, TypeError):
            continue
        if not local_dir:
            continue

        location = ResourceLocation(
            scheme="file",
            host="",
            path=str(local_dir),
            label="local",
        )
        results.append(QueryResult(
            spec=spec_name,
            product_id=f"local_{spec_name}",
            location=location,
            center=aaa,
            campaign=ppp,
            solution=ttt,
            sampling=smp,
            file_template=tmpl,
        ))

    return results


def _ensure_datetime(
    date,
) -> datetime.datetime:
    if isinstance(date, datetime.datetime):
        if date.tzinfo is None:
            return date.replace(tzinfo=datetime.timezone.utc)
        return date
    if isinstance(date, str):
        date = datetime.date.fromisoformat(date)
    return datetime.datetime(
        date.year, date.month, date.day, tzinfo=datetime.timezone.utc
    )


# ===================================================================
# Query engine
# ===================================================================


class ProductQuery:
    """Progressive regex-cascade query over the product space."""

    def __init__(
        self,
        date: datetime.date,
        *,
        _results: Optional[List[QueryResult]] = None,
        _axes: Optional[Dict[str, str]] = None,
        query_spec: QuerySpec,
        remote_factory,
        local_factory,
        meta_catalog,
        product_catalog,
    ):
        self.date = date
        self.axes: Dict[str, str] = dict(_axes) if _axes else {}
        self._query_spec = query_spec
        self._remote_factory = remote_factory
        self._local_factory = local_factory
        self._meta_catalog = meta_catalog
        self._product_catalog = product_catalog
        self._results: List[QueryResult] = (
            _results if _results is not None
            else _build_catalog(
                date,
                query_spec=query_spec,
                remote_factory=remote_factory,
                local_factory=local_factory,
                meta_catalog=meta_catalog,
                product_catalog=product_catalog,
            )
        )

    # -- core API ----------------------------------------------------

    def _derive(self, results: List[QueryResult], axes: Optional[Dict[str, str]] = None) -> "ProductQuery":
        """Return a new query sharing config but with different results/axes."""
        return ProductQuery(
            self.date,
            _results=results,
            _axes=axes if axes is not None else dict(self.axes),
            query_spec=self._query_spec,
            remote_factory=self._remote_factory,
            local_factory=self._local_factory,
            meta_catalog=self._meta_catalog,
            product_catalog=self._product_catalog,
        )

    def narrow(self, **axis_values: str) -> "ProductQuery":
        """Return a new query with additional axis filters applied."""
        for axis_name, axis_value in axis_values.items():
            if not axis_value:
                continue
            allowed = self.allowed_values(axis_name)
            if allowed and axis_value.upper() not in {v.upper() for v in allowed}:
                raise ValueError(
                    f"axis '{axis_name}' value '{axis_value}' not allowed — "
                    f"resource specs provide: {sorted(allowed)}"
                )

        new_axes = {**self.axes, **{k: v for k, v in axis_values.items() if v}}
        filtered = self._results

        for axis_name, axis_value in axis_values.items():
            if not axis_value:
                continue
            filtered = _apply_axis_filter(filtered, axis_name, axis_value)

        return self._derive(filtered, new_axes)

    def location_in(self, *labels: str) -> "ProductQuery":
        """Return a new query limited to locations matching *labels*.

        Parameters
        ----------
        *labels
            Location labels to include (e.g. ``"IGS"``, ``"CDDIS"``,
            ``"local"``).
        """
        allowed = {lb.upper() for lb in labels}
        filtered = [r for r in self._results if r.location.label.upper() in allowed]
        return self._derive(filtered)

    def remote_only(self) -> "ProductQuery":
        """Return a new query with only remote (non-local) results."""
        return self._derive([r for r in self._results if r.location.is_remote])

    def local_only(self) -> "ProductQuery":
        """Return a new query with only local (on-disk) results."""
        return self._derive([r for r in self._results if r.location.is_local])

    @property
    def results(self) -> List[QueryResult]:
        return list(self._results)

    @property
    def count(self) -> int:
        return len(self._results)

    def __iter__(self):
        return iter(self._results)

    def __len__(self) -> int:
        return len(self._results)

    def best(self, prefer: Optional[List[str]] = None, results: Optional[List[QueryResult]] = None) -> Optional[QueryResult]:
        if not self._results:
            return None
        pref = prefer or self._query_spec.solution_preference

        def _key(r: QueryResult) -> int:
            try:
                return pref.index(r.solution)
            except ValueError:
                return len(pref)

        return min(self._results, key=_key)

    # -- discovery helpers -------------------------------------------

    def specs(self) -> List[str]:
        return sorted({r.spec for r in self._results})

    def locations(self) -> List[str]:
        """Return sorted unique location labels."""
        return sorted({r.location.label for r in self._results})

    def centers(self) -> List[str]:
        return sorted({r.center for r in self._results if r.center})

    def campaigns(self) -> List[str]:
        return sorted({r.campaign for r in self._results if r.campaign})

    def solutions(self) -> List[str]:
        return sorted({r.solution for r in self._results if r.solution})

    def samplings(self) -> List[str]:
        return sorted({r.sampling for r in self._results if r.sampling})

    def instruments(self) -> List[str]:
        return sorted({r.extras.get("INSTRUMENT", "") for r in self._results} - {""})

    def group_by(
        self, *keys: str,
    ) -> Dict[Tuple[str, ...], List[QueryResult]]:
        """Group results by one or more field names.

        Parameters
        ----------
        *keys
            Field names on :class:`QueryResult` to group by, e.g.
            ``"remote"``, ``"remote_directory"``, ``"spec"``.

        Returns a dict mapping tuples of field values to result lists.
        """
        groups: Dict[Tuple[str, ...], List[QueryResult]] = defaultdict(list)
        for r in self._results:
            key = tuple(
                getattr(r, k, r.extras.get(k.upper(), ""))
                for k in keys
            )
            groups[key].append(r)
        return dict(groups)

    def axes_summary(self) -> Dict[str, List[str]]:
        return {
            "spec": self.specs(),
            "location": self.locations(),
            "center": self.centers(),
            "campaign": self.campaigns(),
            "solution": self.solutions(),
            "sampling": self.samplings(),
            "instrument": self.instruments(),
        }

    def allowed_values(self, axis_name: str) -> List[str]:
        match axis_name:
            case "spec":
                return self.specs()
            case "location":
                return self.locations()
            case "center":
                return self.centers()
            case "campaign":
                return self.campaigns()
            case "solution":
                return self.solutions()
            case "sampling":
                return self.samplings()
            case _:
                v_upper = axis_name.upper()
                vals: set[str] = set()
                for r in self._results:
                    ev = r.extras.get(v_upper, "")
                    if ev:
                        vals.add(ev)
                return sorted(vals) if vals else []

    # -- local resolution --------------------------------------------

    def find_local(self, base_dir: Optional[Path] = None) -> List[Dict]:
        """Find matching files on disk for local results.

        Parameters
        ----------
        base_dir
            Optional prefix.  When given, ``base_dir / location.path``
            is searched.  When *None*, ``location.path`` is used as-is
            (it should already be absolute for ``scheme="file"`` results).
        """
        found = []
        for r in self._results:
            if not r.location.is_local:
                continue
            d = Path(r.location.path)
            if base_dir is not None:
                d = base_dir / d
            if not d.exists():
                continue
            if not r.file_template:
                files = sorted(d.iterdir())
            else:
                files = sorted(
                    p for p in d.iterdir()
                    if p.is_file() and _match_template(r.file_template, p.name)
                )
            if files:
                found.append({"result": r, "files": files})
        return found

    # -- display -----------------------------------------------------

    def __repr__(self) -> str:
        pinned = ", ".join(f"{k}={v}" for k, v in self.axes.items())
        return f"<ProductQuery({pinned or 'all'}): {self.count} results>"

    def table(self) -> str:
        lines = [
            f"{'spec':<12s} {'location':<10s} {'scheme':<6s} {'center':<6s} "
            f"{'campaign':<9s} {'solution':<9s} {'sampling':<9s} "
            f"{'file_template':<50s}"
        ]
        lines.append("-" * len(lines[0]))
        for r in self._results:
            tmpl_short = r.file_template[:50] if r.file_template else "(none)"
            lines.append(
                f"{r.spec:<12s} {r.location.label:<10s} {r.location.scheme:<6s} "
                f"{r.center:<6s} {r.campaign:<9s} {r.solution:<9s} "
                f"{r.sampling:<9s} {tmpl_short}"
            )
        return "\n".join(lines)


# ===================================================================
# Axis filter
# ===================================================================


def _match_template(file_template: str, filename: str) -> bool:
    """Check if *filename* matches the resolved *file_template* (regex)."""
    try:
        return bool(re.search(file_template, filename, re.IGNORECASE))
    except re.error:
        return file_template in filename


def _apply_axis_filter(
    results: List[QueryResult],
    axis_name: str,
    axis_value: str,
) -> List[QueryResult]:
    v = axis_value.upper()

    match axis_name:
        case "spec":
            return [r for r in results if r.spec.upper() == v]
        case "location":
            return [r for r in results if r.location.label.upper() == v]
        case "center":
            return [r for r in results if r.center.upper() == v]
        case "campaign":
            return [r for r in results if r.campaign.upper() == v]
        case "solution":
            return [r for r in results if r.solution.upper() == v]
        case "sampling":
            return [r for r in results if r.sampling.upper() == v]
        case _:
            v_upper = axis_name.upper()
            return [
                r for r in results
                if r.extras.get(v_upper, "").upper() == v
            ]
