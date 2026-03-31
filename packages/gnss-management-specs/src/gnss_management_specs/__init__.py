"""GNSS Management Specs — bundled YAML configuration data.

Provides path constants for the bundled YAML specifications that
describe GNSS product catalogs, analysis center endpoints, file
formats, and local storage layouts.

Import from :mod:`gnss_management_specs.configs` for individual paths,
or use the top-level convenience re-exports below.
"""

from gnss_management_specs.configs import (
    CENTERS_RESOURCE_DIR as CENTERS_RESOURCE_DIR,
    DEPENDENCY_SPEC_DIR as DEPENDENCY_SPEC_DIR,
    FORMAT_SPEC_YAML as FORMAT_SPEC_YAML,
    LOCAL_SPEC_DIR as LOCAL_SPEC_DIR,
    META_SPEC_YAML as META_SPEC_YAML,
    PRODUCT_SPEC_YAML as PRODUCT_SPEC_YAML,
    QUERY_SPEC_YAML as QUERY_SPEC_YAML,
)
