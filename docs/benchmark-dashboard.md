# Benchmark Dashboard

## Script

- `metrics/dashboard/benchmark_dashboard.py`

## Input

- `--governor`: governor records JSONL (required)
- `--baseline`: baseline records JSONL (optional, used for token savings vs baseline)
- `--outdir`: output directory (required)
- `--title`: chart title prefix (optional)
- `--no-png`: disable Plotly PNG export (HTML still generated)

## Generated Artifacts

- `pareto_scatter.html` / `pareto_scatter.png`
- `category_bars.html` / `category_bars.png`
- `failure_pie.html` / `failure_pie.png`
- `compression_success.html` / `compression_success.png`
- `summary_panel.png` (matplotlib)
- `category_summary.csv`
- `overall_summary.csv`
- `dashboard_summary.json`

## Usage

```bash
python -m metrics.dashboard.benchmark_dashboard \
  --governor metrics/data/governor-v02.jsonl \
  --baseline metrics/data/baseline-v02.jsonl \
  --outdir metrics/reports/v02-dashboard
```

If static PNG export fails, install dependencies:

```bash
pip install kaleido
```
