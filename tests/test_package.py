"""Tests that the mcp_ipi package imports."""

import mcp_ipi

MODULES = ["domains", "environment", "suites", "mcp", "agent", "attacks", "defenses", "runner", "analysis", "cli"]


def test_package_imports():
    assert mcp_ipi.__name__ == "mcp_ipi"
