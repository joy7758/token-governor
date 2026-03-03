# Baseline vs Multi-Mode Report

- Generated UTC: `2026-03-03T13:53:21.924169+00:00`
- Baseline file: `metrics/data/baseline-real.jsonl`

## Comparison Table

| Mode | Mean Token | ΔToken vs Baseline | P95 Token | ΔP95 vs Baseline | Success Rate | ΔSuccess | Mean Latency(s) | ΔLatency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline` | 931.00 | +0.00% | 931.00 | +0.00% | 100.00% | +0.00pp | 7.35 | +0.00% |
| `eco` | 1887.00 | +102.69% | 1887.00 | +102.69% | 100.00% | +0.00pp | 9.66 | +31.38% |
| `auto` | 2059.00 | +121.16% | 2059.00 | +121.16% | 100.00% | +0.00pp | 12.32 | +67.64% |
| `comfort` | 7390.00 | +693.77% | 7390.00 | +693.77% | 100.00% | +0.00pp | 30.23 | +311.22% |
| `sport` | 3573.00 | +283.78% | 3573.00 | +283.78% | 100.00% | +0.00pp | 17.02 | +131.50% |
| `rocket` | 1661.00 | +78.41% | 1661.00 | +78.41% | 100.00% | +0.00pp | 10.26 | +39.51% |

## Raw Summary JSON

```json
{
  "generated_at_utc": "2026-03-03T13:53:21.924169+00:00",
  "baseline_file": "metrics/data/baseline-real.jsonl",
  "mode_files": {
    "eco": "metrics/data/drive-mode-eco-smoke.jsonl",
    "auto": "metrics/data/drive-mode-auto-smoke.jsonl",
    "comfort": "metrics/data/drive-mode-auto-rocket-smoke.jsonl",
    "sport": "metrics/data/drive-mode-rocket-smoke.jsonl",
    "rocket": "metrics/data/governor-auto-strategy-realcheck.jsonl"
  },
  "baseline": {
    "count": 1.0,
    "mean_token": 931.0,
    "p50_token": 931.0,
    "p95_token": 931.0,
    "success_rate": 1.0,
    "mean_latency": 7.351761083000383,
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
        "mean_token_pct": 102.68528464017186,
        "p95_token_pct": 102.68528464017186,
        "mean_latency_pct": 31.378130232399926,
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
        "mean_token_pct": 121.16004296455425,
        "p95_token_pct": 121.16004296455425,
        "mean_latency_pct": 67.63695668096368,
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
        "mean_token_pct": 693.7701396348012,
        "p95_token_pct": 693.7701396348012,
        "mean_latency_pct": 311.21673591791324,
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
        "mean_token_pct": 283.780880773362,
        "p95_token_pct": 283.780880773362,
        "mean_latency_pct": 131.50387221308293,
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
        "mean_token_pct": 78.41031149301826,
        "p95_token_pct": 78.41031149301826,
        "mean_latency_pct": 39.51385095628445,
        "success_rate_pp": 0.0,
        "fallback_trigger_rate_pp": 0.0
      }
    }
  }
}
```
