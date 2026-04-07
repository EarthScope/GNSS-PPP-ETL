"""Author: Franklyn Dunbar

Client — public API layer for GNSS product search and download.
"""

from gnss_product_management.client.gnss_client import GNSSClient
from gnss_product_management.client.search_result import SearchResult

__all__ = ["GNSSClient", "SearchResult"]
