"""Strategy profiles and override resolution for governor runtime options."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


STRATEGY_NAMES = ("auto", "light", "balanced", "knowledge", "enterprise")
MANUAL_STRATEGY_NAMES = ("light", "balanced", "knowledge", "enterprise")
DRIVE_MODE_NAMES = ("auto", "eco", "comfort", "sport", "rocket")


@dataclass(frozen=True)
class StrategyProfile:
    name: str
    description: str
    expected_token: str
    expected_success: str
    expected_latency: str
    enable_context_compression: bool
    enable_smart_tool: bool
    enable_rag: bool
    enable_context_pruning: bool
    enable_semantic_cache: bool
    enable_agentic_plan_cache: bool
    enable_model_routing: bool
    tool_top_k: int
    history_summary_chars: int

    def to_runtime_flags(self) -> dict[str, Any]:
        return {
            "opt_strategy": self.name,
            "enable_context_compression": self.enable_context_compression,
            "enable_smart_tool": self.enable_smart_tool,
            "enable_rag": self.enable_rag,
            "enable_context_pruning": self.enable_context_pruning,
            "enable_semantic_cache": self.enable_semantic_cache,
            "enable_agentic_plan_cache": self.enable_agentic_plan_cache,
            "enable_model_routing": self.enable_model_routing,
            "tool_top_k": self.tool_top_k,
            "history_summary_chars": self.history_summary_chars,
            "expected_token": self.expected_token,
            "expected_success": self.expected_success,
            "expected_latency": self.expected_latency,
        }


PROFILES: dict[str, StrategyProfile] = {
    "light": StrategyProfile(
        name="light",
        description="基础守卫 + 智能工具选择",
        expected_token="small_reduction",
        expected_success="stable",
        expected_latency="stable",
        enable_context_compression=False,
        enable_smart_tool=True,
        enable_rag=False,
        enable_context_pruning=False,
        enable_semantic_cache=False,
        enable_agentic_plan_cache=False,
        enable_model_routing=False,
        tool_top_k=3,
        history_summary_chars=400,
    ),
    "balanced": StrategyProfile(
        name="balanced",
        description="守卫 + 上下文压缩 + 智能工具选择",
        expected_token="medium_reduction",
        expected_success="stable",
        expected_latency="slight_change",
        enable_context_compression=True,
        enable_smart_tool=True,
        enable_rag=False,
        enable_context_pruning=False,
        enable_semantic_cache=False,
        enable_agentic_plan_cache=False,
        enable_model_routing=False,
        tool_top_k=3,
        history_summary_chars=800,
    ),
    "knowledge": StrategyProfile(
        name="knowledge",
        description="balanced + RAG + context pruning",
        expected_token="high_reduction",
        expected_success="stable",
        expected_latency="slight_increase",
        enable_context_compression=True,
        enable_smart_tool=True,
        enable_rag=True,
        enable_context_pruning=True,
        enable_semantic_cache=False,
        enable_agentic_plan_cache=False,
        enable_model_routing=False,
        tool_top_k=3,
        history_summary_chars=1000,
    ),
    "enterprise": StrategyProfile(
        name="enterprise",
        description="knowledge + semantic cache + model routing",
        expected_token="max_reduction",
        expected_success="high_stability",
        expected_latency="controlled_increase",
        enable_context_compression=True,
        enable_smart_tool=True,
        enable_rag=True,
        enable_context_pruning=True,
        enable_semantic_cache=True,
        enable_agentic_plan_cache=True,
        enable_model_routing=True,
        tool_top_k=3,
        history_summary_chars=1200,
    ),
}


DRIVE_MODE_MAP: dict[str, dict[str, Any]] = {
    "eco": {
        "base_strategy": "light",
        "description": "经济模式：成本优先，尽量降低 token 消耗",
        "goal": "cost_first",
        "overrides": {
            "enable_context_compression": True,
            "enable_smart_tool": True,
            "enable_rag": False,
            "enable_context_pruning": False,
            "enable_semantic_cache": False,
            "enable_agentic_plan_cache": False,
            "enable_model_routing": False,
            "tool_top_k": 2,
            "history_summary_chars": 700,
        },
    },
    "comfort": {
        "base_strategy": "balanced",
        "description": "舒适模式：平衡成本、稳定性与效果",
        "goal": "balanced",
        "overrides": {
            "enable_context_compression": True,
            "enable_smart_tool": True,
            "enable_rag": False,
            "enable_context_pruning": False,
            "enable_semantic_cache": True,
            "enable_agentic_plan_cache": False,
            "enable_model_routing": False,
            "tool_top_k": 3,
            "history_summary_chars": 1000,
        },
    },
    "sport": {
        "base_strategy": "knowledge",
        "description": "性能模式：质量与召回优先，接受更高 token 成本",
        "goal": "quality_first",
        "overrides": {
            "enable_context_compression": True,
            "enable_smart_tool": True,
            "enable_rag": True,
            "enable_context_pruning": True,
            "enable_semantic_cache": True,
            "enable_agentic_plan_cache": False,
            "enable_model_routing": False,
            "tool_top_k": 4,
            "history_summary_chars": 1400,
        },
    },
    "rocket": {
        "base_strategy": "enterprise",
        "description": "火箭模式：能力与精度优先，不计成本",
        "goal": "max_quality",
        "overrides": {
            "enable_context_compression": True,
            "enable_smart_tool": True,
            "enable_rag": True,
            "enable_context_pruning": True,
            "enable_semantic_cache": True,
            "enable_agentic_plan_cache": True,
            "enable_model_routing": True,
            "tool_top_k": 5,
            "history_summary_chars": 1800,
        },
    },
}


AUTO_DRIVE_MODE_META: dict[str, Any] = {
    "description": (
        "自动智能模式：按任务特征动态推荐策略组合，默认不自动启用 rocket 高成本配置"
    ),
    "goal": "adaptive_balanced",
}


def resolve_strategy(
    opt_strategy: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if opt_strategy == "auto":
        # `auto` should normally be handled by `governor.auto_strategy`.
        # Fallback to balanced so CLI remains backward compatible.
        opt_strategy = "balanced"

    if opt_strategy not in PROFILES:
        raise ValueError(
            f"Unknown strategy '{opt_strategy}'. Choose one of: {', '.join(STRATEGY_NAMES)}"
        )

    config = dict(PROFILES[opt_strategy].to_runtime_flags())
    if not overrides:
        return config

    for key, value in overrides.items():
        if value is not None:
            config[key] = value
    return config


def resolve_drive_mode(
    drive_mode: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if drive_mode == "auto":
        # `auto` is dynamic and should be resolved in `governor.auto_strategy`.
        # Keep a conservative fallback for callers that resolve directly.
        config = resolve_strategy("balanced", overrides=overrides)
        config["drive_mode"] = "auto"
        config["drive_mode_base_strategy"] = "balanced"
        config["drive_mode_goal"] = AUTO_DRIVE_MODE_META["goal"]
        config["drive_mode_description"] = AUTO_DRIVE_MODE_META["description"]
        config["drive_mode_dynamic"] = True
        return config

    if drive_mode not in DRIVE_MODE_MAP:
        raise ValueError(
            f"Unknown drive mode '{drive_mode}'. Choose one of: {', '.join(DRIVE_MODE_NAMES)}"
        )

    mode_cfg = DRIVE_MODE_MAP[drive_mode]
    base_strategy = str(mode_cfg["base_strategy"])
    config = resolve_strategy(base_strategy, overrides=None)
    for key, value in mode_cfg["overrides"].items():
        config[key] = value

    config["drive_mode"] = drive_mode
    config["drive_mode_base_strategy"] = base_strategy
    config["drive_mode_goal"] = mode_cfg["goal"]
    config["drive_mode_description"] = mode_cfg["description"]

    if not overrides:
        return config
    for key, value in overrides.items():
        if value is not None:
            config[key] = value
    return config


def _feature_extract(tasks: list[str]) -> dict[str, float]:
    if not tasks:
        return {
            "task_count": 0.0,
            "avg_chars": 0.0,
            "long_task_ratio": 0.0,
            "retrieval_ratio": 0.0,
            "analysis_ratio": 0.0,
        }

    lower_tasks = [task.lower() for task in tasks]
    avg_chars = sum(len(task) for task in tasks) / len(tasks)
    long_task_ratio = sum(1 for task in tasks if len(task) > 110) / len(tasks)

    retrieval_terms = (
        "find",
        "latest",
        "source",
        "public",
        "search",
        "article",
        "benchmark",
        "recent",
    )
    analysis_terms = (
        "compare",
        "tradeoff",
        "evaluate",
        "explain",
        "summary",
        "summarize",
    )
    retrieval_ratio = (
        sum(
            1
            for task in lower_tasks
            if any(term in task for term in retrieval_terms)
        )
        / len(tasks)
    )
    analysis_ratio = (
        sum(
            1
            for task in lower_tasks
            if any(term in task for term in analysis_terms)
        )
        / len(tasks)
    )

    return {
        "task_count": float(len(tasks)),
        "avg_chars": float(avg_chars),
        "long_task_ratio": float(long_task_ratio),
        "retrieval_ratio": float(retrieval_ratio),
        "analysis_ratio": float(analysis_ratio),
    }


def recommend_strategy(tasks: list[str], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    features = _feature_extract(tasks)
    score = 0
    reasons: list[str] = []

    if features["task_count"] >= 15:
        score += 1
        reasons.append("任务数量较多，优先使用更系统化的成本治理策略")
    if features["avg_chars"] >= 85:
        score += 1
        reasons.append("平均任务描述较长，建议启用上下文压缩")
    if features["long_task_ratio"] >= 0.35:
        score += 1
        reasons.append("长任务占比高，建议强化上下文治理")
    if features["retrieval_ratio"] >= 0.50:
        score += 2
        reasons.append("检索型任务占比高，建议启用 RAG 相关策略")
    if features["analysis_ratio"] >= 0.45:
        score += 1
        reasons.append("分析总结类任务较多，建议启用压缩与工具筛选")

    if score <= 1:
        selected = "light"
    elif score <= 3:
        selected = "balanced"
    elif score <= 5:
        selected = "knowledge"
    else:
        selected = "enterprise"

    # Retrieval-heavy tasks benefit from knowledge profile defaults.
    if features["retrieval_ratio"] >= 0.50 and selected in {"light", "balanced"}:
        selected = "knowledge"
        reasons.append("检索需求明显，自动升级为 knowledge 策略")

    config = resolve_strategy(selected, overrides=overrides)
    config["auto_recommended_from"] = "auto"
    config["auto_recommendation"] = {
        "selected": selected,
        "score": score,
        "features": features,
        "reasons": reasons,
    }
    return config
