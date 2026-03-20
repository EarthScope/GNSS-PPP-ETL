"""Quick debug for RNX3_BRDC and ATTOBX queries."""
import datetime, sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from dev_specs import parameter_spec_dict, format_spec_dict, product_spec_dict
from gnss_ppp_products.factories import ProductEnvironment, QueryFactory, ResourceFetcher
import yaml

with open(Path(__file__).parent.parent / "src/gnss_ppp_products/configs/centers/wuhan_config.yaml") as f:
    wum = yaml.safe_load(f)

env = ProductEnvironment(
    base_dir="/tmp/gnss_probe",
    parameter_specs=parameter_spec_dict,
    format_specs=format_spec_dict,
    product_specs=product_spec_dict,
    remote_specs=[wum],
    local_config=str(Path(__file__).parent.parent / "src/gnss_ppp_products/configs/local/local_config.yaml"),
)

qf = QueryFactory(
    remote_factory=env.remote_factory,
    local_factory=env.local_factory,
    product_catalog=env.product_catalog,
    parameter_catalog=env.parameter_catalog,
)
fetcher = ResourceFetcher()
date = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)

for pname in ["RNX3_BRDC", "ATTOBX"]:
    print(f"\n{'='*60}")
    print(f"Product: {pname}")
    print(f"{'='*60}")
    queries = qf.get(date=date, product={"name": pname})
    remote = [q for q in queries if "gnsswhu" in q.server.hostname]
    print(f"Total queries: {len(queries)}, Remote WUM queries: {len(remote)}")
    for q in remote:
        d = ResourceFetcher._get_directory(q)
        p = ResourceFetcher._get_file_pattern(q)
        print(f"  Dir: {d}")
        print(f"  Pat: {p}")
        r = fetcher._search_one(q)
        print(f"  Found: {r.found}  Error: {r.error}")
        if r.found:
            print(f"  Files: {r.matched_filenames[:5]}")
        else:
            print(f"  Listing sample: {r.directory_listing[:5]}")
