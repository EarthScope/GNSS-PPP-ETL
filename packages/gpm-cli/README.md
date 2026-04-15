# gpm-cli

Command-line interface for GNSSommelier — search, download, probe, and
configure GNSS product retrieval from the terminal.

## Installation

From the monorepo (development):

```bash
uv sync
```

Standalone:

```bash
uv add gpm-cli
# or
pip install gpm-cli
```

---

## Quick start

```bash
# First-run configuration wizard
gnssommelier config init

# Search for final orbits on a date
gnssommelier search ORBIT --date 2025-01-15

# Download orbit + clock from COD and WUM
gnssommelier download ORBIT CLOCK --date 2025-01-15 --sources COD WUM

# Check server connectivity
gnssommelier probe

# Check which centers have final orbits for a date
gnssommelier probe --date 2025-01-15 --product ORBIT
```

---

## Commands

### `gnssommelier search`

Search for products across all registered analysis centers and print a results
table. Does not download files.

```
gnssommelier search PRODUCT [PRODUCT...] --date YYYY-MM-DD [options]

Options:
  --date       DATE         Target date (required)
  --to         DATE         End date for a range search
  --where      KEY=VALUE    Pin a parameter (e.g. --where TTT=FIN)
  --sources    CENTER...    Limit to specific centers
  --workers    INT          Parallel search threads (default: 4)
  --json       FILE         Write results to a JSON file
```

Example:

```bash
gnssommelier search ORBIT CLOCK --date 2025-01-15 --where TTT=FIN --sources COD WUM GFZ
```

---

### `gnssommelier download`

Download products to the configured `base_dir`.

```
gnssommelier download PRODUCT [PRODUCT...] --date YYYY-MM-DD [options]

Options:
  --date       DATE         Target date (required)
  --sources    CENTER...    Limit to specific centers
  --where      KEY=VALUE    Pin a parameter
  --workers    INT          Parallel download threads (default: 4)
  --dry-run                 Print what would be downloaded without fetching
  --limit      INT          Max files to download
```

Example:

```bash
gnssommelier download ORBIT CLOCK ERP BIA --date 2025-01-15 --where TTT=FIN
```

---

### `gnssommelier probe`

Check server connectivity or product availability across centers.

```
gnssommelier probe [options]

Options:
  --center     CENTER...    Limit to specific centers
  --date       DATE         Enable product-search mode
  --product    PRODUCT...   Products to search for (with --date)
  --workers    INT          Parallel probe threads (default: 4)
  --json       FILE         Write results to a JSON file
```

Without `--date`: tests TCP/FTP connectivity to each server (connection probe).
With `--date`: runs a product search and reports availability per center.

Exit code is `0` if all checks pass, `1` if any fail.

---

### `gnssommelier config`

Manage the persistent user configuration file.

```
gnssommelier config init      # Interactive first-run wizard
gnssommelier config show      # Print all current settings and their source
gnssommelier config set KEY VALUE   # Update a single key
gnssommelier config reset     # Delete the user config file
gnssommelier config validate  # Validate directories and server reachability
```

---

## Configuration

Settings are read from (in priority order):

1. `$GNSS_CONFIG` environment variable — path to a TOML file
2. `gnssommelier.toml` in the current working directory
3. `~/.config/gnssommelier/config.toml` (user-level)

TOML schema:

```toml
log_level = "WARNING"          # DEBUG, INFO, WARNING, ERROR
base_dir = "~/gnss_data"       # local workspace root (or s3://, gs://, az://)
max_connections = 4            # per-host FTP/HTTPS connection pool size
centers = ["COD", "WUM", "GFZ"]  # default center filter (empty = all)
```

Run `gnssommelier config init` to create the user config interactively.

---

## Dependencies

| Package | Role |
|---|---|
| `gnss-product-management` | Product discovery, download, and dependency resolution |
| `typer` | CLI framework |
| `rich` | Terminal output formatting |
