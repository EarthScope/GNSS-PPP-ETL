"""Metadata specification — field registry and template resolution."""

from .registry import _MetadataRegistry, MetadataField, extract_template_fields

__all__ = ["_MetadataRegistry", "MetadataField", "extract_template_fields"]
