"""
dev_unified_query.py — Prototype: Unified Product Query
========================================================

Three approaches for seamless remote + local product queries that behave
like a filesystem search (more specificity → fewer results).

All three approaches build on the existing registries:
  - RemoteResourceRegistry  (centers, servers, products)
  - LocalResourceRegistry   (collections, directories)
  - ProductSpecRegistry     (product specs, filename templates)
  - MetaDataRegistry        (computed date fields, regex defaults)

Run:
    python dev/dev_unified_query.py
"""

from __future__ import annotations

import datetime
import fnmatch
import re
from dataclasses import dataclass, field
from enum import Enum
from itertools import product as itertools_product
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set, Tuple

from gnss_ppp_products.assets.remote_resource_spec import RemoteResourceRegistry
from gnss_ppp_products.assets.local_resource_spec import LocalResourceRegistry
from gnss_ppp_products.assets.product_spec import ProductSpecRegistry
from gnss_ppp_products.assets.meta_spec import MetaDataRegistry

# ═══════════════════════════════════════════════════════════════════════
#  Shared: ProductNode — a single resolvable product variant
# ═══════════════════════════════════════════════════════════════════════

class Availability(Enum):
    REMOTE_ONLY = "remote"
    LOCAL_ONLY  = "local"
    BOTH        = "both"

@dataclass(frozen=True)
class ProductNode:
    """
    One concrete product variant identified by its metadata dimensions.

    Think of it as a single 'file' in a virtual product filesystem.
    The dimensions (center, spec, solution, campaign, sampling) form the
    virtual path; the resolved fields point to real locations.
    """
    # ---- identity dimensions (form the virtual path) ----
    center:   str            # "IGS", "WUM"
    spec:     str            # "ORBIT", "CLOCK", "RNX3_BRDC"
    solution: str = ""       # "FIN", "RAP" (empty for non-product specs)
    campaign: str = ""       # "OPS", "MGX", "DEM"
    sampling: str = ""       # "05M", "30S"
    aaa:      str = ""       # analysis center code in filename ("IGS", "WUM", "WMC")

    # ---- remote resolution ----
    remote_product_id: str = ""
    remote_server:     str = ""
    remote_protocol:   str = ""
    remote_directory:  str = ""
    remote_regex:      str = ""      # filename regex for remote listing

    # ---- local resolution ----
    local_collection: str = ""       # "products", "common", "table"
    local_directory:  str = ""       # resolved relative path

    @property
    def path(self) -> str:
        """Virtual filesystem path built from identity dimensions.

        Segments that are empty are omitted, so less-specified products
        have shorter paths (and match broader queries).

        Format: /{center}/{spec}/{campaign}/{solution}/{sampling}
        Products with multiple AAA codes (e.g. WUM vs WMC) share the
        same virtual path; use .aaa to distinguish them if needed.
        """
        parts = [self.center, self.spec]
        if self.campaign:
            parts.append(self.campaign)
        if self.solution:
            parts.append(self.solution)
        if self.sampling:
            parts.append(self.sampling)
        return "/" + "/".join(parts)

    @property
    def segments(self) -> Tuple[str, ...]:
        return tuple(p for p in self.path.strip("/").split("/") if p)

    @property
    def depth(self) -> int:
        return len(self.segments)


# ═══════════════════════════════════════════════════════════════════════
#  Catalog builder — shared by all three approaches
# ═══════════════════════════════════════════════════════════════════════

