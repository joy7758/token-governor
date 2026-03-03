"""Build model profile JSON from run records for adaptive optimization."""

from __future__ import annotations

import argparse
import glob
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RECOMMENDABLE_MODES = {"auto", "eco", "comfort", "sport", "rocket"}
MANUAL_TO_DRIVE_MODE = {
    "light": "eco",
    "balanced": "comfort",
    "knowledge": "sport",
    "enterprise": "rocket",
}


def parse_inputs(patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        matches = sorted(Path(path_text) for path_text in glob.glob(pattern))
        if matches:
            files.extend(matches)
            continue
        path = Path(pattern)
        if path.exists():
            files.append(path)

    unique: list[Path] = []
    seen: set[str] = set()
    for file_path in files:
        key = str(file_path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(file_path)
    return unique


def load_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    rows.append(json.loads(line))
    return rows


def safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def safe_quality(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    sorted_vals = sorted(values)
    rank = (len(sorted_vals) - 1) * p
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(sorted_vals[low])
    low_val = sorted_vals[low]
    high_val = sorted_vals[high]
    return float(low_val + (high_val - low_val) * (rank - low))


def detect_mode(row: dict[str, Any]) -> str:
    drive_mode = safe_str(row.get("drive_mode"), "").strip().lower()
    if drive_mode:
        return drive_mode

    strategy = row.get("strategy")
    if isinstance(strategy, dict):
        opt_strategy = safe_str(strategy.get("opt_strategy"), "").strip().lower()
        if opt_strategy in MANUAL_TO_DRIVE_MODE:
            return MANUAL_TO_DRIVE_MODE[opt_strategy]
        if opt_strategy:
            return opt_strategy

    mode = safe_str(row.get("mode"), "").strip().lower()
    if mode:
        return mode
    return "unspecified"


def normalize_record(row: dict[str, Any]) -> dict[str, Any]:
    total_tokens = safe_float(row.get("total_tokens"))
    prompt_tokens = safe_float(row.get("input_tokens"))
    response_tokens = safe_float(row.get("output_tokens"))
    latency_ms = safe_float(row.get("latency")) * 1000.0
    success = 1.0 if bool(row.get("success")) else 0.0

    cache_hits = row.get("cache_hits")
    semantic_hit = False
    plan_hit = False
    if isinstance(cache_hits, dict):
        semantic_hit = bool(cache_hits.get("semantic", False))
        plan_hit = bool(cache_hits.get("plan_cache", False))

    if bool(row.get("from_plan_cache", False)):
        plan_hit = True
    if bool(row.get("from_cache", False)) and not bool(row.get("from_plan_cache", False)):
        semantic_hit = True

    raw_tokens = safe_float(row.get("cached_original_total_tokens"))
    if raw_tokens <= 0:
        raw_tokens = total_tokens
    compression_rate = 1.0
    if raw_tokens > 0:
        compression_rate = max(0.0, min(1.0, total_tokens / raw_tokens))

    return {
        "mode": detect_mode(row),
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "response_tokens": response_tokens,
        "latency_ms": latency_ms,
        "success": success,
        "quality_score": safe_quality(row.get("quality_score")),
        "semantic_hit": 1.0 if semantic_hit else 0.0,
        "plan_hit": 1.0 if plan_hit else 0.0,
        "compression_rate": compression_rate,
    }


def summarize_bucket(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "count": 0,
            "avg_tokens": 0.0,
            "avg_prompt_tokens": 0.0,
            "avg_response_tokens": 0.0,
            "median_tokens": 0.0,
            "p95_tokens": 0.0,
            "success_rate": 0.0,
            "avg_latency_ms": 0.0,
            "quality_score": None,
            "semantic_cache_hit_rate": 0.0,
            "plan_cache_hit_rate": 0.0,
            "compression_rate": 1.0,
        }

    tokens = [row["total_tokens"] for row in records]
    prompt_tokens = [row["prompt_tokens"] for row in records]
    response_tokens = [row["response_tokens"] for row in records]
    latencies = [row["latency_ms"] for row in records]
    successes = [row["success"] for row in records]
    semantic_hits = [row["semantic_hit"] for row in records]
    plan_hits = [row["plan_hit"] for row in records]
    compressions = [row["compression_rate"] for row in records]
    quality_values = [
        row["quality_score"] for row in records if row["quality_score"] is not None
    ]

    count = len(records)
    return {
        "count": count,
        "avg_tokens": sum(tokens) / count,
        "avg_prompt_tokens": sum(prompt_tokens) / count,
        "avg_response_tokens": sum(response_tokens) / count,
        "median_tokens": percentile(tokens, 0.50),
        "p95_tokens": percentile(tokens, 0.95),
        "success_rate": sum(successes) / count,
        "avg_latency_ms": sum(latencies) / count,
        "quality_score": (sum(quality_values) / len(quality_values)) if quality_values else None,
        "semantic_cache_hit_rate": sum(semantic_hits) / count,
        "plan_cache_hit_rate": sum(plan_hits) / count,
        "compression_rate": sum(compressions) / count,
    }


def infer_tags(
    overall: dict[str, Any],
    strategy_performance: dict[str, dict[str, Any]],
) -> list[str]:
    tags: list[str] = []
    if overall["semantic_cache_hit_rate"] >= 0.20:
        tags.append("cache_friendly")
    if overall["plan_cache_hit_rate"] >= 0.05:
        tags.append("plan_cache_friendly")
    if overall["avg_latency_ms"] <= 8000:
        tags.append("fast")
    if overall["p95_tokens"] >= 4000:
        tags.append("long_context_active")
    if overall["success_rate"] >= 0.95:
        tags.append("stable")
    if "rocket" in strategy_performance:
        tags.append("high_quality_capable")
    if "eco" in strategy_performance:
        tags.append("cost_optimized")
    if not tags:
        tags.append("general")
    return sorted(set(tags))


def parse_model_version(model_name: str) -> str | None:
    if ":" not in model_name:
        return None
    _, _, version = model_name.partition(":")
    return version.strip() or None


def choose_best_modes(mode_stats: dict[str, dict[str, Any]]) -> dict[str, str]:
    candidates = {
        name: stats
        for name, stats in mode_stats.items()
        if name in RECOMMENDABLE_MODES and stats["count"] > 0
    }
    if not candidates:
        candidates = {
            name: stats
            for name, stats in mode_stats.items()
            if name not in {"baseline", "unspecified"} and stats["count"] > 0
        }
    if not candidates:
        return {
            "best_cost_mode": "eco",
            "best_quality_mode": "sport",
            "best_balance_mode": "comfort",
        }

    best_cost = min(
        candidates.items(),
        key=lambda item: (item[1]["avg_tokens"], item[1]["avg_latency_ms"]),
    )[0]

    def quality_signal(stats: dict[str, Any]) -> float:
        if stats["quality_score"] is not None:
            return float(stats["quality_score"])
        return float(stats["success_rate"])

    best_quality = max(
        candidates.items(),
        key=lambda item: (
            quality_signal(item[1]),
            item[1]["success_rate"],
            -item[1]["avg_latency_ms"],
        ),
    )[0]

    def balance_score(stats: dict[str, Any]) -> float:
        return (
            quality_signal(stats) * 100.0
            - stats["avg_tokens"] / 1000.0
            - stats["avg_latency_ms"] / 2000.0
        )

    non_rocket = {name: s for name, s in candidates.items() if name != "rocket"} or candidates
    best_balance = max(non_rocket.items(), key=lambda item: balance_score(item[1]))[0]

    return {
        "best_cost_mode": best_cost,
        "best_quality_mode": best_quality,
        "best_balance_mode": best_balance,
    }


def to_legacy_modes(strategy_performance: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    legacy: dict[str, dict[str, float]] = {}
    for mode, stats in strategy_performance.items():
        legacy[mode] = {
            "count": float(stats["count"]),
            "mean_token": float(stats["avg_tokens"]),
            "mean_latency": float(stats["avg_latency_ms"] / 1000.0),
            "success_rate": float(stats["success_rate"]),
        }
    return legacy


def build_profiles(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        model = safe_str(row.get("model"), "unknown")
        grouped[model][detect_mode(row)].append(normalize_record(row))

    now_utc = datetime.now(timezone.utc).isoformat()
    profiles: dict[str, Any] = {}
    for model_name, mode_records in grouped.items():
        per_mode: dict[str, dict[str, Any]] = {}
        all_records: list[dict[str, Any]] = []
        for mode, records in mode_records.items():
            per_mode[mode] = summarize_bucket(records)
            all_records.extend(records)

        overall = summarize_bucket(all_records)
        best = choose_best_modes(per_mode)

        profiles[model_name] = {
            "model_name": model_name,
            "version": parse_model_version(model_name),
            "tag": infer_tags(overall, per_mode),
            "total_runs": int(overall["count"]),
            "avg_tokens": float(overall["avg_tokens"]),
            "avg_prompt_tokens": float(overall["avg_prompt_tokens"]),
            "avg_response_tokens": float(overall["avg_response_tokens"]),
            "median_tokens": float(overall["median_tokens"]),
            "p95_tokens": float(overall["p95_tokens"]),
            "success_rate": float(overall["success_rate"]),
            "avg_latency_ms": float(overall["avg_latency_ms"]),
            "quality_score": (
                float(overall["quality_score"])
                if overall["quality_score"] is not None
                else None
            ),
            "semantic_cache_hit_rate": float(overall["semantic_cache_hit_rate"]),
            "plan_cache_hit_rate": float(overall["plan_cache_hit_rate"]),
            "compression_rate": float(overall["compression_rate"]),
            "strategy_performance": per_mode,
            "last_updated": now_utc,
            "entries_sampled": int(overall["count"]),
            # Backward compatibility for current runtime consumer.
            "modes": to_legacy_modes(per_mode),
            **best,
        }

    return {
        "schema_version": "1.0.0",
        "version": "0.2.0",
        "generated_at_utc": now_utc,
        "models": profiles,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build model profile from run records.")
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help=(
            "Input JSONL file path or glob pattern. "
            "Repeatable. Example: --input 'metrics/data/*-real.jsonl'"
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        default="metrics/profiles/model_profiles.json",
        help="Output model profile JSON path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inputs = args.input or ["metrics/data/governor-records-live.jsonl"]
    paths = parse_inputs(inputs)
    if not paths:
        print("[error] No input files matched.")
        return 2

    rows = load_rows(paths)
    if not rows:
        print("[error] Input files are empty.")
        return 2

    profile = build_profiles(rows)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(profile, file, indent=2, ensure_ascii=False)

    print(f"Saved model profile: {output_path}")
    print(f"Models: {len(profile['models'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
