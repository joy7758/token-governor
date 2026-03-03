"""Runtime guard layer around a baseline agent."""

from __future__ import annotations

import re
import time
import uuid
from typing import Any

from governor.context_manager import build_context_slots, compress_history
from governor.policy_runtime import (
    allowed_tool_types,
    capability_gate,
    classify_failure,
    circuit_breaker,
    contains_instruction_like_text,
    fallback_budget,
    has_prohibited_combination,
    load_policy,
)
from governor.tool_selector import select_tools
from metrics.tracker import record_result


class BudgetExceeded(Exception):
    """Raised when cumulative token use exceeds the configured budget."""


class FallbackExceeded(Exception):
    """Raised when fallback retry count exceeds the configured limit."""


class GuardedAgent:
    """
    Wraps baseline agent execution with token and fallback guardrails.

    The wrapped agent should expose `run_task(prompt=..., task_id=...)` and return
    a result dict with at least: `success`, `total_tokens`, and optional `error`.
    """

    def __init__(
        self,
        baseline_agent: Any,
        max_tokens: int = 10_000,
        max_fallback: int = 2,
        *,
        opt_strategy: str = "balanced",
        enable_context_compression: bool = False,
        enable_smart_tool: bool = True,
        enable_rag: bool = False,
        enable_context_pruning: bool = False,
        enable_semantic_cache: bool = False,
        enable_agentic_plan_cache: bool = False,
        enable_model_routing: bool = False,
        tool_top_k: int = 3,
        history_summary_chars: int = 800,
        plan_cache_similarity_threshold: float = 0.82,
        plan_cache_max_entries: int = 128,
        policy_path: str | None = None,
        policy: dict[str, Any] | None = None,
    ) -> None:
        self.agent = baseline_agent
        self.max_tokens = max_tokens
        self.max_fallback = max_fallback
        self.opt_strategy = opt_strategy
        self.enable_context_compression = enable_context_compression
        self.enable_smart_tool = enable_smart_tool
        self.enable_rag = enable_rag
        self.enable_context_pruning = enable_context_pruning
        self.enable_semantic_cache = enable_semantic_cache
        self.enable_agentic_plan_cache = enable_agentic_plan_cache
        self.enable_model_routing = enable_model_routing
        self.tool_top_k = tool_top_k
        self.history_summary_chars = history_summary_chars
        self.plan_cache_similarity_threshold = plan_cache_similarity_threshold
        self.plan_cache_max_entries = plan_cache_max_entries
        self.policy = policy or load_policy(policy_path)
        self._prompt_cache: dict[str, dict[str, Any]] = {}
        self._agentic_plan_cache: dict[str, dict[str, Any]] = {}
        self._agentic_plan_tokens: dict[str, set[str]] = {}
        self._agentic_plan_order: list[str] = []

    def apply_strategy(self, strategy_config: dict[str, Any]) -> None:
        self.opt_strategy = str(strategy_config.get("opt_strategy", self.opt_strategy))
        self.enable_context_compression = bool(
            strategy_config.get(
                "enable_context_compression",
                self.enable_context_compression,
            )
        )
        self.enable_smart_tool = bool(
            strategy_config.get("enable_smart_tool", self.enable_smart_tool)
        )
        self.enable_rag = bool(strategy_config.get("enable_rag", self.enable_rag))
        self.enable_context_pruning = bool(
            strategy_config.get("enable_context_pruning", self.enable_context_pruning)
        )
        self.enable_semantic_cache = bool(
            strategy_config.get("enable_semantic_cache", self.enable_semantic_cache)
        )
        self.enable_agentic_plan_cache = bool(
            strategy_config.get(
                "enable_agentic_plan_cache",
                self.enable_agentic_plan_cache,
            )
        )
        self.enable_model_routing = bool(
            strategy_config.get("enable_model_routing", self.enable_model_routing)
        )
        self.tool_top_k = int(strategy_config.get("tool_top_k", self.tool_top_k))
        self.history_summary_chars = int(
            strategy_config.get("history_summary_chars", self.history_summary_chars)
        )
        if "plan_cache_similarity_threshold" in strategy_config:
            self.plan_cache_similarity_threshold = float(
                strategy_config.get(
                    "plan_cache_similarity_threshold",
                    self.plan_cache_similarity_threshold,
                )
            )

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _invoke_baseline(
        self,
        prompt: str,
        task_id: str | None = None,
        tools_override: list[Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if hasattr(self.agent, "run_task"):
            return self.agent.run_task(
                prompt=prompt,
                task_id=task_id,
                tools_override=tools_override,
                **kwargs,
            )

        if hasattr(self.agent, "run"):
            raw = self.agent.run(prompt, **kwargs)
            if isinstance(raw, dict):
                return raw
            return {
                "task_id": task_id,
                "prompt": prompt,
                "answer": str(raw),
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "success": True,
                "error": None,
            }

        raise TypeError(
            "baseline_agent must implement run_task(prompt=...) or run(prompt)"
        )

    @staticmethod
    def _next_prompt(original_prompt: str, compressed: Any) -> str:
        if isinstance(compressed, str) and compressed.strip():
            return (
                f"{original_prompt}\n\n"
                f"Previous attempts summary:\n{compressed}\n\n"
                "Retry the task with this failure context in mind."
            )
        return original_prompt

    def _strategy_flags(self) -> dict[str, Any]:
        return {
            "opt_strategy": self.opt_strategy,
            "enable_context_compression": self.enable_context_compression,
            "enable_smart_tool": self.enable_smart_tool,
            "enable_rag": self.enable_rag,
            "enable_context_pruning": self.enable_context_pruning,
            "enable_semantic_cache": self.enable_semantic_cache,
            "enable_agentic_plan_cache": self.enable_agentic_plan_cache,
            "enable_model_routing": self.enable_model_routing,
            "tool_top_k": self.tool_top_k,
            "history_summary_chars": self.history_summary_chars,
            "policy_source": self.policy.get("_policy_source", "default"),
        }

    def _strategies_applied(self) -> list[str]:
        applied: list[str] = [f"strategy:{self.opt_strategy}"]
        if self.enable_context_compression:
            applied.append("context_compression")
        if self.enable_smart_tool:
            applied.append("smart_tool")
        if self.enable_rag:
            applied.append("rag")
        if self.enable_context_pruning:
            applied.append("context_pruning")
        if self.enable_semantic_cache:
            applied.append("semantic_cache")
        if self.enable_agentic_plan_cache:
            applied.append("agentic_plan_cache")
        if self.enable_model_routing:
            applied.append("model_routing")
        return applied

    @staticmethod
    def _tokenize_prompt(prompt: str) -> set[str]:
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "to",
            "of",
            "in",
            "on",
            "for",
            "with",
            "about",
            "by",
            "from",
            "is",
            "are",
            "be",
            "this",
            "that",
            "how",
            "what",
            "when",
            "where",
            "find",
            "explain",
            "summarize",
            "compare",
        }
        cleaned = re.sub(r"https?://\S+", " ", prompt.lower())
        cleaned = re.sub(r"[^0-9a-z\u4e00-\u9fff\s]", " ", cleaned)
        tokens = {token for token in cleaned.split() if len(token) > 1}
        return {token for token in tokens if token not in stop_words}

    def _plan_signature(self, prompt: str) -> str:
        normalized = re.sub(r"https?://\S+", " <url> ", prompt.lower())
        normalized = re.sub(r"\d+(?:\.\d+)?", "<num>", normalized)
        normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff\s<>]", " ", normalized)
        parts = [token for token in normalized.split() if token]
        return " ".join(parts[:12])

    @staticmethod
    def _jaccard(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    def _lookup_agentic_plan_cache(
        self,
        prompt: str,
    ) -> tuple[dict[str, Any] | None, float, str | None]:
        if not self._agentic_plan_cache:
            return None, 0.0, None

        plan_key = self._plan_signature(prompt)
        cached = self._agentic_plan_cache.get(plan_key)
        if cached is not None:
            return dict(cached), 1.0, plan_key

        current_tokens = self._tokenize_prompt(prompt)
        best_key: str | None = None
        best_score = 0.0
        for key, tokens in self._agentic_plan_tokens.items():
            score = self._jaccard(current_tokens, tokens)
            if score > best_score:
                best_score = score
                best_key = key

        if best_key is None or best_score < self.plan_cache_similarity_threshold:
            return None, best_score, best_key
        return dict(self._agentic_plan_cache[best_key]), best_score, best_key

    def _store_agentic_plan_cache(self, prompt: str, result: dict[str, Any]) -> None:
        plan_key = self._plan_signature(prompt)
        self._agentic_plan_cache[plan_key] = dict(result)
        self._agentic_plan_tokens[plan_key] = self._tokenize_prompt(prompt)
        if plan_key in self._agentic_plan_order:
            self._agentic_plan_order.remove(plan_key)
        self._agentic_plan_order.append(plan_key)

        while len(self._agentic_plan_order) > self.plan_cache_max_entries:
            oldest = self._agentic_plan_order.pop(0)
            self._agentic_plan_cache.pop(oldest, None)
            self._agentic_plan_tokens.pop(oldest, None)

    def _base_decision_bundle(
        self,
        *,
        session_id: str,
        user_query: str,
        gate: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "user_query": user_query,
            "gate": gate,
            "tool_selection": {
                "top_k_candidates": [],
                "dependency_closure": [],
                "scores": {},
            },
            "context_build": {
                "slots": {},
                "compression_ratios": {},
            },
            "routing": {
                "selected_model": str(getattr(self.agent, "model", "unknown") or "unknown"),
                "reasons": [],
            },
            "fallback": {
                "steps_taken": 0,
                "trigger_reasons": [],
            },
            "outcome": {
                "success": False,
                "validator_results": {},
            },
            "metrics": {
                "tokens_used": 0,
                "latency_ms": 0,
                "fallback_triggered": False,
            },
        }

    def run(
        self,
        prompt: str,
        task_id: str | None = None,
        run_metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        total_tokens = 0
        fallback_count = 0
        history: list[dict[str, Any]] = []
        original_prompt = prompt
        strategy_flags = self._strategy_flags()
        strategies_applied = self._strategies_applied()

        budget_cfg = fallback_budget(self.policy)
        circuit_cfg = circuit_breaker(self.policy)
        effective_max_tokens = min(self.max_tokens, int(budget_cfg["max_total_tokens"]))
        effective_max_fallback = min(self.max_fallback, int(budget_cfg["max_fallback_steps"]))
        max_tool_growth = int(budget_cfg["max_toolset_growth"])
        max_extra_tokens = int(budget_cfg["max_extra_tokens"])

        gate = capability_gate(prompt, self.policy)
        allowed_types = allowed_tool_types(self.policy, gate["decision"])

        session_id = task_id or str(uuid.uuid4())
        decision_bundle = self._base_decision_bundle(
            session_id=session_id,
            user_query=original_prompt,
            gate=gate,
        )

        fallback_reasons: list[str] = []
        total_latency_ms = 0
        tool_error_count = 0
        consecutive_failures = 0
        first_attempt_tokens: int | None = None
        current_top_k = self.tool_top_k

        if self.enable_semantic_cache and prompt in self._prompt_cache:
            cached = dict(self._prompt_cache[prompt])
            original_tokens = self._safe_int(cached.get("total_tokens", 0))
            decision_bundle["routing"]["reasons"] = ["semantic_cache_hit"]
            decision_bundle["outcome"] = {
                "success": bool(cached.get("success", True)),
                "validator_results": {"cache_hit": True},
            }
            decision_bundle["metrics"] = {
                "tokens_used": 0,
                "latency_ms": 0,
                "fallback_triggered": False,
            }
            cached.update(
                {
                    "task_id": task_id or cached.get("task_id"),
                    "prompt": prompt,
                    "mode": "governor",
                    "from_cache": True,
                    "cached_original_total_tokens": original_tokens,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "governor_total_tokens": 0,
                    "fallback_count": 0,
                    "fallback_steps": 0,
                    "strategy": strategy_flags,
                    "strategies_applied": strategies_applied,
                    "cache_hits": {"semantic": True, "plan_cache": False},
                    "model": cached.get("model", getattr(self.agent, "model", None)),
                    "decision_bundle": decision_bundle,
                }
            )
            if run_metadata:
                cached.update(run_metadata)
            record_result(
                prompt=prompt,
                result=cached,
                latency=0.0,
                mode="governor",
            )
            return cached

        if self.enable_agentic_plan_cache:
            plan_cached, similarity, plan_key = self._lookup_agentic_plan_cache(prompt)
            if plan_cached is not None:
                original_tokens = self._safe_int(plan_cached.get("total_tokens", 0))
                decision_bundle["routing"]["reasons"] = ["agentic_plan_cache_hit"]
                decision_bundle["outcome"] = {
                    "success": bool(plan_cached.get("success", True)),
                    "validator_results": {"cache_hit": True, "plan_cache_similarity": round(similarity, 4)},
                }
                decision_bundle["metrics"] = {
                    "tokens_used": 0,
                    "latency_ms": 0,
                    "fallback_triggered": False,
                }
                plan_cached.update(
                    {
                        "task_id": task_id or plan_cached.get("task_id"),
                        "prompt": prompt,
                        "mode": "governor",
                        "from_cache": True,
                        "from_plan_cache": True,
                        "agentic_plan_cache": True,
                        "agentic_plan_key": plan_key,
                        "plan_cache_similarity": round(similarity, 4),
                        "cached_original_total_tokens": original_tokens,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                        "governor_total_tokens": 0,
                        "fallback_count": 0,
                        "fallback_steps": 0,
                        "strategy": strategy_flags,
                        "strategies_applied": strategies_applied,
                        "cache_hits": {"semantic": False, "plan_cache": True},
                        "model": plan_cached.get("model", getattr(self.agent, "model", None)),
                        "decision_bundle": decision_bundle,
                    }
                )
                if run_metadata:
                    plan_cached.update(run_metadata)
                record_result(
                    prompt=prompt,
                    result=plan_cached,
                    latency=0.0,
                    mode="governor",
                )
                return plan_cached

        while True:
            if total_tokens > effective_max_tokens:
                raise BudgetExceeded(f"Token budget exceeded: {total_tokens}")

            all_tools = getattr(self.agent, "tools", [])
            if self.enable_smart_tool:
                selected_tools, tool_trace = select_tools(
                    prompt,
                    all_tools,
                    top_k=current_top_k,
                    policy=self.policy,
                    allowed_tool_types=allowed_types,
                    return_trace=True,
                )
            else:
                selected_tools, tool_trace = select_tools(
                    prompt,
                    all_tools,
                    top_k=len(all_tools),
                    policy=self.policy,
                    allowed_tool_types=allowed_types,
                    return_trace=True,
                )

            decision_bundle["tool_selection"] = {
                "top_k_candidates": tool_trace.get("top_k_candidates", []),
                "dependency_closure": tool_trace.get("dependency_closure", []),
                "scores": tool_trace.get("scores", {}),
            }

            selected_types = list(tool_trace.get("tool_types", []))
            policy_violation = has_prohibited_combination(selected_types, self.policy)
            if policy_violation:
                error_text = "risk_violation: prohibited tool combination"
                family, failure_type = classify_failure(error_text)
                fallback_reasons.append(failure_type)
                decision_bundle["fallback"]["trigger_reasons"] = fallback_reasons
                result = {
                    "task_id": task_id,
                    "mode": "governor",
                    "prompt": prompt,
                    "answer": "",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "success": False,
                    "error": error_text,
                    "failure_family": family,
                    "failure_type": failure_type,
                    "policy_violation": True,
                    "selected_tools": [str(getattr(tool, "name", "unknown")) for tool in selected_tools],
                    "strategy": strategy_flags,
                    "strategies_applied": strategies_applied,
                    "fallback_count": fallback_count,
                    "fallback_steps": fallback_count,
                    "governor_total_tokens": total_tokens,
                }
                decision_bundle["outcome"] = {
                    "success": False,
                    "validator_results": {
                        "policy_violation": True,
                    },
                }
                decision_bundle["metrics"] = {
                    "tokens_used": total_tokens,
                    "latency_ms": total_latency_ms,
                    "fallback_triggered": fallback_count > 0,
                }
                decision_bundle["fallback"]["steps_taken"] = fallback_count
                result["decision_bundle"] = decision_bundle
                if run_metadata:
                    result.update(run_metadata)
                record_result(prompt=prompt, result=result, latency=0.0, mode="governor")
                return result

            context_trace = build_context_slots(
                policy=self.policy,
                goal=original_prompt,
                constraints={
                    "gate": gate,
                    "max_total_tokens": effective_max_tokens,
                    "max_fallback": effective_max_fallback,
                },
                variables={
                    "strategy": strategy_flags,
                    "attempt": fallback_count + 1,
                },
                tool_results=history,
                plan={
                    "selected_tools": tool_trace.get("dependency_closure", []),
                    "fallback_reasons": fallback_reasons,
                },
            )
            decision_bundle["context_build"] = {
                "slots": context_trace.get("slots", {}),
                "compression_ratios": context_trace.get("compression_ratios", {}),
            }

            start = time.perf_counter()
            result = self._invoke_baseline(
                prompt=prompt,
                task_id=task_id,
                tools_override=selected_tools,
                **kwargs,
            )
            latency = time.perf_counter() - start
            latency_ms = int(latency * 1000)
            total_latency_ms += latency_ms

            result = dict(result)
            result["mode"] = "governor"
            result["strategy"] = strategy_flags
            result["strategies_applied"] = strategies_applied
            result["cache_hits"] = {"semantic": False, "plan_cache": False}
            result["selected_tools"] = [
                str(getattr(tool, "name", "unknown")) for tool in selected_tools
            ]
            result["selected_tool_types"] = selected_types
            if run_metadata:
                result.update(run_metadata)
            if self.enable_rag or self.enable_context_pruning or self.enable_model_routing:
                # Placeholders for v0.x roadmap: flags are accepted now so config
                # can be wired through UI/CLI before full implementations land.
                result["strategy_note"] = (
                    "RAG/context-pruning/model-routing flags enabled; "
                    "advanced pipeline integration pending implementation."
                )

            if contains_instruction_like_text(str(result.get("answer", "")), self.policy):
                result["success"] = False
                result["error"] = "unsafe_tool_request: instruction-like tool output"

            used_tokens = self._safe_int(result.get("total_tokens", 0))
            total_tokens += used_tokens
            if first_attempt_tokens is None:
                first_attempt_tokens = used_tokens

            if (
                first_attempt_tokens is not None
                and total_tokens - first_attempt_tokens > max_extra_tokens
            ):
                raise BudgetExceeded(
                    "Fallback extra token budget exceeded: "
                    f"{total_tokens - first_attempt_tokens} > {max_extra_tokens}"
                )

            result["governor_total_tokens"] = total_tokens
            result["fallback_count"] = fallback_count
            result["fallback_steps"] = fallback_count
            result["policy_violation"] = False

            decision_bundle["routing"] = {
                "selected_model": str(result.get("model", getattr(self.agent, "model", "unknown"))),
                "reasons": [
                    f"gate:{gate['decision']}",
                    f"strategy:{self.opt_strategy}",
                ],
            }
            decision_bundle["fallback"] = {
                "steps_taken": fallback_count,
                "trigger_reasons": fallback_reasons,
            }
            decision_bundle["metrics"] = {
                "tokens_used": total_tokens,
                "latency_ms": total_latency_ms,
                "fallback_triggered": fallback_count > 0,
            }

            if result.get("success", False):
                consecutive_failures = 0
            else:
                consecutive_failures += 1

            if result.get("error"):
                tool_error_count += 1
                family, failure_type = classify_failure(result.get("error"))
                result["failure_family"] = family
                result["failure_type"] = failure_type

            decision_bundle["outcome"] = {
                "success": bool(result.get("success", False)),
                "validator_results": {
                    "policy_violation": bool(result.get("policy_violation", False)),
                    "failure_type": result.get("failure_type"),
                    "failure_family": result.get("failure_family"),
                },
            }
            result["decision_bundle"] = decision_bundle

            record_result(
                prompt=prompt,
                result=result,
                latency=latency,
                mode="governor",
            )

            if total_tokens > effective_max_tokens:
                raise BudgetExceeded(f"Token budget exceeded: {total_tokens}")

            if result.get("success", False):
                if self.enable_semantic_cache:
                    self._prompt_cache[original_prompt] = dict(result)
                if self.enable_agentic_plan_cache:
                    self._store_agentic_plan_cache(original_prompt, result)
                return result

            fallback_count += 1
            decision_bundle["fallback"]["steps_taken"] = fallback_count
            result["fallback_count"] = fallback_count
            result["fallback_steps"] = fallback_count

            if fallback_count > effective_max_fallback:
                raise FallbackExceeded(f"Fallback limit exceeded: {fallback_count}")

            if consecutive_failures >= int(circuit_cfg["consecutive_failures"]):
                raise FallbackExceeded(
                    "Circuit breaker: consecutive failures exceeded "
                    f"{consecutive_failures}/{int(circuit_cfg['consecutive_failures'])}"
                )

            if tool_error_count >= int(circuit_cfg["tool_error_threshold"]):
                raise FallbackExceeded(
                    "Circuit breaker: tool error threshold exceeded "
                    f"{tool_error_count}/{int(circuit_cfg['tool_error_threshold'])}"
                )

            history.append(result)
            family, failure_type = classify_failure(result.get("error"))
            fallback_reasons.append(failure_type)
            decision_bundle["fallback"]["trigger_reasons"] = fallback_reasons

            if family == "policy":
                return result

            if family == "deterministic":
                # Deterministic failure: retry once with explicit schema discipline.
                compressed = compress_history(history, max_chars=self.history_summary_chars)
                prompt = (
                    f"{original_prompt}\n\n"
                    "Please retry with strict parameter/schema compliance.\n"
                    f"Failure context: {compressed}"
                )
            else:
                # Probabilistic failure: expand context and optionally broaden toolset.
                if current_top_k < self.tool_top_k + max_tool_growth:
                    current_top_k += 1
                if self.enable_context_compression:
                    compressed = compress_history(
                        history,
                        max_chars=self.history_summary_chars,
                    )
                else:
                    compressed = ""
                prompt = self._next_prompt(original_prompt, compressed)
