"""Singleton query spec registry, loaded at import time."""

from .query import QuerySpec

QuerySpecRegistry = QuerySpec.from_yaml()