def build_catalog(
    date: datetime.date,
    local_base: Optional[Path] = None,
) -> List[ProductNode]:
    """
    Enumerate every concrete product variant from the registries.

    For each RemoteProduct, expands all metadata combinations (e.g.
    AAA × TTT × PPP × SMP) into individual ProductNodes, and annotates
    each with local directory info when a matching local collection is
    found.
    """
    nodes: List[ProductNode] = []

    # Map spec → local collection for cross-referencing
    spec_to_local: Dict[str, Tuple[str, str]] = {}
    for coll_name in LocalResourceRegistry.collections:
        coll = LocalResourceRegistry.get_collection(coll_name)
        resolved_dir = coll.resolve_directory(date)
        for spec_name in coll.specs:
            spec_to_local[spec_name] = (coll_name, resolved_dir)

    # Walk every remote center & product
    for center_id, center in RemoteResourceRegistry.centers.items():
        for rp in center.products:
            if not rp.available:
                continue

            spec_name = rp.spec_name           # "ORBIT", "CLOCK", etc.
            server = RemoteResourceRegistry.get_server_for_product(rp.id)
            directory = rp.resolve_directory(date)

            # Build regexes (one per combination)
            try:
                regexes = rp.to_regexes(date)
            except Exception:
                regexes = []

            # Determine the metadata axes this product varies over.
            # Products like LEAP_SEC have no AAA/TTT/PPP/SMP — they get
            # one node with empty strings for those dimensions.
            aaa_vals = rp.metadata.get("AAA", [""])
            ttt_vals = rp.metadata.get("TTT", [""])
            ppp_vals = rp.metadata.get("PPP", [""])
            smp_vals = rp.metadata.get("SMP", [""])

            # Expand into one node per metadata combination
            combos = list(itertools_product(aaa_vals, ttt_vals, ppp_vals, smp_vals))
            for i, (aaa, ttt, ppp, smp) in enumerate(combos):
                regex = regexes[i] if i < len(regexes) else (regexes[0] if regexes else "")

                local_coll, local_dir = spec_to_local.get(spec_name, ("", ""))

                nodes.append(ProductNode(
                    center=center_id,
                    spec=spec_name,
                    solution=ttt,
                    campaign=ppp,
                    sampling=smp,
                    aaa=aaa,
                    remote_product_id=rp.id,
                    remote_server=server.hostname,
                    remote_protocol=server.protocol,
                    remote_directory=directory,
                    remote_regex=regex,
                    local_collection=local_coll,
                    local_directory=local_dir,
                ))

    return nodes


# ═══════════════════════════════════════════════════════════════════════
#  APPROACH 1 — Virtual Filesystem with ls() and glob()
# ═══════════════════════════════════════════════════════════════════════

class ProductTree:
    """
    Virtual filesystem over the product catalog.

    Every product variant has a path like:
        /IGS/ORBIT/OPS/FIN/05M
        /WUM/CLOCK/MGX/RAP/30S
        /WUM/ATTATX

    Users navigate with ls() (list children at a level) and glob()
    (pattern-match across the tree).  More path segments → narrower results.

    Example:
        tree = ProductTree(date=datetime.date(2025, 1, 15))
        tree.ls("/")                        # → ['IGS', 'WUM']
        tree.ls("/IGS")                     # → ['ORBIT', 'CLOCK', 'ERP', ...]
        tree.ls("/IGS/ORBIT")               # → ['OPS']
        tree.ls("/IGS/ORBIT/OPS")           # → ['FIN', 'RAP']
        tree.ls("/IGS/ORBIT/OPS/FIN")       # → ['05M', '15M']
        tree.glob("/*/ORBIT/**/FIN/*")      # all FIN orbits from any center
        tree.glob("/WUM/**")                # everything from Wuhan
        tree.resolve("/IGS/ORBIT/OPS/FIN/05M")  # → ProductNode with full details
    """

    def __init__(self, date: datetime.date, local_base: Optional[Path] = None):
        self.date = date
        self.nodes = build_catalog(date, local_base)
        # Deduplicate: same path can appear from multiple AAA codes
        self._path_map: Dict[str, ProductNode] = {}
        seen_paths: Set[str] = set()
        self._unique_nodes: List[ProductNode] = []
        for n in self.nodes:
            if n.path not in seen_paths:
                seen_paths.add(n.path)
                self._path_map[n.path] = n
                self._unique_nodes.append(n)

    def ls(self, path: str = "/") -> List[str]:
        """List unique child names at the given path level."""
        path = path.rstrip("/")
        depth = 0 if path == "" else path.count("/")

        children: Set[str] = set()
        for node in self._unique_nodes:
            segs = node.segments
            if len(segs) <= depth:
                continue
            # Check the node's path starts with the query path
            node_prefix = "/" + "/".join(segs[:depth])
            if node_prefix == path or path in ("", "/"):
                children.add(segs[depth])

        return sorted(children)

    def glob(self, pattern: str) -> List[ProductNode]:
        """
        Filesystem-style glob match against virtual paths.

        Supports *, **, and ? wildcards (via fnmatch).
        More specific patterns produce fewer results.
        """
        matched = []
        for node in self._unique_nodes:
            if fnmatch.fnmatch(node.path, pattern):
                matched.append(node)
        return matched

    def resolve(self, path: str) -> Optional[ProductNode]:
        """Resolve an exact virtual path to its ProductNode."""
        return self._path_map.get(path)

    def search(self, *terms: str) -> List[ProductNode]:
        """
        Progressive keyword search — each term narrows results.

        Like typing into a command-line fuzzy finder:
            tree.search("IGS")              # broad
            tree.search("IGS", "ORBIT")     # narrower
            tree.search("IGS", "ORBIT", "FIN")  # most specific
        """
        results = self._unique_nodes
        for term in terms:
            term_upper = term.upper()
            results = [n for n in results if term_upper in n.path.upper()]
        return results

    def summary(self, nodes: Optional[List[ProductNode]] = None) -> str:
        """Pretty-print summary of nodes."""
        nodes = nodes or self._unique_nodes
        lines = []
        for n in nodes:
            location = []
            if n.remote_server:
                location.append(f"remote={n.remote_server}")
            if n.local_directory:
                location.append(f"local={n.local_directory}")
            lines.append(f"  {n.path:<45s}  [{', '.join(location)}]")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
