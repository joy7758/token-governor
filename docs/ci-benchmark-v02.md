# CI: Benchmark v0.2 + Dashboard Auto

## Workflow

- `.github/workflows/benchmark-v02-dashboard-auto.yml`
- `.github/workflows/benchmark-v02-daily-light.yml`
- `.github/workflows/publish-trends-pages.yml`

## Trigger

- `benchmark-v02-dashboard-auto.yml`: `push` to `main` + `workflow_dispatch`
- `benchmark-v02-daily-light.yml`: daily `schedule` + `workflow_dispatch`
  - supports `maintainers` (comma-separated GitHub usernames) and `guardrail_labels`
- `publish-trends-pages.yml`: deploys `docs/` to GitHub Pages on trend/badge updates

## Pipeline Steps

1. Run baseline with `metrics/benchmarks/benchmark_v02_60_tasks.json`
2. Run governor with `policy.yaml`
3. Validate outputs via `metrics.validator`
4. Build dashboard via `metrics.dashboard.benchmark_dashboard`
5. Build `comparison.json` via `metrics.report`
6. (auto workflow) Update README metrics block and chart
7. (auto workflow) Commit generated artifacts and push back
8. (daily light workflow) run guardrail checks and open issue on regression
9. (daily/auto) generate trend JSON, badges, and KPI summary
10. (pages workflow) publish trend dashboard

## Secrets

Set at least one:

- `OPENAI_API_KEY`
- `GOOGLE_API_KEY` or `GEMINI_API_KEY`

## Local Equivalent

```bash
bash scripts/run-benchmark-v02-dashboard.sh
```

## Notes

- README chart uses `${OUTDIR}/summary_panel.png` by default.
- Plotly PNG files require `kaleido`; HTML outputs are always generated.
- Guardrail thresholds are evaluated by `scripts/check_benchmark_guardrails.py`.
- Daily light workflow deduplicates issues by title per day; if already open, it appends a comment instead of creating a new issue.
- Optional channel notifications on guardrail failure use:
  - `scripts/notify_slack.py`
  - `scripts/notify_dingtalk.py`
  - `scripts/notify_email.py`
