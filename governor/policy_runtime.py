"""Runtime helpers for policy-driven governor behavior (v0.2)."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[1] / "policy.yaml"


DEFAULT_POLICY: dict[str, Any] = {
    "version": 0.2,
    "gate": {
        "thresholds": {
            "no_agent_threshold": 0.60,
            "safe_agent_threshold": 0.75,
            "privileged_threshold": 0.90,
        },
        "uncertainty_band": {"low": 0.75, "high": 0.90},
        "safe_mode": {
            "allowed_tool_types": ["read", "search", "extract"],
            "disallowed_tool_types": ["write", "modify", "delete", "send_email"],
            "escalate_to_manual_on_disallowed": True,
        },
    },
    "tool_selection": {
        "topK": 3,
        "max_dependency_depth": 2,
        "cost_weight": 0.5,
        "similarity_weight": 0.4,
        "risk_weight": 0.1,
    },
    "dependency": {
        "required_fields": ["id", "capability_type", "provides", "requires", "io_schema"],
        "closure_expansion": True,
        "closure_max_size": 6,
    },
    "context_slots": {
        "preserve_ordered_slots": [
            "policy",
            "goal",
            "constraints",
            "variables",
            "tool_results",
            "plan",
        ],
        "max_tokens_per_slot": {
            "policy": 2048,
            "goal": 1024,
            "constraints": 1024,
            "variables": 2048,
            "tool_results": 4096,
            "plan": 2048,
        },
        "summarization_model": "small_chat_model",
    },
    "fallback": {
        "max_fallback_steps": 3,
        "max_extra_tokens": 1500,
        "max_toolset_growth": 3,
        "hard_budget_limits": {
            "max_total_tokens": 12000,
            "max_model_promotions": 2,
        },
    },
    "budget": {
        "token": {"baseline_limit": 4000, "governor_limit": 3000},
        "latency": {"max_total_ms": 15000},
        "success_rate": {"min_acceptable": 0.85},
    },
    "circuit_breaker": {
        "consecutive_failures": 3,
        "tool_error_threshold": 2,
    },
    "risk": {
        "allowed": ["read", "search", "extract"],
        "prohibited_combination": [
            ["write", "delete"],
            ["email_send", "production_deploy"],
        ],
    },
    "security": {
        "tool_output_sanitization": "strict",
        "forbid_instruction_like_words_in_tool_output": True,
    },
    "logging": {
        "record_decision_bundle": True,
        "record_fallback_path": True,
        "record_tool_inputs": True,
        "record_tool_outputs": True,
        "anonymize_sensitive_fields": True,
    },
}


_EXTERNAL_HINTS = (
    "find",
    "latest",
    "search",
    "source",
    "recent",
    "benchmark",
    "public",
)

_COMPLEX_HINTS = (
    "compare",
    "tradeoff",
    "analyze",
    "evaluate",
    "pipeline",
    "multi",
)

_HIGH_RISK_HINTS = (
    "delete",
    "modify",
    "drop",
    "deploy",
    "email",
    "send",
    "production",
    "root",
    "admin",
)

_INSTRUCTION_LIKE_WORDS = (
    "ignore previous instructions",
    "ignore all previous",
    "system prompt",
    "developer message",
    "act as",
    "jailbreak",
)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_policy(policy_path: str | Path | None = None) -> dict[str, Any]:
    """Load policy YAML and merge with hardcoded defaults."""
    path = Path(policy_path) if policy_path else DEFAULT_POLICY_PATH
    policy = deepcopy(DEFAULT_POLICY)
    if not path.exists():
        policy["_policy_source"] = "default"
        return policy

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid policy format in {path}: top-level object expected")

    policy = _deep_merge(policy, raw)
    policy["_policy_source"] = str(path)
    return policy


def approx_tokens(text: str) -> int:
    if not text:
        return 0
    # v0.x approximation without tokenizer dependency.
    return max(1, (len(text) + 3) // 4)


def trim_to_tokens(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def capability_gate(user_query: str, policy: dict[str, Any]) -> dict[str, Any]:
    lower = user_query.lower()
    score = 0.62
    reasons: list[str] = []

    if len(user_query) >= 90:
        score += 0.08
        reasons.append("long_query")

    if any(term in lower for term in _EXTERNAL_HINTS):
        score += 0.12
        reasons.append("external_knowledge_required")

    if any(term in lower for term in _COMPLEX_HINTS):
        score += 0.08
        reasons.append("complex_reasoning")

    if any(term in lower for term in _HIGH_RISK_HINTS):
        score -= 0.18
        reasons.append("high_risk_intent")

    score = max(0.0, min(0.99, round(score, 4)))

    thresholds = policy.get("gate", {}).get("thresholds", {})
    no_agent = float(thresholds.get("no_agent_threshold", 0.60))
    safe_agent = float(thresholds.get("safe_agent_threshold", 0.75))
    privileged = float(thresholds.get("privileged_threshold", 0.90))

    if score < no_agent:
        decision = "no_agent"
    elif score >= privileged:
        decision = "privileged_agent"
    elif score >= safe_agent:
        decision = "safe_agent"
    else:
        # uncertainty band defaults to safety-first tool restriction.
        decision = "safe_agent"

    band = policy.get("gate", {}).get("uncertainty_band", {})
    band_low = float(band.get("low", safe_agent))
    band_high = float(band.get("high", privileged))
    if band_low <= score < band_high:
        reasons.append("uncertainty_band")

    return {
        "decision": decision,
        "confidence": score,
        "reason_codes": reasons,
    }


def allowed_tool_types(policy: dict[str, Any], gate_decision: str) -> set[str] | None:
    if gate_decision == "privileged_agent":
        return None
    if gate_decision == "no_agent":
        return set()
    allowed = policy.get("gate", {}).get("safe_mode", {}).get("allowed_tool_types", [])
    return {str(item) for item in allowed}


def has_prohibited_combination(
    tool_types: list[str],
    policy: dict[str, Any],
) -> bool:
    selected = set(tool_types)
    combos = policy.get("risk", {}).get("prohibited_combination", [])
    for combo in combos:
        if not isinstance(combo, list):
            continue
        if all(str(item) in selected for item in combo):
            return True
    return False


def classify_failure(error_message: str | None) -> tuple[str, str]:
    lower = str(error_message or "").strip().lower()
    if not lower:
        return "probabilistic", "reasoning_failure"

    if any(term in lower for term in ("risk", "unsafe", "policy violation", "disallowed")):
        return "policy", "risk_violation"
    if any(term in lower for term in ("unsafe_tool_request", "unsafe intent")):
        return "policy", "unsafe_tool_request"

    if any(term in lower for term in ("schema", "validation", "json", "argument", "param")):
        return "deterministic", "schema_mismatch"
    if any(term in lower for term in ("auth", "permission", "unauthorized", "forbidden", "401", "403")):
        return "deterministic", "auth_error"
    if any(term in lower for term in ("not found", "404", "missing")):
        return "deterministic", "not_found"

    if any(term in lower for term in ("loop", "stuck", "retry", "timeout")):
        return "probabilistic", "planning_error"

    return "probabilistic", "reasoning_failure"


def fallback_budget(policy: dict[str, Any]) -> dict[str, int]:
    fallback_cfg = policy.get("fallback", {})
    hard = fallback_cfg.get("hard_budget_limits", {})
    return {
        "max_fallback_steps": int(fallback_cfg.get("max_fallback_steps", 3) or 3),
        "max_extra_tokens": int(fallback_cfg.get("max_extra_tokens", 1500) or 1500),
        "max_toolset_growth": int(fallback_cfg.get("max_toolset_growth", 3) or 3),
        "max_total_tokens": int(hard.get("max_total_tokens", 12000) or 12000),
        "max_model_promotions": int(hard.get("max_model_promotions", 2) or 2),
    }


def circuit_breaker(policy: dict[str, Any]) -> dict[str, int]:
    cfg = policy.get("circuit_breaker", {})
    return {
        "consecutive_failures": int(cfg.get("consecutive_failures", 3) or 3),
        "tool_error_threshold": int(cfg.get("tool_error_threshold", 2) or 2),
    }


def contains_instruction_like_text(text: str, policy: dict[str, Any]) -> bool:
    security_cfg = policy.get("security", {})
    strict = bool(security_cfg.get("forbid_instruction_like_words_in_tool_output", True))
    if not strict:
        return False

    lower = text.lower()
    return any(marker in lower for marker in _INSTRUCTION_LIKE_WORDS)
