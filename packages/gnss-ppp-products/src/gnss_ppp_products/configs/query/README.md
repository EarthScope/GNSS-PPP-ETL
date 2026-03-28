# `query/`: Product Query Specifications

Alright, listen up. This `query/` directory, home to `query_config.yaml`, is the brain of our "Product Query System." If you want to find a specific GNSS product among the vast oceans of data, this file tells you exactly *how* you're allowed to ask for it. It defines the searchable dimensions – the "axes" – that you can use to narrow down your search.

This `query_config.yaml` file lays out:

*   **Axis Definitions**: It meticulously lists all the available query `axes`, such as `date`, `spec`, `center`, `campaign`, `solution`, and `sampling`. For each axis, you'll find:
    *   A clear `description` of what it represents.
    *   Its `type` (`enum` for a choice from a list, `computed` for values derived dynamically, like dates).
    *   Whether it's `required` for a query to be valid.
    *   The underlying metadata fields it `maps_to` (e.g., `center` maps to the `AAA` analysis-center code).
    *   Helpful `notes` that give you the full context and any special considerations.

    These axes are how our system translates your plain English requests into the arcane codes and patterns found in filenames.
*   **Product Query Profiles**: For each high-level product (like `ORBIT`, `CLOCK`, `IONEX`, `RNX3_BRDC`, `VMF`), it defines:
    *   Which of the global `axes` are applicable. This tells you which parameters you can actually use when searching for that specific product.
    *   `extra_axes`: Some products have unique, specialized query parameters (e.g., `constellation` for broadcast navigation files) that are defined here.
    *   `format_key`: This links the product to its specific format definition in `format_spec.yaml`, ensuring the right filename template is used.
    *   `temporal`: Tells the system if the product is `daily`, `hourly`, or `static`, which influences how date-based queries are handled.
    *   `local_collection`: Specifies which local storage collection (from `local_config.yaml`) this product belongs to once downloaded.

In a nutshell, `query_config.yaml` defines the API for asking for GNSS products. It ensures that when you formulate a query, it's not only valid but also effectively directs the system to find precisely what you're after. It's the rulebook for our data detective work, so don't be mucking about with it unless you've got a very good reason and a solid understanding of its implications!