#  APPROACH 2 — Fluent Query Builder
# ═══════════════════════════════════════════════════════════════════════

class ProductQuery:
    """
    Chainable, progressive filter over the product catalog.

    Each .method() call narrows the result set — like piping through
    successive grep filters.  Call .results() to materialise.

    Example:
        q = ProductQuery(date=datetime.date(2025, 1, 15))
        q.results()                               # everything
        q.center("IGS").results()                  # only IGS
        q.center("IGS").spec("ORBIT").results()    # only IGS orbits
        q.center("IGS").spec("ORBIT").solution("FIN").sampling("05M").results()  # one variant

    Methods are non-destructive (return new query instances) so you can
    branch from intermediate states.
    """

    def __init__(
        self,
        date: datetime.date,
        local_base: Optional[Path] = None,
        _nodes: Optional[List[ProductNode]] = None,
    ):
        self.date = date
        self._nodes = _nodes if _nodes is not None else build_catalog(date, local_base)

    def _filter(self, predicate) -> "ProductQuery":
        return ProductQuery(self.date, _nodes=[n for n in self._nodes if predicate(n)])

    # —— dimension filters ——

    def center(self, value: str) -> "ProductQuery":
        v = value.upper()
        return self._filter(lambda n: n.center.upper() == v)

    def spec(self, value: str) -> "ProductQuery":
        v = value.upper()
        return self._filter(lambda n: n.spec.upper() == v)

    def solution(self, value: str) -> "ProductQuery":
        v = value.upper()
        return self._filter(lambda n: n.solution.upper() == v)

    def campaign(self, value: str) -> "ProductQuery":
        v = value.upper()
        return self._filter(lambda n: n.campaign.upper() == v)

    def sampling(self, value: str) -> "ProductQuery":
        v = value.upper()
        return self._filter(lambda n: n.sampling.upper() == v)

    # —— convenience filters ——

    def available_locally(self, local_base: Path) -> "ProductQuery":
        """Keep only nodes that have at least one matching file on disk."""
        def has_local(n: ProductNode) -> bool:
            if not n.local_directory:
                return False
            d = local_base / n.local_directory
            if not d.exists():
                return False
            if not n.remote_regex:
                return any(d.iterdir())
            pat = re.compile(n.remote_regex, re.IGNORECASE)
            return any(pat.search(f.name) for f in d.iterdir() if f.is_file())
        return self._filter(has_local)

    def remote_only(self) -> "ProductQuery":
        return self._filter(lambda n: n.remote_server and not n.local_directory)

    # —— terminal operations ——

    def results(self) -> List[ProductNode]:
        return list(self._nodes)

    def count(self) -> int:
        return len(self._nodes)

    def first(self) -> Optional[ProductNode]:
        return self._nodes[0] if self._nodes else None

    def paths(self) -> List[str]:
        seen = set()
        result = []
        for n in self._nodes:
            if n.path not in seen:
                seen.add(n.path)
                result.append(n.path)
        return result

    def __repr__(self) -> str:
        return f"<ProductQuery: {self.count()} results>"


# ═══════════════════════════════════════════════════════════════════════
#  APPROACH 3 — Regex Cascade (filesystem-style progressive narrowing)
# ═══════════════════════════════════════════════════════════════════════

