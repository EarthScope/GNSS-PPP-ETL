"""
Unified environment for GNSS product specifications.

An :class:`Environment` bundles all spec registries (meta, product,
remote, local, query, and optionally dependency) into a single
validated container.

Usage::

    from gnss_ppp_products.environment import Environment

    env = Environment.from_yaml("environments/pride_ppp_kin.yml")
    q = env.query(datetime.date(2025, 1, 1))
    result = env.resolve(datetime.date(2025, 1, 1), download=True)
"""

from .environment import Environment

__all__ = ["Environment"]
