"""Runtime guard layer around a baseline agent."""

from __future__ import annotations

import time
from typing import Any

from governor.context_manager import compress_history
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
    ) -> None:
        self.agent = baseline_agent
        self.max_tokens = max_tokens
        self.max_fallback = max_fallback

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
        **kwargs: Any,
    ) -> dict[str, Any]:
        if hasattr(self.agent, "run_task"):
            return self.agent.run_task(prompt=prompt, task_id=task_id, **kwargs)

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
            return compressed
        return original_prompt

    def run(self, prompt: str, task_id: str | None = None, **kwargs: Any) -> dict[str, Any]:
        total_tokens = 0
        fallback_count = 0
        history: list[dict[str, Any]] = []
        original_prompt = prompt

        while True:
            if total_tokens > self.max_tokens:
                raise BudgetExceeded(f"Token budget exceeded: {total_tokens}")

            # v0.1 selection is no-op (return all tools), but we keep the call so
            # the extension point is in place.
            all_tools = getattr(self.agent, "tools", [])
            _selected_tools = select_tools(prompt, all_tools)
            _ = _selected_tools

            start = time.perf_counter()
            result = self._invoke_baseline(prompt=prompt, task_id=task_id, **kwargs)
            latency = time.perf_counter() - start

            result = dict(result)
            result["mode"] = "governor"

            used_tokens = self._safe_int(result.get("total_tokens", 0))
            total_tokens += used_tokens
            result["governor_total_tokens"] = total_tokens
            result["fallback_count"] = fallback_count

            record_result(
                prompt=prompt,
                result=result,
                latency=latency,
                mode="governor",
            )

            if total_tokens > self.max_tokens:
                raise BudgetExceeded(f"Token budget exceeded: {total_tokens}")

            if result.get("success", False):
                return result

            fallback_count += 1
            if fallback_count > self.max_fallback:
                raise FallbackExceeded(f"Fallback limit exceeded: {fallback_count}")

            history.append(result)
            compressed = compress_history(history)
            prompt = self._next_prompt(original_prompt, compressed)
