"""Quick check that all registries load with the new product schema."""
from gnss_ppp_products.configs.defaults import (
    MetaDataRegistry, ProductSpecRegistry, RemoteResourceRegistry,
    LocalResourceRegistry, QuerySpecRegistry,
)

print("=== Metadata Registry ===")
print(f"  Fields: {len(MetaDataRegistry.fields)}")

print("\n=== Product Spec Registry ===")
for name, prod in ProductSpecRegistry.products.items():
    variants = ProductSpecRegistry._resolver.get_variants(name)
    print(f"  {name}: {len(variants)} variant(s)")
    for i, v in enumerate(variants):
        print(f"    [{i}] format_id={v.format_id} version={v.version} variant={v.variant}")
        print(f"        file_templates={v.file_templates}")
        print(f"        constraints={v.constraints}")
        if v.field_defaults:
            print(f"        field_defaults={v.field_defaults}")

print(f"\n=== Remote Registry ===")
print(f"  Centers: {len(RemoteResourceRegistry.centers)}")

print(f"\n=== Query Spec ===")
print(f"  Products: {len(QuerySpecRegistry.products)}")
