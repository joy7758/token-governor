"""Benchmark dashboard generator for Token Governor v0.2 records."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px


FAILURE_FAMILY_MAP: dict[str, str] = {
    "schema_mismatch": "deterministic",
    "param_error": "deterministic",
    "auth_error": "deterministic",
    "not_found": "deterministic",
    "wrong_format": "deterministic",
    "permission_error": "deterministic",
    "reasoning_failure": "probabilistic",
    "planning_error": "probabilistic",
    "reasoning_mismatch": "probabilistic",
    "planning_loop": "probabilistic",
    "risk_violation": "policy",
    "unsafe_tool_request": "policy",
    "unsafe_intent": "policy",
}


def load_records(record_file: Path) -> pd.DataFrame:
    if not record_file.exists():
        raise FileNotFoundError(f"Record file not found: {record_file}")
    return pd.read_json(record_file, lines=True)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _mean_compression_ratio(raw: Any) -> float:
    if isinstance(raw, dict):
        values = [_safe_float(v, default=1.0) for v in raw.values()]
        values = [v for v in values if v >= 0.0]
        if not values:
            return 1.0
        return sum(values) / len(values)

    if isinstance(raw, (int, float)):
        val = _safe_float(raw, default=1.0)
        return val if val >= 0.0 else 1.0

    if isinstance(raw, str) and raw.strip():
        text = raw.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                parsed = None
        if parsed is not None:
            return _mean_compression_ratio(parsed)

    return 1.0


def _fallback_triggered(row: pd.Series) -> bool:
    if bool(row.get("fallback_triggered", False)):
        return True
    if _safe_int(row.get("fallback_steps", 0)) > 0:
        return True
    if _safe_int(row.get("fallback_count", 0)) > 0:
        return True
    err = str(row.get("error", "") or "").lower()
    return "fallback" in err


def _failure_family(row: pd.Series) -> str:
    family = str(row.get("failure_family", "") or "").strip().lower()
    if family in {"deterministic", "probabilistic", "policy"}:
        return family

    failure_type = str(row.get("failure_type", "") or "").strip().lower()
    if failure_type in FAILURE_FAMILY_MAP:
        return FAILURE_FAMILY_MAP[failure_type]

    success = bool(row.get("success", False))
    return "none" if success else "unknown"


def normalize_records(df: pd.DataFrame, run_label: str) -> pd.DataFrame:
    frame = df.copy()

    frame["run_label"] = run_label
    frame["task_category"] = (
        frame.get("category", pd.Series(["unknown"] * len(frame))).fillna("unknown").astype(str)
    )

    frame["tokens_used"] = frame.apply(
        lambda row: _safe_float(
            row.get("tokens_used", row.get("total_tokens", 0.0)),
            default=0.0,
        ),
        axis=1,
    )
    frame["latency_ms"] = frame.apply(
        lambda row: _safe_float(
            row.get(
                "latency_ms",
                _safe_float(row.get("latency", 0.0), default=0.0) * 1000.0,
            ),
            default=0.0,
        ),
        axis=1,
    )
    frame["success_rate_flag"] = frame.apply(
        lambda row: 1.0 if bool(row.get("success", False)) else 0.0,
        axis=1,
    )
    frame["fallback_triggered_flag"] = frame.apply(
        lambda row: 1.0 if _fallback_triggered(row) else 0.0,
        axis=1,
    )
    frame["failure_family"] = frame.apply(_failure_family, axis=1)
    frame["compression_ratio_mean"] = frame.apply(
        lambda row: _mean_compression_ratio(row.get("compression_ratio")),
        axis=1,
    )

    if "task_id" not in frame.columns:
        frame["task_id"] = [f"row-{idx+1:03d}" for idx in range(len(frame))]

    return frame


def build_dataframe(paths: dict[str, Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for run_label, path in paths.items():
        raw = load_records(path)
        norm = normalize_records(raw, run_label=run_label)
        frames.append(norm)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def summarize_by_category(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby(["run_label", "task_category"], dropna=False)
    summary = grouped.agg(
        task_count=("task_id", "count"),
        mean_token=("tokens_used", "mean"),
        median_token=("tokens_used", "median"),
        p95_token=("tokens_used", lambda s: s.quantile(0.95)),
        success_rate=("success_rate_flag", "mean"),
        fallback_rate=("fallback_triggered_flag", "mean"),
        mean_latency_ms=("latency_ms", "mean"),
        mean_compression_ratio=("compression_ratio_mean", "mean"),
    ).reset_index()

    summary["success_rate_pct"] = summary["success_rate"] * 100.0
    summary["fallback_rate_pct"] = summary["fallback_rate"] * 100.0
    return summary


def summarize_overall(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby(["run_label"], dropna=False)
    summary = grouped.agg(
        task_count=("task_id", "count"),
        mean_token=("tokens_used", "mean"),
        median_token=("tokens_used", "median"),
        p95_token=("tokens_used", lambda s: s.quantile(0.95)),
        success_rate=("success_rate_flag", "mean"),
        fallback_rate=("fallback_triggered_flag", "mean"),
        mean_latency_ms=("latency_ms", "mean"),
    ).reset_index()

    summary["success_rate_pct"] = summary["success_rate"] * 100.0
    summary["fallback_rate_pct"] = summary["fallback_rate"] * 100.0
    return summary


def enrich_token_savings(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    baseline = frame[frame["run_label"] == "baseline"]
    if baseline.empty:
        frame["token_savings_vs_baseline"] = 0.0
        frame["token_savings_pct_vs_baseline"] = 0.0
        frame["token_savings_size"] = 5.0
        return frame

    baseline_mean = (
        baseline.groupby("task_category", dropna=False)["tokens_used"].mean().to_dict()
    )

    def compute_abs(row: pd.Series) -> float:
        category = str(row.get("task_category", "unknown"))
        base = _safe_float(baseline_mean.get(category, 0.0), default=0.0)
        if base <= 0:
            return 0.0
        return base - _safe_float(row.get("tokens_used", 0.0), default=0.0)

    def compute_pct(row: pd.Series) -> float:
        category = str(row.get("task_category", "unknown"))
        base = _safe_float(baseline_mean.get(category, 0.0), default=0.0)
        if base <= 0:
            return 0.0
        abs_saving = compute_abs(row)
        return (abs_saving / base) * 100.0

    frame["token_savings_vs_baseline"] = frame.apply(compute_abs, axis=1)
    frame["token_savings_pct_vs_baseline"] = frame.apply(compute_pct, axis=1)
    frame["token_savings_size"] = (
        frame["token_savings_vs_baseline"].abs().fillna(0.0).astype(float) + 5.0
    )
    return frame


def _write_plotly(
    fig: Any,
    *,
    html_path: Path,
    png_path: Path,
    enable_png: bool,
    warnings: list[str],
) -> None:
    fig.write_html(str(html_path), include_plotlyjs="cdn")
    if not enable_png:
        return

    try:
        fig.write_image(str(png_path), width=1500, height=900, scale=2)
    except Exception as exc:  # noqa: BLE001
        warnings.append(
            f"PNG export skipped for {png_path.name}: {exc}. "
            "Install kaleido for Plotly static image export."
        )


def plot_pareto(category_summary: pd.DataFrame, outdir: Path, title_prefix: str, warnings: list[str], enable_png: bool) -> None:
    fig = px.scatter(
        category_summary,
        x="mean_token",
        y="success_rate_pct",
        size="mean_latency_ms",
        color="fallback_rate_pct",
        symbol="run_label",
        hover_data=["task_category", "task_count", "median_token", "p95_token"],
        title=f"{title_prefix}: Token vs Success vs Latency vs Fallback",
        labels={
            "mean_token": "Mean Tokens",
            "success_rate_pct": "Success Rate (%)",
            "mean_latency_ms": "Mean Latency (ms)",
            "fallback_rate_pct": "Fallback Rate (%)",
        },
    )
    fig.update_layout(legend_title_text="Run")
    _write_plotly(
        fig,
        html_path=outdir / "pareto_scatter.html",
        png_path=outdir / "pareto_scatter.png",
        enable_png=enable_png,
        warnings=warnings,
    )


def plot_category_bars(category_summary: pd.DataFrame, outdir: Path, title_prefix: str, warnings: list[str], enable_png: bool) -> None:
    plot_df = category_summary.copy()
    plot_df = plot_df[["run_label", "task_category", "mean_token", "success_rate_pct", "fallback_rate_pct", "p95_token"]]
    melted = plot_df.melt(
        id_vars=["run_label", "task_category"],
        value_vars=["mean_token", "success_rate_pct", "fallback_rate_pct", "p95_token"],
        var_name="metric",
        value_name="value",
    )

    fig = px.bar(
        melted,
        x="task_category",
        y="value",
        color="run_label",
        barmode="group",
        facet_row="metric",
        title=f"{title_prefix}: Category Metrics",
    )
    fig.update_layout(height=1200)
    fig.for_each_annotation(lambda ann: ann.update(text=ann.text.split("=")[-1]))

    _write_plotly(
        fig,
        html_path=outdir / "category_bars.html",
        png_path=outdir / "category_bars.png",
        enable_png=enable_png,
        warnings=warnings,
    )


def plot_failure_pie(df: pd.DataFrame, outdir: Path, title_prefix: str, warnings: list[str], enable_png: bool) -> None:
    fail_counts = (
        df.groupby(["run_label", "failure_family"], dropna=False)
        .size()
        .reset_index(name="count")
    )
    fail_counts["label"] = fail_counts["run_label"] + " : " + fail_counts["failure_family"]

    fig = px.pie(
        fail_counts,
        names="label",
        values="count",
        title=f"{title_prefix}: Failure Family Distribution",
        hole=0.35,
    )
    _write_plotly(
        fig,
        html_path=outdir / "failure_pie.html",
        png_path=outdir / "failure_pie.png",
        enable_png=enable_png,
        warnings=warnings,
    )


def plot_compression_vs_success(df: pd.DataFrame, outdir: Path, title_prefix: str, warnings: list[str], enable_png: bool) -> None:
    fig = px.scatter(
        df,
        x="compression_ratio_mean",
        y="success_rate_flag",
        size="token_savings_size",
        color="task_category",
        symbol="run_label",
        hover_data=["task_id", "tokens_used", "fallback_triggered_flag", "failure_family"],
        title=f"{title_prefix}: Compression Ratio vs Success",
        labels={
            "compression_ratio_mean": "Compression Ratio (mean)",
            "success_rate_flag": "Success (0/1)",
            "token_savings_vs_baseline": "Token Savings vs Baseline",
        },
    )
    fig.update_layout(legend_title_text="Category")
    _write_plotly(
        fig,
        html_path=outdir / "compression_success.html",
        png_path=outdir / "compression_success.png",
        enable_png=enable_png,
        warnings=warnings,
    )


def plot_summary_panel(overall_summary: pd.DataFrame, outdir: Path, title_prefix: str) -> Path:
    labels = overall_summary["run_label"].tolist()

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    axes[0, 0].bar(labels, overall_summary["mean_token"])
    axes[0, 0].set_title("Mean Tokens")
    axes[0, 0].tick_params(axis="x", rotation=20)

    axes[0, 1].bar(labels, overall_summary["success_rate_pct"])
    axes[0, 1].set_title("Success Rate (%)")
    axes[0, 1].tick_params(axis="x", rotation=20)

    axes[1, 0].bar(labels, overall_summary["fallback_rate_pct"])
    axes[1, 0].set_title("Fallback Rate (%)")
    axes[1, 0].tick_params(axis="x", rotation=20)

    axes[1, 1].bar(labels, overall_summary["mean_latency_ms"])
    axes[1, 1].set_title("Mean Latency (ms)")
    axes[1, 1].tick_params(axis="x", rotation=20)

    fig.suptitle(f"{title_prefix}: Overall Summary")
    fig.tight_layout()

    outpath = outdir / "summary_panel.png"
    fig.savefig(outpath)
    plt.close(fig)
    return outpath


def build_dashboard(
    *,
    governor_file: Path,
    baseline_file: Path | None,
    outdir: Path,
    title_prefix: str,
    enable_png: bool,
) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {"governor": governor_file}
    if baseline_file is not None:
        paths["baseline"] = baseline_file

    df = build_dataframe(paths)
    if df.empty:
        raise ValueError("No records loaded from input files.")

    df = enrich_token_savings(df)

    category_summary = summarize_by_category(df)
    overall_summary = summarize_overall(df)

    category_summary_csv = outdir / "category_summary.csv"
    overall_summary_csv = outdir / "overall_summary.csv"
    category_summary.to_csv(category_summary_csv, index=False)
    overall_summary.to_csv(overall_summary_csv, index=False)

    warnings: list[str] = []

    plot_pareto(category_summary, outdir, title_prefix, warnings, enable_png)
    plot_category_bars(category_summary, outdir, title_prefix, warnings, enable_png)
    plot_failure_pie(df, outdir, title_prefix, warnings, enable_png)
    plot_compression_vs_success(df, outdir, title_prefix, warnings, enable_png)
    summary_panel_png = plot_summary_panel(overall_summary, outdir, title_prefix)

    summary_payload = {
        "title": title_prefix,
        "generated_files": {
            "pareto_html": "pareto_scatter.html",
            "pareto_png": "pareto_scatter.png",
            "category_html": "category_bars.html",
            "category_png": "category_bars.png",
            "failure_html": "failure_pie.html",
            "failure_png": "failure_pie.png",
            "compression_html": "compression_success.html",
            "compression_png": "compression_success.png",
            "summary_panel_png": summary_panel_png.name,
            "category_summary_csv": category_summary_csv.name,
            "overall_summary_csv": overall_summary_csv.name,
        },
        "overall_summary": overall_summary.to_dict(orient="records"),
        "warnings": warnings,
        "sources": {name: str(path) for name, path in paths.items()},
    }

    dashboard_summary = outdir / "dashboard_summary.json"
    dashboard_summary.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "outdir": str(outdir),
        "dashboard_summary": str(dashboard_summary),
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate benchmark dashboard charts.")
    parser.add_argument(
        "--governor",
        required=True,
        help="Governor records JSONL file",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="Optional baseline records JSONL file",
    )
    parser.add_argument(
        "--outdir",
        required=True,
        help="Output directory for dashboard artifacts",
    )
    parser.add_argument(
        "--title",
        default="Token Governor Benchmark Dashboard",
        help="Dashboard title prefix",
    )
    parser.add_argument(
        "--no-png",
        action="store_true",
        help="Disable Plotly PNG export (HTML still generated)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    outputs = build_dashboard(
        governor_file=Path(args.governor),
        baseline_file=Path(args.baseline) if args.baseline else None,
        outdir=Path(args.outdir),
        title_prefix=args.title,
        enable_png=not args.no_png,
    )

    print(f"[dashboard] outdir: {outputs['outdir']}")
    print(f"[dashboard] summary: {outputs['dashboard_summary']}")
    for warning in outputs["warnings"]:
        print(f"[dashboard][warn] {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
