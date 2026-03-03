# Observability Extensions (v0.2+)

This document covers the four observability extensions integrated into the benchmark pipeline.

## 1) Notification Channels

Scripts:

- `scripts/notify_slack.py`
- `scripts/notify_dingtalk.py`
- `scripts/notify_email.py`

Usage examples:

```bash
python scripts/notify_slack.py --title "Guardrail Alert" --text-file metrics/reports/daily-light-dashboard/guardrail.md
python scripts/notify_dingtalk.py --msg-file metrics/reports/daily-light-dashboard/guardrail.md
python scripts/notify_email.py --subject "Guardrail Alert" --body-file metrics/reports/daily-light-dashboard/guardrail.md
```

Environment variables:

- Slack: `SLACK_WEBHOOK_URL`
- DingTalk: `DINGTALK_WEBHOOK_URL`
- Email: `EMAIL_SMTP_SERVER`, `EMAIL_SMTP_PORT`, `EMAIL_USER`, `EMAIL_PASSWORD`, `EMAIL_TO`

## 2) Trends Dashboard (GitHub Pages)

Files:

- `docs/trends/trends.html`
- `docs/trends/success_trend.json`
- `docs/trends/token_trend.json`
- `docs/trends/fallback_trend.json`
- `docs/trends/latency_trend.json`

Workflows:

- `benchmark-v02-daily-light.yml` and `benchmark-v02-dashboard-auto.yml` generate trend JSON.
- `publish-trends-pages.yml` deploys `docs/` to GitHub Pages.

## 3) Metrics Badges

Script:

- `scripts/generate_badges.py`

Artifacts:

- `docs/badges/success_rate.svg`
- `docs/badges/token_savings.svg`
- `docs/badges/latency.svg`
- `docs/badges/fallback_rate.svg`
- `docs/badges/status.json`

## 4) KPI Summary

Script:

- `scripts/report_kpi.py`

Inputs / outputs:

- Input: `metrics/reports/all_runs_history.jsonl`
- Output: `docs/trends/kpi_summary.json`, `docs/trends/kpi_summary.md`

## Shared History Pipeline

Scripts:

- `scripts/append_benchmark_history.py`
- `scripts/generate_trends.py`

Default history file:

- `metrics/reports/all_runs_history.jsonl`
