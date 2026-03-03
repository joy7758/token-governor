"""Tool selection policy for governor mode."""

from __future__ import annotations

from typing import Any


def select_tools(query: str, all_tools: list[Any]) -> list[Any]:
    """
    v0.1 keeps behavior simple and returns all available tools.

    Future versions can apply semantic matching and top-k pruning.
    """
    _ = query
    return all_tools
