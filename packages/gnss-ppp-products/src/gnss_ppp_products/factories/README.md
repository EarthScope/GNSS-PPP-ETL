# `factories/`: The Workhorses of GNSS Product Management

Alright, this `factories/` directory is where a lot of the heavy lifting happens. Think of these as the specialist workshops, each one dedicated to building, managing, or orchestrating a particular aspect of our GNSS product handling system. These classes are designed to encapsulate complex logic, create specific types of objects, and generally keep the machinery of data fetching and processing running smoothly.

Here's a rundown of the key players you'll find in this bustling workshop:

*   **`query_factory.py`**: The Master Planner (`QueryFactory`)
    *   This is where we take high-level product requests (like "give me orbits for this date") and turn them into concrete, actionable `ResourceQuery` objects. It narrows down the search space based on our configurations, generating precise instructions for finding products both locally and remotely. It's the brains behind translating intent into search parameters.

*   **`resource_fetcher.py`**: The Data Retriever (`ResourceFetcher`)
    *   Once the `QueryFactory` has figured out *what* to look for, the `ResourceFetcher` rolls up its sleeves and actually goes and finds it. It takes `ResourceQuery` objects, lists remote (FTP/HTTP) or local directories, matches filenames using clever regex patterns, and then, crucially, handles the downloading and initial decompression of those files. It's the intrepid explorer bringing data home.

*   **`local_factory.py`**: The Local Librarian (`LocalResourceFactory`)
    *   This factory is the meticulous housekeeper for our local data archive. It knows exactly where each type of downloaded GNSS product should go on our disk, based on our `local_config.yaml`. It manages the registration of local storage locations, prevents path overlaps, and helps construct the final destination paths for incoming files. It also helps us find files we've already stored.

*   **`remote_factory.py`**: The Remote Expedition Leader (`RemoteResourceFactory`)
    *   Just as the `LocalResourceFactory` handles local storage, the `RemoteResourceFactory` is in charge of understanding and interacting with various remote GNSS data providers (like CDDIS, IGS, WUM, etc.). It registers their server details and product offerings, allowing our system to "source" products from these distant locations.

*   **`connection_pool.py`**: The Network Manager (`ConnectionPoolFactory`)
    *   Any time we talk to a remote server (be it FTP or HTTP), this factory is on the job. It manages and reuses network connections efficiently, preventing us from opening and closing connections unnecessarily. This makes our data fetching much faster and more reliable, especially when dealing with many requests.

*   **`dependency_resolver.py`**: The Supply Chain Manager (`DependencyResolver`)
    *   This factory is responsible for making sure that for any given processing task, all required input products (dependencies) are available. It uses the `dependencies/` configurations to figure out what's needed and can even try multiple sources or preferences to fulfill those needs. It's crucial for getting all the right ingredients before starting a complex computational recipe.

*   **`resource_factory.py`**: The General Foreman (`ResourceFactory`)
    *   This one acts as a more general orchestrator, potentially coordinating the activities of other resource-related factories or providing a unified interface for various resource management tasks. It's often the first point of contact for higher-level components needing to interact with different types of resources.

*   **`models.py`**: The Data Architects
    *   While not a "factory" in the same sense, this file typically contains the Pydantic models and data structures that are created, manipulated, and passed around by all these factories. These models (like `ResourceQuery`, `Product`, `Server`, etc.) define the consistent shape and validation for our data throughout the system.

In essence, the `factories/` directory is where the operational logic for our GNSS product pipeline is implemented. These classes work together in a well-oiled machine to find, fetch, store, and manage the vast quantities of data essential for Precise Point Positioning. Treat them with care, as they are the very engine of our system!