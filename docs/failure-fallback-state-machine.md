# Failure Taxonomy + Fallback State Machine (v0.2)

## Failure Types

```yaml
failure_types:
  deterministic:
    - schema_mismatch
    - permission_error
    - not_found
    - wrong_format
  probabilistic:
    - reasoning_mismatch
    - planning_loop
  policy:
    - unsafe_intent
    - risk_violation
```

## Fallback State Machine

```text
[Initial]
    |
    v
Check Failure Type
    |
    +--> deterministic -> Repair Params / Fix Schema -> Retry once
    |
    +--> probabilistic -> Expand Context / Add Dependency Tools
    |                     -> Retry
    |
    +--> policy -> STOP + Human Review / Safe Answer
    |
    v
[Budget Check]
    |
    +--> within budget -> Continue
    |
    +--> over budget -> Circuit Breaker -> Stop + Response
```
