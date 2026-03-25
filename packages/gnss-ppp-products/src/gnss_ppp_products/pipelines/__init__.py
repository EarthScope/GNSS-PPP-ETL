"""Pipelines — orchestration classes that compose environment state with behavior.

Each pipeline takes a ``ProductEnvironment`` at construction and exposes a
``run()`` method.  Pipelines read catalogs/factories/fetcher from the
environment but never mutate it.
"""

from gnss_ppp_products.pipelines.find import FindPipeline
from gnss_ppp_products.pipelines.download import DownloadPipeline
from gnss_ppp_products.pipelines.lockfile_writer import LockfileWriter
from gnss_ppp_products.pipelines.resolve import ResolvePipeline

__all__ = [
    "FindPipeline",
    "DownloadPipeline",
    "LockfileWriter",
    "ResolvePipeline",
]
