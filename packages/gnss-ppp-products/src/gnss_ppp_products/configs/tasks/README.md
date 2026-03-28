# `tasks/`: Processing Task Configurations

Alright, here in the `tasks/` directory, you'll find the specific blueprints for how particular processing jobs are configured, especially concerning their product dependencies and sourcing strategies. These YAML files are more than just a list of requirements; they're a carefully ordered instruction set for our dependency resolver.

Each YAML file in this folder (e.g., `pride_ppp_kin.yml`) defines a distinct processing task and typically includes:

*   **`name` and `description`**: Clearly identifies the specific processing task this configuration is designed for (e.g., "PRIDE-PPP Kinematic Processing").
*   **`preferences`**: This is the heart of the matter. It's an ordered cascade of preferred sources for our required products. For every single product a task needs, our system will consult this list, working its way down from the top. Each preference entry can specify:
    *   **`center`**: Which analysis center (e.g., `WUM`, `IGS`, `COD`) we'd ideally like to get the product from.
    *   **`solution`**: The preferred quality or latency tier (e.g., `FIN` for final, `RAP` for rapid).
    *   **`campaign`**: The specific IGS campaign or project code (e.g., `MGX`, `OPS`).
    The resolver will try the first preference, then the second, and so on, until it successfully locates the product. This robust mechanism ensures that even if our top-choice source is unavailable, we have sensible fallbacks to keep the processing moving along.
*   **`dependencies`**: This section lists all the core product `spec`s (like `ORBIT`, `CLOCK`, `BIA`, `RNX3_BRDC`) that the task fundamentally requires. It also indicates whether each dependency is strictly `required` or merely `false` (meaning the task can proceed without it, perhaps by using a default or internal model).

In essence, these `tasks/` configurations provide a highly flexible and powerful way to manage the complex web of GNSS product dependencies for any given processing job. They ensure that the right data, from the right source, with the right quality, is always brought to bear on our computational challenges. Treat them as sacred texts, as they orchestrate the very success of our processing endeavors!