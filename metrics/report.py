"""Baseline vs Governor comparison report generator."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any


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


def save_json(data: dict[str, Any], outpath: Path) -> None:
    with outpath.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def plot_comparison(
    baseline_summary: dict[str, float],
    governor_summary: dict[str, float],
    outdir: Path,
) -> Path:
    import matplotlib.pyplot as plt

    labels = ["mean_token", "p95_token", "mean_latency", "success_rate"]
    baseline_vals = [baseline_summary[k] for k in labels]
    governor_vals = [governor_summary[k] for k in labels]

    x = range(len(labels))
    width = 0.35

    plt.figure(figsize=(10, 6))
    plt.bar([i - width / 2 for i in x], baseline_vals, width, label="Baseline")
    plt.bar([i + width / 2 for i in x], governor_vals, width, label="Governor")
    plt.xticks(list(x), labels, rotation=15)
    plt.ylabel("Value")
    plt.title("Baseline vs Governor Summary")
    plt.legend()
    plt.tight_layout()

    fname = outdir / "comparison_summary.png"
    plt.savefig(fname)
    plt.close()
    return fname


def plot_interactive(
    baseline_summary: dict[str, float],
    governor_summary: dict[str, float],
    outdir: Path,
) -> Path:
    try:
        import pandas as pd
        import plotly.express as px
    except ImportError as exc:
        raise RuntimeError(
            "Interactive plot needs plotly and pandas. Run: pip install plotly pandas"
        ) from exc

    labels = ["mean_token", "p95_token", "mean_latency", "success_rate"]
    frame = pd.DataFrame(
        {
            "metric": labels,
            "baseline": [baseline_summary[k] for k in labels],
            "governor": [governor_summary[k] for k in labels],
        }
    )

    fig = px.bar(
        frame.melt(id_vars=["metric"], value_vars=["baseline", "governor"]),
        x="metric",
        y="value",
        color="variable",
        barmode="group",
        title="Baseline vs Governor Summary (Interactive)",
        labels={"variable": "mode"},
    )

    outpath = outdir / "comparison_summary.html"
    fig.write_html(str(outpath), include_plotlyjs="cdn")
    return outpath


def write_markdown(summary: dict[str, Any], outpath: Path) -> None:
    with outpath.open("w", encoding="utf-8") as md:
        md.write("# Baseline vs Governor Report\n\n")
        md.write("## Summary Statistics\n\n")
        md.write(f"```json\n{json.dumps(summary, indent=2, ensure_ascii=False)}\n```\n")


def run_report(
    baseline_file: Path,
    governor_file: Path,
    outdir: Path,
    interactive: bool = False,
) -> dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)

    base_recs = load_records(baseline_file)
    gov_recs = load_records(governor_file)

    base_sum = summarize(base_recs)
    gov_sum = summarize(gov_recs)

    summary: dict[str, Any] = {
        "baseline_file": str(baseline_file),
        "governor_file": str(governor_file),
        "baseline": base_sum,
        "governor": gov_sum,
    }

    json_path = outdir / "comparison.json"
    md_path = outdir / "comparison.md"
    png_path = plot_comparison(base_sum, gov_sum, outdir)

    save_json(summary, json_path)
    write_markdown(summary, md_path)

    outputs: dict[str, Path] = {
        "json": json_path,
        "markdown": md_path,
        "plot_png": png_path,
    }

    if interactive:
        html_path = plot_interactive(base_sum, gov_sum, outdir)
        outputs["plot_html"] = html_path

    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate baseline vs governor report.")
    parser.add_argument("--baseline", type=str, required=True)
    parser.add_argument("--governor", type=str, required=True)
    parser.add_argument("--outdir", type=str, default="metrics/reports")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Also generate Plotly interactive HTML chart.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = run_report(
        baseline_file=Path(args.baseline),
        governor_file=Path(args.governor),
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
