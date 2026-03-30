# `dependencies/`: Product Dependency Specifications

This `dependencies/` directory is where we lay out the shopping lists for specific GNSS processing tasks or software engines. Rather than asking for individual products one by one, we define a *dependency specification* here that bundles all the necessary GNSS products and static tables required for a particular job.

Each YAML file in this folder outlines:

*   **`name` and `description`**: What this dependency specification is for.
*   **`package` and `task`**: Which broader package or task this specification belongs to.
*   **`preferences`**: This is a rather clever bit. It defines a cascade of choices our resolver will make when faced with multiple options for a required product. For instance, it might tell the system to prefer products from Wuhan University (`WUM`) over others, or to always go for `FIN` (final) solutions if available, before settling for `RAP` (rapid) or `ULT` (ultra-rapid) ones. This ensures we get the *best available* data according to predefined rules.
*   **`dependencies`**: The actual list of products and tables that are absolutely `required` for the processing engine to run. Each entry specifies a product `spec` (like `ORBIT`, `CLOCK`, `BIA`) and a brief `description`.

In essence, these specifications are a handy way to ensure that any complex GNSS processing chain gets all its ducks in a row – all the right products, from the right sources, in the right order of preference. It saves us a lot of faffing about when setting up new tasks, making sure we're always working with a complete and appropriately prioritized dataset. Don't go changing these without a proper chinwag first, or you'll break a few processing pipelines, I reckon!