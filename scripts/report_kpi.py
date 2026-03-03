#!/usr/bin/env python3
"""Generate KPI summary from benchmark history JSONL."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


METRIC_KEYS = (
    "success_rate",
    "token_savings_pct",
    "mean_latency",
    "fallback_trigger_rate",
)


def _parse_time(raw: str | None) -> datetime:
    if raw:
        text = raw.strip()
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


def _load_history(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if not isinstance(data, dict):
                continue
            data["_time"] = _parse_time(str(data.get("timestamp_utc", "") or ""))
            rows.append(data)
    rows.sort(key=lambda row: row.get("_time"))
    return rows


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return default


def _metric_value(row: dict[str, Any], key: str) -> float:
    metrics = row.get("metrics", {})
    if isinstance(metrics, dict) and key in metrics:
        return _as_float(metrics.get(key), 0.0)
    return _as_float(row.get(key), 0.0)


def _window_average(rows: list[dict[str, Any]], since: datetime, key: str) -> float:
    values = [_metric_value(row, key) for row in rows if row.get("_time") >= since]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _to_markdown(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# KPI Summary")
    lines.append("")
    lines.append(f"- Mode: `{summary['mode']}`")
    lines.append(f"- Run label: `{summary['run_label']}`")
    lines.append(f"- History file: `{summary['history_file']}`")
    lines.append(f"- Data points: `{summary['data_points']}`")
    lines.append("")
    lines.append("| Metric | Current | 7d Avg | 30d Avg |")
    lines.append("| --- | ---: | ---: | ---: |")

    current = summary["current"]
    avg_7d = summary["avg_7d"]
    avg_30d = summary["avg_30d"]

    lines.append(
        f"| success_rate | {current['success_rate']:.4f} | {avg_7d['success_rate']:.4f} | {avg_30d['success_rate']:.4f} |"
    )
    lines.append(
        f"| token_savings_pct | {current['token_savings_pct']:.4f} | {avg_7d['token_savings_pct']:.4f} | {avg_30d['token_savings_pct']:.4f} |"
    )
    lines.append(
        f"| mean_latency | {current['mean_latency']:.4f} | {avg_7d['mean_latency']:.4f} | {avg_30d['mean_latency']:.4f} |"
    )
    lines.append(
        f"| fallback_trigger_rate | {current['fallback_trigger_rate']:.4f} | {avg_7d['fallback_trigger_rate']:.4f} | {avg_30d['fallback_trigger_rate']:.4f} |"
    )

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate KPI report from history")
    parser.add_argument("--history", required=True, help="History JSONL file")
    parser.add_argument("--mode", default="governor", help="Mode filter")
    parser.add_argument("--run-label", default=None, help="Optional run label filter")
    parser.add_argument("--out-json", required=True, help="Output JSON path")
    parser.add_argument("--out-markdown", required=True, help="Output markdown path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    history_path = Path(args.history)
    rows = _load_history(history_path)

    if args.mode:
        rows = [row for row in rows if str(row.get("mode", "")) == args.mode]
    if args.run_label:
        rows = [row for row in rows if str(row.get("run_label", "")) == args.run_label]

    if not rows:
        raise ValueError("No history rows matched the given filters")

    now = rows[-1].get("_time") or datetime.now(timezone.utc)
    since_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)

    current_row = rows[-1]
    current = {key: _metric_value(current_row, key) for key in METRIC_KEYS}
    avg_7d = {key: _window_average(rows, since_7d, key) for key in METRIC_KEYS}
    avg_30d = {key: _window_average(rows, since_30d, key) for key in METRIC_KEYS}

    summary = {
        "history_file": str(history_path),
        "mode": args.mode,
        "run_label": args.run_label,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_points": len(rows),
        "current": current,
        "avg_7d": avg_7d,
        "avg_30d": avg_30d,
    }

    out_json = Path(args.out_json)
    out_md = Path(args.out_markdown)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_to_markdown(summary) + "\n", encoding="utf-8")

    print(f"[kpi] json: {out_json}")
    print(f"[kpi] markdown: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
