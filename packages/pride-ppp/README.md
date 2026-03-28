# `pride-ppp`: The PRIDE-PPPAR Kinematic Processing Engine

Alright, you've stumbled into the `pride-ppp` package, and let me tell you, this is where the serious work of Kinematic Precise Point Positioning with Ambiguity Resolution (PPP-AR) gets done, using the PRIDE-PPPAR engine. While the `gnss-ppp-products` package handles the general grunt work of fetching and managing GNSS data, this `pride-ppp` package is the specialized bit of kit that actually takes that data and churns out high-precision positioning solutions.

Think of it as the engine room for our kinematic PPP operations. It integrates with the robust data provision from `gnss-ppp-products` to perform the complex calculations necessary for those accurate position fixes.

### What's Under the Bonnet Here? (`src/pride_ppp/`)

Diving into the `src/pride_ppp/` directory, you'll find the core components that make this engine tick:

*   **`configs/`**: This is where we keep the specific configurations that guide the PRIDE-PPPAR engine. You've seen `centers/pride_table_config.yaml`, which points to static tables crucial for PRIDE's operations. Expect to find other specialized configuration bits here that tailor the engine's behavior.
*   **`defaults/`**: Just what it says on the tin – default settings and parameters for the PRIDE-PPPAR processing. If something isn't explicitly configured, this is where it gets its marching orders.
*   **`cli.py`**: This provides the command-line interface for interacting with the PRIDE-PPPAR engine. It's how you'd typically tell the system to kick off a processing run or query its status.
*   **`config.py`**: Handles the loading, parsing, and management of all the configuration files relevant to the `pride-ppp` package. It ensures the engine knows its settings before it starts working.
*   **`output.py`**: Once the PRIDE-PPPAR engine has done its magic, this module takes care of formatting and presenting the results in a sensible and readable manner. Because what's the use of brilliant results if you can't understand 'em, eh?
*   **`products.py`**: This module likely contains specialized logic for handling and preparing GNSS products specifically for the PRIDE-PPPAR engine. It acts as the interface between the raw products fetched by `gnss-ppp-products` and the requirements of the PPP-AR algorithms.
*   **`rinex.py`**: Given the importance of RINEX data in GNSS, this module probably focuses on any specific parsing, validation, or manipulation of RINEX files that are unique to the PRIDE-PPPAR workflow.
*   **`runner.py`**: This is the orchestrator of the entire PRIDE-PPPAR processing chain. It takes the configuration, gathers the products, calls the necessary algorithms, and manages the flow from raw data to final positioning solution. It's the gaffer of the whole operation.
*   **`config_template`**: A handy template or example structure for creating new configuration files specific to `pride-ppp`.

In short, the `pride-ppp` package is the specialized tool that brings all the collected GNSS data to life, performing the complex kinematic PPP-AR computations. It relies heavily on the data management provided by `gnss-ppp-products` and adds its own layer of configuration, processing logic, and output handling to deliver those precise positioning results. Treat it with the respect it deserves; it's a finely tuned engine!