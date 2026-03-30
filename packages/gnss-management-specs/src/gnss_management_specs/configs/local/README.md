# `local/`: Local Storage Configuration for GNSS Products

Alright, you've gone through all the trouble of querying and fetching those splendid GNSS products. Now what? This `local/` directory, specifically `local_config.yaml`, dictates how those precious files are neatly organised and stored on your local disk. Think of it as the meticulous librarian for our incoming data.

This configuration file outlines:

*   **Directory Layout**: It establishes a logical, predictable folder structure for all downloaded products. You'll typically find time-dependent products tucked away under `{YYYY}/{DDD}/` (Year/Day-of-Year), while static reference files (those that don't change daily) reside in a flat `table/` directory. This keeps things tidy and easy to find later.
*   **Temporal Categories**: Products are categorised by their temporal behaviour – `daily`, `hourly`, or `static`. This influences how the date information (year, day-of-year) is used to determine their storage path, ensuring consistency.
*   **Product Collections**: The heart of this file is the `collections` section. Here, various logical groups of products are defined:
    *   `products`: Home for the essential PPP inputs like precise orbits, clocks, biases, and attitude data.
    *   `rinex`: Stores all sorts of RINEX files, including observation, navigation, and meteorological data.
    *   `common`: For shared bits and bobs, such as ionosphere maps and troposphere grids.
    *   `table`: The resting place for static reference data like leap second tables, satellite parameters, and antenna calibration files.
    *   `lockfiles`: A special spot for tracking the provenance and versions of all our downloaded dependencies, ensuring we know exactly what we've got.
    *   `leo`: Dedicated to Level-1B instrument data from Low Earth Orbiting (LEO) satellites.

Each `collection` clearly states its `directory` pattern, `temporal` type, and lists the specific product IDs (from `product_spec.yaml`) that belong within it.

In short, `local_config.yaml` is paramount for maintaining order and accessibility in our local GNSS data archive. It ensures that every retrieved product has a designated, logical spot, making subsequent processing and analysis a far less vexing affair. Treat it with respect, or your local data store will become an absolute shambles!