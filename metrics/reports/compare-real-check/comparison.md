# Baseline vs Multi-Mode Report

- Generated UTC: `2026-03-03T13:55:47.575675+00:00`
- Baseline file: `metrics/data/baseline-auto-check.jsonl`

## Comparison Table

| Mode | Mean Token | ΔToken vs Baseline | P95 Token | ΔP95 vs Baseline | Success Rate | ΔSuccess | Mean Latency(s) | ΔLatency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline` | 935.00 | +0.00% | 935.00 | +0.00% | 100.00% | +0.00pp | 6.63 | +0.00% |
| `eco` | 1887.00 | +101.82% | 1887.00 | +101.82% | 100.00% | +0.00pp | 9.66 | +45.61% |
| `auto` | 2059.00 | +120.21% | 2059.00 | +120.21% | 100.00% | +0.00pp | 12.32 | +85.79% |
| `comfort` | 7390.00 | +690.37% | 7390.00 | +690.37% | 100.00% | +0.00pp | 30.23 | +355.75% |
| `sport` | 3573.00 | +282.14% | 3573.00 | +282.14% | 100.00% | +0.00pp | 17.02 | +156.58% |
| `rocket` | 1661.00 | +77.65% | 1661.00 | +77.65% | 100.00% | +0.00pp | 10.26 | +54.62% |

## Raw Summary JSON

```json
{
  "generated_at_utc": "2026-03-03T13:55:47.575675+00:00",
  "baseline_file": "metrics/data/baseline-auto-check.jsonl",
  "mode_files": {
    "eco": "metrics/data/drive-mode-eco-smoke.jsonl",
    "auto": "metrics/data/drive-mode-auto-smoke.jsonl",
    "comfort": "metrics/data/drive-mode-auto-rocket-smoke.jsonl",
    "sport": "metrics/data/drive-mode-rocket-smoke.jsonl",
    "rocket": "metrics/data/governor-auto-strategy-realcheck.jsonl"
  },
  "baseline": {
    "count": 1.0,
    "mean_token": 935.0,
    "p50_token": 935.0,
    "p95_token": 935.0,
    "success_rate": 1.0,
    "mean_latency": 6.633327833000294,
    "fallback_trigger_rate": 0.0
  },
  "modes": {
    "eco": {
      "file": "metrics/data/drive-mode-eco-smoke.jsonl",
      "summary": {
        "count": 1.0,
        "mean_token": 1887.0,
        "p50_token": 1887.0,
        "p95_token": 1887.0,
        "success_rate": 1.0,
        "mean_latency": 9.658606249999139,
        "fallback_trigger_rate": 0.0
      },
      "vs_baseline": {
        "mean_token_pct": 101.81818181818181,
        "p95_token_pct": 101.81818181818181,
        "mean_latency_pct": 45.60725013391193,
        "success_rate_pp": 0.0,
        "fallback_trigger_rate_pp": 0.0
      }
    },
    "auto": {
      "file": "metrics/data/drive-mode-auto-smoke.jsonl",
      "summary": {
        "count": 1.0,
        "mean_token": 2059.0,
        "p50_token": 2059.0,
        "p95_token": 2059.0,
        "success_rate": 1.0,
        "mean_latency": 12.324268541997299,
        "fallback_trigger_rate": 0.0
      },
      "vs_baseline": {
        "mean_token_pct": 120.21390374331551,
        "p95_token_pct": 120.21390374331551,
        "mean_latency_pct": 85.79314715435913,
        "success_rate_pp": 0.0,
        "fallback_trigger_rate_pp": 0.0
      }
    },
    "comfort": {
      "file": "metrics/data/drive-mode-auto-rocket-smoke.jsonl",
      "summary": {
        "count": 1.0,
        "mean_token": 7390.0,
        "p50_token": 7390.0,
        "p95_token": 7390.0,
        "success_rate": 1.0,
        "mean_latency": 30.231671957997605,
        "fallback_trigger_rate": 0.0
      },
      "vs_baseline": {
        "mean_token_pct": 690.3743315508021,
        "p95_token_pct": 690.3743315508021,
        "mean_latency_pct": 355.75422652258146,
        "success_rate_pp": 0.0,
        "fallback_trigger_rate_pp": 0.0
      }
    },
    "sport": {
      "file": "metrics/data/drive-mode-rocket-smoke.jsonl",
      "summary": {
        "count": 1.0,
        "mean_token": 3573.0,
        "p50_token": 3573.0,
        "p95_token": 3573.0,
        "success_rate": 1.0,
        "mean_latency": 17.01961158300037,
        "fallback_trigger_rate": 0.0
      },
      "vs_baseline": {
        "mean_token_pct": 282.13903743315507,
        "p95_token_pct": 282.13903743315507,
        "mean_latency_pct": 156.5772717930375,
        "success_rate_pp": 0.0,
        "fallback_trigger_rate_pp": 0.0
      }
    },
    "rocket": {
      "file": "metrics/data/governor-auto-strategy-realcheck.jsonl",
      "summary": {
        "count": 1.0,
        "mean_token": 1661.0,
        "p50_token": 1661.0,
        "p95_token": 1661.0,
        "success_rate": 1.0,
        "mean_latency": 10.256724999999278,
        "fallback_trigger_rate": 0.0
      },
      "vs_baseline": {
        "mean_token_pct": 77.64705882352942,
        "p95_token_pct": 77.64705882352942,
        "mean_latency_pct": 54.62412318855798,
        "success_rate_pp": 0.0,
        "fallback_trigger_rate_pp": 0.0
      }
    }
  }
}
```
