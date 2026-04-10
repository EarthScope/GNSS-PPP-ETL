"""Shared test fixtures for the pride-ppp test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

# Path to the bundled fixture files used across all test modules.
DATA_DIR = Path(__file__).parent / "data"

# Fixture filenames (no extension — pdp3 writes extensionless kin/res files).
KIN_FILE = DATA_DIR / "kin_2021220_bako"
RES_FILE = DATA_DIR / "res_2021220_bako"


@pytest.fixture(scope="session")
def kin_file() -> Path:
    """Path to a sample pdp3 .kin output file."""
    assert KIN_FILE.exists(), f"Fixture missing: {KIN_FILE}"
    return KIN_FILE


@pytest.fixture(scope="session")
def res_file() -> Path:
    """Path to a sample pdp3 .res residuals file."""
    assert RES_FILE.exists(), f"Fixture missing: {RES_FILE}"
    return RES_FILE
