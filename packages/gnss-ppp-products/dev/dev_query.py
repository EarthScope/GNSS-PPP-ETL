import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging
import re

from wcwidth import center

logger = logging.getLogger(__name__)

from gnss_ppp_products.specifications.metadata import MetadataCatalog,MetadataSpec
from gnss_ppp_products.specifications.products import ProductCatalog,ProductSpecCollection, ProductVariant
from gnss_ppp_products.specifications.remote import RemoteResourceFactory,RemoteResourceSpec, RemoteResourceCatalog
from gnss_ppp_products.specifications.format import FormatCatalog,FormatSpecCollection
from gnss_ppp_products.specifications.local import LocalResourceSpec, LocalResourceFactory
from gnss_ppp_products.specifications.queries import ProductQueryProfile, AxisDef, ExtraAxisDef,QuerySpec, ProductQuery,QueryResult
from gnss_ppp_products.utilities.metadata_funcs import register_computed_fields
from gnss_ppp_products.server.ftp import (
    ftp_list_directory,
    ftp_download_file,
)
from gnss_ppp_products.server.http import (
    http_list_directory,
    extract_filenames_from_html,
    http_get_file,
)


config_dir = Path(__file__).parent.parent / "src" / "gnss_ppp_products" / "configs"

meta_config_path = config_dir / "meta"/"meta_spec.yaml"
metadata_spec: MetadataCatalog = MetadataCatalog.from_yaml(meta_config_path)
register_computed_fields(metadata_spec)

format_spec_path = config_dir / "products" / "product_spec.yaml"
format_spec: FormatSpecCollection = FormatSpecCollection.from_yaml(format_spec_path)
format_catalog = FormatCatalog.resolve(format_spec,metadata_spec)

product_config_path = config_dir / "products"/"product_spec.yaml"
product_spec: ProductSpecCollection = ProductSpecCollection.from_yaml(product_config_path)
product_catalog = ProductCatalog.resolve(product_spec_collection=product_spec, format_catalog=format_catalog)

local_resource_config_path = config_dir / "local" / "local_config.yaml"
local_resource_spec: LocalResourceSpec = LocalResourceSpec.from_yaml(local_resource_config_path)
local_resource_factory = LocalResourceFactory.resolve(local_resource_spec, product_catalog)
local_resource_factory._metadata_catalog = metadata_spec

remote_resource_config_paths = (config_dir/"centers").glob("*.yaml")
remote_resource_specs = [RemoteResourceSpec.from_yaml(p) for p in remote_resource_config_paths]
remote_resource_catalogs = [RemoteResourceCatalog.resolve(spec, product_catalog, metadata_spec) for spec in remote_resource_specs]
remote_resource_factory = RemoteResourceFactory(product_catalog, metadata_spec)
for catalog in remote_resource_catalogs:
    remote_resource_factory._register(catalog)


query_config_path = config_dir / "query" / "query_config.yaml"
query_spec: QuerySpec = QuerySpec.from_yaml(query_config_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _match_template(file_template: str, filename: str) -> bool:
    """Check if *filename* matches the resolved *file_template*.

    The template may contain regex-like character classes from format
    field defaults (e.g. ``[A-Z0-9]{3}``).  We try it as a regex first;
    if it's not a valid pattern we fall back to a plain substring check.
    """
    try:
        return bool(re.search(file_template, filename, re.IGNORECASE))
    except re.error:
        return file_template in filename


def _list_remote(result: QueryResult) -> list[str]:
    """List files in the remote directory of *result*."""
    proto = result.remote_protocol.upper()
    server = result.remote_server
    directory = result.remote_directory

    if proto in ("FTP", "FTPS"):
        use_tls = proto == "FTPS"
        return ftp_list_directory(server, directory, use_tls=use_tls)

    if proto in ("HTTP", "HTTPS"):
        html = http_list_directory(server, directory)
        if html is None:
            return []
        return extract_filenames_from_html(html)

    print("Unsupported protocol %s for %s", proto, result.product_id)
    return []


def _download(
    result: QueryResult,
    filename: str,
    dest_dir: Path,
) -> bool:
    """Download *filename* from the remote described by *result*."""
    proto = result.remote_protocol.upper()
    server = result.remote_server
    directory = result.remote_directory
    dest_path = dest_dir / filename

    if dest_path.exists() and dest_path.stat().st_size > 0:
        log.info("  SKIP (exists) %s", dest_path)
        return True

    if proto in ("FTP", "FTPS"):
        use_tls = proto == "FTPS"
        return ftp_download_file(
            server, directory, filename, dest_path, use_tls=use_tls
        )

    if proto in ("HTTP", "HTTPS"):
        got = http_get_file(server, directory, filename, dest_dir=dest_dir)
        return got is not None

    print("Unsupported protocol %s", proto)
    return False


DATE= datetime.datetime(2024, 1, 1)
LOCAL_DIR = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP")
local_resource_factory._base_dir = LOCAL_DIR

query = ProductQuery(
    DATE,
    query_spec=query_spec,
    remote_factory=remote_resource_factory,
    local_factory=local_resource_factory,
    meta_catalog=metadata_spec,
    product_catalog=product_catalog,
)
query = query.narrow(spec="ORBIT")  # from IGS & CDDIS remotes, narrow to COD analysis center

print("Query produced %d results across specs: %s" % (query.count, query.specs()))
print("Remotes: %s" % query.remotes())
print("Centers (AAA): %s" % query.centers())
print("Solutions: %s" % query.solutions())
print("Campaigns: %s" % query.campaigns())


print()
print(query.table())
print()

# ---------------------------------------------------------------------------
# 2) Iterate results, list remotes, match, and download
# ---------------------------------------------------------------------------

stats = {"listed": 0, "matched": 0, "downloaded": 0, "skipped": 0, "failed": 0}

for r in query.results:
    label = f"{r.spec}/{r.remote}/{r.center}/{r.campaign}/{r.solution}/{r.sampling}"

    # -- resolve local destination -----------------------------------
    if not r.local_directory:

        dest_dir = local_resource_factory.resolve_directory(
            spec_name=r.spec,
            date=DATE,
        )
        dest_dir.mkdir(parents=True, exist_ok=True)

    else:
        dest_dir = Path(r.local_directory)

    listing = _list_remote(r)
    stats["listed"] += len(listing)

    if not listing:
      
        continue

    # -- match against resolved file_template -----------------------
    if not r.file_template:
       
        continue

    matches = [f for f in listing if _match_template(r.file_template, f)]
    stats["matched"] += len(matches)

    if not matches:
        #print("  0 matches for template: %s" % r.file_template[:80])
        continue

    else:
        print(
            f" Product Spec: {r.spec} | Remote: {r.remote} | Center (AAA): {r.center} | Remote Dir: {r.remote_directory} | Server: {r.remote_server} | Local Dir: {r.local_directory} | File Template: {r.file_template}"
        )
        print("  %d match(es): %s" % (len(matches), matches[:2]))
