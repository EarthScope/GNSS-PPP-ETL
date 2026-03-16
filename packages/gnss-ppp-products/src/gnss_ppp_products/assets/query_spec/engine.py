"""
Unified product query engine (regex cascade).

Provides a single query interface over both remote and local product
resources.  Queries narrow progressively: each axis value pins a
metadata field, reducing the regex pattern space.  Omitted axes
remain as wildcards.

The engine is spec-driven — query profiles from ``query_v2.yaml``
determine which axes apply to each product, what values are valid,
and how they map to filename metadata fields.

Usage::

    from gnss_ppp_products.data_query.unified import ProductQuery
    import datetime

    q = ProductQuery(date=datetime.date(2025, 1, 15))
    q.narrow(spec="ORBIT")                       # all ORBIT variants
    q.narrow(spec="ORBIT", center="IGS")          # only IGS
    q.narrow(spec="ORBIT", center="IGS",
             solution="FIN", sampling="05M")       # single variant

    for r in q.results:
        print(r.regex, r.remote_url, r.local_dir)
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from gnss_ppp_products.assets.query_spec.registry import QuerySpecRegistry
from gnss_ppp_products.assets.query_spec.query import ProductQueryProfile
from gnss_ppp_products.assets.remote_resource_spec import RemoteResourceRegistry

_GPS_EPOCH = datetime.datetime(1980, 1, 6, tzinfo=datetime.timezone.utc)
_GPSWEEK_RE = re.compile(r"_(\d{4})\.atx")
from gnss_ppp_products.assets.local_resource_spec import LocalResourceRegistry


# ===================================================================
# Query result
# ===================================================================


@dataclass(frozen=True)
class QueryResult:
    """A single resolved product variant from a query.

    Contains everything needed to fetch (remote) or find (local) the
    file.  One QueryResult corresponds to one filename regex that can
    match exactly one file on disk or on a remote directory listing.
    """

    # ---- identity ----
    spec:       str         # "ORBIT", "CLOCK", ...
    center:     str         # "IGS", "WUM"
    product_id: str         # "igs_orbit", "wuhan_clock"

    # ---- query axis values (empty = wildcard in parent query) ----
    campaign:   str = ""
    solution:   str = ""
    sampling:   str = ""

    # ---- resolved locations ----
    regex:          str = ""     # compiled filename regex
    remote_server:  str = ""     # "ftp://igs.ign.fr"
    remote_protocol: str = ""    # "ftp", "https"
    remote_directory: str = ""   # "pub/igs/products/2349/"
    local_collection: str = ""   # "products", "common", "table"
    local_directory:  str = ""   # "2025/015/products"
    extras: Dict[str, str] = field(default_factory=dict)  # non-standard metadata (e.g. INSTRUMENT)

    @property
    def remote_url(self) -> str:
        """Full URL to the remote directory."""
        if self.remote_server and self.remote_directory:
            return f"{self.remote_server}/{self.remote_directory}"
        return ""


# ===================================================================
# ANTEX best-match selection
# ===================================================================


def _gpsweek_from_filename(filename: str) -> Optional[int]:
    """Extract a GPS week number from an ANTEX archive filename.

    Expects names like ``igs20_2350.atx`` or ``igs20_2350.atx.gz``.
    Returns ``None`` if no week number is found.
    """
    m = _GPSWEEK_RE.search(filename)
    return int(m.group(1)) if m else None


def select_best_antex(
    filenames: List[str],
    target_date: datetime.date,
) -> Optional[str]:
    """Pick the most recent ANTEX archive file whose GPS week ≤ the target.

    Parameters
    ----------
    filenames
        Directory listing entries that already match the ATTATX regex
        (e.g. ``["igs20_2343.atx", "igs20_2350.atx"]``).
    target_date
        The epoch for which the ANTEX file is needed.

    Returns
    -------
    str or None
        The best-matching filename, or *None* if no file qualifies.
    """
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
    query_registry=None,
    remote_registry=None,
    local_registry=None,
    meta_registry=None,
    product_registry=None,
) -> List[QueryResult]:
    """
    Enumerate every concrete product variant from the registries,
    informed by the query spec.

    Expands all remote product metadata combinations into individual
    QueryResults annotated with local storage info.

    When registry parameters are ``None`` the global singletons are
    used, preserving full backward compatibility.
    """
    _qreg = query_registry if query_registry is not None else QuerySpecRegistry
    _rreg = remote_registry if remote_registry is not None else RemoteResourceRegistry
    _lreg = local_registry if local_registry is not None else LocalResourceRegistry

    results: List[QueryResult] = []

    for center_id, center in _rreg.centers.items():
        for rp in center.products:
            if not rp.available:
                continue

            spec_name = rp.spec_name

            # Check the query spec knows about this product
            if spec_name not in _qreg.products:
                continue

            profile = _qreg.profile(spec_name)
            server = _rreg.get_server_for_product(rp.id)
            directory = rp.resolve_directory(date, meta_registry=meta_registry)

            # Build regexes (one per metadata combination)
            try:
                regexes = rp.to_regexes(
                    date,
                    meta_registry=meta_registry,
                    product_registry=product_registry,
                )
            except Exception:
                regexes = []

            # Expand metadata combinations
            combos = rp._metadata_combinations()

            # Local storage mapping
            try:
                local_dir = _lreg.resolve_directory(
                    spec_name, date, meta_registry=meta_registry
                )
                local_coll = _lreg.collection_name_for_spec(spec_name)
            except (KeyError, ValueError):
                local_dir = ""
                local_coll = ""

            for i, combo in enumerate(combos):
                regex = regexes[i] if i < len(regexes) else (regexes[0] if regexes else "")

                # Resolve metadata-combo placeholders in directory
                dir_resolved = directory
                for key, value in combo.items():
                    dir_resolved = dir_resolved.replace(f"{{{key}}}", value)

                # Non-standard metadata for extra-axis filtering
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

    Instantiate with a date, then call :meth:`narrow` with axis values
    to filter.  Each call returns a **new** ProductQuery (the original
    is unchanged), so you can branch from intermediate states.

    Attributes
    ----------
    date : datetime.date
        The target epoch.
    axes : dict[str, str]
        Currently pinned axis values.
    results : list[QueryResult]
        Matching product variants after all axis filters are applied.
    """

    def __init__(
        self,
        date: datetime.date,
        *,
        _results: Optional[List[QueryResult]] = None,
        _axes: Optional[Dict[str, str]] = None,
        query_registry=None,
        remote_registry=None,
        local_registry=None,
        meta_registry=None,
        product_registry=None,
    ):
        self.date = date
        self.axes: Dict[str, str] = dict(_axes) if _axes else {}
        # Store registries so narrow() can propagate them
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
        """
        Return a new query with additional axis filters applied.

        Each keyword argument is an axis name (spec, center, campaign,
        solution, sampling, or any extra_axis) mapped to a value.

        Raises :class:`ValueError` if a supplied axis value is not
        among the values currently allowed by the resource specs
        (i.e. not present in the current result set).

        Examples::

            q = ProductQuery(date)
            q1 = q.narrow(spec="ORBIT")
            q2 = q1.narrow(center="IGS", solution="FIN")
            q3 = q.narrow(spec="ORBIT", center="IGS",
                          solution="FIN", sampling="05M")
        """
        # Validate that each requested value is allowed in the catalog
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
        """All matching product variants."""
        return list(self._results)

    @property
    def count(self) -> int:
        return len(self._results)

    def best(self, prefer: Optional[List[str]] = None) -> Optional[QueryResult]:
        """Return the highest-preference result, or None.

        *prefer* defaults to the solution sort_preference from the query
        spec (FIN > RAP > ULT > ...).
        """
        if not self._results:
            return None
        _qreg = self._query_registry if self._query_registry is not None else QuerySpecRegistry
        pref = prefer or _qreg.solution_preference
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
        """Unique spec names in current results."""
        return sorted({r.spec for r in self._results})

    def centers(self) -> List[str]:
        """Unique center names in current results."""
        return sorted({r.center for r in self._results})

    def campaigns(self) -> List[str]:
        """Unique campaign values in current results."""
        return sorted({r.campaign for r in self._results if r.campaign})

    def solutions(self) -> List[str]:
        """Unique solution values in current results."""
        return sorted({r.solution for r in self._results if r.solution})

    def samplings(self) -> List[str]:
        """Unique sampling values in current results."""
        return sorted({r.sampling for r in self._results if r.sampling})

    def instruments(self) -> List[str]:
        """Unique instrument values in current results (LEO products)."""
        return sorted({r.extras.get("INSTRUMENT", "") for r in self._results} - {""})

    def axes_summary(self) -> Dict[str, List[str]]:
        """Current possible values for each axis dimension."""
        return {
            "spec": self.specs(),
            "center": self.centers(),
            "campaign": self.campaigns(),
            "solution": self.solutions(),
            "sampling": self.samplings(),
            "instrument": self.instruments(),
        }

    def allowed_values(self, axis_name: str) -> List[str]:
        """Values currently allowed for *axis_name* by the resource specs.

        Introspects the live result set — not a static list — so
        allowed values naturally shrink as axes are pinned.
        """
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
                # Extra axis — check extras dict first, then regex fallback
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
        """Search for matching files on local disk.

        Returns a list of dicts with ``result`` (QueryResult) and
        ``files`` (list of Paths).
        """
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
        """Formatted table of results."""
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
    """Filter results by a single axis value."""

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
            # Extra axis — check extras dict first, then regex fallback
            v_upper = axis_name.upper()
            return [
                r for r in results
                if r.extras.get(v_upper, "").upper() == v
                or (not r.extras.get(v_upper) and v in (r.regex or "").upper())
            ]
