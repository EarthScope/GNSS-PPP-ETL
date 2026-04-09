"""Author: Franklyn Dunbar

FindPipeline — query → search → rank.

Composes :class:`SearchPlanner` + :class:`WormHole` + ranking
into a single ``run()`` call that returns :class:`FoundResource` results.
"""

from __future__ import annotations

import datetime
import logging
from typing import Dict, List, Optional, Tuple, Union, overload

from gnss_product_management.environments import ProductRegistry
from gnss_product_management.environments import WorkSpace
from gnss_product_management.factories.models import FoundResource
from gnss_product_management.factories.ranking import (
    sort_by_preferences,
    sort_by_protocol,
)
from gnss_product_management.factories.remote_transport import WormHole
from gnss_product_management.factories.search_planner import SearchPlanner
from gnss_product_management.specifications.dependencies.dependencies import (
    SearchPreference,
)
from gnss_product_management.specifications.remote.resource import SearchTarget

logger = logging.getLogger(__name__)


class FindPipeline:
    """Query → search → rank pipeline.

    Builds queries via :class:`SearchPlanner`, searches via
    :class:`WormHole`, ranks results by preference cascade,
    and returns :class:`FoundResource` objects.

    Args:
        env: The product registry with built catalogs and remote planner.
        workspace: Workspace with registered local resources.
        max_connections: Maximum concurrent connections per host.
    """

    def __init__(
        self,
        env: ProductRegistry,
        workspace: WorkSpace,
        *,
        max_connections: int = 4,
        transport: Optional[WormHole] = None,
    ) -> None:
        self._env = env
        self._planner = SearchPlanner(product_registry=env, workspace=workspace)
        self._transport = transport or WormHole(
            max_connections=max_connections, product_registry=env
        )

    def run(
        self,
        date: datetime.datetime,
        product: str,
        *,
        centers: Optional[List[str]] = None,
        filters: Optional[Dict[str, str]] = None,
        preferences: Optional[List[SearchPreference]] = None,
        all: bool = False,
    ) -> Union[Optional[FoundResource], List[FoundResource]]:
        """Find products matching the criteria.

        Args:
            date: Target date (timezone-aware datetime).
            product: Product name (e.g. ``"ORBIT"``).
            centers: Restrict to these remote center IDs.
            filters: Parameter constraints, e.g. ``{"TTT": "FIN"}``.
            preferences: Preference cascade for ranking results.
            all: If ``True``, return all results as a ranked list.
                Otherwise return only the single best result (or ``None``).

        Returns:
            A single :class:`FoundResource` (or ``None``) by default,
            or ``list[FoundResource]`` when ``all=True``.
        """
        queries = self._planner.get(
            date=date,
            product={"name": product},
            parameters=filters,
            remote_resources=centers,
        )

        if not queries:
            return [] if all else None

        expanded = self._transport.search(queries)

        if preferences:
            expanded = sort_by_preferences(expanded, preferences)
        ranked = sort_by_protocol(expanded)

        results = self._deduplicate_and_build(ranked)

        if all:
            return results
        return results[0] if results else None

    @property
    def planner(self) -> SearchPlanner:
        """The :class:`SearchPlanner` used by this pipeline."""
        return self._planner

    @property
    def transport(self) -> WormHole:
        """The :class:`WormHole` used by this pipeline."""
        return self._transport

    # -- Internal --------------------------------------------------

    @staticmethod
    def _deduplicate_and_build(
        targets: List[SearchTarget],
    ) -> List[FoundResource]:
        """Build FoundResource list, deduplicating by (hostname, filename)."""
        results: List[FoundResource] = []
        seen: set = set()

        for st in targets:
            hostname = st.server.hostname
            filename = st.product.filename.value if st.product.filename else ""
            key = (hostname, filename)
            if key in seen:
                continue
            seen.add(key)

            params = {
                p.name: p.value for p in st.product.parameters if p.value is not None
            }
            protocol = (st.server.protocol or "").upper()
            is_local = protocol in ("FILE", "LOCAL")

            if is_local:
                uri = str(
                    (
                        st.server.hostname
                        + "/"
                        + (st.directory.value or st.directory.pattern)
                        + "/"
                        + filename
                    )
                )
            else:
                proto = (st.server.protocol or "ftp").lower()
                uri = f"{proto}://{hostname}/{st.directory.value or st.directory.pattern}/{filename}"

            r = FoundResource(
                product=st.product.name,
                source="local" if is_local else "remote",
                uri=uri,
                parameters=params,
            )
            r._query = st
            results.append(r)

        return results
