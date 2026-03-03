"""Model profile utilities for model-aware adaptive optimization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_model_profiles(profile_path: str | None) -> dict[str, Any]:
    if not profile_path:
        return {}
    path = Path(profile_path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    models = payload.get("models", {})
    if isinstance(models, dict):
        return models
    return {}


def _pick_mode_from_strategy_performance(
    profile: dict[str, Any],
    objective: str,
) -> str | None:
    strategy_performance = profile.get("strategy_performance")
    if not isinstance(strategy_performance, dict) or not strategy_performance:
        return None

    def score_cost(stats: dict[str, Any]) -> tuple[float, float]:
        return (
            float(stats.get("avg_tokens", 0.0) or 0.0),
            float(stats.get("avg_latency_ms", 0.0) or 0.0),
        )

    def score_quality(stats: dict[str, Any]) -> tuple[float, float, float]:
        quality = stats.get("quality_score")
        quality_value = float(quality) if quality is not None else float(stats.get("success_rate", 0.0) or 0.0)
        return (
            quality_value,
            float(stats.get("success_rate", 0.0) or 0.0),
            -float(stats.get("avg_latency_ms", 0.0) or 0.0),
        )

    if objective == "cost":
        mode, _ = min(strategy_performance.items(), key=lambda item: score_cost(item[1]))
        return str(mode).lower()

    if objective == "quality":
        mode, _ = max(strategy_performance.items(), key=lambda item: score_quality(item[1]))
        return str(mode).lower()

    # balanced: prefer non-rocket if possible
    non_rocket = {
        name: stats for name, stats in strategy_performance.items() if str(name).lower() != "rocket"
    } or strategy_performance

    def score_balanced(stats: dict[str, Any]) -> float:
        quality = stats.get("quality_score")
        quality_value = float(quality) if quality is not None else float(stats.get("success_rate", 0.0) or 0.0)
        return (
            quality_value * 100.0
            - float(stats.get("avg_tokens", 0.0) or 0.0) / 1000.0
            - float(stats.get("avg_latency_ms", 0.0) or 0.0) / 2000.0
        )

    mode, _ = max(non_rocket.items(), key=lambda item: score_balanced(item[1]))
    return str(mode).lower()


def recommend_drive_mode_from_profile(
    model_profiles: dict[str, Any],
    model_name: str,
    *,
    objective: str = "balanced",
) -> tuple[str | None, str | None]:
    if not model_profiles:
        return None, None

    profile = model_profiles.get(model_name)
    if not isinstance(profile, dict):
        return None, None

    objective_map = {
        "cost": "best_cost_mode",
        "balanced": "best_balance_mode",
        "quality": "best_quality_mode",
    }
    key = objective_map.get(objective, "best_balance_mode")
    mode = profile.get(key)
    if not isinstance(mode, str) or not mode:
        mode = _pick_mode_from_strategy_performance(profile, objective)

    if not isinstance(mode, str) or not mode:
        return None, None

    reason = (
        f"Model profile suggests drive mode '{mode}' for objective '{objective}' "
        f"on model '{model_name}'"
    )
    return mode.lower(), reason
