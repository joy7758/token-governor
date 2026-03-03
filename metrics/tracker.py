"""Utilities for recording per-task metrics and run summaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MetricsTracker:
    def __init__(self, output_dir: str = "metrics/data") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.records: list[dict[str, Any]] = []

    def add_record(self, record: dict[str, Any]) -> None:
        self.records.append(record)

    def summary(self) -> dict[str, Any]:
        total = len(self.records)
        success_count = sum(1 for row in self.records if row.get("success"))

        total_input_tokens = sum(int(row.get("input_tokens", 0) or 0) for row in self.records)
        total_output_tokens = sum(
            int(row.get("output_tokens", 0) or 0) for row in self.records
        )
        total_tokens = sum(int(row.get("total_tokens", 0) or 0) for row in self.records)
        total_latency = sum(float(row.get("latency", 0) or 0) for row in self.records)

        return {
            "num_tasks": total,
            "success_count": success_count,
            "success_rate": (success_count / total) if total else 0.0,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
            "avg_tokens_per_task": (total_tokens / total) if total else 0.0,
            "avg_latency": (total_latency / total) if total else 0.0,
            "total_latency": total_latency,
        }

    def save_run(self, mode: str = "baseline") -> dict[str, str]:
        now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        records_path = self.output_dir / f"{mode}-records-{now}.jsonl"
        summary_path = self.output_dir / f"{mode}-summary-{now}.json"

        with records_path.open("w", encoding="utf-8") as file:
            for row in self.records:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")

        summary_payload = {
            "mode": mode,
            "created_at_utc": now,
            "summary": self.summary(),
        }
        with summary_path.open("w", encoding="utf-8") as file:
            json.dump(summary_payload, file, ensure_ascii=False, indent=2)

        return {
            "records_file": str(records_path),
            "summary_file": str(summary_path),
        }


def record_result(
    prompt: str,
    result: dict[str, Any],
    latency: float,
    mode: str = "governor",
    output_dir: str = "metrics/data",
) -> dict[str, Any]:
    """
    Append one result row to a live JSONL file.

    This helper is designed for runtime logging from guarded execution loops.
    """
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    records_path = path / f"{mode}-records-live.jsonl"

    row = {
        "task_id": result.get("task_id"),
        "prompt": prompt,
        "answer": result.get("answer", ""),
        "input_tokens": int(result.get("input_tokens", 0) or 0),
        "output_tokens": int(result.get("output_tokens", 0) or 0),
        "total_tokens": int(result.get("total_tokens", 0) or 0),
        "latency": float(latency),
        "success": bool(result.get("success", False)),
        "mode": mode,
        "error": result.get("error"),
        "logged_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    if "governor_total_tokens" in result:
        row["governor_total_tokens"] = result["governor_total_tokens"]
    if "fallback_count" in result:
        row["fallback_count"] = result["fallback_count"]
    if "strategy" in result:
        row["strategy"] = result["strategy"]
    if "selected_tools" in result:
        row["selected_tools"] = result["selected_tools"]
    if "model" in result:
        row["model"] = result["model"]
    if "strategies_applied" in result:
        row["strategies_applied"] = result["strategies_applied"]
    if "cache_hits" in result:
        row["cache_hits"] = result["cache_hits"]
    if "from_cache" in result:
        row["from_cache"] = bool(result["from_cache"])
    if "from_plan_cache" in result:
        row["from_plan_cache"] = bool(result["from_plan_cache"])
    if "agentic_plan_cache" in result:
        row["agentic_plan_cache"] = bool(result["agentic_plan_cache"])
    if "agentic_plan_key" in result:
        row["agentic_plan_key"] = result["agentic_plan_key"]
    if "plan_cache_similarity" in result:
        row["plan_cache_similarity"] = float(result["plan_cache_similarity"] or 0)
    if "cached_original_total_tokens" in result:
        row["cached_original_total_tokens"] = int(
            result["cached_original_total_tokens"] or 0
        )
    if "strategy_note" in result:
        row["strategy_note"] = result["strategy_note"]
    if "auto_strategy_reasons" in result:
        row["auto_strategy_reasons"] = result["auto_strategy_reasons"]
    if "auto_task_features" in result:
        row["auto_task_features"] = result["auto_task_features"]
    if "auto_selected_strategy" in result:
        row["auto_selected_strategy"] = result["auto_selected_strategy"]
    if "drive_mode" in result:
        row["drive_mode"] = result["drive_mode"]
    if "drive_mode_goal" in result:
        row["drive_mode_goal"] = result["drive_mode_goal"]
    if "drive_mode_description" in result:
        row["drive_mode_description"] = result["drive_mode_description"]
    if "model_profile_hint_mode" in result:
        row["model_profile_hint_mode"] = result["model_profile_hint_mode"]
    if "model_profile_hint_reason" in result:
        row["model_profile_hint_reason"] = result["model_profile_hint_reason"]
    if "task_features" in result:
        row["task_features"] = result["task_features"]

    with records_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")

    return row
