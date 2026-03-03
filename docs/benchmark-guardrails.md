# Benchmark Guardrails

## Script

- `scripts/check_benchmark_guardrails.py`

## Purpose

Evaluate benchmark comparison outputs and fail when regression exceeds configured thresholds.

## Checks

- `success_drop_pp`: baseline success - mode success (percentage points)
- `token_increase_pct`: mode mean token increase vs baseline (%)
- `latency_increase_pct`: mode mean latency increase vs baseline (%)

## Usage

```bash
python scripts/check_benchmark_guardrails.py \
  --comparison metrics/reports/daily-light-dashboard/comparison.json \
  --mode governor \
  --max-success-drop-pp 2.0 \
  --max-token-increase-pct 25.0 \
  --max-latency-increase-pct 50.0 \
  --out-json metrics/reports/daily-light-dashboard/guardrail.json \
  --out-markdown metrics/reports/daily-light-dashboard/guardrail.md
```

Exit code:

- `0`: pass
- `2`: guardrail failed

## CI Integration

- Used by `.github/workflows/benchmark-v02-daily-light.yml`
- On failure, CI creates or updates a daily deduplicated issue and uploads artifacts.
- Optional maintainer mentions are supported via workflow input `maintainers`.
