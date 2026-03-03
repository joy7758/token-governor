"""Baseline agent that loads all tools and runs tasks without governance."""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.messages import AIMessage, BaseMessage


class BaselineAgent:
    """Simple baseline agent that always has full tool access."""

    def __init__(
        self,
        model_name: str = "auto",
        verbose: bool = False,
    ) -> None:
        load_dotenv()

        self.model = self._resolve_model_name(model_name)
        self._validate_provider_key(self.model)
        self.verbose = verbose
        self.system_prompt = (
            "You are a helpful assistant. Use tools when needed and provide"
            " concise, accurate final answers."
        )
        self.tools = self._build_tools()
        self.agent = self._build_agent(self.tools)

    @staticmethod
    def _resolve_model_name(model_name: str) -> str:
        """
        Resolve a runnable model string for LangChain `create_agent`.

        Supported forms:
        - `auto` (prefers Gemini key, then OpenAI key)
        - provider-prefixed values, e.g. `openai:gpt-4o-mini`
        - bare names, e.g. `gpt-4o-mini` or `gemini-2.0-flash`
        """
        google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if model_name == "auto":
            if google_key:
                return "google_genai:gemini-2.5-flash"
            if openai_key:
                return "openai:gpt-4o-mini"
            raise ValueError(
                "No provider key found. Set GOOGLE_API_KEY (or GEMINI_API_KEY) "
                "or OPENAI_API_KEY."
            )

        if ":" in model_name:
            return model_name

        if model_name.startswith("gemini"):
            return f"google_genai:{model_name}"
        return f"openai:{model_name}"

    @staticmethod
    def _validate_provider_key(model_name: str) -> None:
        provider, _, _ = model_name.partition(":")
        if provider == "openai":
            if not os.getenv("OPENAI_API_KEY"):
                raise ValueError(
                    "OPENAI_API_KEY is required for OpenAI models. "
                    "Set it in your environment or .env file."
                )
            return
        if provider == "google_genai":
            if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
                raise ValueError(
                    "GOOGLE_API_KEY or GEMINI_API_KEY is required for Gemini models. "
                    "Set one in your environment or .env file."
                )
            return

    @staticmethod
    def _build_tools() -> list[DuckDuckGoSearchRun]:
        web_search = DuckDuckGoSearchRun(
            name="web_search",
            description="Search the web for recent public information.",
        )
        return [web_search]

    def _build_agent(self, tools: list[Any]) -> Any:
        return create_agent(
            model=self.model,
            tools=tools,
            system_prompt=self.system_prompt,
            debug=self.verbose,
        )

    @staticmethod
    def _extract_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
                elif isinstance(item, str):
                    chunks.append(item)
            return "\n".join(chunks).strip()
        return str(content)

    @staticmethod
    def _extract_usage(messages: list[BaseMessage]) -> dict[str, int]:
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0

        for message in messages:
            if not isinstance(message, AIMessage):
                continue

            usage = message.usage_metadata or {}
            in_count = int(
                usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
            )
            out_count = int(
                usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
            )
            total_count = int(usage.get("total_tokens", 0) or 0)

            input_tokens += in_count
            output_tokens += out_count
            total_tokens += total_count

        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

    def run_task(
        self,
        prompt: str,
        task_id: str | None = None,
        tools_override: list[Any] | None = None,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        run_id = task_id or str(uuid.uuid4())

        try:
            runner = self.agent
            if tools_override is not None:
                runner = self._build_agent(tools_override)

            output = runner.invoke(
                {"messages": [{"role": "user", "content": prompt}]}
            )
            messages = output.get("messages", [])

            final_answer = ""
            for message in reversed(messages):
                if isinstance(message, AIMessage):
                    final_answer = self._extract_text(message.content)
                    if final_answer:
                        break

            usage = self._extract_usage(messages)
            latency = time.perf_counter() - start

            return {
                "task_id": run_id,
                "mode": "baseline",
                "model": self.model,
                "prompt": prompt,
                "answer": final_answer,
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
                "total_tokens": usage["total_tokens"],
                "latency": latency,
                "success": True,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            latency = time.perf_counter() - start
            return {
                "task_id": run_id,
                "mode": "baseline",
                "model": self.model,
                "prompt": prompt,
                "answer": "",
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "latency": latency,
                "success": False,
                "error": str(exc),
            }
