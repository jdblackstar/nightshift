"""Exceptions raised by Nightshift library and CLI code."""

from __future__ import annotations


class NightshiftError(RuntimeError):
    pass


class NightshiftConfigError(NightshiftError):
    pass
