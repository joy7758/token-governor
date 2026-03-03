#!/usr/bin/env python3
"""Guardrail checks for benchmark comparison outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Comparison file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid comparison JSON: top-level object expected")
    return data


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


def _pct_change(new_value: float, base_value: float) -> float:
    if base_value == 0:
        return 0.0
    return ((new_value - base_value) / base_value) * 100.0


def _get_mode_summary(data: dict[str, Any], mode: str) -> dict[str, float]:
    modes = data.get("modes")
    if isinstance(modes, dict) and mode in modes:
        return _extract_summary(modes[mode])

    # backward compatibility for older single-mode shape
    if mode in data:
        return _extract_summary(data[mode])

    available: list[str] = []
    if isinstance(modes, dict):
        available.extend(sorted(modes.keys()))
    for name in ("governor", "eco", "auto", "comfort", "sport", "rocket"):
        if name in data and name not in available:
            available.append(name)
    raise ValueError(f"Mode '{mode}' not found. Available: {', '.join(available) if available else 'none'}")


def build_guardrail_report(
    *,
    comparison: dict[str, Any],
    mode: str,
    max_success_drop_pp: float,
    max_token_increase_pct: float,
    max_latency_increase_pct: float,
) -> tuple[dict[str, Any], bool]:
    baseline = _extract_summary(comparison.get("baseline"))
    selected = _get_mode_summary(comparison, mode)

    success_drop_pp = (baseline["success_rate"] - selected["success_rate"]) * 100.0
    token_increase_pct = _pct_change(selected["mean_token"], baseline["mean_token"])
    latency_increase_pct = _pct_change(selected["mean_latency"], baseline["mean_latency"])

    checks = {
        "success_drop_pp": {
            "value": round(success_drop_pp, 4),
            "threshold": max_success_drop_pp,
            "pass": success_drop_pp <= max_success_drop_pp,
            "note": "pass when governor success drop is within threshold",
        },
        "token_increase_pct": {
            "value": round(token_increase_pct, 4),
            "threshold": max_token_increase_pct,
            "pass": token_increase_pct <= max_token_increase_pct,
            "note": "pass when mean token increase is within threshold",
        },
        "latency_increase_pct": {
            "value": round(latency_increase_pct, 4),
            "threshold": max_latency_increase_pct,
            "pass": latency_increase_pct <= max_latency_increase_pct,
            "note": "pass when mean latency increase is within threshold",
        },
    }

    passed = all(item["pass"] for item in checks.values())

    report = {
        "mode": mode,
        "baseline": baseline,
        "selected": selected,
        "checks": checks,
        "pass": passed,
    }
    return report, passed


def _markdown_report(report: dict[str, Any], comparison_path: Path) -> str:
    checks = report["checks"]
    status = "PASS" if report["pass"] else "FAIL"

    lines: list[str] = []
    lines.append("# Benchmark Guardrail Result")
    lines.append("")
    lines.append(f"- Status: **{status}**")
    lines.append(f"- Comparison: `{comparison_path}`")
    lines.append(f"- Mode: `{report['mode']}`")
    lines.append("")
    lines.append("## Check Results")
    lines.append("")
    lines.append("| Check | Value | Threshold | Pass |")
    lines.append("| --- | ---: | ---: | --- |")
    for key in ("success_drop_pp", "token_increase_pct", "latency_increase_pct"):
        row = checks[key]
        lines.append(
            f"| `{key}` | {row['value']:.4f} | {row['threshold']:.4f} | {'yes' if row['pass'] else 'no'} |"
        )
    lines.append("")
    lines.append("## Baseline vs Selected")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps({"baseline": report["baseline"], "selected": report["selected"]}, ensure_ascii=False, indent=2))
    lines.append("```")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check benchmark guardrail thresholds.")
    parser.add_argument(
        "--comparison",
        required=True,
        help="Path to comparison.json generated by metrics.report",
    )
    parser.add_argument(
        "--mode",
        default="governor",
        help="Optimized mode to check against baseline",
    )
    parser.add_argument(
        "--max-success-drop-pp",
        type=float,
        default=2.0,
        help="Fail if success rate drop (percentage points) is greater than this value",
    )
    parser.add_argument(
        "--max-token-increase-pct",
        type=float,
        default=25.0,
        help="Fail if mean token increase percent is greater than this value",
    )
    parser.add_argument(
        "--max-latency-increase-pct",
        type=float,
        default=50.0,
        help="Fail if mean latency increase percent is greater than this value",
    )
    parser.add_argument(
        "--out-json",
        default=None,
        help="Optional output path for guardrail JSON report",
    )
    parser.add_argument(
        "--out-markdown",
        default=None,
        help="Optional output path for guardrail markdown report",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    comparison_path = Path(args.comparison)
    comparison = _load_json(comparison_path)

    report, passed = build_guardrail_report(
        comparison=comparison,
        mode=args.mode,
        max_success_drop_pp=args.max_success_drop_pp,
        max_token_increase_pct=args.max_token_increase_pct,
        max_latency_increase_pct=args.max_latency_increase_pct,
    )

    if args.out_json:
        out_json = Path(args.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[guardrail] wrote json: {out_json}")

    md_text = _markdown_report(report, comparison_path)
    if args.out_markdown:
        out_md = Path(args.out_markdown)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(md_text + "\n", encoding="utf-8")
        print(f"[guardrail] wrote markdown: {out_md}")

    print("[guardrail] mode:", report["mode"])
    print("[guardrail] pass:", report["pass"])
    for key in ("success_drop_pp", "token_increase_pct", "latency_increase_pct"):
        row = report["checks"][key]
        print(f"[guardrail] {key}: value={row['value']:.4f} threshold={row['threshold']:.4f} pass={row['pass']}")

    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
