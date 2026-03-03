# Changelog

All notable changes to this project are documented in this file.

## [v0.x] - 2026-03-03

### Added

- Auto strategy recommendation mode via `--auto-strategy`.
- Drive mode support via `--drive-mode <auto|eco|comfort|sport|rocket>`.
- Task-feature driven strategy selection (`history_tokens`, `tool_calls`, `external_query`).
- Agentic plan cache support via `--enable-agentic-plan-cache`.
- Strategy metadata and recommendation reasons in governor logs:
  - `auto_strategy_reasons`
  - `auto_task_features`
  - `auto_selected_strategy`
  - `agentic_plan_cache`
  - `agentic_plan_key`
  - `plan_cache_similarity`
  - `drive_mode`
  - `drive_mode_goal`
- Extended CLI strategy controls:
  - `--opt-strategy <light|balanced|knowledge|enterprise>`
  - `--enable/--disable-context-compression`
  - `--enable/--disable-smart-tool`
  - `--enable/--disable-rag`
  - `--enable/--disable-context-pruning`
  - `--enable/--disable-semantic-cache`
  - `--enable/--disable-agentic-plan-cache`
  - `--enable/--disable-model-routing`
  - `--tool-top-k`
  - `--history-summary-chars`
- README enhancements:
  - one-click deployment flow
  - scenario examples
  - FAQ
  - command templates
  - drive-mode comparison table and APC research note for rocket mode
  - auto-updatable metrics block markers (`METRICS_START/END`)
- Automation scripts:
  - `scripts/run-all-and-update.sh`
  - `scripts/update_readme_metrics.py`
  - `scripts/build_model_profiles.py`
- Model-aware auto optimization:
  - optional `--model-profile` for profile-guided auto mode
  - profile hint fields in runtime metadata/logging
  - richer model profile schema in `scripts/build_model_profiles.py`:
    token distribution, cache hit rates, per-strategy metrics
  - model profile schema doc: `docs/model-profile-schema.md`

### Changed

- `GuardedAgent` now supports dynamic strategy application and richer runtime metadata.
- `BaselineAgent` now supports `tools_override` to enable smart tool selection.
- `metrics/tracker.py` now captures strategy and auto-strategy fields.

### Fixed

- Auto strategy no longer unintentionally disables baseline defaults of selected profiles.
- Auto strategy now applies incremental toggles and preserves profile semantics.

### Validation

- Static compile check passed:
  - `python3 -m compileall baseline governor main.py metrics docs`
- Smoke test passed with auto strategy:
  - `venv/bin/python main.py --mode governor --auto-strategy --limit 1 ...`
