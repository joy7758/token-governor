"""Run baseline or governor benchmark over a fixed task set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from baseline.agent import BaselineAgent
from governor.agent import BudgetExceeded, FallbackExceeded, GuardedAgent
from metrics.tracker import MetricsTracker


DEFAULT_TASKS = [
    "Find OpenAI GPT-4o release date and list its key improvements.",
    "Explain how LangChain agents call external tools in Python.",
    "Summarize the latest public description of Retrieval-Augmented Generation.",
    "Find one recent article discussing AI agent evaluation methods and summarize it.",
    "Compare two popular vector databases and list tradeoffs.",
    "Find a public benchmark comparing LLM latency and summarize the setup.",
    "Summarize the purpose of the Model Context Protocol (MCP).",
    "Find a practical guide for writing robust prompt templates and summarize key points.",
    "Find recent public discussion about tool-calling reliability in LLMs.",
    "Summarize best practices for handling API retries in Python clients.",
    "Find one source on AI cost optimization and summarize actionable tactics.",
    "Explain what token usage metrics should be tracked in agent experiments.",
    "Find a source that explains eval datasets for agent tasks.",
    "Summarize a public comparison between zero-shot and few-shot prompting.",
    "Find recent info on OpenAI Responses API usage patterns.",
    "Summarize one source explaining function/tool schema design for LLM tools.",
    "Find a source about preventing hallucinations in web-search assistants.",
    "Explain how to evaluate answer faithfulness for retrieval systems.",
    "Find practical tips for reducing context window waste in multi-turn chats.",
    "Summarize one source on error handling patterns for autonomous agents.",
]


def _print_summary(title: str, summary: dict[str, float], paths: dict[str, str]) -> None:
    print(f"\n=== {title} Summary ===")
    print(f"tasks: {summary['num_tasks']}")
    print(f"success: {summary['success_count']}/{summary['num_tasks']}")
    print(f"success_rate: {summary['success_rate']:.2%}")
    print(f"total_tokens: {summary['total_tokens']}")
    print(f"avg_tokens_per_task: {summary['avg_tokens_per_task']:.2f}")
    print(f"avg_latency: {summary['avg_latency']:.2f}s")
    print(f"records_file: {paths['records_file']}")
    print(f"summary_file: {paths['summary_file']}")


def _write_out_file(records: list[dict[str, object]], out_file: str | None) -> None:
    if not out_file:
        return
    out_path = Path(out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as file:
        for row in records:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"out_file: {out_path}")


def run_baseline(
    model_name: str,
    limit: int | None = None,
    out_file: str | None = None,
) -> int:
    load_dotenv()

    tasks = DEFAULT_TASKS if limit is None else DEFAULT_TASKS[:limit]
    tracker = MetricsTracker(output_dir="metrics/data")

    try:
        agent = BaselineAgent(model_name=model_name, verbose=False)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] failed to initialize BaselineAgent: {exc}")
        return 1

    for idx, prompt in enumerate(tasks, start=1):
        task_id = f"task-{idx:03d}"
        print(f"[run] {task_id}: {prompt}")
        result = agent.run_task(prompt=prompt, task_id=task_id)
        tracker.add_record(result)
        print(
            "[done] "
            f"success={result['success']} "
            f"tokens={result['total_tokens']} "
            f"latency={result['latency']:.2f}s"
        )
        if result["error"]:
            print(f"[warn] {task_id} error: {result['error']}")

    summary = tracker.summary()
    paths = tracker.save_run(mode="baseline")
    _write_out_file(tracker.records, out_file)
    _print_summary("Baseline", summary, paths)
    return 0


def run_governor(
    model_name: str,
    limit: int | None = None,
    max_tokens: int = 12_000,
    max_fallback: int = 2,
    out_file: str | None = None,
) -> int:
    load_dotenv()

    tasks = DEFAULT_TASKS if limit is None else DEFAULT_TASKS[:limit]
    tracker = MetricsTracker(output_dir="metrics/data")

    try:
        baseline_agent = BaselineAgent(model_name=model_name, verbose=False)
        guarded_agent = GuardedAgent(
            baseline_agent=baseline_agent,
            max_tokens=max_tokens,
            max_fallback=max_fallback,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[error] failed to initialize GuardedAgent: {exc}")
        return 1

    for idx, prompt in enumerate(tasks, start=1):
        task_id = f"task-{idx:03d}"
        print(f"[run] {task_id}: {prompt}")
        try:
            result = guarded_agent.run(prompt=prompt, task_id=task_id)
        except (BudgetExceeded, FallbackExceeded) as exc:
            result = {
                "task_id": task_id,
                "mode": "governor",
                "prompt": prompt,
                "answer": "",
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "latency": 0.0,
                "success": False,
                "error": str(exc),
            }

        tracker.add_record(result)
        print(
            "[done] "
            f"success={result['success']} "
            f"tokens={result['total_tokens']} "
            f"latency={result['latency']:.2f}s"
        )
        if result["error"]:
            print(f"[warn] {task_id} error: {result['error']}")

    summary = tracker.summary()
    paths = tracker.save_run(mode="governor")
    _write_out_file(tracker.records, out_file)
    _print_summary("Governor", summary, paths)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run baseline or governor benchmark.")
    parser.add_argument(
        "--mode",
        choices=["baseline", "governor"],
        default="baseline",
        help="Run plain baseline or guarded governor mode.",
    )
    parser.add_argument(
        "--model",
        default="auto",
        help=(
            "Model name, e.g. auto, gpt-4o-mini, gemini-2.0-flash, "
            "openai:gpt-4o-mini, google_genai:gemini-2.0-flash"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of tasks to run (for quick smoke tests).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=12_000,
        help="Governor-only: cumulative token budget per task.",
    )
    parser.add_argument(
        "--max-fallback",
        type=int,
        default=2,
        help="Governor-only: maximum allowed fallback retries.",
    )
    parser.add_argument(
        "--out-file",
        type=str,
        default=None,
        help="Optional JSONL output path for this run (stable filename).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.mode == "governor":
        raise SystemExit(
            run_governor(
                model_name=args.model,
                limit=args.limit,
                max_tokens=args.max_tokens,
                max_fallback=args.max_fallback,
                out_file=args.out_file,
            )
        )
    raise SystemExit(
        run_baseline(
            model_name=args.model,
            limit=args.limit,
            out_file=args.out_file,
        )
    )