class RegexCatalog:
    """
    Query products by progressively building a filename regex.

    Like searching a filesystem with `find` and a pattern that gets
    more specific.  At each step you're appending to a regex that
    matches against the full IGS long-filename convention:

        {AAA}{V}{PPP}{TTT}_{YYYY}{DDD}HHMM_{LEN}_{SMP}_{CNT}.{FMT}[.gz]

    The more fields you pin, the fewer products match.

    Example:
        cat = RegexCatalog(date=datetime.date(2025, 1, 15))

        cat.match()                          # all regexes for all products
        cat.match(center="IGS")              # only IGS patterns
        cat.match(center="IGS", content="ORB")         # IGS orbits
        cat.match(center="IGS", content="ORB", solution="FIN", sampling="05M")  # one file

    Each result includes the compiled regex + remote/local locations,
    ready for direct directory listing and matching.
    """

    def __init__(self, date: datetime.date, local_base: Optional[Path] = None):
        self.date = date
        self.nodes = build_catalog(date, local_base)

    def match(
        self,
        center:   Optional[str] = None,
        spec:     Optional[str] = None,
        solution: Optional[str] = None,
        campaign: Optional[str] = None,
        sampling: Optional[str] = None,
        content:  Optional[str] = None,
        fmt:      Optional[str] = None,
    ) -> List[Dict]:
        """
        Return all product variants matching the given constraints.

        Each additional keyword narrows the set.  Unspecified fields
        remain as regex wildcards in the filename pattern.
        """
        results = []
        for node in self.nodes:
            # Progressive dimension filters
            if center and node.center.upper() != center.upper():
                continue
            if spec and node.spec.upper() != spec.upper():
                continue
            if solution and node.solution.upper() != solution.upper():
                continue
            if campaign and node.campaign.upper() != campaign.upper():
                continue
            if sampling and node.sampling.upper() != sampling.upper():
                continue

            # For content/format, narrow via the regex itself
            regex = node.remote_regex
            if regex:
                if content:
                    # Check if the content code appears in the regex
                    if content.upper() not in regex.upper():
                        continue
                if fmt:
                    if not regex.upper().endswith(fmt.upper()):
                        if fmt.upper() not in regex.upper():
                            continue

            results.append({
                "node":       node,
                "path":       node.path,
                "regex":      regex,
                "remote_url": f"{node.remote_server}/{node.remote_directory}" if node.remote_server else None,
                "local_dir":  node.local_directory or None,
            })

        return results

    def preview(self, results: List[Dict]) -> str:
        """Formatted preview of match results."""
        lines = []
        for r in results:
            n = r["node"]
            lines.append(
                f"  {n.path:<40s}  regex={r['regex'][:60]}..."
                if len(r.get("regex", "")) > 60 else
                f"  {n.path:<40s}  regex={r.get('regex', '(none)')}"
            )
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
#  Demo / Comparison
# ═══════════════════════════════════════════════════════════════════════

