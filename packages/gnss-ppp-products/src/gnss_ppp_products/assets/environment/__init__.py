"""
Unified environment for GNSS product specifications.

An :class:`Environment` bundles all spec registries (meta, product,
remote, local, query, and optionally dependency) into a single
validated container.  It can be built programmatically or loaded
from a manifest YAML file.

Usage::

    from gnss_ppp_products.assets.environment import Environment

    # From a manifest file
    env = Environment.from_yaml("environments/pride_ppp_kin.yml")

    # Query within this environment
    q = env.query(datetime.date(2025, 1, 1))
    q_orbit = q.narrow(spec="ORBIT", center="IGS")

    # Resolve dependencies and download
    result = env.resolve(datetime.date(2025, 1, 1), download=True)
"""

from .environment import Environment

__all__ = ["Environment"]
