"""Context compression policy for governor mode."""

from __future__ import annotations

from typing import Any


def compress_history(history: list[Any], max_chars: int = 800) -> str:
    """
    Compress retry history into a short textual summary.

    For v0.x we keep this deterministic and local (no extra LLM call):
    include only the last few failures and trim to max_chars.
    """
    if not history:
        return ""

    parts: list[str] = []
    for item in history[-3:]:
        if isinstance(item, dict):
            error = str(item.get("error", "") or "").strip()
            answer = str(item.get("answer", "") or "").strip()
            tokens = int(item.get("total_tokens", 0) or 0)
            snippet = answer[:180] if answer else ""
            parts.append(
                f"tokens={tokens}; error={error[:160]}; answer={snippet}"
            )
        else:
            parts.append(str(item)[:220])

    summary = " | ".join(parts)
    if len(summary) > max_chars:
        summary = summary[-max_chars:]
    return summary
