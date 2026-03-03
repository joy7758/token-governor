"""Run baseline or governor benchmark over a fixed task set."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from dotenv import load_dotenv

from baseline.agent import BaselineAgent
from governor.auto_strategy import apply_auto_strategy
from governor.agent import BudgetExceeded, FallbackExceeded, GuardedAgent
from governor.model_profile import load_model_profiles, recommend_drive_mode_from_profile
from governor.strategy import DRIVE_MODE_NAMES, STRATEGY_NAMES, resolve_drive_mode, resolve_strategy
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


def load_tasks(
    tasks_file: str | None = None,
    limit: int | None = None,
) -> list[dict[str, object]]:
    if not tasks_file:
        prompts = DEFAULT_TASKS if limit is None else DEFAULT_TASKS[:limit]
        return [
            {
                "id": f"task-{idx:03d}",
                "category": "default",
                "description": "Default benchmark prompt",
                "input": prompt,
                "allowed_tools": [],
                "forbidden_tools": [],
                "expected_output": "",
                "validator": {"type": "manual"},
                "is_adversarial": False,
            }
            for idx, prompt in enumerate(prompts, start=1)
        ]

    path = Path(tasks_file)
    if not path.exists():
        raise FileNotFoundError(f"Tasks file not found: {path}")

    raw_tasks: list[object]
    if path.suffix.lower() == ".jsonl":
        raw_tasks = []
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                raw_tasks.append(json.loads(line))
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            raw_tasks = list(payload.get("tasks", []))
        elif isinstance(payload, list):
            raw_tasks = payload
        else:
            raise ValueError(f"Unsupported tasks format in {path}")

    normalized: list[dict[str, object]] = []
    for idx, item in enumerate(raw_tasks, start=1):
        if isinstance(item, str):
            row: dict[str, object] = {"input": item}
        elif isinstance(item, dict):
            row = dict(item)
        else:
            continue

        prompt = str(row.get("input", row.get("prompt", "")) or "").strip()
        if not prompt:
            continue

        task_id = str(row.get("id", f"task-{idx:03d}"))
        normalized.append(
            {
                "id": task_id,
                "category": str(row.get("category", "custom")),
                "description": str(row.get("description", "")),
                "input": prompt,
                "allowed_tools": row.get("allowed_tools", []),
                "forbidden_tools": row.get("forbidden_tools", []),
                "expected_output": str(row.get("expected_output", "")),
                "validator": row.get("validator", {"type": "manual"}),
                "is_adversarial": bool(row.get("is_adversarial", False)),
            }
        )

    if limit is not None:
        return normalized[:limit]
    return normalized


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


def _resolve_bool_override(
    enabled: bool,
    disabled: bool,
    *,
    flag_name: str,
) -> bool | None:
    if enabled and disabled:
        raise ValueError(f"Cannot enable and disable {flag_name} at the same time.")
    if enabled:
        return True
    if disabled:
        return False
    return None


def build_strategy_overrides(args: argparse.Namespace) -> dict[str, object]:
    return {
        "enable_context_compression": _resolve_bool_override(
            args.enable_context_compression,
            args.disable_context_compression,
            flag_name="context-compression",
        ),
        "enable_smart_tool": _resolve_bool_override(
            args.enable_smart_tool,
            args.disable_smart_tool,
            flag_name="smart-tool",
        ),
        "enable_rag": _resolve_bool_override(
            args.enable_rag,
            args.disable_rag,
            flag_name="rag",
        ),
        "enable_context_pruning": _resolve_bool_override(
            args.enable_context_pruning,
            args.disable_context_pruning,
            flag_name="context-pruning",
        ),
        "enable_semantic_cache": _resolve_bool_override(
            args.enable_semantic_cache,
            args.disable_semantic_cache,
            flag_name="semantic-cache",
        ),
        "enable_agentic_plan_cache": _resolve_bool_override(
            args.enable_agentic_plan_cache,
            args.disable_agentic_plan_cache,
            flag_name="agentic-plan-cache",
        ),
        "enable_model_routing": _resolve_bool_override(
            args.enable_model_routing,
            args.disable_model_routing,
            flag_name="model-routing",
        ),
        "tool_top_k": args.tool_top_k,
        "history_summary_chars": args.history_summary_chars,
    }


def detect_external_requirements(prompt: str) -> bool:
    keywords = (
        "find",
        "latest",
        "source",
        "search",
        "article",
        "benchmark",
        "recent",
        "public",
        "according to",
    )
    lower = prompt.lower()
    return any(keyword in lower for keyword in keywords)


def estimate_history_tokens(records: list[dict[str, object]]) -> int:
    if not records:
        return 0
    return int(sum(int(row.get("total_tokens", 0) or 0) for row in records[-3:]))


def _tokenize_for_similarity(text: str) -> set[str]:
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
    cleaned = re.sub(r"https?://\S+", " ", text.lower())
    cleaned = re.sub(r"[^0-9a-z\u4e00-\u9fff\s]", " ", cleaned)
    tokens = {token for token in cleaned.split() if len(token) > 1}
    return {token for token in tokens if token not in stop_words}


def semantic_similarity_score(prompt: str, previous_prompts: list[str]) -> float:
    if not previous_prompts:
        return 0.0
    current = _tokenize_for_similarity(prompt)
    if not current:
        return 0.0

    best = 0.0
    for old_prompt in previous_prompts[-12:]:
        old = _tokenize_for_similarity(old_prompt)
        if not old:
            continue
        union = current | old
        if not union:
            continue
        score = len(current & old) / len(union)
        if score > best:
            best = score
    return round(best, 4)


def build_task_context(
    prompt: str,
    records: list[dict[str, object]],
    tool_count: int,
) -> dict[str, object]:
    previous_prompts = [
        str(row.get("prompt", "") or "")
        for row in records
        if str(row.get("prompt", "") or "").strip()
    ]
    similarity = semantic_similarity_score(prompt, previous_prompts)
    external_query = detect_external_requirements(prompt)
    return {
        "history_tokens": estimate_history_tokens(records),
        "tool_calls": tool_count,
        "external_query": external_query,
        "external_data": external_query,
        "semantic_similarity_score": similarity,
        "context_length": len(prompt),
    }


def run_baseline(
    model_name: str,
    limit: int | None = None,
    out_file: str | None = None,
    tasks_file: str | None = None,
) -> int:
    load_dotenv()

    tasks = load_tasks(tasks_file=tasks_file, limit=limit)
    tracker = MetricsTracker(output_dir="metrics/data")

    try:
        agent = BaselineAgent(model_name=model_name, verbose=False)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] failed to initialize BaselineAgent: {exc}")
        return 1

    for task in tasks:
        task_id = str(task.get("id", "task-unknown"))
        prompt = str(task.get("input", "") or "")
        print(f"[run] {task_id}: {prompt}")
        result = agent.run_task(prompt=prompt, task_id=task_id)
        result.update(
            {
                "category": task.get("category"),
                "benchmark_description": task.get("description"),
                "allowed_tools": task.get("allowed_tools"),
                "forbidden_tools": task.get("forbidden_tools"),
                "expected_output": task.get("expected_output"),
                "validator": task.get("validator"),
                "is_adversarial": task.get("is_adversarial"),
            }
        )
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
    strategy_config: dict[str, object] | None = None,
    strategy_overrides: dict[str, object] | None = None,
    auto_strategy: bool = False,
    drive_mode: str | None = None,
    model_profiles: dict[str, object] | None = None,
    policy_file: str | None = None,
    tasks_file: str | None = None,
) -> int:
    load_dotenv()

    tasks = load_tasks(tasks_file=tasks_file, limit=limit)
    tracker = MetricsTracker(output_dir="metrics/data")
    effective_strategy = strategy_config or resolve_strategy("balanced")
    overrides = strategy_overrides or {}
    profiles = model_profiles or {}

    try:
        baseline_agent = BaselineAgent(model_name=model_name, verbose=False)
        guarded_agent = GuardedAgent(
            baseline_agent=baseline_agent,
            max_tokens=max_tokens,
            max_fallback=max_fallback,
            opt_strategy="balanced",
            policy_path=policy_file,
        )
        guarded_agent.apply_strategy(effective_strategy)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] failed to initialize GuardedAgent: {exc}")
        return 1

    last_strategy_snapshot = ""

    for task in tasks:
        task_id = str(task.get("id", "task-unknown"))
        prompt = str(task.get("input", "") or "")
        task_context = build_task_context(
            prompt=prompt,
            records=tracker.records,
            tool_count=len(getattr(baseline_agent, "tools", [])),
        )

        run_metadata: dict[str, object] = {
            "task_features": task_context,
            "category": task.get("category"),
            "benchmark_description": task.get("description"),
            "allowed_tools": task.get("allowed_tools"),
            "forbidden_tools": task.get("forbidden_tools"),
            "expected_output": task.get("expected_output"),
            "validator": task.get("validator"),
            "is_adversarial": task.get("is_adversarial"),
        }
        if auto_strategy:
            profile_hint_reason: str | None = None
            profile_hint_mode: str | None = None
            if drive_mode == "auto":
                profile_hint_mode, profile_hint_reason = recommend_drive_mode_from_profile(
                    profiles,
                    str(getattr(baseline_agent, "model", "")),
                    objective="balanced",
                )
                if profile_hint_mode:
                    task_context["profile_drive_mode_hint"] = profile_hint_mode

            effective_strategy, reasons = apply_auto_strategy(
                task_context,
                overrides=overrides,
                drive_mode=drive_mode,
            )
            run_metadata.update(
                {
                    "auto_strategy_reasons": reasons,
                    "auto_task_features": effective_strategy.get("auto_task_features", {}),
                    "auto_selected_strategy": effective_strategy.get("opt_strategy"),
                    "drive_mode": effective_strategy.get("drive_mode"),
                    "drive_mode_goal": effective_strategy.get("drive_mode_goal"),
                    "drive_mode_description": effective_strategy.get("drive_mode_description"),
                    "model_profile_hint_mode": profile_hint_mode,
                    "model_profile_hint_reason": profile_hint_reason,
                }
            )
            guarded_agent.apply_strategy(effective_strategy)
        elif drive_mode:
            run_metadata.update(
                {
                    "drive_mode": effective_strategy.get("drive_mode"),
                    "drive_mode_goal": effective_strategy.get("drive_mode_goal"),
                    "drive_mode_description": effective_strategy.get("drive_mode_description"),
                }
            )

        strategy_snapshot = json.dumps(
            {
                "opt_strategy": guarded_agent.opt_strategy,
                "drive_mode": effective_strategy.get("drive_mode"),
                "enable_context_compression": guarded_agent.enable_context_compression,
                "enable_smart_tool": guarded_agent.enable_smart_tool,
                "enable_rag": guarded_agent.enable_rag,
                "enable_context_pruning": guarded_agent.enable_context_pruning,
                "enable_semantic_cache": guarded_agent.enable_semantic_cache,
                "enable_agentic_plan_cache": guarded_agent.enable_agentic_plan_cache,
                "enable_model_routing": guarded_agent.enable_model_routing,
                "tool_top_k": guarded_agent.tool_top_k,
                "history_summary_chars": guarded_agent.history_summary_chars,
                "auto_mode": auto_strategy,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        if strategy_snapshot != last_strategy_snapshot:
            print("[strategy] " + strategy_snapshot)
            if run_metadata.get("auto_strategy_reasons"):
                print("[strategy_reasons] " + json.dumps(run_metadata, ensure_ascii=False))
            last_strategy_snapshot = strategy_snapshot

        print(f"[run] {task_id}: {prompt}")
        try:
            result = guarded_agent.run(
                prompt=prompt,
                task_id=task_id,
                run_metadata=run_metadata,
            )
        except (BudgetExceeded, FallbackExceeded) as exc:
            error_text = str(exc)
            failure_type = "budget_exceeded" if isinstance(exc, BudgetExceeded) else "fallback_exceeded"
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
                "error": error_text,
                "failure_family": "deterministic" if isinstance(exc, BudgetExceeded) else "probabilistic",
                "failure_type": failure_type,
                "fallback_steps": max_fallback,
                "policy_violation": False,
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
            "Model name, e.g. auto, gpt-4o-mini, gemini-2.5-flash, "
            "openai:gpt-4o-mini, google_genai:gemini-2.5-flash"
        ),
    )
    parser.add_argument(
        "--opt-strategy",
        choices=list(STRATEGY_NAMES),
        default="balanced",
        help="Governor-only manual strategy profile: light/balanced/knowledge/enterprise.",
    )
    parser.add_argument(
        "--auto-strategy",
        action="store_true",
        help="Governor-only: enable AI-driven automatic strategy recommendation.",
    )
    parser.add_argument(
        "--drive-mode",
        choices=list(DRIVE_MODE_NAMES),
        default=None,
        help=(
            "Governor-only driving preset: auto/eco/comfort/sport/rocket. "
            "`auto` implies dynamic recommendation path."
        ),
    )
    parser.add_argument(
        "--model-profile",
        type=str,
        default=None,
        help=(
            "Optional model profile JSON path generated by "
            "scripts/build_model_profiles.py"
        ),
    )
    parser.add_argument(
        "--policy-file",
        type=str,
        default="policy.yaml",
        help="Governor-only: path to policy YAML (default: policy.yaml).",
    )
    parser.add_argument(
        "--tasks-file",
        type=str,
        default=None,
        help=(
            "Optional benchmark task file path (.json/.jsonl). "
            "If omitted, built-in DEFAULT_TASKS are used."
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
    parser.add_argument(
        "--enable-context-compression",
        action="store_true",
        help="Override: enable context compression.",
    )
    parser.add_argument(
        "--disable-context-compression",
        action="store_true",
        help="Override: disable context compression.",
    )
    parser.add_argument(
        "--enable-smart-tool",
        action="store_true",
        help="Override: enable smart tool selector.",
    )
    parser.add_argument(
        "--disable-smart-tool",
        action="store_true",
        help="Override: disable smart tool selector.",
    )
    parser.add_argument(
        "--enable-rag",
        action="store_true",
        help="Override: enable RAG stage.",
    )
    parser.add_argument(
        "--disable-rag",
        action="store_true",
        help="Override: disable RAG stage.",
    )
    parser.add_argument(
        "--enable-context-pruning",
        action="store_true",
        help="Override: enable context pruning stage.",
    )
    parser.add_argument(
        "--disable-context-pruning",
        action="store_true",
        help="Override: disable context pruning stage.",
    )
    parser.add_argument(
        "--enable-semantic-cache",
        action="store_true",
        help="Override: enable semantic cache.",
    )
    parser.add_argument(
        "--disable-semantic-cache",
        action="store_true",
        help="Override: disable semantic cache.",
    )
    parser.add_argument(
        "--enable-model-routing",
        action="store_true",
        help="Override: enable model routing.",
    )
    parser.add_argument(
        "--disable-model-routing",
        action="store_true",
        help="Override: disable model routing.",
    )
    parser.add_argument(
        "--enable-agentic-plan-cache",
        action="store_true",
        help="Override: enable agentic plan cache.",
    )
    parser.add_argument(
        "--disable-agentic-plan-cache",
        action="store_true",
        help="Override: disable agentic plan cache.",
    )
    parser.add_argument(
        "--tool-top-k",
        type=int,
        default=None,
        help="Override: smart tool selector top-k.",
    )
    parser.add_argument(
        "--history-summary-chars",
        type=int,
        default=None,
        help="Override: max chars for retry history summary.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.mode == "governor":
        auto_mode_enabled = args.auto_strategy or args.drive_mode == "auto"
        strategy_overrides = build_strategy_overrides(args)
        strategy_config: dict[str, object] | None = None
        model_profiles = load_model_profiles(args.model_profile)
        if auto_mode_enabled and args.opt_strategy not in {"balanced", "auto"}:
            print(
                "[info] auto strategy path is enabled; "
                f"--opt-strategy={args.opt_strategy} is ignored."
            )
        if args.drive_mode == "auto" and not args.auto_strategy:
            print(
                "[info] --drive-mode=auto implies dynamic auto strategy mode."
            )
        if auto_mode_enabled and args.drive_mode:
            print(
                "[info] auto strategy path is enabled with "
                f"--drive-mode={args.drive_mode}; drive mode acts as intent override."
            )
        if not auto_mode_enabled:
            if args.drive_mode:
                strategy_config = resolve_drive_mode(
                    args.drive_mode,
                    overrides=strategy_overrides,
                )
            else:
                strategy_config = resolve_strategy(
                    args.opt_strategy,
                    overrides=strategy_overrides,
                )
        raise SystemExit(
            run_governor(
                model_name=args.model,
                limit=args.limit,
                max_tokens=args.max_tokens,
                max_fallback=args.max_fallback,
                out_file=args.out_file,
                strategy_config=strategy_config,
                strategy_overrides=strategy_overrides,
                auto_strategy=auto_mode_enabled,
                drive_mode=args.drive_mode,
                model_profiles=model_profiles,
                policy_file=args.policy_file,
                tasks_file=args.tasks_file,
            )
        )
    raise SystemExit(
        run_baseline(
            model_name=args.model,
            limit=args.limit,
            out_file=args.out_file,
            tasks_file=args.tasks_file,
        )
    )
