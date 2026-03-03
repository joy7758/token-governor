#!/usr/bin/env python3
"""Append benchmark run summary into history JSONL for trends/KPI."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid JSON object: {path}")
    return data


def _parse_iso_time(value: str | None) -> datetime:
    if value:
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _extract_summary(block: Any) -> dict[str, float]:
    if isinstance(block, dict) and "summary" in block and isinstance(block["summary"], dict):
        block = block["summary"]
    if not isinstance(block, dict):
        raise ValueError("Invalid summary block")

    return {
        "count": float(block.get("count", 0.0) or 0.0),
        "mean_token": float(block.get("mean_token", 0.0) or 0.0),
        "p95_token": float(block.get("p95_token", 0.0) or 0.0),
        "success_rate": float(block.get("success_rate", 0.0) or 0.0),
        "mean_latency": float(block.get("mean_latency", 0.0) or 0.0),
        "fallback_trigger_rate": float(block.get("fallback_trigger_rate", 0.0) or 0.0),
    }


def _select_mode_summary(payload: dict[str, Any], mode: str) -> dict[str, float]:
    modes = payload.get("modes")
    if isinstance(modes, dict) and mode in modes:
        return _extract_summary(modes[mode])

    if mode in payload:
        return _extract_summary(payload[mode])

    raise ValueError(f"Mode '{mode}' not found in comparison payload")


def _load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if isinstance(data, dict):
                rows.append(data)
    return rows


def _token_savings_pct(baseline: dict[str, float], selected: dict[str, float]) -> float:
    baseline_token = baseline.get("mean_token", 0.0)
    if baseline_token <= 0:
        return 0.0
    return ((baseline_token - selected.get("mean_token", 0.0)) / baseline_token) * 100.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append benchmark history point")
    parser.add_argument("--comparison", required=True, help="comparison.json path")
    parser.add_argument("--mode", default="governor", help="mode to record")
    parser.add_argument(
        "--history",
        default="metrics/reports/all_runs_history.jsonl",
        help="history JSONL path",
    )
    parser.add_argument(
        "--run-label",
        default="v02",
        help="optional run label, e.g., daily-light / full",
    )
    parser.add_argument(
        "--replace-same-day",
        action="store_true",
        help="replace existing same date+mode record",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    comparison_path = Path(args.comparison)
    history_path = Path(args.history)

    payload = _load_json(comparison_path)
    baseline = _extract_summary(payload.get("baseline", {}))
    selected = _select_mode_summary(payload, args.mode)

    generated_at_raw = str(payload.get("generated_at_utc", "") or "")
    generated_at = _parse_iso_time(generated_at_raw)

    token_savings_pct = _token_savings_pct(baseline, selected)

    record = {
        "date": generated_at.date().isoformat(),
        "timestamp_utc": generated_at.isoformat(),
        "mode": args.mode,
        "run_label": args.run_label,
        "metrics": {
            "success_rate": selected["success_rate"],
            "token_savings_pct": token_savings_pct,
            "mean_token": selected["mean_token"],
            "mean_latency": selected["mean_latency"],
            "fallback_trigger_rate": selected["fallback_trigger_rate"],
            "baseline_success_rate": baseline["success_rate"],
            "baseline_mean_token": baseline["mean_token"],
            "baseline_mean_latency": baseline["mean_latency"],
        },
    }

    rows = _load_history(history_path)
    if args.replace_same_day:
        rows = [
            row
            for row in rows
            if not (
                str(row.get("date", "")) == record["date"]
                and str(row.get("mode", "")) == record["mode"]
                and str(row.get("run_label", "")) == record["run_label"]
            )
        ]
    rows.append(record)
    rows.sort(key=lambda row: str(row.get("timestamp_utc", "")))

    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"[history] appended: mode={record['mode']} date={record['date']}")
    print(f"[history] output: {history_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
