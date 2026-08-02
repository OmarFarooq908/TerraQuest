"""Shared pytest fixtures and markers."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "unit: fast offline unit tests")
    config.addinivalue_line("markers", "integration: multi-package offline integration")
    config.addinivalue_line("markers", "requires_osmium: needs osmium-tool on PATH")
    config.addinivalue_line("markers", "requires_network: hits remote OSM/DEM endpoints")
