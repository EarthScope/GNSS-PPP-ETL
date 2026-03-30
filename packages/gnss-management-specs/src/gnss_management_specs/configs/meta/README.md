# `meta/`: Metadata Field Specifications

Right, this `meta/` directory holds the `meta_spec.yaml` file, which is essentially our comprehensive dictionary for all the metadata fields we use across the various GNSS product formats. Think of it as the master glossary, ensuring everyone's speaking the same language when it comes to file names and data attributes.

This `meta_spec.yaml` file details each and every metadata field, such as `SSSS` (station code), `YYYY` (4-digit year), `AAA` (analysis-center code), `FMT` (format code), `GPSWEEK` (GPS week number), and so on. For each field, it provides:

*   **`pattern`**: This is a crucial regular expression that defines the exact format and expected structure of the metadata value. It's what allows our system to correctly parse information *out* of existing filenames and construct valid patterns when *generating* new file paths. Without these patterns, our file-matching would be an absolute guessing game.
*   **`description`**: A plain English explanation of what the field actually represents. Handy for us humans trying to make sense of all the abbreviations!
*   **`derivation`**: This tells us how the value for a given field is typically obtained. If it says `enum`, it means the value is chosen from a predefined list of options. If it says `computed`, it means the value is dynamically derived from other information, often a `datetime` object (e.g., calculating `YYYY` and `DDD` from a given date).

### Registering Metadata Compute Values: The Clever Bits

Now, a particularly neat trick this system pulls off involves what we call "metadata compute values." You'll notice some fields with `derivation: computed` – these aren't just picked from a list; they're *calculated* on the fly based on a given date. Think `YYYY`, `DDD`, `GPSWEEK`, or even `REFFRAME`.

The magic here is that you can register specific Python functions (or "compute values") with the `ParameterCatalog` that know how to generate these dynamic bits of metadata from a simple `datetime` object. So, when our `QueryFactory` needs to build a filename pattern for a particular date, it doesn't have to hardcode the logic for figuring out the GPS week or day of year. Instead, it just asks the `ParameterCatalog` to compute these values, and *presto*, the correct, date-specific pattern is generated.

This keeps our configuration clean and our date-handling consistent across the board. It's a proper bit of engineering, ensuring that time-dependent file attributes are always spot-on without a lot of fuss and bother.

In the grand scheme of things, `meta_spec.yaml` is the bedrock upon which our dynamic query system is built. It provides the canonical definitions for all the placeholders you see in our `format_spec.yaml` templates and underpins the `ParameterCatalog`'s ability to resolve and validate these crucial metadata elements. Without this file, our system for identifying and querying GNSS products would be a right muddle. So, treat this file with the reverence it deserves – it's the Rosetta Stone of our GNSS data!