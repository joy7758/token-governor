#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -x "venv/bin/python" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

LIMIT="${LIMIT:-20}"
MODEL="${MODEL:-auto}"
DATA_DIR="${DATA_DIR:-metrics/data}"
OUTDIR="${OUTDIR:-metrics/reports/compare-real}"

mkdir -p "${DATA_DIR}" "${OUTDIR}"

echo "[1/8] Run baseline..."
"${PYTHON_BIN}" main.py \
  --mode baseline \
  --model "${MODEL}" \
  --limit "${LIMIT}" \
  --out-file "${DATA_DIR}/baseline-real.jsonl"

echo "[2/8] Run eco mode..."
"${PYTHON_BIN}" main.py \
  --mode governor \
  --model "${MODEL}" \
  --drive-mode eco \
  --enable-context-compression \
  --enable-smart-tool \
  --tool-top-k 1 \
  --history-summary-chars 800 \
  --limit "${LIMIT}" \
  --out-file "${DATA_DIR}/eco-real.jsonl"

echo "[3/8] Run auto mode..."
"${PYTHON_BIN}" main.py \
  --mode governor \
  --model "${MODEL}" \
  --drive-mode auto \
  --limit "${LIMIT}" \
  --out-file "${DATA_DIR}/auto-real.jsonl"

echo "[4/8] Run comfort mode..."
"${PYTHON_BIN}" main.py \
  --mode governor \
  --model "${MODEL}" \
  --drive-mode comfort \
  --enable-context-compression \
  --enable-semantic-cache \
  --tool-top-k 2 \
  --history-summary-chars 1200 \
  --limit "${LIMIT}" \
  --out-file "${DATA_DIR}/comfort-real.jsonl"

echo "[5/8] Run sport mode..."
"${PYTHON_BIN}" main.py \
  --mode governor \
  --model "${MODEL}" \
  --drive-mode sport \
  --enable-context-compression \
  --enable-semantic-cache \
  --enable-rag \
  --tool-top-k 3 \
  --history-summary-chars 1400 \
  --limit "${LIMIT}" \
  --out-file "${DATA_DIR}/sport-real.jsonl"

echo "[6/8] Run rocket mode..."
"${PYTHON_BIN}" main.py \
  --mode governor \
  --model "${MODEL}" \
  --drive-mode rocket \
  --enable-context-compression \
  --enable-semantic-cache \
  --enable-rag \
  --enable-model-routing \
  --enable-agentic-plan-cache \
  --tool-top-k 4 \
  --history-summary-chars 1600 \
  --limit "${LIMIT}" \
  --out-file "${DATA_DIR}/rocket-real.jsonl"

echo "[7/8] Build multi-mode report..."
"${PYTHON_BIN}" -m metrics.report \
  --baseline "${DATA_DIR}/baseline-real.jsonl" \
  --eco "${DATA_DIR}/eco-real.jsonl" \
  --auto "${DATA_DIR}/auto-real.jsonl" \
  --comfort "${DATA_DIR}/comfort-real.jsonl" \
  --sport "${DATA_DIR}/sport-real.jsonl" \
  --rocket "${DATA_DIR}/rocket-real.jsonl" \
  --outdir "${OUTDIR}" \
  --interactive

echo "[8/9] Build model profile..."
"${PYTHON_BIN}" scripts/build_model_profiles.py \
  --input "${DATA_DIR}/baseline-real.jsonl" \
  --input "${DATA_DIR}/eco-real.jsonl" \
  --input "${DATA_DIR}/auto-real.jsonl" \
  --input "${DATA_DIR}/comfort-real.jsonl" \
  --input "${DATA_DIR}/sport-real.jsonl" \
  --input "${DATA_DIR}/rocket-real.jsonl" \
  --output metrics/profiles/model_profiles.json

echo "[9/9] Update README metrics block..."
"${PYTHON_BIN}" scripts/update_readme_metrics.py \
  --comparison "${OUTDIR}/comparison.json" \
  --readme README.md

echo "Done."
echo "- Report JSON: ${OUTDIR}/comparison.json"
echo "- Report Markdown: ${OUTDIR}/comparison.md"
echo "- Report PNG: ${OUTDIR}/comparison_summary.png"
echo "- Report HTML: ${OUTDIR}/comparison_summary.html"
echo "- Model profile: metrics/profiles/model_profiles.json"
