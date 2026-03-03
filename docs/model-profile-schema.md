# Model Profile Schema

## Purpose

`Model Profile` is a model-aware behavior summary built from real runtime records.
It is used by auto strategy (`--drive-mode auto`) to bias recommendations by:

- token efficiency
- success/quality stability
- latency
- cache friendliness

This file defines the JSON schema produced by:

```bash
python scripts/build_model_profiles.py \
  --input "metrics/data/*-real.jsonl" \
  --output metrics/profiles/model_profiles.json
```

## Top-Level Structure

```json
{
  "schema_version": "1.0.0",
  "version": "0.2.0",
  "generated_at_utc": "2026-03-03T14:00:00+00:00",
  "models": {
    "google_genai:gemini-2.5-flash": {
      "...": "model profile object"
    }
  }
}
```

## Model Profile Object

```jsonc
{
  "model_name": "google_genai:gemini-2.5-flash",
  "version": "gemini-2.5-flash",
  "tag": ["stable", "cost_optimized"],

  "total_runs": 120,
  "avg_tokens": 1604.9,
  "avg_prompt_tokens": 820.1,
  "avg_response_tokens": 784.8,
  "median_tokens": 984.0,
  "p95_tokens": 4868.05,

  "success_rate": 1.0,
  "avg_latency_ms": 10036.8,
  "quality_score": null,

  "semantic_cache_hit_rate": 0.33,
  "plan_cache_hit_rate": 0.06,
  "compression_rate": 0.71,

  "strategy_performance": {
    "eco": {
      "count": 30,
      "avg_tokens": 1100.0,
      "avg_prompt_tokens": 540.0,
      "avg_response_tokens": 560.0,
      "median_tokens": 900.0,
      "p95_tokens": 2300.0,
      "success_rate": 0.97,
      "avg_latency_ms": 7800.0,
      "quality_score": null,
      "semantic_cache_hit_rate": 0.21,
      "plan_cache_hit_rate": 0.01,
      "compression_rate": 0.82
    }
  },

  "best_cost_mode": "eco",
  "best_quality_mode": "sport",
  "best_balance_mode": "comfort",

  "last_updated": "2026-03-03T14:00:00+00:00",
  "entries_sampled": 120,

  // backward-compatible fields for existing runtime loaders
  "modes": {
    "eco": {
      "count": 30.0,
      "mean_token": 1100.0,
      "mean_latency": 7.8,
      "success_rate": 0.97
    }
  }
}
```

## Field Notes

- `avg_latency_ms` is milliseconds.
- `quality_score` is optional. If no evaluator exists, it stays `null`.
- `compression_rate` is ratio of effective tokens after optimization vs raw tokens.
- `best_balance_mode` avoids `rocket` by default when alternatives exist.

## Runtime Consumption

Current runtime integration:

```bash
python main.py --mode governor \
  --drive-mode auto \
  --model-profile metrics/profiles/model_profiles.json \
  --limit 20
```

Flow:

1. Load `models[model_name]` from profile JSON.
2. Read `best_balance_mode` as hint for auto mode.
3. Keep user explicit overrides as highest priority.
4. Persist hint fields to task logs:
   - `model_profile_hint_mode`
   - `model_profile_hint_reason`

## Recommended Update Loop

1. Run periodic benchmarks (`baseline` + drive modes).
2. Rebuild profile JSON from fresh records.
3. Run auto mode with updated profile.
4. Compare against previous cycle (`metrics.report`) and update README metrics block.
