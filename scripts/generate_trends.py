#!/usr/bin/env python3
"""Generate trends JSON from benchmark history JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_history(path: Path) -> list[dict[str, Any]]:
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


def _extract_metric(record: dict[str, Any], metric: str) -> float:
    metrics = record.get("metrics", {})
    if isinstance(metrics, dict) and metric in metrics:
        try:
            return float(metrics.get(metric, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(record.get(metric, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate trend JSON from history")
    parser.add_argument("--history", required=True, help="History JSONL path")
    parser.add_argument("--metric", required=True, help="Metric key")
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--mode", default=None, help="Optional mode filter")
    parser.add_argument("--run-label", default=None, help="Optional run_label filter")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    history_path = Path(args.history)
    out_path = Path(args.out)

    if not history_path.exists():
        raise FileNotFoundError(f"History not found: {history_path}")

    rows = _load_history(history_path)

    if args.mode:
        rows = [row for row in rows if str(row.get("mode", "")) == args.mode]
    if args.run_label:
        rows = [row for row in rows if str(row.get("run_label", "")) == args.run_label]

    rows.sort(key=lambda row: str(row.get("timestamp_utc", row.get("date", ""))))

    dates: list[str] = []
    values: list[float] = []
    for row in rows:
        dates.append(str(row.get("date", "")))
        values.append(_extract_metric(row, args.metric))

    payload = {
        "metric": args.metric,
        "mode": args.mode,
        "run_label": args.run_label,
        "dates": dates,
        "values": values,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[trends] metric={args.metric} points={len(values)} out={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
