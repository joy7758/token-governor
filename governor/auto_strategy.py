"""Auto strategy selector for governor runtime optimization."""

from __future__ import annotations

import enum
from typing import Any

from governor.strategy import resolve_drive_mode, resolve_strategy


class AutoFlag(enum.Enum):
    HISTORY_LONG = "history_long"
    HIGH_TOOL_USAGE = "high_tool_usage"
    EXTERNAL_KNOWLEDGE = "external_knowledge"
    HIGH_SEMANTIC_SIMILARITY = "high_semantic_similarity"


def extract_task_features(task_context: dict[str, Any]) -> tuple[list[AutoFlag], dict[str, Any]]:
    """
    Extract lightweight task features used by auto strategy recommendation.
    """
    history_len = int(task_context.get("history_tokens", 0) or 0)
    tool_count = int(task_context.get("tool_calls", 0) or 0)
    external_knowledge = bool(
        task_context.get("external_query", task_context.get("external_data", False))
    )
    semantic_similarity = float(task_context.get("semantic_similarity_score", 0.0) or 0.0)

    flags: list[AutoFlag] = []
    if history_len > 1500:
        flags.append(AutoFlag.HISTORY_LONG)
    if tool_count > 1:
        flags.append(AutoFlag.HIGH_TOOL_USAGE)
    if external_knowledge:
        flags.append(AutoFlag.EXTERNAL_KNOWLEDGE)
    if semantic_similarity >= 0.78:
        flags.append(AutoFlag.HIGH_SEMANTIC_SIMILARITY)

    features = {
        "history_tokens": history_len,
        "tool_calls": tool_count,
        "external_query": external_knowledge,
        "semantic_similarity_score": round(semantic_similarity, 4),
    }
    return flags, features


def recommend_strategy(flags: list[AutoFlag]) -> tuple[dict[str, Any], list[str]]:
    """
    Recommend a strategy profile and feature toggles based on extracted flags.
    """
    opt: dict[str, Any] = {"base": "light"}
    reasons: list[str] = []

    if AutoFlag.HISTORY_LONG in flags:
        opt["base"] = "balanced"
        reasons.append("History context length is high -> enable context compression")

    if AutoFlag.HIGH_TOOL_USAGE in flags:
        opt["enable_smart_tool"] = True
        reasons.append("Tool usage count is high -> enable smart tool selection")

    if AutoFlag.EXTERNAL_KNOWLEDGE in flags:
        opt["base"] = "knowledge"
        opt["enable_rag"] = True
        opt["enable_context_pruning"] = True
        reasons.append("External knowledge inferred -> enable RAG & context pruning")

    if AutoFlag.HIGH_SEMANTIC_SIMILARITY in flags:
        opt["enable_semantic_cache"] = True
        opt["enable_agentic_plan_cache"] = True
        reasons.append("High semantic repeat score -> enable semantic cache & plan cache")

    if (
        AutoFlag.HISTORY_LONG in flags
        and AutoFlag.EXTERNAL_KNOWLEDGE in flags
    ):
        # Auto mode intentionally avoids upgrading directly to rocket/enterprise.
        # Keep a high-capability but non-rocket profile by default.
        opt["base"] = "knowledge"
        opt["enable_model_routing"] = False
        reasons.append("History + external demand high -> keep knowledge profile (non-rocket)")

    if (
        AutoFlag.HIGH_TOOL_USAGE in flags
        and AutoFlag.HISTORY_LONG in flags
    ):
        opt["enable_context_compression"] = True
        reasons.append("History and tool usage are both high -> force context compression")

    return opt, reasons


def apply_auto_strategy(
    task_context: dict[str, Any],
    overrides: dict[str, Any] | None = None,
    drive_mode: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """
    Generate effective strategy config and human-readable recommendation reasons.
    """
    flags, features = extract_task_features(task_context)
    recommendation, reasons = recommend_strategy(flags)

    base = str(recommendation.get("base", "balanced"))
    effective = resolve_strategy(base, overrides=overrides)

    # Apply auto-generated toggles on top of the base profile.
    for key, value in recommendation.items():
        if key == "base":
            continue
        effective[key] = value

    if drive_mode == "auto":
        profile_hint = str(task_context.get("profile_drive_mode_hint", "") or "").lower()
        if profile_hint in {"eco", "comfort", "sport"}:
            hinted_config = resolve_drive_mode(profile_hint, overrides=None)
            for key, value in hinted_config.items():
                if key.startswith("drive_mode"):
                    continue
                effective[key] = value
            reasons.insert(
                0,
                f"Model profile hint applied inside auto mode: '{profile_hint}'",
            )

        effective["drive_mode"] = "auto"
        effective["drive_mode_goal"] = "adaptive_balanced"
        effective["drive_mode_description"] = (
            "自动智能模式：动态推荐策略组合，默认不自动启用 rocket"
        )
        reasons.insert(
            0,
            "Drive mode 'auto' keeps dynamic recommendation and avoids rocket by default",
        )
    elif drive_mode:
        drive_mode_config = resolve_drive_mode(drive_mode, overrides=None)
        for key, value in drive_mode_config.items():
            effective[key] = value
        reasons.insert(0, f"Drive mode '{drive_mode}' applied as intent override")

    # Finally apply user overrides as highest priority.
    if overrides:
        for key, value in overrides.items():
            if value is not None:
                effective[key] = value

    effective["auto_recommended_from"] = "auto"
    effective["auto_flags"] = [flag.value for flag in flags]
    effective["auto_task_features"] = features
    effective["auto_strategy_reasons"] = reasons
    return effective, reasons
