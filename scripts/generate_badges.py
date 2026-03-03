#!/usr/bin/env python3
"""Generate local SVG badges from benchmark summary CSV."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.sax.saxutils as saxutils

import pandas as pd


def _pick_color(value: float, *, good: float, warn: float, inverse: bool = False) -> str:
    if inverse:
        if value <= good:
            return "4c1"
        if value <= warn:
            return "dfb317"
        return "e05d44"
    if value >= good:
        return "4c1"
    if value >= warn:
        return "dfb317"
    return "e05d44"


def _text_width(text: str) -> int:
    return max(24, int(len(text) * 7 + 10))


def _badge_svg(label: str, value: str, color: str) -> str:
    label = saxutils.escape(label)
    value = saxutils.escape(value)
    lw = _text_width(label)
    rw = _text_width(value)
    w = lw + rw

    return f"""<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{w}\" height=\"20\" role=\"img\" aria-label=\"{label}: {value}\">
  <linearGradient id=\"g\" x2=\"0\" y2=\"100%\">
    <stop offset=\"0\" stop-color=\"#fff\" stop-opacity=\".7\"/>
    <stop offset=\".1\" stop-color=\"#aaa\" stop-opacity=\".1\"/>
    <stop offset=\".9\" stop-opacity=\".3\"/>
    <stop offset=\"1\" stop-opacity=\".5\"/>
  </linearGradient>
  <rect rx=\"3\" width=\"{w}\" height=\"20\" fill=\"#555\"/>
  <rect rx=\"3\" x=\"{lw}\" width=\"{rw}\" height=\"20\" fill=\"#{color}\"/>
  <path fill=\"#{color}\" d=\"M{lw} 0h4v20h-4z\"/>
  <rect rx=\"3\" width=\"{w}\" height=\"20\" fill=\"url(#g)\"/>
  <g fill=\"#fff\" text-anchor=\"middle\" font-family=\"Verdana,Geneva,DejaVu Sans,sans-serif\" text-rendering=\"geometricPrecision\" font-size=\"11\">
    <text x=\"{lw / 2}\" y=\"15\" fill=\"#010101\" fill-opacity=\".3\">{label}</text>
    <text x=\"{lw / 2}\" y=\"14\">{label}</text>
    <text x=\"{lw + rw / 2}\" y=\"15\" fill=\"#010101\" fill-opacity=\".3\">{value}</text>
    <text x=\"{lw + rw / 2}\" y=\"14\">{value}</text>
  </g>
</svg>
"""


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return default


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate local SVG badges")
    parser.add_argument(
        "--metrics",
        required=True,
        help="Path to overall_summary.csv",
    )
    parser.add_argument(
        "--outdir",
        default="docs/badges",
        help="Output directory",
    )
    parser.add_argument(
        "--mode",
        default="governor",
        help="Target mode row to visualize",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    df = pd.read_csv(args.metrics)

    target = df[df["run_label"] == args.mode]
    if target.empty:
        raise ValueError(f"Mode '{args.mode}' not found in {args.metrics}")

    target_row = target.iloc[0]
    baseline = df[df["run_label"] == "baseline"]

    success = _as_float(target_row.get("success_rate_pct"), 0.0)
    latency = _as_float(target_row.get("mean_latency_ms"), 0.0)
    fallback = _as_float(target_row.get("fallback_rate_pct"), 0.0)

    token_savings = 0.0
    if not baseline.empty:
        base_token = _as_float(baseline.iloc[0].get("mean_token"), 0.0)
        target_token = _as_float(target_row.get("mean_token"), 0.0)
        if base_token > 0:
            token_savings = ((base_token - target_token) / base_token) * 100.0

    payload = {
        "mode": args.mode,
        "success_rate_pct": success,
        "token_savings_pct": token_savings,
        "mean_latency_ms": latency,
        "fallback_rate_pct": fallback,
    }

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    badges = {
        "success_rate.svg": (
            "success rate",
            f"{success:.1f}%",
            _pick_color(success, good=95.0, warn=90.0),
        ),
        "token_savings.svg": (
            "token savings",
            f"{token_savings:.1f}%",
            _pick_color(token_savings, good=35.0, warn=15.0),
        ),
        "latency.svg": (
            "latency",
            f"{latency:.0f}ms",
            _pick_color(latency, good=200.0, warn=400.0, inverse=True),
        ),
        "fallback_rate.svg": (
            "fallback",
            f"{fallback:.1f}%",
            _pick_color(fallback, good=10.0, warn=20.0, inverse=True),
        ),
    }

    for filename, (label, value, color) in badges.items():
        svg = _badge_svg(label, value, color)
        (outdir / filename).write_text(svg, encoding="utf-8")

    status_path = outdir / "status.json"
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[badges] outdir: {outdir}")
    print(f"[badges] status: {status_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
