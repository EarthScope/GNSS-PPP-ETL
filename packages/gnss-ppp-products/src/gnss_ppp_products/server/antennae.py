
from typing import List, Optional


from ..assets.antennae import AntennaeFileQuery
from .products import process_product_query

def process_antennae_query(antennae_query: AntennaeFileQuery) -> Optional[List[AntennaeFileQuery]]:
    strict_queries = []
    current_queries = []
    assert antennae_query.date is not None, "Antennae queries must have a date to compare against"
    
    for found in process_product_query(antennae_query):
        if not found or found.date is None:
            continue
        if found.date < antennae_query.date:
            strict_queries.append(found)
        elif found.date == antennae_query.date:
            current_queries.append(found)
    if strict_queries:
        strict_queries = [max(strict_queries, key=lambda q: q.date)]
    return current_queries + strict_queries