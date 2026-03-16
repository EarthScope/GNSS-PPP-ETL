# Specifications

## Class Diagram

```mermaid
graph TB


```

### Layer summary

| Layer | Package | Consumes | Provides |
|-------|---------|----------|----------|
| 1 | `metadata/` | — | Field patterns, computed-field registry |
| 2 | `products/` | metadata fields | Product specs, filename regex, format templates |
| 3a | `remote/` | product specs | Per-center server list, hosted product catalog |
| 3b | `local/` | product specs | Directory templates, collection groupings |
| 4 | `query/` | remote + local specs | Unified search axes, ranked query results |
| 5 | `dependencies/` | query engine | Task dependency resolution with preference cascade |