def demo():
    date = datetime.date(2025, 1, 15)
    sep = "=" * 72

    # ------------------------------------------------------------------
    print(f"\n{sep}")
    print("  Building unified product catalog for", date)
    print(sep)
    nodes = build_catalog(date)
    print(f"  Total product variants: {len(nodes)}")
    print()

    # ------------------------------------------------------------------
    # APPROACH 1 — Virtual Filesystem
    # ------------------------------------------------------------------
    print(f"\n{sep}")
    print("  APPROACH 1: Virtual Filesystem (ls / glob / search)")
    print(sep)

    tree = ProductTree(date)

    print("\n  tree.ls('/')  — top-level centers:")
    for c in tree.ls("/"):
        print(f"    {c}")

    print("\n  tree.ls('/IGS')  — IGS product specs:")
    for s in tree.ls("/IGS"):
        print(f"    {s}")

    print("\n  tree.ls('/IGS/ORBIT')  — IGS orbit campaigns:")
    for c in tree.ls("/IGS/ORBIT"):
        print(f"    {c}")

    print("\n  tree.ls('/IGS/ORBIT/OPS')  — IGS OPS orbit solutions:")
    for s in tree.ls("/IGS/ORBIT/OPS"):
        print(f"    {s}")

    print("\n  tree.ls('/IGS/ORBIT/OPS/FIN')  — IGS OPS FIN orbit sampling:")
    for s in tree.ls("/IGS/ORBIT/OPS/FIN"):
        print(f"    {s}")

    print("\n  tree.search('ORBIT', 'FIN')  — all FIN orbits:")
    for n in tree.search("ORBIT", "FIN"):
        print(f"    {n.path}")

    print("\n  tree.glob('/*/ORBIT/*/FIN/*')  — glob for FIN orbits:")
    for n in tree.glob("/*/ORBIT/*/FIN/*"):
        print(f"    {n.path}")

    if tree.resolve("/IGS/ORBIT/OPS/FIN/05M"):
        print("\n  tree.resolve('/IGS/ORBIT/OPS/FIN/05M'):")
        n = tree.resolve("/IGS/ORBIT/OPS/FIN/05M")
        print(f"    server:    {n.remote_server}")
        print(f"    directory: {n.remote_directory}")
        print(f"    regex:     {n.remote_regex}")
        print(f"    local:     {n.local_directory}")

    # ------------------------------------------------------------------
    # APPROACH 2 — Fluent Query Builder
    # ------------------------------------------------------------------
    print(f"\n{sep}")
    print("  APPROACH 2: Fluent Query Builder (progressive filtering)")
    print(sep)

    q = ProductQuery(date)
    print(f"\n  ProductQuery(date)                           → {q.count()} results")

    q1 = q.center("IGS")
    print(f"  .center('IGS')                               → {q1.count()} results")

    q2 = q1.spec("ORBIT")
    print(f"  .center('IGS').spec('ORBIT')                 → {q2.count()} results")

    q3 = q2.solution("FIN")
    print(f"  .center('IGS').spec('ORBIT').solution('FIN') → {q3.count()} results")

    q4 = q3.sampling("05M")
    print(f"  ...solution('FIN').sampling('05M')           → {q4.count()} results")

    if q4.first():
        n = q4.first()
        print(f"\n  Final result:")
        print(f"    path:      {n.path}")
        print(f"    server:    {n.remote_server}")
        print(f"    directory: {n.remote_directory}")
        print(f"    regex:     {n.remote_regex}")

    # Branching: both solutions from same base
    print(f"\n  Branching from .center('WUM').spec('ORBIT'):")
    wum_orbit = q.center("WUM").spec("ORBIT")
    for sol in ("FIN", "RAP"):
        branch = wum_orbit.solution(sol)
        print(f"    .solution('{sol}') → {branch.count()} variants: {branch.paths()}")

    # ------------------------------------------------------------------
    # APPROACH 3 — Regex Cascade
    # ------------------------------------------------------------------
    print(f"\n{sep}")
    print("  APPROACH 3: Regex Cascade (progressive filename narrowing)")
    print(sep)

    cat = RegexCatalog(date)

    r0 = cat.match()
    print(f"\n  match()                           → {len(r0)} patterns")

    r1 = cat.match(center="IGS")
    print(f"  match(center='IGS')               → {len(r1)} patterns")

    r2 = cat.match(center="IGS", spec="ORBIT")
    print(f"  match(center='IGS', spec='ORBIT') → {len(r2)} patterns")

    r3 = cat.match(center="IGS", spec="ORBIT", solution="FIN")
    print(f"  match(..., solution='FIN')         → {len(r3)} patterns")

    r4 = cat.match(center="IGS", spec="ORBIT", solution="FIN", sampling="05M")
    print(f"  match(..., sampling='05M')         → {len(r4)} patterns")

    if r4:
        print(f"\n  Final regex pattern (ready for directory listing):")
        print(f"    {r4[0]['regex']}")
        print(f"    remote: {r4[0]['remote_url']}")
        print(f"    local:  {r4[0]['local_dir']}")

    # ------------------------------------------------------------------
    # Comparison Summary
    # ------------------------------------------------------------------
    print(f"\n{sep}")
    print("  COMPARISON SUMMARY")
    print(sep)
    print("""
    ┌─────────────────────┬───────────────────────────────────────────────────┐
    │ Approach            │ Characteristics                                  │
    ├─────────────────────┼───────────────────────────────────────────────────┤
    │ 1. Virtual FS       │ • Most intuitive filesystem metaphor             │
    │    (ls/glob/search) │ • ls() for discovery, glob() for batch queries   │
    │                     │ • Paths are human-readable product identifiers    │
    │                     │ • Natural for CLI tools (tab-completion, etc.)    │
    │                     │ • Best for: interactive exploration               │
    ├─────────────────────┼───────────────────────────────────────────────────┤
    │ 2. Fluent Builder   │ • Programmatic & composable                      │
    │    (.center.spec..) │ • Non-destructive branching (fork from any point) │
    │                     │ • Easy to add new filter dimensions               │
    │                     │ • IDE-friendly (autocomplete on methods)          │
    │                     │ • Best for: library API / pipeline integration    │
    ├─────────────────────┼───────────────────────────────────────────────────┤
    │ 3. Regex Cascade    │ • Closest to actual filename matching             │
    │    (match+filters)  │ • Returns ready-to-use regex for FTP/HTTP listing │
    │                     │ • No intermediate abstractions — direct to action │
    │                     │ • Maps 1:1 to existing server protocol code       │
    │                     │ • Best for: download engine / automation          │
    └─────────────────────┴───────────────────────────────────────────────────┘

    All three share the same catalog builder.  They could coexist as
    different "views" over the same ProductNode index, or you could pick
    one as the primary API and derive the others from it.
    """)


if __name__ == "__main__":
    demo()
