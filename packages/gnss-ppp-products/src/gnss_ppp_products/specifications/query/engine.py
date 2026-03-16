"""
Unified product query engine (regex cascade).

Provides a single query interface over both remote and local product
resources.  Queries narrow progressively: each axis value pins a
metadata field, reducing the regex pattern space.

This module is agnostic — all registry dependencies are passed via
constructor parameters.  No global singletons are imported.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .models import QuerySpec

_GPS_EPOCH = datetime.datetime(1980, 1, 6, tzinfo=datetime.timezone.utc)
_GPSWEEK_RE = re.compile(r"_(\d{4})\.atx")


# ===================================================================
# Query result
# ===================================================================


@dataclass(frozen=True)
class QueryResult:
    """A single resolved product variant from a query."""

    spec:       str
    center:     str
    product_id: str

    campaign:   str = ""
    solution:   str = ""
    sampling:   str = ""

    regex:          str = ""
    remote_server:  str = ""
    remote_protocol: str = ""
    remote_directory: str = ""
    local_collection: str = ""
    local_directory:  str = ""
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
    """Pick the most recent ANTEX archive file whose GPS week <= the target."""
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
# Catalog builder
# ===================================================================


def _build_catalog(
    date: datetime.date,
    *,
    query_registry: QuerySpec,
    remote_registry,
    local_registry,
    meta_registry,
    product_registry,
) -> List[QueryResult]:
    """
    Enumerate every concrete product variant from the registries.

    All registry parameters are **required** — this function does not
    fall back to global singletons.
    """
    results: List[QueryResult] = []

    for center_id, center in remote_registry.centers.items():
        for rp in center.products:
            if not rp.available:
                continue

            spec_name = rp.spec_name

            if spec_name not in query_registry.products:
                continue

            profile = query_registry.profile(spec_name)
            server = remote_registry.get_server_for_product(rp.id)
            directory = rp.resolve_directory(date, meta_registry=meta_registry)

            try:
                regexes = rp.to_regexes(
                    date,
                    meta_registry=meta_registry,
                    product_registry=product_registry,
                )
            except Exception:
                regexes = []

            combos = rp._metadata_combinations()

            try:
                local_dir = local_registry.resolve_directory(
                    spec_name, date, meta_registry=meta_registry
                )
                local_coll = local_registry.collection_name_for_spec(spec_name)
            except (KeyError, ValueError, TypeError):
                local_dir = ""
                local_coll = ""

            for i, combo in enumerate(combos):
                regex = regexes[i] if i < len(regexes) else (regexes[0] if regexes else "")

                dir_resolved = directory
                for key, value in combo.items():
                    dir_resolved = dir_resolved.replace(f"{{{key}}}", value)

                extras = {k: v for k, v in combo.items() if k not in ("PPP", "TTT", "SMP")}

                results.append(QueryResult(
                    spec=spec_name,
                    center=center_id,
                    product_id=rp.id,
                    campaign=combo.get("PPP", ""),
                    solution=combo.get("TTT", ""),
                    sampling=combo.get("SMP", ""),
                    regex=regex,
                    remote_server=server.hostname,
                    remote_protocol=server.protocol,
                    remote_directory=dir_resolved,
                    local_collection=local_coll,
                    local_directory=local_dir,
                    extras=extras,
                ))

    return results


# ===================================================================
# Query engine
# ===================================================================


class ProductQuery:
    """
    Progressive regex-cascade query over the product space.

    All registry parameters are **required** — this class does not
    fall back to global singletons.
    """

    def __init__(
        self,
        date: datetime.date,
        *,
        _results: Optional[List[QueryResult]] = None,
        _axes: Optional[Dict[str, str]] = None,
        query_registry: QuerySpec,
        remote_registry,
        local_registry,
        meta_registry,
        product_registry,
    ):
        self.date = date
        self.axes: Dict[str, str] = dict(_axes) if _axes else {}
        self._query_registry = query_registry
        self._remote_registry = remote_registry
        self._local_registry = local_registry
        self._meta_registry = meta_registry
        self._product_registry = product_registry
        self._results: List[QueryResult] = (
            _results if _results is not None
            else _build_catalog(
                date,
                query_registry=query_registry,
                remote_registry=remote_registry,
                local_registry=local_registry,
                meta_registry=meta_registry,
                product_registry=product_registry,
            )
        )

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

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

        return ProductQuery(
            self.date,
            _results=filtered,
            _axes=new_axes,
            query_registry=self._query_registry,
            remote_registry=self._remote_registry,
            local_registry=self._local_registry,
            meta_registry=self._meta_registry,
            product_registry=self._product_registry,
        )

    @property
    def results(self) -> List[QueryResult]:
        return list(self._results)

    @property
    def count(self) -> int:
        return len(self._results)

    def best(self, prefer: Optional[List[str]] = None) -> Optional[QueryResult]:
        if not self._results:
            return None
        pref = prefer or self._query_registry.solution_preference
        def _key(r: QueryResult) -> int:
            try:
                return pref.index(r.solution)
            except ValueError:
                return len(pref)
        return min(self._results, key=_key)

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------

    def specs(self) -> List[str]:
        return sorted({r.spec for r in self._results})

    def centers(self) -> List[str]:
        return sorted({r.center for r in self._results})

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
                if vals:
                    return sorted(vals)
                return []

    # ------------------------------------------------------------------
    # Local resolution
    # ------------------------------------------------------------------

    def find_local(self, base_dir: Path) -> List[Dict]:
        found = []
        for r in self._results:
            if not r.local_directory:
                continue
            d = base_dir / r.local_directory
            if not d.exists():
                continue
            if not r.regex:
                files = sorted(d.iterdir())
            else:
                pat = re.compile(r.regex, re.IGNORECASE)
                files = sorted(
                    p for p in d.iterdir()
                    if p.is_file() and pat.search(p.name)
                )
            if files:
                found.append({"result": r, "files": files})
        return found

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        pinned = ", ".join(f"{k}={v}" for k, v in self.axes.items())
        return f"<ProductQuery({pinned or 'all'}): {self.count} results>"

    def table(self) -> str:
        lines = [
            f"{'spec':<12s} {'center':<6s} {'campaign':<9s} "
            f"{'solution':<9s} {'sampling':<9s} {'regex':<50s}"
        ]
        lines.append("-" * len(lines[0]))
        for r in self._results:
            regex_short = r.regex[:50] if r.regex else "(none)"
            lines.append(
                f"{r.spec:<12s} {r.center:<6s} {r.campaign:<9s} "
                f"{r.solution:<9s} {r.sampling:<9s} {regex_short}"
            )
        return "\n".join(lines)


# ===================================================================
# Axis filter implementation
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
                or (not r.extras.get(v_upper) and v in (r.regex or "").upper())
            ]
