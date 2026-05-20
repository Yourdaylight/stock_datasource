"""Shared pytest configuration.

Tests in this repository should exercise real project modules and, where data is
needed, the real configured database. Do not replace database-backed behavior
with synthetic mock data in this file.
"""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the repository root for tests that need file paths."""
    return Path(__file__).resolve().parents[1]
