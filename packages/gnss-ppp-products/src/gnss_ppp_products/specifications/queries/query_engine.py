"""
Query engine — unified product query with resolved file templates.

Uses ``meta_catalog.resolve()`` to substitute date fields into file
templates from the product catalog.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from gnss_ppp_products.specifications.queries.query import (
    AxisDef,
    ExtraAxisDef,
    ProductQueryProfile,
)

_GPS_EPOCH = datetime.datetime(1980, 1, 6, tzinfo=datetime.timezone.utc)
_GPSWEEK_RE = re.compile(r"_(\d{4})\.atx")


# ===================================================================
# Query result
# ===================================================================


@dataclass(frozen=True)
class QueryResult:
    """A single resolved product variant from a query."""

    spec: str
    remote: str
    product_id: str

    center: str = ""
    campaign: str = ""
    solution: str = ""
    sampling: str = ""

    file_template: str = ""
    remote_server: str = ""
    remote_protocol: str = ""
    remote_directory: str = ""
    local_collection: str = ""
    local_directory: str = ""
    extras: Dict[str, str] = field(default_factory=dict)

    @property
    def remote_url(self) -> str:
        if self.remote_server and self.remote_directory:
            return f"{self.remote_server}/{self.remote_directory}"
        return ""


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
                # Use all format variants for this product
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

            # Resolve local directory
            try:
                local_dir = local_factory.resolve_directory(
                    spec_name, date, meta_catalog=meta_catalog
                )
                local_coll = local_factory.collection_name_for_spec(spec_name)
            except (KeyError, ValueError, TypeError):
                local_dir = ""
                local_coll = ""

            combos = rp.metadata_combinations()

            for i, combo in enumerate(combos):
                tmpl = templates[i] if i < len(templates) else (
                    templates[0] if templates else ""
                )

                dir_resolved = directory
                # Substitute combo metadata into both directory and template
                for key, value in combo.items():
                    dir_resolved = dir_resolved.replace(f"{{{key}}}", value)
                    tmpl = tmpl.replace(f"{{{key}}}", value)

                # Resolve any remaining placeholders as regex patterns
                tmpl = meta_catalog.resolve(tmpl, dt)

                extras = {
                    k: v for k, v in combo.items()
                    if k not in ("AAA", "PPP", "TTT", "SMP")
                }

                results.append(QueryResult(
                    spec=spec_name,
                    remote=center_id,
                    product_id=rp.id,
                    center=combo.get("AAA", ""),
                    campaign=combo.get("PPP", ""),
                    solution=combo.get("TTT", ""),
                    sampling=combo.get("SMP", ""),
                    file_template=tmpl,
                    remote_server=server.hostname,
                    remote_protocol=server.protocol,
                    remote_directory=dir_resolved,
                    local_collection=local_coll,
                    local_directory=local_dir,
                    extras=extras,
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

    def remote_in(self, *remote_ids: str) -> "ProductQuery":
        """Return a new query limited to specific remote data centers.

        Parameters
        ----------
        *remote_ids
            Data-center IDs to include (e.g. ``"IGS"``, ``"CDDIS"``).
        """
        allowed = {r.upper() for r in remote_ids}
        filtered = [r for r in self._results if r.remote.upper() in allowed]
        return self._derive(filtered)

    @property
    def results(self) -> List[QueryResult]:
        return list(self._results)

    @property
    def count(self) -> int:
        return len(self._results)

    def best(self, prefer: Optional[List[str]] = None) -> Optional[QueryResult]:
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

    def remotes(self) -> List[str]:
        return sorted({r.remote for r in self._results})

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

    def axes_summary(self) -> Dict[str, List[str]]:
        return {
            "spec": self.specs(),
            "remote": self.remotes(),
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

    def find_local(self, base_dir: Path) -> List[Dict]:
        found = []
        for r in self._results:
            if not r.local_directory:
                continue
            d = base_dir / r.local_directory
            if not d.exists():
                continue
            if not r.file_template:
                files = sorted(d.iterdir())
            else:
                files = sorted(
                    p for p in d.iterdir()
                    if p.is_file() and r.file_template in p.name
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
            f"{'spec':<12s} {'remote':<8s} {'center':<6s} {'campaign':<9s} "
            f"{'solution':<9s} {'sampling':<9s} {'file_template':<50s}"
        ]
        lines.append("-" * len(lines[0]))
        for r in self._results:
            tmpl_short = r.file_template[:50] if r.file_template else "(none)"
            lines.append(
                f"{r.spec:<12s} {r.remote:<8s} {r.center:<6s} {r.campaign:<9s} "
                f"{r.solution:<9s} {r.sampling:<9s} {tmpl_short}"
            )
        return "\n".join(lines)


# ===================================================================
# Axis filter
# ===================================================================


def _apply_axis_filter(
    results: List[QueryResult],
    axis_name: str,
    axis_value: str,
) -> List[QueryResult]:
    v = axis_value.upper()

    match axis_name:
        case "spec":
            return [r for r in results if r.spec.upper() == v]
        case "center":
            return [r for r in results if r.center.upper() == v]
        case "remote":
            return [r for r in results if r.remote.upper() == v]
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
