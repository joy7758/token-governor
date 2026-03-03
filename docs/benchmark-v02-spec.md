# Benchmark v0.2 Task Spec

## Files

- `metrics/benchmarks/benchmark_v02_60_tasks.json`
- `metrics/benchmarks/benchmark_v02_60_tasks.jsonl`

## Task Fields

Each task row contains:

- `id`: stable task id (e.g. `task025`)
- `category`: one of:
  - `single_turn_no_tool`
  - `single_tool_sensitive`
  - `multi_tool_chain`
  - `long_history_reasoning`
  - `adversarial_security`
- `description`: short scenario description
- `input`: user prompt
- `goal`: benchmark objective
- `allowed_tools`: allowlist tool types
- `forbidden_tools`: denylist tool types
- `expected_output`: human-readable expected behavior
- `validator`: structured validation config
- `notes`: optional notes
- `is_adversarial`: adversarial/security flag

## Validator Types

Current validator engine (`metrics/validator.py`) supports:

- `exact_match`
- `allowed_values`
- `contains_keywords`
- `regex_count`
- `list_min_items`
- `table_markdown_min_rows`
- `deny_patterns`
- `safe_refusal`
- `history_constraints`
- `manual`

## Run + Validate

```bash
python main.py --mode governor \
  --policy-file policy.yaml \
  --tasks-file metrics/benchmarks/benchmark_v02_60_tasks.json \
  --out-file metrics/data/governor-v02.jsonl

python -m metrics.validator \
  --tasks metrics/benchmarks/benchmark_v02_60_tasks.json \
  --records metrics/data/governor-v02.jsonl \
  --out metrics/reports/validator-v02.json
```
