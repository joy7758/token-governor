"""Tool selection policy for governor mode."""

from __future__ import annotations

from typing import Any


def _tool_text(tool: Any) -> str:
    name = str(getattr(tool, "name", "") or "")
    description = str(getattr(tool, "description", "") or "")
    return f"{name} {description}".strip().lower()


def _score(query: str, tool: Any) -> int:
    query_terms = [term for term in query.lower().split() if term]
    if not query_terms:
        return 0
    text = _tool_text(tool)
    return sum(1 for term in query_terms if term in text)


def select_tools(query: str, all_tools: list[Any], top_k: int | None = None) -> list[Any]:
    """
    Select top-k tools by lightweight keyword overlap.

    This implementation is intentionally simple so that strategy switches are
    deterministic and easy to debug.
    """
    if not all_tools:
        return []

    if top_k is None or top_k <= 0 or top_k >= len(all_tools):
        return list(all_tools)

    ranked = sorted(all_tools, key=lambda tool: _score(query, tool), reverse=True)
    return ranked[:top_k]
