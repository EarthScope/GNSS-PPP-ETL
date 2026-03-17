"""Quick verification that all imports resolve after restructuring."""

import sys

errors = []

def check(label, fn):
    try:
        fn()
        print(f"  OK  {label}")
    except Exception as e:
        errors.append((label, e))
        print(f"  FAIL {label}: {e}")

print("=== Layer 1: specifications (pure models) ===")
check("metadata", lambda: __import__("gnss_ppp_products.specifications.metadata", fromlist=["MetadataField"]))
check("formats", lambda: __import__("gnss_ppp_products.specifications.formats", fromlist=["FormatFieldDef", "FormatVersionSpec", "FormatSpec"]))
check("products", lambda: __import__("gnss_ppp_products.specifications.products", fromlist=["ProductFormatBinding", "ProductSpec"]))
check("remote", lambda: __import__("gnss_ppp_products.specifications.remote", fromlist=["ServerSpec", "RemoteProductSpec", "RemoteResourceSpec"]))
check("local", lambda: __import__("gnss_ppp_products.specifications.local", fromlist=["LocalCollection", "LocalResourceSpec"]))
check("query", lambda: __import__("gnss_ppp_products.specifications.query", fromlist=["AxisDef", "ExtraAxisDef", "ProductQueryProfile"]))
check("dependencies", lambda: __import__("gnss_ppp_products.specifications.dependencies", fromlist=["DependencySpec", "DependencyResolution"]))
check("specs __init__", lambda: __import__("gnss_ppp_products.specifications", fromlist=["MetadataField", "FormatSpec", "ProductSpec"]))

print("\n=== Layer 2: catalogs ===")
check("catalogs __init__", lambda: __import__("gnss_ppp_products.catalogs", fromlist=["MetadataCatalog", "ProductSpecRegistry"]))
check("metadata_catalog", lambda: __import__("gnss_ppp_products.catalogs.metadata_catalog", fromlist=["MetadataCatalog"]))
check("format_catalog", lambda: __import__("gnss_ppp_products.catalogs.format_catalog", fromlist=["FormatCatalog"]))
check("product_catalog", lambda: __import__("gnss_ppp_products.catalogs.product_catalog", fromlist=["ProductCatalog", "ProductResolver"]))
check("local_factory", lambda: __import__("gnss_ppp_products.catalogs.local_factory", fromlist=["LocalResourceFactory"]))
check("remote_factory", lambda: __import__("gnss_ppp_products.catalogs.remote_factory", fromlist=["RemoteResourceFactory"]))
check("query_engine", lambda: __import__("gnss_ppp_products.catalogs.query_engine", fromlist=["ProductQuery", "QuerySpec"]))
check("dependency_resolver", lambda: __import__("gnss_ppp_products.catalogs.dependency_resolver", fromlist=["DependencyResolver"]))
check("validation", lambda: __import__("gnss_ppp_products.catalogs.validation", fromlist=["validate_catalogs"]))

print("\n=== Layer 3: environment ===")
check("environment", lambda: __import__("gnss_ppp_products.environment.environment", fromlist=["Environment"]))

print("\n=== configs ===")
check("configs paths", lambda: __import__("gnss_ppp_products.configs", fromlist=["META_SPEC_YAML"]))

if errors:
    print(f"\n*** {len(errors)} FAILURES ***")
    for label, err in errors:
        print(f"  {label}: {err}")
    sys.exit(1)
else:
    print("\nAll imports OK!")
