"""Pytest hooks for the Nightshift test suite."""

from __future__ import annotations

import sys

if sys.version_info < (3, 11):
    raise RuntimeError(
        "Nightshift requires Python 3.11 or newer (see pyproject.toml). "
        "Run tests with the project venv, for example: uv run pytest"
    )
