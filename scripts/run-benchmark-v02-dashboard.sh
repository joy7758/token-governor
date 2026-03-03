#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -x "venv/bin/python" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

MODEL="${MODEL:-auto}"
LIMIT="${LIMIT:-60}"
TASKS_FILE="${TASKS_FILE:-metrics/benchmarks/benchmark_v02_60_tasks.json}"
POLICY_FILE="${POLICY_FILE:-policy.yaml}"
DATA_DIR="${DATA_DIR:-metrics/data}"
OUTDIR="${OUTDIR:-metrics/reports/v02-dashboard}"
BRANCH="${BRANCH:-main}"
MODE="${MODE:-governor}"
UPDATE_README="${UPDATE_README:-false}"
CHART_PATH="${CHART_PATH:-${OUTDIR}/summary_panel.png}"
RUN_LABEL="${RUN_LABEL:-v02}"
HISTORY_FILE="${HISTORY_FILE:-metrics/reports/all_runs_history.jsonl}"
TRENDS_OUT_DIR="${TRENDS_OUT_DIR:-docs/trends}"
BADGES_OUT_DIR="${BADGES_OUT_DIR:-docs/badges}"
KPI_OUT_DIR="${KPI_OUT_DIR:-docs/trends}"
ENABLE_HISTORY="${ENABLE_HISTORY:-true}"
ENABLE_TRENDS="${ENABLE_TRENDS:-true}"
ENABLE_BADGES="${ENABLE_BADGES:-true}"
ENABLE_KPI="${ENABLE_KPI:-true}"

mkdir -p "${DATA_DIR}" "${OUTDIR}"

if [[ -z "${OPENAI_API_KEY:-}" && -z "${GOOGLE_API_KEY:-}" && -z "${GEMINI_API_KEY:-}" ]]; then
  echo "[error] Missing API keys. Set OPENAI_API_KEY or GOOGLE_API_KEY/GEMINI_API_KEY."
  exit 1
fi

echo "[1/10] Run baseline v0.2 benchmark..."
"${PYTHON_BIN}" main.py \
  --mode baseline \
  --model "${MODEL}" \
  --tasks-file "${TASKS_FILE}" \
  --limit "${LIMIT}" \
  --out-file "${DATA_DIR}/baseline-v02.jsonl"

echo "[2/10] Run governor v0.2 benchmark..."
"${PYTHON_BIN}" main.py \
  --mode governor \
  --model "${MODEL}" \
  --policy-file "${POLICY_FILE}" \
  --tasks-file "${TASKS_FILE}" \
  --limit "${LIMIT}" \
  --out-file "${DATA_DIR}/governor-v02.jsonl"

echo "[3/10] Validate governor outputs..."
"${PYTHON_BIN}" -m metrics.validator \
  --tasks "${TASKS_FILE}" \
  --records "${DATA_DIR}/governor-v02.jsonl" \
  --out "${OUTDIR}/validator-v02.json"

echo "[4/10] Generate v0.2 dashboard..."
"${PYTHON_BIN}" -m metrics.dashboard.benchmark_dashboard \
  --governor "${DATA_DIR}/governor-v02.jsonl" \
  --baseline "${DATA_DIR}/baseline-v02.jsonl" \
  --outdir "${OUTDIR}" \
  --title "Token Governor v0.2 Benchmark Dashboard"

echo "[5/10] Build comparison report (JSON/MD/summary chart)..."
"${PYTHON_BIN}" -m metrics.report \
  --baseline "${DATA_DIR}/baseline-v02.jsonl" \
  --governor "${DATA_DIR}/governor-v02.jsonl" \
  --outdir "${OUTDIR}" \
  --interactive

if [[ "${ENABLE_HISTORY}" == "true" ]]; then
  echo "[6/10] Append history point..."
  "${PYTHON_BIN}" scripts/append_benchmark_history.py \
    --comparison "${OUTDIR}/comparison.json" \
    --mode "${MODE}" \
    --history "${HISTORY_FILE}" \
    --run-label "${RUN_LABEL}" \
    --replace-same-day
else
  echo "[6/10] Skip history append (ENABLE_HISTORY=false)"
fi

if [[ "${ENABLE_TRENDS}" == "true" && -f "${HISTORY_FILE}" ]]; then
  echo "[7/10] Generate trends JSON..."
  "${PYTHON_BIN}" scripts/generate_trends.py \
    --history "${HISTORY_FILE}" \
    --metric success_rate \
    --mode "${MODE}" \
    --run-label "${RUN_LABEL}" \
    --out "${TRENDS_OUT_DIR}/success_trend.json"
  "${PYTHON_BIN}" scripts/generate_trends.py \
    --history "${HISTORY_FILE}" \
    --metric token_savings_pct \
    --mode "${MODE}" \
    --run-label "${RUN_LABEL}" \
    --out "${TRENDS_OUT_DIR}/token_trend.json"
  "${PYTHON_BIN}" scripts/generate_trends.py \
    --history "${HISTORY_FILE}" \
    --metric fallback_trigger_rate \
    --mode "${MODE}" \
    --run-label "${RUN_LABEL}" \
    --out "${TRENDS_OUT_DIR}/fallback_trend.json"
  "${PYTHON_BIN}" scripts/generate_trends.py \
    --history "${HISTORY_FILE}" \
    --metric mean_latency \
    --mode "${MODE}" \
    --run-label "${RUN_LABEL}" \
    --out "${TRENDS_OUT_DIR}/latency_trend.json"
else
  echo "[7/10] Skip trends generation"
fi

if [[ "${ENABLE_BADGES}" == "true" ]]; then
  echo "[8/10] Generate badges..."
  "${PYTHON_BIN}" scripts/generate_badges.py \
    --metrics "${OUTDIR}/overall_summary.csv" \
    --outdir "${BADGES_OUT_DIR}" \
    --mode "${MODE}"
else
  echo "[8/10] Skip badge generation (ENABLE_BADGES=false)"
fi

if [[ "${ENABLE_KPI}" == "true" && -f "${HISTORY_FILE}" ]]; then
  echo "[9/10] Generate KPI summary..."
  "${PYTHON_BIN}" scripts/report_kpi.py \
    --history "${HISTORY_FILE}" \
    --mode "${MODE}" \
    --run-label "${RUN_LABEL}" \
    --out-json "${KPI_OUT_DIR}/kpi_summary.json" \
    --out-markdown "${KPI_OUT_DIR}/kpi_summary.md"
else
  echo "[9/10] Skip KPI report generation"
fi

echo "[10/10] Optional README update..."
if [[ "${UPDATE_README}" == "true" ]]; then
  "${PYTHON_BIN}" scripts/update_readme_metrics.py \
    --comparison "${OUTDIR}/comparison.json" \
    --readme README.md \
    --mode "${MODE}" \
    --branch "${BRANCH}" \
    --chart-path "${CHART_PATH}"
  echo "[done] README updated from ${OUTDIR}/comparison.json"
else
  echo "[skip] UPDATE_README=false"
fi

echo "[done] v0.2 benchmark + dashboard finished"
echo "- Baseline records: ${DATA_DIR}/baseline-v02.jsonl"
echo "- Governor records: ${DATA_DIR}/governor-v02.jsonl"
echo "- Validator report: ${OUTDIR}/validator-v02.json"
echo "- Dashboard summary: ${OUTDIR}/dashboard_summary.json"
echo "- Comparison JSON: ${OUTDIR}/comparison.json"
echo "- History JSONL: ${HISTORY_FILE}"
