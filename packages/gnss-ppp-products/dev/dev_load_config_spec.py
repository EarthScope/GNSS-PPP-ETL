"""
dev_load_config_spec.py

Equivalent of dev_load_config.py but using the new registry-based
spec architecture (RemoteResourceRegistry + ProductSpecRegistry +
MetaDataRegistry) instead of the old GNSSCenterConfig approach.
"""

import datetime
import json
import re
from typing import List

from gnss_ppp_products.assets.remote_resource_spec import RemoteResourceRegistry
from gnss_ppp_products.server.ftp import ftp_list_directory, ftp_find_best_match_in_listing
from gnss_ppp_products.server.http import http_list_directory, extract_filenames_from_html

# ------------------------------------------------------------------
# Target date
# ------------------------------------------------------------------
date = datetime.datetime(2025, 1, 15, tzinfo=datetime.timezone.utc)

# ------------------------------------------------------------------
# Query every product from every centre
# ------------------------------------------------------------------
found = []

for product in RemoteResourceRegistry.all_products:
    if not product.available:
        continue

    server = RemoteResourceRegistry.get_server_for_product(product.id)
    centre = RemoteResourceRegistry.get_product_centre(product.id)
    directory = product.resolve_directory(date)
    regexes = product.to_regexes(date)

    print(f"\n=== [{centre.id}] {product.id}  (spec={product.spec_name}) ===")
    print(f"    server:    {server.hostname}  ({server.protocol})")
    print(f"    directory: {directory}")
    print(f"    regexes:   {len(regexes)}")

    # List the remote directory
    hostname = server.hostname
    protocol = server.protocol.upper()
    matches: List[str] = []

    try:
        if protocol in ("FTP", "FTPS"):
            listing = ftp_list_directory(
                hostname, directory, use_tls=(protocol == "FTPS")
            )
            for regex in regexes:
                for hit in ftp_find_best_match_in_listing(listing, regex):
                    if hit not in matches:
                        matches.append(hit)

        elif protocol in ("HTTP", "HTTPS"):
            html = http_list_directory(server=hostname, directory=directory)
            if html:
                filenames = extract_filenames_from_html(html)
                for regex in regexes:
                    pat = re.compile(regex)
                    for fn in filenames:
                        if pat.search(fn) and fn not in matches:
                            matches.append(fn)
    except Exception as e:
        print(f"    ERROR: {e}")
        continue

    for m in matches:
        print(f"    MATCH: {m}")
        found.append({
            "centre": centre.id,
            "product_id": product.id,
            "spec": product.spec_name,
            "server": hostname,
            "protocol": server.protocol,
            "directory": directory,
            "filename": m,
        })

# ------------------------------------------------------------------
# Write results
# ------------------------------------------------------------------
outfile = "found_products_spec.json"
with open(outfile, "w") as f:
    json.dump(found, f, indent=2)

print(f"\n{'='*60}")
print(f"Found {len(found)} files total, written to {outfile}")
