# `centers/`: GNSS Analysis Center Configurations

Alright, listen up. This `centers/` directory is where we keep the vital statistics for all the GNSS (Global Navigation Satellite System) Analysis Centers we deal with. Think of these YAML files as our little dossiers on each center, detailing exactly who they are, where to find their precious data, and what sorts of products they're flogging.

Each YAML file here, like `igs_config.yaml` or `gfz_config.yaml`, defines a single analysis center. Within each of these files, you'll find:

*   **`id` and `name`**: The short and long names for the center, useful for referencing.
*   **`description` and `website`**: A bit of background and where to find more information, should you be so inclined.
*   **`servers`**: This bit's crucial. It lists the FTP or HTTP servers where we can actually get our grubby mitts on their data. It includes hostnames, protocols, and any authentication nitty-gritty.
*   **`products`**: This is the real meat and potatoes. It details every single product type that center offers, complete with its unique `id`, a description, and crucially, the `parameters` and `directory` templates needed to construct a valid file path for querying. This is how we know what to ask for and where to look.

In short, these configs are the blueprints for how our system interacts with each specific GNSS data provider. Without 'em, we'd be lost at sea trying to find those precise orbits and clocks. Don't go messing about with these unless you know exactly what you're doing, or you'll throw the whole data pipeline into a right state!