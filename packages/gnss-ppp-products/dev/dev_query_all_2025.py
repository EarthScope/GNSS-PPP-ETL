"""Query all products for 2025-01-01 using the new Environment + catalogs."""

import datetime
from gnss_ppp_products.environment.environment import Environment

date = datetime.date(2025, 1, 1)
env = Environment.default()

print(f"Environment: {env.name}")
print(f"Date: {date}")
print(f"Validation errors: {len(env.validate())}")
print()

q = env.query(date)
print(f"Total query results: {q.count}")
print(f"Specs:    {q.specs()}")
print(f"Centers:  {q.centers()}")
print()

# Show full table
print(q.table())
print()

# Narrow by each spec and show details
for spec in q.specs():
    sq = q.narrow(spec=spec)
    print(f"\n{'='*80}")
    print(f"  {spec}  ({sq.count} results)")
    print(f"{'='*80}")
    for r in sq.results:
        print(
            f"  center={r.center:<6s}  campaign={r.campaign:<5s}  "
            f"solution={r.solution:<5s}  sampling={r.sampling:<5s}  "
            f"server={r.remote_server}"
        )
        if r.regex:
            print(f"    regex: {r.regex[:90]}")
        if r.remote_directory:
            print(f"    remote_dir: {r.remote_directory}")
        if r.local_directory:
            print(f"    local_dir: {r.local_directory} ({r.local_collection})")
