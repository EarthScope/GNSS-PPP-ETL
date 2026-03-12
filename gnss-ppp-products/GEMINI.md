This file provides context for me to better assist you with your project.

### About This Project

This project's primary goal is to ETL (Extract, Transform, Load) GNSS (Global Navigation Satellite System) products for tasks like PPP (Precise Point Positioning) using PRIDE. It dynamically generates configuration files, stores products in a local sink, and provides an exhaustive resource of queries for GNSS analysis centers and products.

### Key Technologies

*   **Python**: The core language for the project.
*   **Dagster**: Used for orchestrating the ETL pipelines.
*   **Pydantic**: For data validation and settings management.
*   **Pytest**: For running tests.
*   **uv**: For managing Python dependencies.
*   **npm**: For managing Node.js dependencies.
*   **madr**: For creating and managing Architecture Decision Records.

### Project Structure

*   `src/gnss_ppp_products`: The main source code for the project.
    *   `data_query`: Handles the logic for querying remote data sources.
    *   `resources`: Contains Pydantic models, configuration files for different data providers (e.g., IGS, GFZ), and product definitions. This is a central part of the application.
    *   `utils`: Contains utility functions for tasks like FTP downloads and configuration management.
*   `test/`: Contains tests for the project.
*   `config/`: Contains configuration for folder structures and data sources.
*   `docs/`: Contains project documentation, including Architecture Decision Records.

### Development Setup

**Python Environment**

This project uses `uv` for Python package management. To set up the environment, run:

```bash
uv sync
```

**Node.js Environment**

This project uses `npm` for Node.js package management. To set up the environment, run:

```bash
npm install
```

### Running Tests

This project uses `pytest` for testing. To run the tests, use the following command:

```bash
pytest
```

You can skip tests that require live FTP connections by running:

```bash
pytest -m "not integration"
```

### Future Work: Product Query System

A key feature under development is a product query system that will function like an API endpoint. This system is designed to search for GNSS product files across remote FTP and HTTP servers, providing a flexible and powerful way to locate necessary data.

**Query Parameters**

The query system will use the following parameters:

*   **Mandatory**: `format`, `content`, `time`
*   **Optional**: `center`, `campaign`, `quality`, `interval`, `duration`

**Core Functionality**

The system will dynamically build a list of candidate files from remote servers. If optional parameters are omitted from a query, the system will use regular expressions to match against the available files. This allows for broad or very specific searches depending on the user's needs.

**Intended Workflow**

1.  A `CenterConfig` object will build a list of product queries from the provided parameters.
2.  These queries will be executed to search for product files on the remote servers.
3.  The search will return a list of remote product addresses.
4.  These addresses can then be used to retrieve the actual product files.

### Configuration Lifecycle: From YAML to File Query

The project uses a structured lifecycle to transform static YAML definitions into a dynamic set of file queries that can be executed against remote servers. This process is central to the ETL functionality.

**1. Static Definition (YAML)**

*   The lifecycle begins in the YAML configuration files located in `src/gnss_ppp_products/resources/config/` (e.g., `igs.yaml`).
*   Each file represents a single analysis center and is modeled by the `GNSSCenterConfig` Pydantic model.
*   Within each file, specific data types are defined as entries in the `products` and `rinex` lists. Each of these entries (e.g., `id: igs_sp3`) corresponds to a `ProductConfig` or `RinexConfig` model.
*   This static definition specifies a `filename` and `directory` template and, crucially, lists all possible values for a product's attributes (e.g., `quality_set`, `sampling_set`, `station_set`).

**2. Loading and Hydration (Pydantic)**

*   At runtime, the `GNSSCenterConfig.from_yaml()` method reads a YAML file.
*   Pydantic parses and validates the file, "hydrating" the raw text into a structured hierarchy of Python objects: a `GNSSCenterConfig` object that contains lists of `ProductConfig` and `RinexConfig` objects.

**3. Dynamic Query Generation (`.build()` methods)**

*   To find files for a specific day, your code calls `GNSSCenterConfig.build_product_queries(date=...)` or `build_rinex_queries(date=...)`.
*   This top-level method iterates through each of the loaded `ProductConfig` or `RinexConfig` objects.
*   For each config object, it calls that object's own `.build(date)` method. This is the combinatorial engine: it loops through all the `_set` lists (e.g., `quality_set`, `station_set`) and creates a `ProductFileQuery` or `RinexFileQuery` object for **every possible combination** of those attributes.

**4. Filename and Path Resolution (`.build_query()` method)**

*   As each `ProductFileQuery` or `RinexFileQuery` is created, its `.build_query()` method is called.
*   This method takes the `filename` and `directory` templates from the original YAML and populates them with the specific values for that single combination (e.g., a specific quality, interval, and station).
*   The result is a concrete filename pattern to search for, like `IGS0OPSFIN_20231230000_01D_05M_ORB.SP3.*`.

**5. Final Result**

*   The final output is a flat list of `ProductFileQuery` or `RinexFileQuery` objects. Each object in this list represents one potential, concrete file that might exist on a remote server, complete with the server information and the exact path and filename pattern to find it.