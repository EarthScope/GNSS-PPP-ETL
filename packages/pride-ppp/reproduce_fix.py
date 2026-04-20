import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pride_ppp.factories.processor as proc


@dataclass
class MockResolvedDependency:
    spec: str
    local_path: Any


@dataclass
class MockDependencyResolution:
    fulfilled: list[MockResolvedDependency]


def test_fix():
    # Use ORBIT spec, as_path should handle it.
    # The fix we apply (using as_path on local_path) should prevent AttributeError.

    # We use a filename matching the expected pattern .SP3
    dummy_path = "/tmp/dummy/orbit_file.SP3"

    rd = MockResolvedDependency(spec="ORBIT", local_path=dummy_path)
    res = MockDependencyResolution(fulfilled=[rd])

    print(f"Testing with local_path as string: {dummy_path}")
    try:
        products, product_dir = proc._resolution_to_satellite_products(res)
        print("Success! No AttributeError raised.")
        print(f"Resulting product_dir: {product_dir}")
        print(f"Product dir type: {type(product_dir)}")
        assert isinstance(product_dir, Path)
        assert product_dir == Path("/tmp/dummy")
        assert products.satellite_orbit == "orbit_file.SP3"
    except AttributeError as e:
        print(f"Failed! Still raising AttributeError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    test_fix()
