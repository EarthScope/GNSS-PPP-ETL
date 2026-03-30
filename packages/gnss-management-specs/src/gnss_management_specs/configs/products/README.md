# `products/`: GNSS Product and Format Specifications

Alright, listen here, this `products/` directory is where the very DNA of our GNSS product handling system resides. It contains two utterly vital YAML files: `product_spec.yaml` and `format_spec.yaml`. Together, these files define *what* GNSS products we care about and *how* those products are represented in the wild, specifically in their filenames.

### `product_spec.yaml`

This file is the high-level catalogue of all the different GNSS product *types* our system recognizes. It defines:

*   **Abstract Product Definitions**: Think `ORBIT`, `CLOCK`, `BIA`, `IONEX`, `VMF`, and so on. These are the conceptual types of data we're interested in.
*   **Constraints**: For each product, it specifies general constraints and the allowed `formats` (linking to `format_spec.yaml`), along with any specific constraints (e.g., that an `ORBIT` product must have a `CNT` of "ORB" and an `FMT` of "SP3"). This ensures that when we ask for an `ORBIT` product, we're talking about a very specific type of data file.

Essentially, `product_spec.yaml` tells us *what* a particular GNSS product is, in a broad, abstract sense.

### `format_spec.yaml`

This file is the nitty-gritty detailer for *how* different data formats are structured, particularly concerning their filenames. It defines:

*   **Concrete Format Structures**: This includes specifications for formats like `RINEX` (versions 2, 3, and 4), `PRODUCT` (our generic product format), `VIENNA_MAPPING_FUNCTIONS`, `ANTENNAE`, and others.
*   **Versions and Variants**: For each format, it distinguishes between different `versions` (e.g., RINEX 2 vs. RINEX 3) and `variants` (e.g., `observation`, `navigation`, `meteorological` for RINEX).
*   **Filename Templates**: Crucially, it provides the exact `filename` templates (e.g., `{SSSS}{DDD}0.{YY}{T}` for RINEX 2 observation files) and lists the `parameters` (metadata fields from `meta_spec.yaml`) that populate those templates.

In short, `format_spec.yaml` acts as the blueprint for constructing and deconstructing filenames, tying together the abstract product definitions with the physical reality of how these files appear on servers.

### The Dynamic Duo

These two files work hand-in-glove. `product_spec.yaml` tells our system "I need an ORBIT product," and then `format_spec.yaml` (with the help of `meta_spec.yaml`) tells it "Right, an ORBIT product is typically an SP3 file, and its filename will look like `{AAA}{V}{PPP}...`". This powerful combination allows our `QueryFactory` to dynamically build precise file queries and our parsing routines to correctly interpret incoming data, forming the very backbone of our ETL process. Don't even think about messing with these unless you're prepared for the whole system to go belly-up!