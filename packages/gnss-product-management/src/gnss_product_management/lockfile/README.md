# `lockfile/`: Ensuring Reproducibility and Data Provenance

Alright, you listen up! This `lockfile/` directory is home to the critical machinery that ensures our GNSS processing is not just repeatable, but *verifiably* so. In the world of scientific computing, knowing exactly which version of which data went into a result is paramount, and this module provides precisely that: a meticulous record-keeping system for our downloaded products.

Think of these lockfiles as a ship's log for every piece of data we acquire. They tell us not just where a product ended up, but where it came from, *when* we got it, and a cryptographic fingerprint to prove it hasn't been tampered with.

This module is primarily split into two main files:

### `models.py`: The Blueprint for Provenance

This file defines the strict data structures (using Pydantic models, of course) that dictate what information is captured in a lockfile:

*   **`LockProduct`**: This model records every detail about a single downloaded product. It includes:
    *   **`url`**: The precise web address from which the product was fetched.
    *   **`hash`**: A cryptographic hash (like SHA-256) of the file content. This is the ultimate proof of integrity; if the file changes, the hash changes!
    *   **`size`**: The file size, another quick check for consistency.
    *   **`sink`**: The local path where the file is stored.
    *   `name`, `description`, `timestamp`, and `alternatives` (other possible download sources).
*   **`DependencyLockFile`**: This is the top-level manifest, a comprehensive list of *all* the `LockProduct` entries needed for a particular processing day and task. It aggregates all individual product records, along with metadata about the processing context (`station`, `date`, `package`, `task`).

### `operations.py`: The Keeper of the Log

This file contains all the functions required to manage the lifecycle of our lockfiles:

*   **`build_lock_product()`**: This function takes a freshly downloaded product file and automatically generates a `LockProduct` record for it, computing the all-important hash and size.
*   **`validate_lock_product()`**: A crucial verification step! This function checks if a local file corresponding to a `LockProduct` entry still exists and, if a hash was recorded, re-computes the file's hash to ensure it matches the stored one. It's smart enough to even handle compressed (`.gz`) files, checking against the decompressed version if the original `.gz` is gone.
*   **Reading and Writing**: Functions for seamlessly saving these `LockProduct` entries as "sidecar" JSON files (e.g., `product.sp3_lock.json`) next to the actual data, and for reading/writing the larger `DependencyLockFile` manifests that bundle all products for a specific processing run.
*   **`get_dependency_lockfile_name()`**: A utility to derive a standardized filename for a `DependencyLockFile`, ensuring consistent naming and easy discovery.

In essence, the `lockfile/` module is our ultimate safeguard against data ambiguity. By providing a clear, verifiable record of every piece of data, it ensures that our GNSS processing is fully reproducible, auditable, and robust against any future uncertainties. It's the ultimate peace of mind for any diligent researcher!
