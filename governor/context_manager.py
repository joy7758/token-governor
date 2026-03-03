"""Context compression policy for governor mode."""

from __future__ import annotations

import json
from typing import Any

from governor.policy_runtime import approx_tokens, trim_to_tokens


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


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


def build_context_slots(
    *,
    policy: dict[str, Any],
    goal: str,
    constraints: dict[str, Any] | None = None,
    variables: dict[str, Any] | None = None,
    tool_results: list[dict[str, Any]] | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build v0.2 slot-structured context and compression stats."""

    cfg = policy.get("context_slots", {})
    ordered_slots = [str(slot) for slot in cfg.get("preserve_ordered_slots", [])]
    token_limits = cfg.get("max_tokens_per_slot", {})

    raw_slots: dict[str, Any] = {
        "policy": {
            "version": policy.get("version"),
            "gate": policy.get("gate", {}),
            "tool_selection": policy.get("tool_selection", {}),
            "fallback": policy.get("fallback", {}),
        },
        "goal": goal,
        "constraints": constraints or {},
        "variables": variables or {},
        "tool_results": tool_results or [],
        "plan": plan or {},
    }

    if not ordered_slots:
        ordered_slots = list(raw_slots.keys())

    slots: dict[str, str] = {}
    compression_ratios: dict[str, float] = {}

    for slot_name in ordered_slots:
        content = _to_text(raw_slots.get(slot_name, ""))
        original_tokens = approx_tokens(content)
        max_tokens = int(token_limits.get(slot_name, 1024) or 1024)
        compressed = trim_to_tokens(content, max_tokens)
        compressed_tokens = approx_tokens(compressed)

        slots[slot_name] = compressed
        compression_ratios[slot_name] = (
            round(compressed_tokens / original_tokens, 4)
            if original_tokens > 0
            else 1.0
        )

    return {
        "slots": slots,
        "compression_ratios": compression_ratios,
        "ordered_slots": ordered_slots,
    }
