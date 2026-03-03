"""Multi-mode benchmark report generator for baseline vs drive modes."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MODE_ORDER = ("governor", "eco", "auto", "comfort", "sport", "rocket")


def load_records(file_path: Path) -> list[dict[str, Any]]:
    with file_path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


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


def summarize(records: list[dict[str, Any]]) -> dict[str, float]:
    tokens = [float(row.get("total_tokens", 0) or 0) for row in records]
    latencies = [float(row.get("latency", 0) or 0) for row in records]
    successes = [1.0 if row.get("success") else 0.0 for row in records]

    fallback_events = 0.0
    for row in records:
        fallback_count = int(row.get("fallback_count", 0) or 0)
        err = str(row.get("error", "") or "").lower()
        if fallback_count > 0 or "fallback" in err:
            fallback_events += 1.0

    count = float(len(records))
    if not records:
        return {
            "count": 0.0,
            "mean_token": 0.0,
            "p50_token": 0.0,
            "p95_token": 0.0,
            "success_rate": 0.0,
            "mean_latency": 0.0,
            "fallback_trigger_rate": 0.0,
        }

    return {
        "count": count,
        "mean_token": statistics.mean(tokens),
        "p50_token": percentile(tokens, 0.50),
        "p95_token": percentile(tokens, 0.95),
        "success_rate": statistics.mean(successes),
        "mean_latency": statistics.mean(latencies),
        "fallback_trigger_rate": fallback_events / count,
    }


def pct_change(value: float, baseline: float) -> float:
    if baseline == 0:
        return 0.0
    return ((value - baseline) / baseline) * 100.0


def diff_vs_baseline(
    mode_summary: dict[str, float],
    baseline_summary: dict[str, float],
) -> dict[str, float]:
    return {
        "mean_token_pct": pct_change(
            mode_summary["mean_token"],
            baseline_summary["mean_token"],
        ),
        "p95_token_pct": pct_change(
            mode_summary["p95_token"],
            baseline_summary["p95_token"],
        ),
        "mean_latency_pct": pct_change(
            mode_summary["mean_latency"],
            baseline_summary["mean_latency"],
        ),
        "success_rate_pp": (
            mode_summary["success_rate"] - baseline_summary["success_rate"]
        )
        * 100.0,
        "fallback_trigger_rate_pp": (
            mode_summary["fallback_trigger_rate"]
            - baseline_summary["fallback_trigger_rate"]
        )
        * 100.0,
    }


def save_json(data: dict[str, Any], outpath: Path) -> None:
    with outpath.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def _ordered_mode_names(mode_names: list[str]) -> list[str]:
    ordered = [name for name in DEFAULT_MODE_ORDER if name in mode_names]
    ordered += [name for name in mode_names if name not in ordered]
    return ordered


def _mode_table_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    baseline = summary["baseline"]
    modes = summary["modes"]
    rows: list[dict[str, Any]] = [
        {
            "mode": "baseline",
            "summary": baseline,
            "vs_baseline": {
                "mean_token_pct": 0.0,
                "p95_token_pct": 0.0,
                "mean_latency_pct": 0.0,
                "success_rate_pp": 0.0,
                "fallback_trigger_rate_pp": 0.0,
            },
        }
    ]
    for name in _ordered_mode_names(list(modes.keys())):
        rows.append({"mode": name, **modes[name]})
    return rows


def plot_comparison(summary: dict[str, Any], outdir: Path) -> Path:
    import matplotlib.pyplot as plt

    rows = _mode_table_rows(summary)
    labels = [row["mode"] for row in rows]

    mean_tokens = [row["summary"]["mean_token"] for row in rows]
    p95_tokens = [row["summary"]["p95_token"] for row in rows]
    latencies = [row["summary"]["mean_latency"] for row in rows]
    success_rates = [row["summary"]["success_rate"] * 100.0 for row in rows]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))

    axes[0][0].bar(labels, mean_tokens)
    axes[0][0].set_title("Mean Token")
    axes[0][0].tick_params(axis="x", rotation=20)

    axes[0][1].bar(labels, p95_tokens)
    axes[0][1].set_title("P95 Token")
    axes[0][1].tick_params(axis="x", rotation=20)

    axes[1][0].bar(labels, latencies)
    axes[1][0].set_title("Mean Latency (s)")
    axes[1][0].tick_params(axis="x", rotation=20)

    axes[1][1].bar(labels, success_rates)
    axes[1][1].set_title("Success Rate (%)")
    axes[1][1].tick_params(axis="x", rotation=20)

    fig.suptitle("Baseline vs Multi-Mode Summary")
    fig.tight_layout()

    outpath = outdir / "comparison_summary.png"
    fig.savefig(outpath)
    plt.close(fig)
    return outpath


def plot_interactive(summary: dict[str, Any], outdir: Path) -> Path:
    try:
        import pandas as pd
        import plotly.express as px
    except ImportError as exc:
        raise RuntimeError(
            "Interactive plot needs plotly and pandas. Run: pip install plotly pandas"
        ) from exc

    rows = _mode_table_rows(summary)
    table_rows: list[dict[str, Any]] = []
    metric_keys = ("mean_token", "p95_token", "mean_latency", "success_rate")
    for row in rows:
        mode_name = str(row["mode"])
        for metric in metric_keys:
            value = row["summary"][metric]
            if metric == "success_rate":
                value = value * 100.0
            table_rows.append({"mode": mode_name, "metric": metric, "value": value})

    frame = pd.DataFrame(table_rows)
    fig = px.bar(
        frame,
        x="mode",
        y="value",
        color="mode",
        facet_col="metric",
        facet_col_wrap=2,
        title="Baseline vs Multi-Mode Summary (Interactive)",
    )
    fig.update_layout(showlegend=False)

    outpath = outdir / "comparison_summary.html"
    fig.write_html(str(outpath), include_plotlyjs="cdn")
    return outpath


def _fmt_num(value: float) -> str:
    return f"{value:.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _fmt_delta_pct(value: float) -> str:
    return f"{value:+.2f}%"


def _fmt_delta_pp(value: float) -> str:
    return f"{value:+.2f}pp"


def write_markdown(summary: dict[str, Any], outpath: Path) -> None:
    rows = _mode_table_rows(summary)
    with outpath.open("w", encoding="utf-8") as md:
        md.write("# Baseline vs Multi-Mode Report\n\n")
        md.write(f"- Generated UTC: `{summary['generated_at_utc']}`\n")
        md.write(f"- Baseline file: `{summary['baseline_file']}`\n\n")

        md.write("## Comparison Table\n\n")
        md.write(
            "| Mode | Mean Token | ΔToken vs Baseline | P95 Token | ΔP95 vs Baseline | "
            "Success Rate | ΔSuccess | Mean Latency(s) | ΔLatency |\n"
        )
        md.write(
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n"
        )
        for row in rows:
            name = row["mode"]
            s = row["summary"]
            d = row["vs_baseline"]
            md.write(
                f"| `{name}` | {_fmt_num(s['mean_token'])} | {_fmt_delta_pct(d['mean_token_pct'])} "
                f"| {_fmt_num(s['p95_token'])} | {_fmt_delta_pct(d['p95_token_pct'])} "
                f"| {_fmt_pct(s['success_rate'])} | {_fmt_delta_pp(d['success_rate_pp'])} "
                f"| {_fmt_num(s['mean_latency'])} | {_fmt_delta_pct(d['mean_latency_pct'])} |\n"
            )

        md.write("\n## Raw Summary JSON\n\n")
        md.write(f"```json\n{json.dumps(summary, indent=2, ensure_ascii=False)}\n```\n")


def run_report(
    baseline_file: Path,
    mode_files: dict[str, Path],
    outdir: Path,
    interactive: bool = False,
) -> dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)

    baseline_records = load_records(baseline_file)
    baseline_summary = summarize(baseline_records)

    modes: dict[str, dict[str, Any]] = {}
    for mode_name, file_path in mode_files.items():
        records = load_records(file_path)
        mode_summary = summarize(records)
        modes[mode_name] = {
            "file": str(file_path),
            "summary": mode_summary,
            "vs_baseline": diff_vs_baseline(mode_summary, baseline_summary),
        }

    summary: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_file": str(baseline_file),
        "mode_files": {name: str(path) for name, path in mode_files.items()},
        "baseline": baseline_summary,
        "modes": modes,
    }

    # Backward compatibility for older consumers expecting `governor` top-level.
    if "governor" in modes:
        summary["governor_file"] = modes["governor"]["file"]
        summary["governor"] = modes["governor"]["summary"]

    json_path = outdir / "comparison.json"
    md_path = outdir / "comparison.md"
    png_path = plot_comparison(summary, outdir)

    save_json(summary, json_path)
    write_markdown(summary, md_path)

    outputs: dict[str, Path] = {
        "json": json_path,
        "markdown": md_path,
        "plot_png": png_path,
    }

    if interactive:
        outputs["plot_html"] = plot_interactive(summary, outdir)
    return outputs


def collect_mode_files(args: argparse.Namespace) -> dict[str, Path]:
    mode_files: dict[str, Path] = {}
    if args.governor:
        mode_files["governor"] = Path(args.governor)
    for mode_name in ("eco", "auto", "comfort", "sport", "rocket"):
        value = getattr(args, mode_name)
        if value:
            mode_files[mode_name] = Path(value)

    for mode_entry in args.mode_file:
        if "=" not in mode_entry:
            raise ValueError(
                f"Invalid --mode-file value '{mode_entry}'. Use format: name=path/to/file.jsonl"
            )
        name, path_text = mode_entry.split("=", 1)
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError(f"Invalid mode name in --mode-file: '{mode_entry}'")
        mode_files[normalized] = Path(path_text.strip())
    return mode_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate baseline vs multi-mode report.")
    parser.add_argument("--baseline", type=str, required=True)
    parser.add_argument(
        "--governor",
        type=str,
        default=None,
        help="Backward-compatible single governor records file.",
    )
    parser.add_argument("--eco", type=str, default=None)
    parser.add_argument("--auto", type=str, default=None)
    parser.add_argument("--comfort", type=str, default=None)
    parser.add_argument("--sport", type=str, default=None)
    parser.add_argument("--rocket", type=str, default=None)
    parser.add_argument(
        "--mode-file",
        action="append",
        default=[],
        help="Additional mode file in format name=path/to/file.jsonl (repeatable).",
    )
    parser.add_argument("--outdir", type=str, default="metrics/reports")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Also generate Plotly interactive HTML chart.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mode_files = collect_mode_files(args)
    if not mode_files:
        print(
            "[error] No comparison modes were provided. "
            "Use --governor or one/more of: --eco --auto --comfort --sport --rocket."
        )
        return 2

    outputs = run_report(
        baseline_file=Path(args.baseline),
        mode_files=mode_files,
        outdir=Path(args.outdir),
        interactive=args.interactive,
    )

    print(f"Saved JSON report: {outputs['json']}")
    print(f"Saved Markdown report: {outputs['markdown']}")
    print(f"Saved static plot: {outputs['plot_png']}")
    if "plot_html" in outputs:
        print(f"Saved interactive plot: {outputs['plot_html']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
