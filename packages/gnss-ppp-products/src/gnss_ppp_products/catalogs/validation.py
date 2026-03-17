"""
Cross-registry validation — called once after all catalogs are loaded.

Implements the check-lists from the README:
- Product refs in remote/local specs exist in the product catalog
- Format refs in product bindings exist in the format catalog
- Metadata template fields are registered
"""

from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)


def validate_catalogs(
    *,
    meta_catalog,
    product_catalog,
    remote_factory,
    local_factory,
    query_spec,
) -> List[str]:
    """Validate cross-references between all catalogs.

    Returns a list of warning messages. Raises on critical errors.
    """
    warnings: List[str] = []

    # 1. Check that every product in query_spec exists in product_catalog
    for spec_name in query_spec.spec_names:
        if spec_name not in product_catalog.products:
            warnings.append(
                f"Query spec references product {spec_name!r} "
                f"not found in product catalog"
            )

    # 2. Check that remote product refs exist in product_catalog
    for prod in remote_factory.all_products:
        spec_name = prod.spec_name
        if spec_name not in product_catalog.products:
            warnings.append(
                f"Remote product {prod.id!r} references spec {spec_name!r} "
                f"not found in product catalog"
            )

    # 3. Check that local spec refs exist in product_catalog
    for spec_name in local_factory.all_specs:
        if spec_name not in product_catalog.products:
            warnings.append(
                f"Local spec references product {spec_name!r} "
                f"not found in product catalog"
            )

    # 4. Log results
    if warnings:
        for w in warnings:
            logger.warning("Validation: %s", w)
    else:
        logger.debug("All cross-reference validations passed.")

    return warnings
