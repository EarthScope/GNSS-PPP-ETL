"""Quick script to count query output per product for WUM."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))
import yaml, pathlib
from datetime import datetime as DateTime, timezone
from gnss_ppp_products.factories import ProductEnvironment, QueryFactory
from dev_specs import parameter_spec_dict, format_spec_dict, product_spec_dict

BASE = pathlib.Path(os.path.dirname(__file__), '..').resolve()
config_dir = BASE / 'src' / 'gnss_ppp_products' / 'configs' / 'centers'
local_config = BASE / 'src' / 'gnss_ppp_products' / 'configs' / 'local' / 'local_config.yaml'
center_dict = yaml.safe_load((config_dir / 'wuhan_config.yaml').read_text())
date_val = DateTime(2025, 1, 1, tzinfo=timezone.utc)

env_base = ProductEnvironment(
    base_dir="/tmp/gnss_probe",
    parameter_specs=parameter_spec_dict,
    format_specs=format_spec_dict,
    product_specs=product_spec_dict,
    local_config=local_config,
)

env = ProductEnvironment(
    base_dir="/tmp/gnss_probe",
    parameter_specs=parameter_spec_dict,
    format_specs=format_spec_dict,
    product_specs=product_spec_dict,
    remote_specs=[center_dict],
)

qf = QueryFactory(
    remote_factory=env.remote_factory,
    local_factory=env_base.local_factory,
    product_catalog=env.product_catalog,
    parameter_catalog=env.parameter_catalog,
)

products = list(env.product_catalog.products.keys())
print(f"Catalog products: {products}")
print(f"Center products: {[p['product_name'] for p in center_dict.get('products', [])]}")
print()
for pname in products:
    try:
        queries = qf.get(date=date_val, product={'name': pname})
        remote_queries = [q for q in queries if q.server.hostname != '/tmp/gnss_probe']
        dirs = set()
        for q in remote_queries:
            dirs.add(f'{q.server.hostname}:{q.directory.pattern}')
        print(f'{pname}: {len(remote_queries)} queries, {len(dirs)} unique dirs')
    except Exception as e:
        print(f'{pname}: ERROR - {e}')
