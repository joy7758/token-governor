"""Context compression policy for governor mode."""

from __future__ import annotations

from typing import Any


def compress_history(history: list[Any]) -> list[Any]:
    """
    v0.1 does not compress history.

    Future versions can summarize old steps to reduce context cost.
    """
    return history
