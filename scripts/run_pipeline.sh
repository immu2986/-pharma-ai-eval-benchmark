#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"
[ -f data/cases.jsonl ] || { python scripts/build_synthetic_dataset.py && python -m pharmaeval autograde && python scripts/generate_synthetic_annotations.py; }
python -m pharmaeval run-all
python -m pytest -q
echo "Done. Open reports/dashboard.html"
